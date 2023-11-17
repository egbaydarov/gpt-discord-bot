"""
my first cogs !
Allow to change the parameters of the thread :
- Persona
- Models
- System Message

"""

from typing import Optional, cast

import discord
from discord import app_commands
from discord.ext import commands
from main import client, models_choice, personas_choice
from rich.console import Console
from utils.parse_model import (
    create_model_commands,
    edit_embed,
    get_model_from_name,
)
from utils.personas import (
    get_all_icons,
    get_persona,
    get_persona_by_emoji,
    get_system_message,
    update_persona_models,
)
from utils.threads import allowed_thread
from utils.utils import send_to_log_channel

console = Console()
error = Console(stderr=True, style="bold red")


class EditThread(commands.GroupCog, name="edit"):
    def __init__(self, bot: commands.Bot) -> None:  # noqa
        self.bot = bot
        super().__init__()

    @app_commands.command(name="persona")
    @discord.app_commands.describe(persona="The persona to use with the model")
    @discord.app_commands.choices(persona=personas_choice)
    @discord.app_commands.guild_only()
    async def change_persona(
        self,  # noqa
        int: discord.Interaction,
        persona: Optional[discord.app_commands.Choice[str]] = None,
    ) -> None:
        console.log(
            f"Changing persona to {persona.value} in Guild: {int.guild}"  # type: ignore
        )
        if not allowed_thread(self.bot, int.channel, int.guild, int.user):
            await int.response.send_message(
                "This command can only be used in a thread created by the bot",
                ephemeral=True,
            )
            return

        thread = cast(discord.Thread, int.channel)
        gpt_models = create_model_commands(None, persona)
        persona_system = get_persona(persona.value if persona else None)
        original_persona = persona_system
        persona_system = update_persona_models(persona_system, gpt_models)
        system_message = get_system_message(thread, persona_system)
        sys_msg = ""
        if not system_message.system == original_persona.system:
            sys_msg = "**__System Message__**:\n> " + system_message.system
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
            await edit_embed(thread, gpt_models, sys_msg)
        else:
            await int.response.send_message(
                f"Failed to change persona to {persona_system.title}",
                ephemeral=True,
            )

    @app_commands.command(name="model")
    @discord.app_commands.describe(model="The model to change to")
    @discord.app_commands.choices(model=models_choice)
    @discord.app_commands.guild_only()
    async def change_gpt_model(
        self,  # noqa
        int: discord.Interaction,
        model: Optional[discord.app_commands.Choice[str]] = None,
    ) -> None:
        if not allowed_thread(self.bot, int.channel, int.guild, int.user):
            await int.response.send_message(
                "This command can only be used in a thread created by the bot",
                ephemeral=True,
            )
            return
        thread = cast(discord.Thread, int.channel)
        # default model from persona thread model if not specified
        gpt_models = model.value if model else get_persona_by_emoji(thread).model
        await edit_embed(thread, get_model_from_name(gpt_models), None)
        await send_to_log_channel(
            client,
            int.guild.id,  # type: ignore
            thread.name,
            int.user.global_name,  # type: ignore
            None,
            get_model_from_name(gpt_models),
            "changed",
        )
        await int.response.send_message(
            f"Changed model to {gpt_models}", ephemeral=True
        )

    @app_commands.command(
        name="system",
        description="Change the system message, override the persona. Let empty to return to default message.",
    )
    @discord.app_commands.describe(system="The system message to change to")
    @discord.app_commands.guild_only()
    async def change_system_message(
        self,  # noqa
        int: discord.Interaction,
        system: Optional[str] = None,
    ) -> None:
        if not allowed_thread(self.bot, int.channel, int.guild, int.user):
            await int.response.send_message(
                "This command can only be used in a thread created by the bot",
                ephemeral=True,
            )
            return
        thread = cast(discord.Thread, int.channel)
        persona_system = get_persona_by_emoji(thread)
        persona_system = get_system_message(thread, persona_system)

        if not system:
            system = ""  # remove the system message and return to the original persona system message
        else:
            system = "**__System Message__**:\n> " + system

        await edit_embed(thread, None, system, int)

        await send_to_log_channel(
            self.bot,
            int.guild.id,  # type: ignore
            thread.name,
            int.user.global_name,  # type: ignore
            persona_system,
            None,
            "changed",
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(EditThread(bot))
