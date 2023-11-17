import asyncio
from typing import Optional, cast

import discord
from discord import app_commands
from discord.ext import commands
from main import (
    TOKEN_ENCODING,
    client,
    models_choice,
    personas_choice,
)
from rich.console import Console
from utils.chat import start_chat_thread
from utils.completion import generate_completion_response, process_response
from utils.messages import (
    count_token_message,
    generate_initial_system,
    remove_last_bot_message,
)
from utils.parse_model import get_models_completion
from utils.personas import get_persona_by_emoji, update_persona_models
from utils.threads import allowed_thread, close_thread, should_block
from utils.utils import send_to_log_channel

console = Console()
error = Console(stderr=True, style="bold red")


class Communicate(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:  # noqa
        self.bot = bot

    @app_commands.command(name="start", description="Start a chat thread")
    @discord.app_commands.describe(
        persona="The persona to use with the model, changing this response style"
    )
    @discord.app_commands.describe(models="The model to use for the response")
    @discord.app_commands.describe(
        system_message="The system message to use (override persona if any)"
    )
    @discord.app_commands.choices(persona=personas_choice)
    @discord.app_commands.choices(models=models_choice)
    @discord.app_commands.checks.has_permissions(send_messages=True)
    @discord.app_commands.checks.has_permissions(view_channel=True)
    @discord.app_commands.checks.bot_has_permissions(send_messages=True)
    @discord.app_commands.checks.bot_has_permissions(view_channel=True)
    @discord.app_commands.checks.bot_has_permissions(manage_threads=True)
    async def chat_command(  # noqa
        self,  # noqa
        int: discord.Interaction,
        message: str,
        persona: Optional[discord.app_commands.Choice[str]] = None,
        models: Optional[discord.app_commands.Choice[str]] = None,
        system_message: Optional[str] = None,
    ) -> None:
        await start_chat_thread(
            client, int, message, persona, model=models, system_message=system_message
        )

    @app_commands.command(name="rerun", description="Rerun the last message")
    async def rerun(self, int: discord.Interaction) -> None:  # noqa
        if not allowed_thread(self.bot, int.channel, int.guild, int.user):
            await int.response.send_message(
                "This command can only be used in a thread created by the bot",
                ephemeral=True,
            )
            return
        await int.response.defer()
        follow_up = await int.followup.send("Rerunning...", wait=True, ephemeral=True)
        thread = cast(discord.Thread, int.channel)
        log_persona = get_persona_by_emoji(thread)
        model_usage = await get_models_completion(thread, log_persona)
        log_persona = update_persona_models(log_persona, model_usage)
        channel_messages = await generate_initial_system(client, thread, log_persona)

        nb_tokens = count_token_message(channel_messages, TOKEN_ENCODING)

        await send_to_log_channel(
            client,
            int.guild.id,  # type: ignore
            thread.name,
            int.user.global_name,  # type: ignore
            log_persona,
            model_usage,
            "message",
            token=nb_tokens,
        )
        if nb_tokens > model_usage.max_input_token:
            await close_thread(thread)
            return

        try:
            async with thread.typing():
                response_data = await generate_completion_response(
                    messages=remove_last_bot_message(channel_messages[:-1]),
                    model=model_usage.name,
                )
                await process_response(thread=thread, response_data=response_data)
        except Exception as e:
            error.print_exception()
            await follow_up.edit(content=f"Failed to rerun: {str(e)}")
            return
        await follow_up.delete()

    @app_commands.command(
        name="start_long",
        description="Start a chat with a long message that need to be split",
    )
    @discord.app_commands.describe(
        persona="The persona to use with the model, changing this response style"
    )
    @discord.app_commands.describe(model="The model to use for the response")
    @discord.app_commands.describe(
        system_message="The system message to use (override persona if any)"
    )
    @discord.app_commands.choices(persona=personas_choice)
    @discord.app_commands.choices(model=models_choice)
    @discord.app_commands.checks.has_permissions(send_messages=True)
    @discord.app_commands.checks.has_permissions(view_channel=True)
    @discord.app_commands.checks.bot_has_permissions(send_messages=True)
    @discord.app_commands.checks.bot_has_permissions(view_channel=True)
    @discord.app_commands.checks.bot_has_permissions(manage_threads=True)
    async def chat_multiple(  # noqa
        self,  # noqa
        int: discord.Interaction,
        first_message: str,
        persona: Optional[discord.app_commands.Choice[str]] = None,
        model: Optional[discord.app_commands.Choice[str]] = None,
        system_message: Optional[str] = None,
    ) -> None:
        try:
            # only support creating thread in text channel
            if not isinstance(int.channel, discord.TextChannel) or should_block(
                int.guild
            ):
                return
            # Before creating the message, wait for the multiple message

            def check(message: discord.Message) -> bool:
                return message.author == int.user and message.channel == int.channel

            messages = []
            channel = cast(discord.TextChannel, int.channel)
            await channel.send(
                "Starting chat, please send your message in the next 60 seconds.\nUse `$end`, `$done` or `$stop` to end the chat. Use `$cancel` to cancel the chat\nUse `$cancel` to cancel the command.",
                delete_after=30,
            )

            async def message_wait_for() -> list[str]:
                message = []
                channel = cast(discord.TextChannel, int.channel)
                try:
                    while True:
                        msg = await client.wait_for("message", check=check, timeout=60)

                        if msg.content.lower() in ("$end", "$done", "$stop"):
                            await msg.reply("End of message", delete_after=5)
                            return message
                        elif msg.content.lower() in ("$cancel"):
                            await msg.reply("Canceling", delete_after=5)
                            return []
                        else:
                            message.append(msg.content)
                            await msg.reply("Message received", delete_after=5)
                        await msg.delete()
                except asyncio.TimeoutError:
                    await channel.send("Timeout, stopping the chat", delete_after=10)
                    return []

            messages = await message_wait_for()
            if len(messages) == 0:
                return

            message = first_message + "\n" + "\n".join(messages)
            await start_chat_thread(
                client,
                int,
                message,
                persona,
                follow_up=None,
                model=model,
                system_message=system_message,
            )

        except Exception as e:
            error.print_exception()
            await int.response.send_message(
                f"Failed to start chat {str(e)}", ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Communicate(bot))
