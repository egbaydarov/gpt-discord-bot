import asyncio
from pathlib import Path

import discord
import tiktoken
from constants import (
    BOT_INVITE_URL,
    DISCORD_BOT_TOKEN,
)
from discord import Message as DiscordMessage
from discord.ext import commands
from rich.console import Console
from utils.chat import chat_bot
from utils.parse_model import generate_choice_model
from utils.personas import (
    generate_choice_persona,
)

error = Console(stderr=True, style="bold red")
console = Console()

intents = discord.Intents.default()
intents.message_content = True


class Owlly(commands.Bot):
    def __init__(self, *, intents: discord.Intents, command_prefix: str) -> None:  # noqa
        super().__init__(intents=intents, command_prefix=command_prefix)
        self.command_prefix = command_prefix

    async def setup_hook(self) -> None:  # noqa
        console.log("Setting up slash commands")
        cogs = Path("src/cogs").glob("*.py")
        for cog in cogs:
            await client.load_extension(f"cogs.{cog.stem}")
            console.log(f"Loaded cog {cog.stem}")
        await self.tree.sync()


client = Owlly(intents=intents, command_prefix="!")
tree = client.tree

TOKEN_ENCODING = tiktoken.encoding_for_model(
    "gpt-4"
)  # need to be upgraded to the new gpt-4 turbo but can do the job for now
personas_choice = generate_choice_persona()
models_choice = generate_choice_model()


@client.event
async def on_ready() -> None:
    console.log(f"We have logged in as {client.user}. Invite URL: {BOT_INVITE_URL}")


# calls for each message
@client.event
async def on_message(message: DiscordMessage) -> None:  # noqa
    await chat_bot(message, client, TOKEN_ENCODING)


async def main() -> None:
    async with client:
        await client.start(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
