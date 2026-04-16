"""Meeting management — CRUD operations via Zoom API.

Covers:
- Create / update / delete meetings
- List meetings
- Get meeting details
- Meeting settings (recording, waiting room, etc.)
"""

from typing import Any
from cli_anything.zoom.utils.zoom_backend import api_get, api_post, api_patch, api_delete


def create_meeting(
    topic: str,
    start_time: str | None = None,
    duration: int = 60,
    timezone: str = "UTC",
    meeting_type: int = 2,
    agenda: str = "",
    password: str | None = None,
    auto_recording: str = "none",
    waiting_room: bool = False,
    join_before_host: bool = False,
    mute_upon_entry: bool = True,
) -> dict:
    """Create a new Zoom meeting.

    Args:
        topic: Meeting subject/title.
        start_time: ISO 8601 datetime (e.g., '2025-01-15T10:00:00Z').
                    None for instant meeting.
        duration: Meeting duration in minutes.
        timezone: Timezone string (e.g., 'Asia/Shanghai', 'America/New_York').
        meeting_type: 1=instant, 2=scheduled, 3=recurring no fixed time,
                      8=recurring fixed time.
        agenda: Meeting description.
        password: Meeting password (auto-generated if None).
        auto_recording: 'none', 'local', or 'cloud'.
        waiting_room: Enable waiting room.
        join_before_host: Allow participants to join before host.
        mute_upon_entry: Mute participants on entry.

    Returns:
        Meeting details dict from Zoom API.
    """
    body: dict[str, Any] = {
        "topic": topic,
        "type": meeting_type,
        "duration": duration,
        "timezone": timezone,
        "settings": {
            "auto_recording": auto_recording,
            "waiting_room": waiting_room,
            "join_before_host": join_before_host,
            "mute_upon_entry": mute_upon_entry,
        },
    }

    if start_time:
        body["start_time"] = start_time

    if agenda:
        body["agenda"] = agenda

    if password:
        body["password"] = password

    result = api_post("/users/me/meetings", body)

    return _format_meeting(result)


def list_meetings(
    status: str = "upcoming",
    page_size: int = 30,
    page_number: int = 1,
) -> dict:
    """List meetings for the authenticated user.

    Args:
        status: 'upcoming', 'scheduled', 'live', or 'pending'.
        page_size: Number of results per page (max 300).
        page_number: Page number to return.

    Returns:
        Dict with meetings list and pagination info.
    """
    params = {
        "type": status,
        "page_size": min(page_size, 300),
        "page_number": page_number,
    }

    result = api_get("/users/me/meetings", params=params)

    meetings = [_format_meeting_summary(m) for m in result.get("meetings", [])]

    return {
        "total_records": result.get("total_records", 0),
        "page_count": result.get("page_count", 0),
        "page_number": result.get("page_number", 1),
        "page_size": result.get("page_size", page_size),
        "meetings": meetings,
    }


def get_meeting(meeting_id: int | str) -> dict:
    """Get detailed information about a specific meeting.

    Args:
        meeting_id: The Zoom meeting ID.

    Returns:
        Meeting details dict.
    """
    result = api_get(f"/meetings/{meeting_id}")
    return _format_meeting(result)


def update_meeting(
    meeting_id: int | str,
    topic: str | None = None,
    start_time: str | None = None,
    duration: int | None = None,
    timezone: str | None = None,
    agenda: str | None = None,
    password: str | None = None,
    auto_recording: str | None = None,
    waiting_room: bool | None = None,
    join_before_host: bool | None = None,
    mute_upon_entry: bool | None = None,
) -> dict:
    """Update an existing meeting.

    Only provided fields are updated; None fields are left unchanged.

    Returns:
        Dict confirming the update.
    """
    body: dict[str, Any] = {}
    settings: dict[str, Any] = {}

    if topic is not None:
        body["topic"] = topic
    if start_time is not None:
        body["start_time"] = start_time
    if duration is not None:
        body["duration"] = duration
    if timezone is not None:
        body["timezone"] = timezone
    if agenda is not None:
        body["agenda"] = agenda
    if password is not None:
        body["password"] = password

    if auto_recording is not None:
        settings["auto_recording"] = auto_recording
    if waiting_room is not None:
        settings["waiting_room"] = waiting_room
    if join_before_host is not None:
        settings["join_before_host"] = join_before_host
    if mute_upon_entry is not None:
        settings["mute_upon_entry"] = mute_upon_entry

    if settings:
        body["settings"] = settings

    if not body:
        raise ValueError("No fields provided for update.")

    api_patch(f"/meetings/{meeting_id}", body)

    return {"status": "updated", "meeting_id": str(meeting_id)}


def delete_meeting(meeting_id: int | str) -> dict:
    """Delete a scheduled meeting.

    Args:
        meeting_id: The Zoom meeting ID.

    Returns:
        Dict confirming deletion.
    """
    api_delete(f"/meetings/{meeting_id}")
    return {"status": "deleted", "meeting_id": str(meeting_id)}


def get_join_url(meeting_id: int | str) -> dict:
    """Get the join URL for a meeting.

    Returns:
        Dict with join_url and start_url.
    """
    result = api_get(f"/meetings/{meeting_id}")
    return {
        "meeting_id": result.get("id"),
        "topic": result.get("topic", ""),
        "join_url": result.get("join_url", ""),
        "start_url": result.get("start_url", ""),
        "password": result.get("password", ""),
    }


def _format_meeting(data: dict) -> dict:
    """Format a full meeting response."""
    return {
        "id": data.get("id"),
        "uuid": data.get("uuid", ""),
        "topic": data.get("topic", ""),
        "type": data.get("type"),
        "status": data.get("status", ""),
        "start_time": data.get("start_time", ""),
        "duration": data.get("duration", 0),
        "timezone": data.get("timezone", ""),
        "agenda": data.get("agenda", ""),
        "join_url": data.get("join_url", ""),
        "start_url": data.get("start_url", ""),
        "password": data.get("password", ""),
        "settings": {
            "auto_recording": data.get("settings", {}).get("auto_recording", "none"),
            "waiting_room": data.get("settings", {}).get("waiting_room", False),
            "join_before_host": data.get("settings", {}).get("join_before_host", False),
            "mute_upon_entry": data.get("settings", {}).get("mute_upon_entry", True),
        },
        "created_at": data.get("created_at", ""),
    }


def _format_meeting_summary(data: dict) -> dict:
    """Format a meeting list item."""
    return {
        "id": data.get("id"),
        "topic": data.get("topic", ""),
        "type": data.get("type"),
        "start_time": data.get("start_time", ""),
        "duration": data.get("duration", 0),
        "timezone": data.get("timezone", ""),
        "join_url": data.get("join_url", ""),
        "created_at": data.get("created_at", ""),
    }
