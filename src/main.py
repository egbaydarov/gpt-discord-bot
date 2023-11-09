import asyncio
import logging
from typing import Optional, cast

import discord
import tiktoken
from base import Message
from completion import generate_completion_response, parse_thread_name, process_response
from constants import (
    ACTIVATE_THREAD_PREFX,
    BOT_INVITE_URL,
    DISCORD_BOT_TOKEN,
    MAX_INPUTS_TOKENS,
    SECONDS_DELAY_RECEIVING_MSG,
)
from discord import Message as DiscordMessage
from discord.ext import commands
from utils import (
    allowed_thread,
    close_thread,
    count_token_message,
    generate_choice_persona,
    generate_initial_system,
    get_all_icons,
    get_persona,
    is_last_message_stale,
    logger,
    remove_last_bot_message,
    should_block,
)

logging.basicConfig(
    format="[%(asctime)s] [%(filename)s:%(lineno)d] %(message)s", level=logging.INFO
)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)
bot = commands.Bot(command_prefix="!", intents=intents)
model = tiktoken.encoding_for_model(
    "gpt-4"
)  # need to be upgraded to the new gpt-4 turbo but can do the job for now
personas_choice = generate_choice_persona()


class Client(discord.Client):
    def __init__(self, *, intents: discord.Intents) -> None:  # noqa
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self) -> None:  # noqa
        logger.info("Setting up slash commands")
        await self.tree.sync()


@client.event
async def on_ready() -> None:
    logger.info(f"We have logged in as {client.user}. Invite URL: {BOT_INVITE_URL}")
    await tree.sync()


# /chat message:
@tree.command(name="chat", description="Create a new thread for conversation")
@discord.app_commands.describe(
    persona="The persona to use with the model, changing this response style"
)
@discord.app_commands.choices(persona=personas_choice)
@discord.app_commands.checks.has_permissions(send_messages=True)
@discord.app_commands.checks.has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(send_messages=True)
@discord.app_commands.checks.bot_has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(manage_threads=True)
async def chat_command(
    int: discord.Interaction,
    message: str,
    persona: Optional[discord.app_commands.Choice[str]] = None,
) -> None:
    try:
        # only support creating thread in text channel
        if not isinstance(int.channel, discord.TextChannel) or should_block(int.guild):
            return
        # ADD FOLLOWUP
        await int.response.defer(thinking=True)
        follow_up = await int.followup.send("Creating thread...", wait=True)
        user = int.user
        try:
            persona_system = get_persona(persona.value if persona else None)

            embed = discord.Embed(
                title=f"{persona_system.icon} {persona_system.title}",
                description=f"<@{user.id}> started a new chat",
                color=discord.Color.from_str(persona_system.color),
            )
            embed.add_field(name="Message :", value=f"> {message}")

            await follow_up.edit(content="", embed=embed)
        except Exception as e:
            logger.exception(e)
            await follow_up.edit(content=f"Failed to start chat {str(e)}")
            return

        thread_name = await parse_thread_name(int, message, follow_up)
        logger.info(f"Thread name - {thread_name}")
        thread = await int.channel.create_thread(
            message=follow_up,
            name=f"{ACTIVATE_THREAD_PREFX} - {persona_system.icon} {thread_name}",
            reason=message,
            auto_archive_duration=60,
        )
        async with thread.typing():
            # prepare the initial system message
            system_message = (
                persona_system.system.replace("\n-", "")
                .replace("\n", "")
                .replace("__", "")
            )  # remove newlines
            logger.info(f"Thread created - {user}: {message}")
            # fetch completion
            messages = [
                Message(user="system", text=system_message),
                Message(user="user", text=message),
            ]
            response_data = await generate_completion_response(
                messages=messages,
            )
            await process_response(thread=thread, response_data=response_data)

    except Exception as e:
        logger.error(e)
        await int.response.send_message(
            f"Failed to start chat {str(e)}", ephemeral=True
        )


# calls for each message
@client.event
async def on_message(message: DiscordMessage) -> None:  # noqa
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
        channel_messages = await generate_initial_system(client, thread)
        nb_tokens = count_token_message(channel_messages, model)

        if nb_tokens > MAX_INPUTS_TOKENS:
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

        logger.info(
            f"Thread message to process - {message.author}: {message.content[:50]} - {thread.name} {thread.jump_url}"
        )

        # prepare the initial system message
        if message.content.lower().strip() == "$$stop":
            await close_thread(thread)
            return
        # generate the response
        async with thread.typing():
            response_data = await generate_completion_response(
                messages=channel_messages
            )

        # if the message is == "/rerun" then rerun with the same message before the /rerun and the last reply of the bot
        if message.content.lower() == "$$rerun":
            await message.delete()
            # remove the last message from the channel_messages
            async with thread.typing():
                response_data = await generate_completion_response(
                    messages=remove_last_bot_message(channel_messages[:-1])
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
    except Exception as e:
        logger.exception(e)


@tree.command(name="help", description="Print each persona and their description")
@discord.app_commands.checks.has_permissions(send_messages=True)
@discord.app_commands.checks.has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(send_messages=True)
@discord.app_commands.checks.bot_has_permissions(view_channel=True)
@discord.app_commands.describe(
    persona="The persona to use with the model, changing this response style"
)
@discord.app_commands.choices(persona=personas_choice)
async def help_command(
    int: discord.Interaction, persona: Optional[discord.app_commands.Choice[str]] = None
) -> None:
    persona_system = get_persona(persona.value if persona else None)
    embed = discord.Embed(
        title=f"{persona_system.icon} {persona_system.title}",
        description=persona_system.system,
        color=discord.Colour.from_str(persona_system.color),
    )
    await int.response.send_message(embed=embed)


@tree.command(name="change", description="Change the persona of the current thread")
@discord.app_commands.describe(persona="The persona to use with the model")
@discord.app_commands.choices(persona=personas_choice)
@discord.app_commands.guild_only()
async def change_persona(
    int: discord.Interaction, persona: Optional[discord.app_commands.Choice[str]] = None
) -> None:
    logger.info(
        f"Changing persona to {persona.value} in Guild: {int.guild}"  # type: ignore
    )
    if not allowed_thread(client, int.channel, int.guild, int.user):
        await int.response.send_message(
            "This command can only be used in a thread created by the bot",
            ephemeral=True,
        )
        return

    thread = cast(discord.Thread, int.channel)
    persona_system = get_persona(persona.value if persona else None)
    thread_name = thread.name.split(" ")
    # replace the 3rd element with the new persona icon
    icon = thread_name[2]
    icon_list = get_all_icons()
    if icon in icon_list:
        thread_name[2] = persona_system.icon
        await thread.edit(name=" ".join(thread_name))
        await int.response.send_message(
            f"Changed persona to {persona_system.title}", ephemeral=True
        )
    else:
        await int.response.send_message(
            f"Failed to change persona to {persona_system.title}",
            ephemeral=True,
        )


client.run(DISCORD_BOT_TOKEN)
