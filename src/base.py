from dataclasses import dataclass
from typing import Optional, Union

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

    def render(self):  # noqa
        result = {
            "name": self.name,
            "icon": self.icon,
            "system": self.system,
            "color": self.color,
            "title": self.title,
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
