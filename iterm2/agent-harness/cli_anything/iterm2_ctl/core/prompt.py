"""Shell prompt and command detection for iTerm2.

Requires Shell Integration to be installed in the target session.
Install with:
    curl -L https://iterm2.com/shell_integration/install_shell_integration.sh | bash

All functions are async coroutines intended to be called via
cli_anything.iterm2_ctl.utils.iterm2_backend.run_iterm2().
"""
import asyncio
from typing import Dict, List


def _prompt_to_dict(prompt) -> Dict:
    """Convert an iterm2.Prompt object to a plain dict.

    Returns a dict with all available prompt fields. If the prompt is None
    (Shell Integration not installed or no prompt yet), returns a dict with
    'available': False.
    """
    if prompt is None:
        return {"available": False}

    import iterm2

    return {
        "available": True,
        "unique_id": prompt.unique_id,
        "command": prompt.command,
        "working_directory": prompt.working_directory,
        "state": prompt.state.name if prompt.state is not None else None,
        "has_prompt_range": prompt.prompt_range is not None,
        "has_command_range": prompt.command_range is not None,
        "has_output_range": prompt.output_range is not None,
    }


async def get_last_prompt(connection, session_id: str) -> Dict:
    """Get info about the last shell prompt in a session.

    Requires Shell Integration. Returns a dict with command, working_directory,
    state (PromptState name), and range availability flags. If Shell Integration
    is not installed or no prompt has been recorded yet, returns a dict with
    'available': False.

    Args:
        session_id: The iTerm2 session ID to query.

    Returns:
        Dict with prompt info, or {'available': False} if not available.
    """
    import iterm2
    prompt = await iterm2.async_get_last_prompt(connection, session_id)
    return _prompt_to_dict(prompt)


async def list_prompts(connection, session_id: str) -> Dict:
    """List all recorded prompt IDs in a session.

    Requires Shell Integration. Each ID can be used to identify individual
    command executions within the session's history.

    Args:
        session_id: The iTerm2 session ID to query.

    Returns:
        Dict with 'session_id' and 'prompt_ids' (list of strings).
    """
    import iterm2
    prompt_ids = await iterm2.async_list_prompts(connection, session_id)
    return {
        "session_id": session_id,
        "prompt_ids": list(prompt_ids) if prompt_ids else [],
        "count": len(prompt_ids) if prompt_ids else 0,
    }


async def wait_for_prompt(
    connection,
    session_id: str,
    timeout: float = 30.0,
) -> Dict:
    """Wait for the next shell prompt to appear in a session.

    Useful for waiting until a command finishes before sending the next one.
    Monitors for a PROMPT event, which fires when the shell displays its
    next prompt (i.e. the previous command has completed).

    Args:
        session_id: The iTerm2 session ID to monitor.
        timeout: Maximum seconds to wait. Default 30.

    Returns:
        Dict with 'timed_out' (bool), and prompt info if available.
    """
    import iterm2

    result: Dict = {"session_id": session_id, "timed_out": False}

    async def _wait(conn):
        async with iterm2.PromptMonitor(
            conn,
            session_id,
            modes=[iterm2.PromptMonitor.Mode.PROMPT],
        ) as mon:
            mode, value = await mon.async_get()
            result["mode"] = mode.name if mode is not None else None
            result["value"] = value

    try:
        await asyncio.wait_for(_wait(connection), timeout=timeout)
    except asyncio.TimeoutError:
        result["timed_out"] = True

    # Attempt to attach the latest prompt info after the event
    if not result["timed_out"]:
        import iterm2 as _iterm2
        prompt = await _iterm2.async_get_last_prompt(connection, session_id)
        result.update(_prompt_to_dict(prompt))

    return result


async def wait_for_command_end(
    connection,
    session_id: str,
    timeout: float = 30.0,
) -> Dict:
    """Wait for the current command to finish executing.

    Monitors for a COMMAND_END event. When a COMMAND_END fires, the
    associated value is the integer exit status of the completed command.

    Args:
        session_id: The iTerm2 session ID to monitor.
        timeout: Maximum seconds to wait. Default 30.

    Returns:
        Dict with 'exit_status' (int or None) and 'timed_out' (bool).
    """
    import iterm2

    result: Dict = {
        "session_id": session_id,
        "timed_out": False,
        "exit_status": None,
    }

    async def _wait(conn):
        async with iterm2.PromptMonitor(
            conn,
            session_id,
            modes=[iterm2.PromptMonitor.Mode.COMMAND_END],
        ) as mon:
            mode, value = await mon.async_get()
            result["mode"] = mode.name if mode is not None else None
            result["exit_status"] = value  # int exit code for COMMAND_END

    try:
        await asyncio.wait_for(_wait(connection), timeout=timeout)
    except asyncio.TimeoutError:
        result["timed_out"] = True

    return result


async def watch_prompt(
    connection,
    session_id: str,
    count: int = 1,
) -> Dict:
    """Watch for N prompt events and return them.

    Collects up to `count` events of any prompt type (PROMPT, COMMAND_START,
    COMMAND_END) and returns them. Useful for monitoring a full command
    lifecycle: COMMAND_START fires when the user hits Enter, COMMAND_END fires
    when the command exits, and PROMPT fires when the shell re-displays its
    prompt.

    Args:
        session_id: The iTerm2 session ID to monitor.
        count: Number of events to collect before returning. Default 1.

    Returns:
        Dict with 'events': list of dicts, each containing 'mode' and 'value'.
    """
    import iterm2

    events: List[Dict] = []

    async with iterm2.PromptMonitor(
        connection,
        session_id,
        modes=[
            iterm2.PromptMonitor.Mode.PROMPT,
            iterm2.PromptMonitor.Mode.COMMAND_START,
            iterm2.PromptMonitor.Mode.COMMAND_END,
        ],
    ) as mon:
        for _ in range(count):
            mode, value = await mon.async_get()
            events.append({
                "mode": mode.name if mode is not None else None,
                "value": value,
            })

    return {
        "session_id": session_id,
        "events": events,
        "event_count": len(events),
    }
