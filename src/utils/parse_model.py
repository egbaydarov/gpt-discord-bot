import json
from pathlib import Path
from typing import Optional

import discord
from base import OpenAIModel, Persona
from constants import KNOWLEDGE_CUTOFF, MAX_INPUTS_TOKENS, OPENAI_DEFAULT_MODEL
from rich.console import Console
from utils.personas import get_persona

console = Console()
error = Console(stderr=True, style="bold red")


def open_model() -> list[OpenAIModel]:
    model_file = Path("openai_models.json")
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


async def edit_embed(
    thread: discord.Thread,
    model: OpenAIModel,
    message_system: Optional[str] = None,
    int: Optional[discord.Interaction] = None,
) -> None:
    first_thread_message = thread.starter_message
    if first_thread_message:
        # get footer
        footer = first_thread_message.embeds[0].footer.text
        if footer:
            # replace model after the "model: " text
            old_model = footer.split("Model: ")[1]
            new_model = model.name
            new_footer = footer.replace(old_model, new_model)
        else:
            new_footer = f"Model: {model.name}"
        # edit first message
        await first_thread_message.edit(
            content=message_system if message_system else first_thread_message.content,
            embed=discord.Embed(
                title=first_thread_message.embeds[0].title,
                description=first_thread_message.embeds[0].description,
                color=first_thread_message.embeds[0].color,
            ).set_footer(text=new_footer),
        )
        if int:
            msg = f"Changed model to {model.name}"
            if message_system:
                msg += f"with:\n>>>{message_system}"
            await int.response.send_message(
                f"Changed model to {model.name}", ephemeral=True
            )
    else:
        if int:
            await int.response.send_message(
                f"Failed to change model to {model.name}", ephemeral=True
            )
        error.log("Failed to change model", log_locals=True)
