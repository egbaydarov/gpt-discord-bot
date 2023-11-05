import asyncio
import datetime
import logging
from typing import Optional

import discord
from base import Message
from completion import generate_completion_response, process_response
from constants import (
    ACTIVATE_THREAD_PREFX,
    BOT_INVITE_URL,
    DISCORD_BOT_TOKEN,
    KNOWLEDGE_CUTOFF,
    MAX_THREAD_MESSAGES,
    SECONDS_DELAY_RECEIVING_MSG,
    SYSTEM_MESSAGE,
)
from discord import Message as DiscordMessage
from discord.ext import commands
from utils import (
    close_thread,
    discord_message_to_message,
    get_persona,
    is_last_message_stale,
    logger,
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
@discord.app_commands.choices(
    persona=[
        discord.app_commands.Choice(name="default", value="default"),
        discord.app_commands.Choice(name="dan", value="dan"),
        discord.app_commands.Choice(name="sda", value="sda"),
        discord.app_commands.Choice(name="confidant", value="confidant"),
        discord.app_commands.Choice(name="based", value="based"),
        discord.app_commands.Choice(name="oppo", value="oppo"),
        discord.app_commands.Choice(name="dev", value="dev"),
        discord.app_commands.Choice(name="DUDE", value="dude"),
        discord.app_commands.Choice(name="AIM", value="aim"),
        discord.app_commands.Choice(name="AIM", value="aim"),
        discord.app_commands.Choice(name="ucar", value="ucar"),
        discord.app_commands.Choice(name="Jailbreak", value="jailbreak"),
    ]
)
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
        if not isinstance(int.channel, discord.TextChannel):
            return

        # block servers not in allow list
        if should_block(guild=int.guild):
            return

        user = int.user
        try:
            embed = discord.Embed(
                description=f"<@{user.id}> wants to chat! 🤖",
                color=discord.Color.green(),
            )
            embed.add_field(name=user.name, value=message)

            await int.response.send_message(embed=embed)
            response = await int.original_response()
        except Exception as e:
            logger.exception(e)
            await int.response.send_message(
                f"Failed to start chat {str(e)}", ephemeral=True
            )
            return
        today_date = datetime.datetime.now().strftime("%Y-%m-%d")
        # create the thread
        thread = await response.create_thread(
            name=f"[{today_date}] - {user.display_name[:10]} : {message[:10]}",
            slowmode_delay=1,
            reason="gpt-bot",
            auto_archive_duration=60,
        )
        async with thread.typing():
            # prepare the initial system message
            current_date = datetime.datetime.now().strftime("%Y-%m-%d")
            system_message = (
                SYSTEM_MESSAGE.format(
                    knowledge_cutoff=KNOWLEDGE_CUTOFF, current_date=current_date
                )
                if not persona
                else get_persona(persona.value)
            )
            # fetch completion
            messages = [
                Message(user="system", text=system_message),
                Message(user="user", text=message),
            ]
            response_data = await generate_completion_response(
                messages=messages,
            )
            # send the result
            await process_response(thread=thread, response_data=response_data)
    except Exception as e:
        logger.exception(e)
        await int.response.send_message(
            f"Failed to start chat {str(e)}", ephemeral=True
        )


# calls for each message
@client.event
async def on_message(message: DiscordMessage) -> None:
    try:
        # block servers not in allow list
        if (
            should_block(guild=message.guild)
            or not client.user
            or message.author == client.user
        ):
            return
        # ignore messages not in a thread
        channel = message.channel
        if not isinstance(channel, discord.Thread):
            return

        # ignore threads not created by the bot
        thread = channel

        # ignore threads that are archived locked or title is not what we want
        if (
            not thread
            or not thread.last_message
            or thread.owner_id != client.user.id
            or thread.archived
            or thread.locked
            or not thread.name.startswith(ACTIVATE_THREAD_PREFX)
        ):
            # ignore this thread
            return

        if thread.message_count > MAX_THREAD_MESSAGES:
            # too many messages, no longer going to reply
            await close_thread(thread=thread)
            return

        # wait a bit in case user has more messages
        if SECONDS_DELAY_RECEIVING_MSG > 0:
            await asyncio.sleep(SECONDS_DELAY_RECEIVING_MSG)
            if is_last_message_stale(
                interaction_message=message,
                last_message=thread.last_message,
                bot_id=str(client.user.id),
            ):
                # there is another message, so ignore this one
                return

        logger.info(
            f"Thread message to process - {message.author}: {message.content[:50]} - {thread.name} {thread.jump_url}"
        )

        # prepare the initial system message
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        system_message = SYSTEM_MESSAGE.format(
            knowledge_cutoff=KNOWLEDGE_CUTOFF, current_date=current_date
        )

        channel_messages = [
            discord_message_to_message(message=message, bot_name=client.user.name)
            async for message in thread.history(limit=MAX_THREAD_MESSAGES)
        ]
        channel_messages = [x for x in channel_messages if x is not None]
        channel_messages.append(Message(user="system", text=system_message))
        channel_messages.reverse()

        # generate the response
        async with thread.typing():
            response_data = await generate_completion_response(
                messages=channel_messages
            )

        if is_last_message_stale(
            interaction_message=message,
            last_message=thread.last_message,
            bot_id=str(client.user.id),
        ):
            # there is another message and its not from us, so ignore this response
            return
        async with thread.typing():
            await process_response(thread=thread, response_data=response_data)
    except Exception as e:
        logger.exception(e)


client.run(DISCORD_BOT_TOKEN)
