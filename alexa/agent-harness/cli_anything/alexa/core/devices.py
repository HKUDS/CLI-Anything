"""Device normalization and name resolution.

Amazon returns raw device records (``accountName``, ``serialNumber`` ...).
This module turns them into a small stable shape for agents and resolves a
user-supplied name ("kitchen", "Living Room Echo", a serial) to one device.
Pure functions only: no network access.
"""

from __future__ import annotations

from typing import Any

# Device families that are real speakers able to run TTS / announcements /
# custom commands. Everything else (apps, phones, smart plugs exposed as
# "devices", speaker groups' virtual entries) is hidden unless --all is used.
SPEAKER_FAMILIES = {"ECHO", "KNIGHT", "ROOK", "TABLET", "WHA", "FIRE_TV", "THIRD_PARTY_AVS_SONOS_BOOTLEG"}
SPEAKER_CAPABILITIES = {"VOLUME_SETTING", "MICROPHONE", "AUDIO_PLAYER"}


class DeviceNotFound(LookupError):
    """No device matched the requested name."""


class AmbiguousDevice(LookupError):
    """More than one device matched the requested name."""


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Reduce an Amazon device record to the fields agents need."""
    caps = list(raw.get("capabilities") or [])
    family = raw.get("deviceFamily") or ""
    return {
        "name": raw.get("accountName") or raw.get("serialNumber") or "",
        "serial": raw.get("serialNumber") or "",
        "type": raw.get("deviceType") or "",
        "family": family,
        "online": bool(raw.get("online")),
        "owner_customer_id": raw.get("deviceOwnerCustomerId") or "",
        "software_version": raw.get("softwareVersion") or "",
        "cluster_members": list(raw.get("clusterMembers") or []),
        "is_speaker": is_speaker(family, caps),
        "capabilities": caps,
    }


def is_speaker(family: str, capabilities: list[str]) -> bool:
    """True if the device can speak (TTS, announcements, commands)."""
    if family in SPEAKER_FAMILIES:
        return True
    return bool(SPEAKER_CAPABILITIES.intersection(capabilities or []))


def filter_devices(devices: list[dict[str, Any]], include_all: bool = False) -> list[dict[str, Any]]:
    """Keep only speakers unless ``include_all`` is set; sort by name."""
    out = devices if include_all else [d for d in devices if d.get("is_speaker")]
    return sorted(out, key=lambda d: d.get("name", "").lower())


def resolve(devices: list[dict[str, Any]], query: str) -> dict[str, Any]:
    """Find exactly one device by serial, exact name, or unique substring.

    Matching is case-insensitive. Raises DeviceNotFound / AmbiguousDevice with
    the candidate names so an agent can retry with a precise name.
    """
    q = (query or "").strip().lower()
    if not q:
        raise DeviceNotFound("Device name is empty.")
    for d in devices:
        if d.get("serial", "").lower() == q:
            return d
    exact = [d for d in devices if d.get("name", "").lower() == q]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise AmbiguousDevice(_ambiguous_msg(query, exact))
    partial = [d for d in devices if q in d.get("name", "").lower()]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        raise AmbiguousDevice(_ambiguous_msg(query, partial))
    names = ", ".join(sorted(d.get("name", "") for d in devices)) or "(none)"
    raise DeviceNotFound(f"No device matches '{query}'. Known devices: {names}")


def _ambiguous_msg(query: str, matches: list[dict[str, Any]]) -> str:
    names = ", ".join(f"{d['name']} ({d['serial']})" for d in matches)
    return f"'{query}' matches several devices: {names}. Use the full name or serial."
