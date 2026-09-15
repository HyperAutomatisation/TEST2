"""LogChannel v1 : toute alerte passe par send(), jamais un réseau en dur."""

from __future__ import annotations

from typing import Protocol

from corridor.db import connect


class Channel(Protocol):
    name: str

    def send(self, recipient: str | None, subject: str, text: str) -> None:
        ...


class LogChannel:
    name = "log"

    def send(self, recipient: str | None, subject: str, text: str) -> None:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO notification_log (channel, recipient, subject, text, status)
                VALUES (%s, %s, %s, %s, 'logged')
                """,
                (self.name, recipient, subject, text),
            )
            conn.commit()


_CHANNELS: dict[str, Channel] = {"log": LogChannel()}


def send(channel: str, recipient: str | None, subject: str, text: str) -> None:
    impl = _CHANNELS.get(channel)
    if impl is None:
        impl = _CHANNELS["log"]
    impl.send(recipient, subject, text)
