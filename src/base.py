from dataclasses import dataclass
from typing import Literal, Optional, Union
from xmlrpc.client import boolean

from discord import (
    CategoryChannel,
    DMChannel,
    ForumChannel,
    GroupChannel,
    PartialMessageable,
    StageChannel,
    TextChannel,
    Thread,
    VoiceChannel,
)


@dataclass(frozen=True)
class Message:
    user: str
    text: Optional[str] = None

    def render(self):  # noqa
        result = {"role": self.user, "content": self.text}
        return result


@dataclass(frozen=True)
class Persona:
    name: str
    icon: str
    system: str
    color: str
    title: str
    model: str

    def render(self):  # noqa
        result = {
            "name": self.name,
            "icon": self.icon,
            "system": self.system,
            "color": self.color,
            "title": self.title,
            "model": self.model,
        }
        return result


@dataclass(frozen=True)
class ChannelLogs:
    channel_id: int
    event: dict[Literal["message", "changed", "created", "closed"], boolean]

    def render(self):  # noqa
        result = {
            "channel_id": self.channel_id,
            "event": self.event,
        }
        return result


@dataclass(frozen=True)
class OpenAIModel:
    name: str
    knowledge_cutoff: str
    max_input_token: int

    def render(self):  # noqa
        result = {
            "name": self.name,
            "knowledge_cutoff": self.knowledge_cutoff,
            "max_input_token": self.max_input_token,
        }
        return result


InteractionChannel = Union[
    VoiceChannel,
    StageChannel,
    TextChannel,
    ForumChannel,
    CategoryChannel,
    Thread,
    DMChannel,
    GroupChannel,
]
PartialMessageableChannel = Union[
    TextChannel, VoiceChannel, StageChannel, Thread, DMChannel, PartialMessageable
]
MessageableChannel = Union[PartialMessageableChannel, GroupChannel]
