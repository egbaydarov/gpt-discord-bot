import asyncio
import textwrap
from typing import Optional, cast

import discord
from base import Message
from constants import (
    ACTIVATE_THREAD_PREFX,
    SECONDS_DELAY_RECEIVING_MSG,
)
from discord import Message as DiscordMessage
from rich.console import Console
from tiktoken import Encoding
from utils.completion import (
    generate_completion_response,
    parse_thread_name,
    process_response,
)
from utils.messages import (
    count_token_message,
    generate_initial_system,
    is_last_message_stale,
)
from utils.parse_model import create_model_commands, get_models_completion
from utils.personas import (
    create_system_message,
    get_persona,
    get_persona_by_emoji,
    get_system_message,
    update_persona_models,
)
from utils.threads import allowed_thread, close_thread, should_block
from utils.utils import send_to_log_channel

console = Console()
error = Console(stderr=True, style="bold red")


async def start_chat_thread(  # noqa
    client: discord.Client,
    int: discord.Interaction,
    message: str,
    persona: Optional[discord.app_commands.Choice[str]] = None,
    follow_up: Optional[discord.WebhookMessage] = None,
    model: Optional[discord.app_commands.Choice[str]] = None,
    system_message: Optional[str] = None,
) -> None:
    try:
        # only support creating thread in text channel
        if not isinstance(int.channel, discord.TextChannel) or should_block(int.guild):
            return
        # ADD FOLLOWUP
        if not follow_up:
            await int.response.defer(thinking=True)
            follow_up = await int.followup.send("Creating thread...", wait=True)
        user = int.user

        try:
            models_to_use = create_model_commands(model, persona)
            persona_system = get_persona(persona.value if persona else None)
            original_persona = persona_system
            persona_system = update_persona_models(persona_system, models_to_use)
            persona_system = create_system_message(persona_system, system_message)
            message_content = ""
            if not persona_system.system == original_persona.system:
                message_content = f"**__System Message__**:\n> {persona_system.system}"
            embed = discord.Embed(
                title=f"{persona_system.icon} {persona_system.title}",
                description=f"<@{user.id}> started a new chat",
                color=discord.Color.from_str(persona_system.color),
            )
            # cut text if > 1024
            message_cut = textwrap.shorten(message, width=1020)
            embed.add_field(name="Message :", value=f">>> {message_cut}")
            embed.set_footer(text=f"Model: {models_to_use.name}")

            await follow_up.edit(
                content=message_content,
                embed=embed,
            )
        except Exception as e:
            error.print_exception(show_locals=True)
            await follow_up.edit(content=f"Failed to start chat {str(e)}")
            return

        thread_name = await parse_thread_name(int, message, follow_up)

        thread = await int.channel.create_thread(
            message=follow_up,
            name=f"{ACTIVATE_THREAD_PREFX} - {persona_system.icon} {thread_name}",
            reason=message,
            auto_archive_duration=60,
        )
        async with thread.typing():
            # prepare the initial system message
            system_message = (
                persona_system.system.replace("\n-", " ")
                .replace("\n", " ")
                .replace("__", "")
            )  # remove newlines
            console.log(f"Thread created - {user.global_name}: {message}")

            await send_to_log_channel(
                client,
                int.guild.id,  # type: ignore
                thread.name,
                user.global_name,  # type: ignore
                persona_system,
                models_to_use,
                "created",
            )
            # fetch completion
            messages = [
                Message(user="system", text=system_message),
                Message(user="user", text=message),
            ]
            response_data = await generate_completion_response(
                messages=messages,
                model=models_to_use.name,
            )
            await process_response(thread=thread, response_data=response_data)

    except Exception as e:
        error.print_exception(show_locals=True)
        await int.response.send_message(
            f"Failed to start chat {str(e)}", ephemeral=True
        )


async def chat_bot(
    message: DiscordMessage, client: discord.Client, model: Encoding
) -> None:  # noqa
    try:
        # block servers not in allow list
        if not allowed_thread(
            client,
            message.channel,
            message.guild,
            message.author,
            need_last_message=True,
        ):
            return

        thread = cast(discord.Thread, message.channel)
        persona_log = get_persona_by_emoji(thread)
        models_completion = await get_models_completion(thread, persona_log)
        persona_log = update_persona_models(persona_log, models_completion)
        persona_log = get_system_message(thread, persona_log)
        channel_messages = await generate_initial_system(client, thread, persona_log)

        nb_tokens: int = count_token_message(channel_messages, model)

        await send_to_log_channel(
            client,
            message.guild.id,  # type: ignore
            thread.name,
            message.author.global_name,  # type: ignore
            persona_log,
            models_completion,
            "message",
            token=nb_tokens,
        )

        if nb_tokens > models_completion.max_input_token:
            await close_thread(thread)
            return

        # wait a bit in case user has more messages
        if SECONDS_DELAY_RECEIVING_MSG > 0:
            await asyncio.sleep(SECONDS_DELAY_RECEIVING_MSG)
            if is_last_message_stale(
                interaction_message=message,
                last_message=thread.last_message,  # type: ignore
                bot_id=str(client.user.id),  # type: ignore
            ):
                # there is another message, so ignore this one
                return

        console.log(
            f"Thread message to process - {message.author}: {message.content[:50]} - {thread.name} {thread.jump_url}"
        )

        async with thread.typing():
            response_data = await generate_completion_response(
                messages=channel_messages,
                model=models_completion.name,
            )

        if is_last_message_stale(
            interaction_message=message,
            last_message=thread.last_message,  # type: ignore
            bot_id=str(client.user.id),  # type: ignore
        ):
            # there is another message and its not from us, so ignore this response
            return
        async with thread.typing():
            await process_response(thread=thread, response_data=response_data)
    except Exception:
        error.print_exception(show_locals=True)
