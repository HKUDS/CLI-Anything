"""Recording management — list, download, and delete cloud recordings.

Handles:
- List recordings for a date range
- Get recording files for a specific meeting
- Download recording files
- Delete recordings
"""

import os
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from cli_anything.zoom.utils.zoom_backend import api_get, api_delete, api_request


def _strip_token_from_url(url: str) -> str:
    """Remove access_token query parameter from a URL to prevent token leakage."""
    if not url:
        return url
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params.pop("access_token", None)
    clean_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=clean_query))


def list_recordings(
    from_date: str = "",
    to_date: str = "",
    page_size: int = 30,
) -> dict:
    """List cloud recordings for the authenticated user.

    Args:
        from_date: Start date (YYYY-MM-DD). Defaults to 30 days ago.
        to_date: End date (YYYY-MM-DD). Defaults to today.
        page_size: Results per page (max 300).

    Returns:
        Dict with recording list.
    """
    params = {"page_size": min(page_size, 300)}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    result = api_get("/users/me/recordings", params=params)

    meetings = []
    for m in result.get("meetings", []):
        files = []
        for f in m.get("recording_files", []):
            files.append({
                "id": f.get("id", ""),
                "file_type": f.get("file_type", ""),
                "file_extension": f.get("file_extension", ""),
                "file_size": f.get("file_size", 0),
                "status": f.get("status", ""),
                "recording_start": f.get("recording_start", ""),
                "recording_end": f.get("recording_end", ""),
                "download_url": _strip_token_from_url(f.get("download_url", "")),
            })
        meetings.append({
            "meeting_id": m.get("id"),
            "uuid": m.get("uuid", ""),
            "topic": m.get("topic", ""),
            "start_time": m.get("start_time", ""),
            "duration": m.get("duration", 0),
            "total_size": m.get("total_size", 0),
            "recording_count": m.get("recording_count", 0),
            "recording_files": files,
        })

    return {
        "total_records": result.get("total_records", 0),
        "meetings": meetings,
    }


def get_meeting_recordings(meeting_id: int | str) -> dict:
    """Get recording files for a specific meeting.

    Args:
        meeting_id: Zoom meeting ID or UUID.

    Returns:
        Dict with recording files.
    """
    # Double-encode UUID if needed
    mid = str(meeting_id)
    if mid.startswith("/"):
        from urllib.parse import quote
        mid = quote(quote(mid, safe=""), safe="")

    result = api_get(f"/meetings/{mid}/recordings")

    files = []
    for f in result.get("recording_files", []):
        files.append({
            "id": f.get("id", ""),
            "file_type": f.get("file_type", ""),
            "file_extension": f.get("file_extension", ""),
            "file_size": f.get("file_size", 0),
            "status": f.get("status", ""),
            "download_url": _strip_token_from_url(f.get("download_url", "")),
            "play_url": _strip_token_from_url(f.get("play_url", "")),
            "recording_start": f.get("recording_start", ""),
            "recording_end": f.get("recording_end", ""),
        })

    return {
        "meeting_id": result.get("id"),
        "uuid": result.get("uuid", ""),
        "topic": result.get("topic", ""),
        "start_time": result.get("start_time", ""),
        "duration": result.get("duration", 0),
        "total_size": result.get("total_size", 0),
        "recording_files": files,
    }


def download_recording(
    download_url: str,
    output_path: str,
    overwrite: bool = False,
) -> dict:
    """Download a recording file.

    Args:
        download_url: The download URL from the recording file info.
        output_path: Local path to save the file.
        overwrite: Whether to overwrite existing files.

    Returns:
        Dict with download result.
    """
    out = Path(output_path)
    if out.exists() and not overwrite:
        raise FileExistsError(f"File already exists: {output_path}")

    out.parent.mkdir(parents=True, exist_ok=True)

    # For recording downloads, we need to use the direct URL with Bearer token
    import requests
    from cli_anything.zoom.utils.zoom_backend import _get_valid_token

    token = _get_valid_token()
    resp = requests.get(
        download_url,
        headers={"Authorization": f"Bearer {token}"},
        stream=True,
        timeout=300,
    )
    resp.raise_for_status()

    total_size = int(resp.headers.get("content-length", 0))
    downloaded = 0

    with open(out, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)

    actual_size = out.stat().st_size

    return {
        "status": "downloaded",
        "path": str(out.resolve()),
        "size_bytes": actual_size,
        "size_mb": round(actual_size / (1024 * 1024), 2),
    }


def delete_recording(meeting_id: int | str) -> dict:
    """Delete all recordings for a meeting.

    Args:
        meeting_id: Zoom meeting ID or UUID.

    Returns:
        Confirmation dict.
    """
    mid = str(meeting_id)
    if mid.startswith("/"):
        from urllib.parse import quote
        mid = quote(quote(mid, safe=""), safe="")

    api_delete(f"/meetings/{mid}/recordings")
    return {"status": "deleted", "meeting_id": str(meeting_id)}


def delete_recording_file(
    meeting_id: int | str,
    recording_id: str,
) -> dict:
    """Delete a specific recording file.

    Args:
        meeting_id: Zoom meeting ID or UUID.
        recording_id: The recording file ID.

    Returns:
        Confirmation dict.
    """
    mid = str(meeting_id)
    if mid.startswith("/"):
        from urllib.parse import quote
        mid = quote(quote(mid, safe=""), safe="")

    api_delete(f"/meetings/{mid}/recordings/{recording_id}")
    return {
        "status": "deleted",
        "meeting_id": str(meeting_id),
        "recording_id": recording_id,
    }
