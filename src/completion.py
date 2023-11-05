import io
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import aiohttp
import discord

from src.base import Message
from src.constants import (
    MAX_CHARS_PER_REPLY_MSG,
    OPENAI_API_KEY,
    OPENAI_API_URL,
    OPENAI_MODEL,
)
from src.utils import close_thread, logger, split_into_shorter_messages


class CompletionResult(Enum):
    OK = 0
    TOO_LONG = 1
    ERROR = 2


@dataclass
class CompletionData:
    status: CompletionResult
    reply_text: Optional[str]
    status_text: Optional[str]


async def generate_completion_response(
    messages: List[Message],
) -> CompletionData:
    try:
        async with aiohttp.ClientSession() as session:
            messages = [message.render() for message in messages]  # type: ignore
            async with session.post(
                url=OPENAI_API_URL,
                json={"model": OPENAI_MODEL, "messages": messages},
                auth=aiohttp.BasicAuth("", OPENAI_API_KEY),
            ) as r:
                if r.status == 200:  # noqa
                    js = await r.json()
                    reply = js["choices"][0]["message"]["content"]
                    return CompletionData(
                        status=CompletionResult.OK, reply_text=reply, status_text=None
                    )
                else:
                    js = await r.json()
                    code = js["error"]["code"]
                    status = (
                        CompletionResult.TOO_LONG
                        if code == "context_length_exceeded"
                        else CompletionResult.ERROR
                    )
                    return CompletionData(
                        status=status, reply_text=None, status_text=js
                    )
    except Exception as e:
        logger.exception(e)
        return CompletionData(
            status=CompletionResult.ERROR, reply_text=None, status_text=str(e)
        )


async def process_response(
    thread: discord.Thread, response_data: CompletionData
) -> None:
    status = response_data.status
    reply_text = response_data.reply_text
    status_text = response_data.status_text
    if status is CompletionResult.OK:
        if not reply_text:
            await thread.send(
                embed=discord.Embed(
                    description="**Invalid response** - empty response",
                    color=discord.Color.yellow(),
                )
            )
        else:
            shorter_response = split_into_shorter_messages(reply_text)
            for r in shorter_response:
                if len(r) > MAX_CHARS_PER_REPLY_MSG:
                    file = discord.File(io.StringIO(r), "message.txt")  # type: ignore
                    await thread.send(file=file)
                else:
                    await thread.send(r)
    elif status is CompletionResult.TOO_LONG:
        await close_thread(thread)
    else:
        await thread.send(
            embed=discord.Embed(
                description=f"**Error** - {status_text}",
                color=discord.Color.yellow(),
            )
        )
