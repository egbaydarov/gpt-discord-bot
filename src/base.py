from dataclasses import dataclass
from typing import Optional


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
