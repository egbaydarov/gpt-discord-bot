from typing import Any, Optional, cast

import discord
import tiktoken
from base import Message, Persona, Thread
from constants import MAX_CHARS_PER_REPLY_MSG
from discord import Client, ClientUser
from discord import Message as DiscordMessage
from rich.console import Console

console = Console()
error = Console(stderr=True, style="bold red")


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
        console.log(f"field.name - {field.name}")
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
) -> Any | list[Any]:  # noqa
    def split_at_boundary(s, boundary) -> Any | list[Any]:  # noqa
        parts = s.split(boundary)
        result = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                result.extend(split_code_block(part))
            else:
                result += split_substring(part)
        return result

    def split_substring(s) -> Any | list[Any]:  # noqa
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

    def split_code_block(s) -> Any | list[Any]:  # noqa
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


def count_token_message(messages: list[Message], models: tiktoken.Encoding) -> int:
    """Count the number of tokens in a list of messages
    Use the tiktoken API to count the number of tokens in a message
    """
    token = 0
    for message in messages:
        if message.text:
            token += len(models.encode(message.text))
    return token


async def generate_initial_system(
    client: Client, thread: Thread, persona: Persona
) -> list[Message]:
    system_message = (
        persona.system.replace("\n-", " ").replace("\n", " ").replace("__", "")
    )  # remove newlines
    user = cast(ClientUser, client.user)
    channel_messages = [
        discord_message_to_message(message=message, bot_name=user.name)
        async for message in thread.history()
    ]
    channel_messages = [x for x in channel_messages if x is not None]
    channel_messages.append(Message(user="system", text=system_message))
    channel_messages.reverse()
    return channel_messages
