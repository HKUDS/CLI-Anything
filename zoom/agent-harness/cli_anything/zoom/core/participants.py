"""Participant management — add, remove, list registrants for meetings.

Zoom distinguishes between:
- Registrants: people who registered before the meeting
- Participants: people who actually attended (available after meeting ends)

This module handles both.
"""

from cli_anything.zoom.utils.zoom_backend import api_get, api_post, api_patch


def add_registrant(
    meeting_id: int | str,
    email: str,
    first_name: str = "",
    last_name: str = "",
) -> dict:
    """Register a participant for a meeting.

    The meeting must have registration enabled (type 2 with registration).

    Args:
        meeting_id: Zoom meeting ID.
        email: Registrant email address.
        first_name: First name.
        last_name: Last name.

    Returns:
        Registration result with registrant_id and join_url.
    """
    body = {"email": email}
    if first_name:
        body["first_name"] = first_name
    if last_name:
        body["last_name"] = last_name

    result = api_post(f"/meetings/{meeting_id}/registrants", body)

    return {
        "registrant_id": result.get("registrant_id", ""),
        "id": result.get("id", ""),
        "topic": result.get("topic", ""),
        "email": email,
        "join_url": result.get("join_url", ""),
        "start_time": result.get("start_time", ""),
    }


def add_batch_registrants(
    meeting_id: int | str,
    registrants: list[dict],
) -> dict:
    """Register multiple participants at once.

    Args:
        meeting_id: Zoom meeting ID.
        registrants: List of dicts with 'email', optional 'first_name', 'last_name'.

    Returns:
        Summary of batch registration results.
    """
    results = []
    errors = []

    for reg in registrants:
        email = reg.get("email", "")
        if not email:
            errors.append({"error": "Missing email", "input": reg})
            continue
        try:
            result = add_registrant(
                meeting_id,
                email=email,
                first_name=reg.get("first_name", ""),
                last_name=reg.get("last_name", ""),
            )
            results.append(result)
        except Exception as e:
            errors.append({"email": email, "error": str(e)})

    return {
        "meeting_id": str(meeting_id),
        "registered": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }


def list_registrants(
    meeting_id: int | str,
    status: str = "approved",
    page_size: int = 30,
) -> dict:
    """List registrants for a meeting.

    Args:
        meeting_id: Zoom meeting ID.
        status: 'approved', 'pending', or 'denied'.
        page_size: Results per page (max 300).

    Returns:
        Dict with registrants list.
    """
    params = {
        "status": status,
        "page_size": min(page_size, 300),
    }
    result = api_get(f"/meetings/{meeting_id}/registrants", params=params)

    registrants = []
    for r in result.get("registrants", []):
        registrants.append({
            "id": r.get("id", ""),
            "email": r.get("email", ""),
            "first_name": r.get("first_name", ""),
            "last_name": r.get("last_name", ""),
            "status": r.get("status", ""),
            "create_time": r.get("create_time", ""),
        })

    return {
        "meeting_id": str(meeting_id),
        "total_records": result.get("total_records", 0),
        "registrants": registrants,
    }


def remove_registrant(
    meeting_id: int | str,
    registrant_id: str,
) -> dict:
    """Cancel a registrant's registration.

    Args:
        meeting_id: Zoom meeting ID.
        registrant_id: The registrant ID to cancel.

    Returns:
        Confirmation dict.
    """
    body = {
        "action": "cancel",
        "registrants": [{"id": registrant_id}],
    }
    api_patch(f"/meetings/{meeting_id}/registrants/status", body)
    return {
        "status": "cancelled",
        "meeting_id": str(meeting_id),
        "registrant_id": registrant_id,
    }


def list_past_participants(
    meeting_id: str,
    page_size: int = 30,
) -> dict:
    """List participants who actually attended a past meeting.

    Note: meeting_id must be the meeting UUID for past meetings.
    The meeting must have ended.

    Args:
        meeting_id: Meeting UUID (double-encoded if starts with / or //).
        page_size: Results per page.

    Returns:
        Dict with participants list.
    """
    # Double-encode UUID if it starts with / or //
    if meeting_id.startswith("/"):
        from urllib.parse import quote
        meeting_id = quote(quote(meeting_id, safe=""), safe="")

    params = {"page_size": min(page_size, 300)}
    result = api_get(
        f"/past_meetings/{meeting_id}/participants",
        params=params,
    )

    participants = []
    for p in result.get("participants", []):
        participants.append({
            "id": p.get("id", ""),
            "name": p.get("name", ""),
            "email": p.get("user_email", ""),
            "join_time": p.get("join_time", ""),
            "leave_time": p.get("leave_time", ""),
            "duration": p.get("duration", 0),
        })

    return {
        "meeting_id": meeting_id,
        "total_records": result.get("total_records", 0),
        "participants": participants,
    }
