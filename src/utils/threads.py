from typing import Optional

import discord
from base import InteractionChannel, MessageableChannel
from constants import (
    ACTIVATE_THREAD_PREFX,
    ALLOWED_SERVER_IDS,
    INACTIVATE_THREAD_PREFIX,
)
from rich.console import Console

console = Console()
error = Console(stderr=True, style="bold red")


def should_block(guild: Optional[discord.Guild]) -> bool:
    if guild is None:
        # dm's not supported
        error.log("DM not supported")
        return True
    if guild.id and guild.id not in ALLOWED_SERVER_IDS:
        # not allowed in this server
        error.log(f"Guild {guild} not allowed")
        return True
    return False


async def close_thread(thread: discord.Thread) -> None:
    await thread.edit(name=INACTIVATE_THREAD_PREFIX)
    await thread.send(
        embed=discord.Embed(
            description="**Thread closed**...",
            color=discord.Color.blue(),
        )
    )
    await thread.edit(archived=True, locked=True)


def allowed_thread(
    client: discord.Client,
    thread: Optional[InteractionChannel | MessageableChannel] = None,
    guild: Optional[discord.Guild] = None,
    author: Optional[discord.User | discord.Member] = None,
    need_last_message: bool = False,
) -> bool:
    print()
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
