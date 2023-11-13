import asyncio
import logging
import textwrap
import typing
from typing import Any, List, Literal, Optional

import discord
import tiktoken
from base import ChannelLogs, InteractionChannel, Message, MessageableChannel, Persona
from constants import (
    ACTIVATE_THREAD_PREFX,
    ALLOWED_SERVER,
    ALLOWED_SERVER_IDS,
    INACTIVATE_THREAD_PREFIX,
    MAX_CHARS_PER_REPLY_MSG,
)
from discord import Client, ClientUser, Thread
from discord import Message as DiscordMessage
from discord.ext.commands import Bot
from personas import get_persona_by_emoji

logger = logging.getLogger(__name__)


def discord_message_to_message(
    message: DiscordMessage, bot_name: str
) -> Optional[Message]:
    user_name = "assistant" if message.author.name == bot_name else "user"
    if (
        message.reference
        and message.type == discord.MessageType.thread_starter_message
        and message.reference.cached_message
        and len(message.reference.cached_message.embeds) > 0
        and len(message.reference.cached_message.embeds[0].fields) > 0
    ):
        field = message.reference.cached_message.embeds[0].fields[0]
        logger.info(f"field.name - {field.name}")
        return Message(user="user", text=field.value)
    elif message.content:
        user_name = "assistant" if message.author.name == bot_name else "user"
        return Message(user=user_name, text=message.content)
    return None


def remove_last_bot_message(message: list[Message]) -> list[Message]:
    # remove the lasts messages send by the bot
    while message[-1].user == "assistant":
        message.pop()
    return message


def split_into_shorter_messages(
    text,  # noqa
    limit=MAX_CHARS_PER_REPLY_MSG,  # noqa
    code_block="```",  # noqa
) -> Any | List[Any]:  # noqa
    def split_at_boundary(s, boundary) -> Any | List[Any]:  # noqa
        parts = s.split(boundary)
        result = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                result.extend(split_code_block(part))
            else:
                result += split_substring(part)
        return result

    def split_substring(s) -> Any | List[Any]:  # noqa
        if len(s) <= limit:
            return [s]
        for boundary in ("\n", " "):
            if boundary in s:
                break
        else:
            return [s[:limit]] + split_substring(s[limit:])

        pieces = s.split(boundary)
        result = []
        current_part = pieces[0]
        for piece in pieces[1:]:
            if len(current_part) + len(boundary) + len(piece) > limit:
                result.append(current_part)
                current_part = piece
            else:
                current_part += boundary + piece
        result.append(current_part)
        return result

    def split_code_block(s) -> Any | List[Any]:  # noqa
        if len(code_block + s + code_block) <= limit:
            return [code_block + s + code_block]
        else:
            lines = s.split("\n")
            result = [code_block]
            for line in lines:
                if len(result[-1] + "\n" + line) > limit:
                    result[-1] += code_block
                    result.append(code_block + line)
                else:
                    result[-1] += "\n" + line
            result[-1] += code_block
            return result

    if code_block in text:
        return split_at_boundary(text, code_block)
    else:
        return split_substring(text)


def is_last_message_stale(
    interaction_message: DiscordMessage, last_message: DiscordMessage, bot_id: str
) -> bool:
    return (
        last_message
        and last_message.id != interaction_message.id
        and last_message.author
        and last_message.author.id != bot_id
    )


async def close_thread(thread: discord.Thread) -> None:
    await thread.edit(name=INACTIVATE_THREAD_PREFIX)
    await thread.send(
        embed=discord.Embed(
            description="**Thread closed**...",
            color=discord.Color.blue(),
        )
    )
    await thread.edit(archived=True, locked=True)


def should_block(guild: Optional[discord.Guild]) -> bool:
    if guild is None:
        # dm's not supported
        logger.info("DM not supported")
        return True
    if guild.id and guild.id not in ALLOWED_SERVER_IDS:
        # not allowed in this server
        logger.info(f"Guild {guild} not allowed")
        return True
    return False


def count_token_message(messages: list[Message], models: tiktoken.Encoding) -> int:
    """Count the number of tokens in a list of messages
    Use the tiktoken API to count the number of tokens in a message
    """
    token = 0
    for message in messages:
        if message.text:
            token += len(models.encode(message.text))
    return token


async def generate_initial_system(client: Client, thread: Thread) -> list[Message]:
    system_message = get_persona_by_emoji(thread).system

    user = typing.cast(ClientUser, client.user)
    channel_messages = [
        discord_message_to_message(message=message, bot_name=user.name)
        async for message in thread.history()
    ]
    channel_messages = [x for x in channel_messages if x is not None]
    channel_messages.append(Message(user="system", text=system_message))
    channel_messages.reverse()
    return channel_messages


def allowed_thread(
    client: Client,
    thread: Optional[InteractionChannel | MessageableChannel] = None,
    guild: Optional[discord.Guild] = None,
    author: Optional[discord.User | discord.Member] = None,
    need_last_message: bool = False,
) -> bool:
    if should_block(guild) or not client.user or not author or author.bot:
        return False

    # ignore messages not in a thread
    if not isinstance(thread, discord.Thread):
        return False

    if (
        not thread
        or (need_last_message and not thread.last_message)
        or thread.owner_id != client.user.id
        or thread.archived
        or thread.locked
        or not thread.name.startswith(ACTIVATE_THREAD_PREFX)
    ):
        # ignore this thread
        return False
    return True


async def send_to_log_channel(  # noqa
    client: Client,
    guild_id: int,
    thread_name: str,
    user: str,
    persona: Persona | None,
    type: Literal["message", "created", "changed", "closed", "token"],
    token: Optional[int] = None,
) -> None:
    """Send a message to the log channel"""
    try:
        logs = next((x for x in ALLOWED_SERVER if x["id"] == guild_id), None)
        if not logs or logs.get("logs", None) is None:
            return
        logs = ChannelLogs(logs["logs"]["channel_id"], logs["logs"]["event"])
        log_channel = client.get_channel(logs.channel_id)
        message = ""
        logger.info(f"logs.event - {logs.event.get('message', False)}")
        match type:
            case "message":
                message = "New message received"
                if not logs.event.get("message", False):
                    logger.info("logs.event.get('message', False) - True")
                    return
            case "created":
                message = "Thread created"
                if not logs.event.get("created", False):
                    return
            case "changed":
                message = "Persona changed"
                if not logs.event.get("changed", False):
                    return
            case "closed":
                message = "Thread closed"
                if not logs.event.get("closed", False):
                    return
            case "token":
                if token:
                    message = f"Token count: {token}"
        if log_channel and isinstance(log_channel, discord.TextChannel):
            message = f"""
            **{message}**
            - __Thread name__: `{thread_name}`
            - __User__: `{user}`
            """
            if persona:
                message += f"- __Persona__: `{persona.title}`"
            await log_channel.send(textwrap.dedent(message))
    except Exception as e:
        logger.exception(e)
        return


async def wait_for_message(int: discord.Interaction, bot: Bot) -> Optional[str]:
    rep = []
    try:
        message = await bot.wait_for(
            "message",
            check=lambda m: m.author == int.user and m.channel == int.channel,
        )
        if message.content.lower() == "cancel":
            await int.response.send_message("Cancelled", ephemeral=True)
            return
        elif message.content.lower() in ("end", "done", "stop"):
            return
        rep.append(message.content)
        await wait_for_message(int, bot)
    except asyncio.TimeoutError:
        await int.response.send_message("Timed out", ephemeral=True)
        return
    finally:
        reponse = "\n".join(rep)
        return reponse
