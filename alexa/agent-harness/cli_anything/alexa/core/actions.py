"""Action planning: validate user input and build backend action dicts.

Each CLI command builds an *action* here (a plain dict) and hands it to the
backend for execution. Keeping validation and planning pure makes every
command testable without Amazon, and powers ``--dry-run``.
"""

from __future__ import annotations

from typing import Any

# Built-in Alexa sequences exposed as `alexa sequence <name>`.
SEQUENCES = {
    "weather": "Alexa.Weather.Play",
    "traffic": "Alexa.Traffic.Play",
    "flash-briefing": "Alexa.FlashBriefing.Play",
    "good-morning": "Alexa.GoodMorning.Play",
    "good-night": "Alexa.GoodNight.Play",
    "sing": "Alexa.SingASong.Play",
    "story": "Alexa.TellStory.Play",
    "fun-fact": "Alexa.FunFact.Play",
    "joke": "Alexa.Joke.Play",
    "clean-up": "Alexa.CleanUp.Play",
    "calendar-today": "Alexa.Calendar.PlayToday",
    "calendar-tomorrow": "Alexa.Calendar.PlayTomorrow",
    "calendar-next": "Alexa.Calendar.PlayNext",
}

# Music provider ids accepted by Amazon's Alexa.Music.PlaySearchPhrase.
MUSIC_PROVIDERS = {
    "amazon": "AMAZON_MUSIC",
    "spotify": "SPOTIFY",
    "apple": "APPLE_MUSIC",
    "tunein": "TUNEIN",
    "iheart": "I_HEART_RADIO",
    "pandora": "PANDORA",
    "deezer": "DEEZER",
    "cloudplayer": "CLOUDPLAYER",
}

MEDIA_OPS = ("play", "pause", "next", "previous", "stop")
MAX_TEXT = 1000  # Amazon rejects very long TTS payloads


class ActionError(ValueError):
    """Invalid user input for an action."""


def _text(value: str, what: str = "text") -> str:
    value = (value or "").strip()
    if not value:
        raise ActionError(f"{what} must not be empty.")
    if len(value) > MAX_TEXT:
        raise ActionError(f"{what} is {len(value)} characters; the limit is {MAX_TEXT}.")
    return value


def speak(device: dict[str, Any], text: str) -> dict[str, Any]:
    return {"op": "speak", "device": device, "text": _text(text)}


def announce(devices: list[dict[str, Any]], text: str, title: str = "Announcement") -> dict[str, Any]:
    if not devices:
        raise ActionError("announce needs at least one target device.")
    return {"op": "announce", "devices": devices, "text": _text(text), "title": title or "Announcement"}


def command(device: dict[str, Any], text: str) -> dict[str, Any]:
    """Run text as if it were spoken to the device ("turn off the lights")."""
    return {"op": "command", "device": device, "text": _text(text, "command")}


def routine(device: dict[str, Any], utterance: str) -> dict[str, Any]:
    return {"op": "routine", "device": device, "utterance": _text(utterance, "routine utterance")}


def sequence(device: dict[str, Any], name: str) -> dict[str, Any]:
    key = (name or "").strip().lower()
    if key not in SEQUENCES:
        raise ActionError(f"Unknown sequence '{name}'. Choose from: {', '.join(sorted(SEQUENCES))}")
    return {"op": "sequence", "device": device, "sequence": SEQUENCES[key], "name": key}


def music(device: dict[str, Any], query: str, provider: str = "amazon", timer: int | None = None) -> dict[str, Any]:
    key = (provider or "amazon").strip().lower()
    if key not in MUSIC_PROVIDERS:
        raise ActionError(f"Unknown provider '{provider}'. Choose from: {', '.join(sorted(MUSIC_PROVIDERS))}")
    if timer is not None and timer <= 0:
        raise ActionError("--timer must be a positive number of seconds.")
    return {
        "op": "music",
        "device": device,
        "query": _text(query, "search phrase"),
        "provider": MUSIC_PROVIDERS[key],
        "timer": timer,
    }


def media(device: dict[str, Any], op: str) -> dict[str, Any]:
    if op not in MEDIA_OPS:
        raise ActionError(f"Unknown media operation '{op}'. Choose from: {', '.join(MEDIA_OPS)}")
    return {"op": "media", "device": device, "media_op": op}


def volume(device: dict[str, Any], level: int) -> dict[str, Any]:
    if not isinstance(level, int) or not 0 <= level <= 100:
        raise ActionError("Volume must be an integer from 0 to 100.")
    return {"op": "volume", "device": device, "level": level}


def light(entity_id: str, on: bool, brightness: int | None = None, color: str | None = None) -> dict[str, Any]:
    if not (entity_id or "").strip():
        raise ActionError("Light entity id must not be empty (see `smarthome list`).")
    if brightness is not None and not 0 <= brightness <= 100:
        raise ActionError("Brightness must be from 0 to 100.")
    return {"op": "light", "entity_id": entity_id.strip(), "on": on, "brightness": brightness, "color": color}


def describe(action: dict[str, Any]) -> dict[str, Any]:
    """JSON-safe summary of an action (device dicts reduced to name+serial)."""
    out = {}
    for k, v in action.items():
        if k == "device":
            out["device"] = {"name": v.get("name"), "serial": v.get("serial")}
        elif k == "devices":
            out["devices"] = [{"name": d.get("name"), "serial": d.get("serial")} for d in v]
        else:
            out[k] = v
    return out
