import logging
from datetime import datetime
from pathlib import Path

import discord
import yaml
from base import OpenAIModel, Persona
from constants import KNOWLEDGE_CUTOFF, OPENAI_DEFAULT_MODEL, SYSTEM_MESSAGE
from discord import Thread

logger = logging.getLogger(__name__)


def open_persona():  # noqa
    main_personas = Path("persona.yml")
    private_persona = Path("persona.private.yml")
    personas = yaml.safe_load(main_personas.open(encoding="utf-8"))
    if private_persona.exists():
        private_personas = yaml.safe_load(private_persona.open(encoding="utf-8"))
        personas.update(private_personas)
        # delete duplicate personas
        personas = {
            k: v for k, v in personas.items()
        }  # note : will override duplicate keys with the second value
    return personas


def get_persona(persona: str | None) -> Persona:
    """Get the persona from the persona.json file"""
    all_personas = open_persona()
    if persona:
        get_persona = all_personas.get(persona, None)
        if get_persona:
            # convert to Persona object
            return Persona(
                name=persona if persona else "default",
                icon=get_persona.get("icon", ""),
                system=get_persona.get("system", ""),
                color=get_persona.get("color", ""),
                title=get_persona.get("name", ""),
                model=get_persona.get("model", OPENAI_DEFAULT_MODEL),
            )
    return Persona(
        name="GPT-4",
        icon="🤖",
        system=SYSTEM_MESSAGE,
        title="GPT-4",
        color="#000000",
        model=OPENAI_DEFAULT_MODEL,
    )


def update_persona_models(persona: Persona, model: OpenAIModel) -> Persona:
    current_date = datetime.now().strftime("%Y-%m-%d")
    return Persona(
        name=persona.name,
        icon=persona.icon,
        system=persona.system.format(
            knowledge_cutoff=model.knowledge_cutoff,
            current_date=current_date,
        ),
        color=persona.color,
        title=persona.title,
        model=model.name,
    )


def get_persona_by_emoji(thread: Thread) -> Persona:
    # first emoji in the thread name
    emoji = thread.name.split(" ")[2]
    all_personas = open_persona()
    for persona, value in all_personas.items():
        if emoji in value.get("icon"):
            return Persona(
                name=persona,
                icon=value.get("icon", ""),
                system=value.get("system", ""),
                color=value.get("color", ""),
                title=value.get("name", ""),
                model=value.get("model", OPENAI_DEFAULT_MODEL),
            )
    current_date = datetime.now().strftime("%Y-%m-%d")
    return Persona(
        name="GPT-4",
        icon="🤖",
        system=SYSTEM_MESSAGE.format(
            knowledge_cutoff=KNOWLEDGE_CUTOFF, current_date=current_date
        ),
        title="GPT-4",
        color="#000000",
        model=OPENAI_DEFAULT_MODEL,
    )


def generate_choice_persona() -> list[discord.app_commands.Choice]:
    all_personas = open_persona()
    persona_list = []
    for persona, value in all_personas.items():
        persona_list.append(
            discord.app_commands.Choice(name=value.get("keywords"), value=persona)
        )
    logger.info(f"persona_list: {persona_list}")
    return persona_list


def get_all_icons() -> list[str]:
    all_personas = open_persona()
    icon_list = []
    for persona, value in all_personas.items():
        icon_list.append(value.get("icon"))
    icon_list.append("🤖")
    return icon_list
