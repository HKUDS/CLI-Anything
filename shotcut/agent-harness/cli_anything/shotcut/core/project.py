"""Project management operations."""

from typing import Optional

from ..utils import mlt_xml
from .session import Session


# Standard video profiles
PROFILES = {
    "hd1080p30": {
        "width": "1920", "height": "1080",
        "frame_rate_num": "30000", "frame_rate_den": "1001",
        "sample_aspect_num": "1", "sample_aspect_den": "1",
        "display_aspect_num": "16", "display_aspect_den": "9",
        "progressive": "1", "colorspace": "709",
    },
    "hd1080p60": {
        "width": "1920", "height": "1080",
        "frame_rate_num": "60000", "frame_rate_den": "1001",
        "sample_aspect_num": "1", "sample_aspect_den": "1",
        "display_aspect_num": "16", "display_aspect_den": "9",
        "progressive": "1", "colorspace": "709",
    },
    "hd1080p24": {
        "width": "1920", "height": "1080",
        "frame_rate_num": "24000", "frame_rate_den": "1001",
        "sample_aspect_num": "1", "sample_aspect_den": "1",
        "display_aspect_num": "16", "display_aspect_den": "9",
        "progressive": "1", "colorspace": "709",
    },
    "hd720p30": {
        "width": "1280", "height": "720",
        "frame_rate_num": "30000", "frame_rate_den": "1001",
        "sample_aspect_num": "1", "sample_aspect_den": "1",
        "display_aspect_num": "16", "display_aspect_den": "9",
        "progressive": "1", "colorspace": "709",
    },
    "4k30": {
        "width": "3840", "height": "2160",
        "frame_rate_num": "30000", "frame_rate_den": "1001",
        "sample_aspect_num": "1", "sample_aspect_den": "1",
        "display_aspect_num": "16", "display_aspect_den": "9",
        "progressive": "1", "colorspace": "709",
    },
    "4k60": {
        "width": "3840", "height": "2160",
        "frame_rate_num": "60000", "frame_rate_den": "1001",
        "sample_aspect_num": "1", "sample_aspect_den": "1",
        "display_aspect_num": "16", "display_aspect_den": "9",
        "progressive": "1", "colorspace": "709",
    },
    "sd480p": {
        "width": "720", "height": "480",
        "frame_rate_num": "30000", "frame_rate_den": "1001",
        "sample_aspect_num": "10", "sample_aspect_den": "11",
        "display_aspect_num": "4", "display_aspect_den": "3",
        "progressive": "1", "colorspace": "601",
    },
}


def _get_bin_ids(root):
    main_bin = mlt_xml.find_element_by_id(root, "main_bin")
    if main_bin is None:
        return set()
    return {entry.get("producer", "") for entry in main_bin.findall("entry")}


def _get_media_producers(root):
    bin_ids = _get_bin_ids(root)
    return [
        p for p in mlt_xml.get_all_producers(root)
        if mlt_xml.get_property(p, "mlt_service") not in ("color", "colour")
        and mlt_xml.get_property(p, "resource") not in ("0", "")
        and not (p.tag == "chain" and p.get("id", "") not in bin_ids)
    ]


def new_project(session: Session, profile_name: str = "hd1080p30") -> dict:
    """Create a new blank project.

    Args:
        session: The active session
        profile_name: Name of the video profile (see PROFILES)

    Returns:
        Dict with project info
    """
    if profile_name not in PROFILES:
        available = ", ".join(sorted(PROFILES.keys()))
        raise ValueError(f"Unknown profile: {profile_name!r}. Available: {available}")

    profile = PROFILES[profile_name]
    session.new_project(profile)

    return {
        "action": "new_project",
        "profile": profile_name,
        "resolution": f"{profile['width']}x{profile['height']}",
        "fps": f"{profile['frame_rate_num']}/{profile['frame_rate_den']}",
    }


def open_project(session: Session, path: str) -> dict:
    """Open an existing .mlt project file.

    Returns:
        Dict with project info
    """
    session.open_project(path)
    profile = session.get_profile()

    # Count tracks
    try:
        tractor = session.get_main_tractor()
        tracks = mlt_xml.get_tractor_tracks(tractor)
        track_count = len(tracks)
    except RuntimeError:
        track_count = 0

    return {
        "action": "open_project",
        "path": session.project_path,
        "profile": profile,
        "track_count": track_count,
        "media_clip_count": len(_get_media_producers(session.root)),
    }


def save_project(session: Session, path: Optional[str] = None) -> dict:
    """Save the current project.

    Returns:
        Dict with save info
    """
    saved_path = session.save_project(path)
    return {
        "action": "save_project",
        "path": saved_path,
    }


def project_info(session: Session) -> dict:
    """Get detailed info about the current project.

    Returns:
        Dict with comprehensive project info
    """
    if not session.is_open:
        raise RuntimeError("No project is open")

    profile = session.get_profile()
    root = session.root

    media_producers = []
    for p in _get_media_producers(root):
        media_producers.append({
            "id": p.get("id"),
            "resource": mlt_xml.get_property(p, "resource", ""),
            "caption": mlt_xml.get_property(p, "shotcut:caption", ""),
            "in": p.get("in", ""),
            "out": p.get("out", ""),
            "service": mlt_xml.get_property(p, "mlt_service") or "avformat",
        })

    # Tracks
    tracks_info = []
    try:
        tractor = session.get_main_tractor()
        track_elements = mlt_xml.get_tractor_tracks(tractor)
        for i, te in enumerate(track_elements):
            producer_id = te.get("producer", "")
            hide = te.get("hide", "")
            playlist = mlt_xml.find_element_by_id(root, producer_id)

            track_data = {
                "index": i,
                "playlist_id": producer_id,
                "hide": hide,
            }

            if playlist is not None:
                track_data["name"] = mlt_xml.get_property(playlist, "shotcut:name", "")
                is_video = mlt_xml.get_property(playlist, "shotcut:video")
                is_audio = mlt_xml.get_property(playlist, "shotcut:audio")
                if is_video:
                    track_data["type"] = "video"
                elif is_audio or hide == "video":
                    track_data["type"] = "audio"
                elif producer_id == "background":
                    track_data["type"] = "background"
                else:
                    track_data["type"] = "video"

                entries = mlt_xml.get_playlist_entries(playlist)
                from .timeline import real_clip_entries
                track_data["clip_count"] = len(real_clip_entries(entries, root))
                track_data["blank_count"] = sum(1 for e in entries if e["type"] == "blank")
            else:
                track_data["type"] = "unknown"
                track_data["clip_count"] = 0

            tracks_info.append(track_data)
    except RuntimeError:
        pass

    # Filters on main tractor
    filters_info = []
    try:
        tractor = session.get_main_tractor()
        for f in tractor.findall("filter"):
            filters_info.append({
                "id": f.get("id"),
                "service": mlt_xml.get_property(f, "mlt_service", ""),
            })
    except RuntimeError:
        pass

    return {
        "project_path": session.project_path,
        "modified": session.is_modified,
        "profile": profile,
        "media_clips": media_producers,
        "tracks": tracks_info,
        "global_filters": filters_info,
    }


def list_profiles() -> dict:
    """List all available video profiles."""
    result = {}
    for name, prof in sorted(PROFILES.items()):
        fps_num = int(prof["frame_rate_num"])
        fps_den = int(prof["frame_rate_den"])
        fps = round(fps_num / fps_den, 2)
        result[name] = {
            "resolution": f"{prof['width']}x{prof['height']}",
            "fps": fps,
            "colorspace": prof.get("colorspace", "709"),
        }
    return result
