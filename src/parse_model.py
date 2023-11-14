import json
from pathlib import Path

import discord
from base import OpenAIModel


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
