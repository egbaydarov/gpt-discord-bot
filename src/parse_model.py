import json
from pathlib import Path
from typing import Optional

import discord
from base import OpenAIModel, Persona
from constants import KNOWLEDGE_CUTOFF, MAX_INPUTS_TOKENS, OPENAI_DEFAULT_MODEL
from personas import get_persona


def open_model() -> list[OpenAIModel]:
    model_file = Path("models_list.json")
    data_models = json.load(model_file.open(encoding="utf-8"))
    models = []
    for model in data_models:
        models.append(
            OpenAIModel(
                name=model.get("name"),
                knowledge_cutoff=model.get("knowledge_cutoff"),
                max_input_token=model.get("max_input_token"),
            )
        )
    return models


def generate_choice_model() -> list[discord.app_commands.Choice]:
    all_models = open_model()
    model_list = []
    for model in all_models:
        model_list.append(
            discord.app_commands.Choice(name=model.name, value=model.name)
        )
    return model_list


def get_model_from_name(model_name: str | None) -> OpenAIModel:
    all_models = open_model()
    for model in all_models:
        if model.name == model_name:
            return model
    return OpenAIModel(
        model_name if model_name else OPENAI_DEFAULT_MODEL,
        KNOWLEDGE_CUTOFF,
        MAX_INPUTS_TOKENS,
    )


def get_models_completion(
    thread: discord.Thread, persona: Persona | None
) -> OpenAIModel:
    open_model()
    first_thread_message = thread.starter_message
    if first_thread_message:
        # get footer
        footer = first_thread_message.embeds[0].footer.text
        if footer:
            footer_model = footer.replace("Model: ", "")
            return get_model_from_name(footer_model)
    if persona:
        return get_model_from_name(persona.model)
    return get_model_from_name(None)


def create_model_commands(
    model: Optional[discord.app_commands.Choice[str]] = None,
    persona: Optional[discord.app_commands.Choice[str]] = None,
) -> OpenAIModel:
    if model:
        return get_model_from_name(model.value)
    elif persona:
        persona_model = get_persona(persona.value)
        return get_model_from_name(persona_model.model)
    return OpenAIModel(
        name=OPENAI_DEFAULT_MODEL,
        knowledge_cutoff=KNOWLEDGE_CUTOFF,
        max_input_token=MAX_INPUTS_TOKENS,
    )
