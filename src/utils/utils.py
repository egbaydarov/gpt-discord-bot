import asyncio
import textwrap
from typing import Literal, Optional

import discord
from base import (
    ChannelLogs,
    OpenAIModel,
    Persona,
)
from constants import (
    ALLOWED_SERVER,
    OPENAI_DEFAULT_MODEL,
)
from discord import Client
from discord.ext.commands import Bot
from rich.console import Console

console = Console()
error = Console(stderr=True, style="bold red")


async def send_to_log_channel(  # noqa
    client: Client,
    guild_id: int,
    thread_name: str,
    user: str,
    persona: Persona | None,
    openai_model: OpenAIModel | None,
    type: Literal["message", "created", "changed", "closed"],
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
        match type:
            case "message":
                message = "New message received"
                if not logs.event.get("message", False):
                    return
                if token:
                    message += f"\n- __Token count__: {token}"
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

        if log_channel and isinstance(log_channel, discord.TextChannel):
            message = f"""
            **{message}**
            - __Thread name__: `{thread_name}`
            - __User__: `{user}`
            - __Model__: `{OPENAI_DEFAULT_MODEL}`
            """
            if persona:
                message += f"\n- __Persona__: `{persona.title}`"
                message = message.replace(OPENAI_DEFAULT_MODEL, persona.model)
            if openai_model:
                message = message.replace(OPENAI_DEFAULT_MODEL, openai_model.name)
            await log_channel.send(textwrap.dedent(message))
    except Exception:
        error.print_exception()
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
