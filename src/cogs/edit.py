"""
my first cogs !
Allow to change the parameters of the thread :
- Persona
- Models
- System Message

"""

import logging
from typing import Optional, cast

import discord
from discord import app_commands
from discord.ext import commands
from main import client, personas_choice, models_choice
from src.utils.personas import get_all_icons, get_persona
from utils.utils import allowed_thread, send_to_log_channel

logger = logging.getLogger(__name__)


class EditThread(commands.GroupCog, name="edit"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        super().__init__()

    @app_commands.command(name="persona")
    @discord.app_commands.describe(persona="The persona to use with the model")
    @discord.app_commands.choices(persona=personas_choice)
    @discord.app_commands.guild_only()
    async def change_persona(
        self: commands.Cog,
        int: discord.Interaction,
        persona: Optional[discord.app_commands.Choice[str]] = None,
    ) -> None:
        logger.info(
            f"Changing persona to {persona.value} in Guild: {int.guild}"  # type: ignore
        )
        if not allowed_thread(client, int.channel, int.guild, int.user):
            await int.response.send_message(
                "This command can only be used in a thread created by the bot",
                ephemeral=True,
            )
            return

        thread = cast(discord.Thread, int.channel)
        persona_system = get_persona(persona.value if persona else None)
        thread_name = thread.name.split(" ")
        # replace the 3rd element with the new persona icon
        icon = thread_name[2]
        icon_list = get_all_icons()
        if icon in icon_list:
            thread_name[2] = persona_system.icon
            await thread.edit(name=" ".join(thread_name))
            await send_to_log_channel(
                client,
                int.guild.id,  # type: ignore
                thread.name,
                int.user.global_name,  # type: ignore
                persona_system,
                None,
                "changed",
            )
            await int.response.send_message(
                f"Changed persona to {persona_system.title}", ephemeral=True
            )
        else:
            await int.response.send_message(
                f"Failed to change persona to {persona_system.title}",
                ephemeral=True,
            )
    @app_commands.command(name="model")
    @discord.app_commands.describe(model="The model to change to")
    @discord.app_commands.choices(model=models_choice)
    @discord.app_commands.guild_only()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EditThread(bot))
