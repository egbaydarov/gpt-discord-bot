import asyncio
import logging
from pathlib import Path

import discord
import tiktoken
from constants import (
    BOT_INVITE_URL,
    DISCORD_BOT_TOKEN,
)
from discord import Message as DiscordMessage
from discord.ext import commands
from utils.chat import chat_bot
from utils.parse_model import generate_choice_model
from utils.personas import (
    generate_choice_persona,
)
from utils.utils import (
    logger,
)

logging.basicConfig(
    format="[%(asctime)s] [%(filename)s:%(lineno)d] %(message)s", level=logging.INFO
)

intents = discord.Intents.default()
intents.message_content = True


class Owlly(discord.Client):
    def __init__(self, *, intents: discord.Intents) -> None:  # noqa
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)

    async def setup_hook(self) -> None:  # noqa
        logger.info("Setting up slash commands")
        cogs = Path("src/cogs").glob("*.py")
        for cog in cogs:
            await bot.load_extension(f"cogs.{cog.stem}")
            logger.info(f"Loaded cog {cog.stem}")
        await self.tree.sync()


client = Owlly(intents=intents)
tree = client.tree
bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN_ENCODING = tiktoken.encoding_for_model(
    "gpt-4"
)  # need to be upgraded to the new gpt-4 turbo but can do the job for now
personas_choice = generate_choice_persona()
models_choice = generate_choice_model()


@client.event
async def on_ready() -> None:
    logger.info(f"We have logged in as {client.user}. Invite URL: {BOT_INVITE_URL}")


# calls for each message
@client.event
async def on_message(message: DiscordMessage) -> None:  # noqa
    await chat_bot(message, client, TOKEN_ENCODING)


async def main() -> None:
    async with client:
        await client.start(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
