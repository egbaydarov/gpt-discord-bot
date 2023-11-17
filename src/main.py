import logging
from typing import Optional, cast

import discord
import tiktoken
from src.utils.chat import chat_bot
from constants import (
    BOT_INVITE_URL,
    DISCORD_BOT_TOKEN,
)
from discord import Message as DiscordMessage
from discord.ext import commands
from src.utils.parse_model import generate_choice_model
from src.utils.personas import (
    generate_choice_persona,
    get_persona,
)

from src.utils.utils import (
    allowed_thread,
    close_thread,
    logger,
    send_to_log_channel,
)

logging.basicConfig(
    format="[%(asctime)s] [%(filename)s:%(lineno)d] %(message)s", level=logging.INFO
)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client)
bot = commands.Bot(command_prefix="!", intents=intents)
TOKEN_ENCODING = tiktoken.encoding_for_model(
    "gpt-4"
)  # need to be upgraded to the new gpt-4 turbo but can do the job for now
personas_choice = generate_choice_persona()
models_choice = generate_choice_model()


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
    await bot.load_extension("cogs.create")
    await bot.load_extension("cogs.edit")
    await tree.sync()


# calls for each message
@client.event
async def on_message(message: DiscordMessage) -> None:  # noqa
    await chat_bot(message, client, TOKEN_ENCODING)


@tree.command(name="help", description="Print each persona and their description")
@discord.app_commands.checks.has_permissions(send_messages=True)
@discord.app_commands.checks.has_permissions(view_channel=True)
@discord.app_commands.checks.bot_has_permissions(send_messages=True)
@discord.app_commands.checks.bot_has_permissions(view_channel=True)
@discord.app_commands.describe(
    persona="The persona to use with the model, changing this response style"
)
@discord.app_commands.choices(persona=personas_choice)
async def help_command(
    int: discord.Interaction, persona: Optional[discord.app_commands.Choice[str]] = None
) -> None:
    persona_system = get_persona(persona.value if persona else None)
    embed = discord.Embed(
        title=f"{persona_system.icon} {persona_system.title}",
        description=persona_system.system,
        color=discord.Colour.from_str(persona_system.color),
    )
    embed.add_field(
        name="Model",
        value=f"{persona_system.model}",
        inline=True,
    )
    await int.response.send_message(embed=embed)


@tree.command(name="close", description="Stop the chat and archive the thread")
async def stop(int: discord.Interaction) -> None:
    logger.info(f"Closing thread in Guild: {int.guild}")
    # followup
    await int.response.defer()
    follow_up = await int.followup.send("Closing thread...", wait=True, ephemeral=True)
    if not allowed_thread(client, int.channel, int.guild, int.user):
        await int.response.send_message(
            "This command can only be used in a thread created by the bot",
            ephemeral=True,
        )
        return
    thread = cast(discord.Thread, int.channel)
    await close_thread(thread)

    await send_to_log_channel(
        client,
        int.guild.id,  # type: ignore
        thread.name,
        openai_model=None,
        user=int.user.global_name,  # type: ignore
        persona=None,
        type="closed",
    )
    await follow_up.delete()


client.run(DISCORD_BOT_TOKEN)
