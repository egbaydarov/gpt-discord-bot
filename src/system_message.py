from typing import Optional

import discord
from base import Persona


def get_system_message(thread: discord.Thread, persona: Persona) -> Persona:
    first_message = thread.starter_message
    if first_message:
        content = first_message.content
        if "**__System Message__**:\n>" in content:
            return Persona(
                name=persona.name,
                title=persona.title,
                icon=persona.icon,
                color=persona.color,
                system=content.replace("**__System Message__**:\n> ", ""),
                model=persona.model,
            )
    return persona


def create_system_message(
    persona: Persona, system_message: Optional[str] = None
) -> Persona:
    if system_message:
        return Persona(
            name=persona.name,
            title=persona.title,
            icon=persona.icon,
            color=persona.color,
            system=system_message,
            model=persona.model,
        )
    return persona
