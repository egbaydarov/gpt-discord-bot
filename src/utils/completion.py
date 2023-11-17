import io
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

import aiohttp
import discord
from base import Message
from constants import (
    DATE_FORMAT,
    MAX_CHARS_PER_REPLY_MSG,
    OPENAI_API_KEY,
    OPENAI_API_URL,
    OPENAI_DEFAULT_MODEL,
    THREAD_NAME,
    TIME_FORMAT,
)
from rich.console import Console
from utils.messages import split_into_shorter_messages
from utils.threads import close_thread

console = Console()
error = Console(stderr=True, style="bold red")


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
    model: str = OPENAI_DEFAULT_MODEL,
) -> CompletionData:
    try:
        async with aiohttp.ClientSession() as session:
            messages = [message.render() for message in messages]  # type: ignore
            async with session.post(
                url=OPENAI_API_URL,
                json={"model": model, "messages": messages},
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
        error.print_exception()
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
            # remove empty messages in shorter_response
            shorter_response = [r for r in shorter_response if len(r) > 0]
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


async def resume_message(
    message: Message, followup: discord.WebhookMessage
) -> str | None:
    try:
        system_message = Message(
            user="system",
            text="Resume the message in 1 to 2 words please, with keeping the language used by the user. Don't add any point, comma, or quotes. It must be a short sentence to create a thread.",
        )
        messages = [system_message, message]
        response_data = await generate_completion_response(
            messages, model="gpt-3.5-turbo"
        )
        status = response_data.status
        reply_text = response_data.reply_text
        status_text = response_data.status_text
        if status is CompletionResult.OK:
            if not reply_text:
                await followup.edit(
                    content="",
                    embed=discord.Embed(
                        description="**Invalid response** - empty response",
                        color=discord.Color.yellow(),
                    ),
                )
                return ""
            elif len(reply_text) > MAX_CHARS_PER_REPLY_MSG:
                await followup.edit(
                    content="",
                    embed=discord.Embed(
                        description="**Invalid response** - too long",
                        color=discord.Color.yellow(),
                    ),
                )
                return ""
            else:
                return reply_text.replace(".", "").replace('"', "")

        elif status is CompletionResult.TOO_LONG:
            await followup.edit(
                content="",
                embed=discord.Embed(
                    description=f"**Error** - {status_text}",
                    color=discord.Color.yellow(),
                ),
            )
            return ""
        else:
            await followup.edit(
                content="",
                embed=discord.Embed(
                    description=f"**Error** - {status_text}",
                    color=discord.Color.yellow(),
                ),
            )
            return ""
    except Exception as e:
        error.print_exception()
        await followup.edit(
            content="",
            embed=discord.Embed(
                description=f"**Error** - {str(e)}",
                color=discord.Color.yellow(),
            ),
        )
        return ""


async def parse_thread_name(
    interaction: discord.Interaction, message: str, followup: discord.WebhookMessage
) -> str:
    gpt_message = Message(
        user="user",
        text=message,
    )

    accepted_value = {
        "{{date}}": datetime.now().strftime(DATE_FORMAT),
        "{{time}}": datetime.now().strftime(TIME_FORMAT),
        "{{author}}": interaction.user.display_name[:10],
        "{{message}}": message[:5],
    }
    thread_name = THREAD_NAME
    for key, value in accepted_value.items():
        thread_name = thread_name.replace(key, value)
        if "{{resume}}" in thread_name:
            resume = await resume_message(gpt_message, followup)
            if resume:
                thread_name = thread_name.replace("{{resume}}", resume)
    return thread_name
