from typing import Optional, cast

import discord
from discord import app_commands
from discord.ext import commands
from main import client, personas_choice
from rich.console import Console
from utils.personas import get_persona
from utils.threads import allowed_thread, close_thread
from utils.utils import send_to_log_channel

console = Console()
error = Console(stderr=True, style="bold red")


class UtilsCommands(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:  # noqa
        self.bot = bot

    @app_commands.command(name="ping", description="Ping the bot")
    async def ping(self, int: discord.Interaction) -> None:  # noqa
        await int.response.send_message("Pong!", ephemeral=True)

    @app_commands.command(
        name="close", description="Stop the chat and archive the thread"
    )
    async def stop(self, int: discord.Interaction) -> None:  # noqa
        console.log(f"Closing thread in Guild: {int.guild}")
        # followup
        await int.response.defer()
        follow_up = await int.followup.send(
            "Closing thread...", wait=True, ephemeral=True
        )
        if not allowed_thread(self.bot, int.channel, int.guild, int.user):
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

    @app_commands.command(
        name="help", description="Print each persona and their description"
    )
    @discord.app_commands.checks.has_permissions(send_messages=True)
    @discord.app_commands.checks.has_permissions(view_channel=True)
    @discord.app_commands.checks.bot_has_permissions(send_messages=True)
    @discord.app_commands.checks.bot_has_permissions(view_channel=True)
    @discord.app_commands.describe(
        persona="The persona to use with the model, changing this response style"
    )
    @discord.app_commands.choices(persona=personas_choice)
    async def help_command(
        self,  # noqa
        int: discord.Interaction,
        persona: Optional[discord.app_commands.Choice[str]] = None,
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UtilsCommands(bot))
