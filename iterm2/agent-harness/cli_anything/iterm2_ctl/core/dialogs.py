"""Dialog and panel operations for iTerm2.

Covers modal alerts, text-input dialogs, and file open/save panels.
All functions are async coroutines.
"""
from typing import Any, Dict, List, Optional


async def show_alert(
    connection,
    title: str,
    subtitle: str,
    buttons: Optional[List[str]] = None,
    window_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Show a modal alert dialog with optional buttons.

    Args:
        title: Bold title text shown at the top.
        subtitle: Informative text body (may be multi-line).
        buttons: List of button labels. Defaults to ["OK"] if empty.
        window_id: Attach to a window (None = application-modal).

    Returns:
        Dict with 'button_index' (1000-based) and 'button_label'.
    """
    import iterm2
    alert = iterm2.Alert(title, subtitle, window_id=window_id)
    if buttons:
        for b in buttons:
            alert.add_button(b)
    index = await alert.async_run(connection)
    # button_index is 1000-based; map back to 0-based label
    label = None
    if buttons:
        zero_based = index - 1000
        label = buttons[zero_based] if 0 <= zero_based < len(buttons) else None
    else:
        label = "OK"
    return {
        "button_index": index,
        "button_label": label,
    }


async def show_text_input(
    connection,
    title: str,
    subtitle: str,
    placeholder: str = "",
    default_value: str = "",
    window_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Show a modal alert with a text input field.

    Args:
        title: Bold title text.
        subtitle: Informative text body.
        placeholder: Gray placeholder text in the input field.
        default_value: Pre-filled text value.
        window_id: Attach to a window (None = application-modal).

    Returns:
        Dict with 'text' (the entered string) or 'cancelled' (bool).
    """
    import iterm2
    alert = iterm2.TextInputAlert(
        title,
        subtitle,
        placeholder,
        default_value,
        window_id=window_id,
    )
    result = await alert.async_run(connection)
    if result is None:
        return {"cancelled": True, "text": None}
    return {"cancelled": False, "text": result}


async def show_open_panel(
    connection,
    title: str = "Open",
    path: Optional[str] = None,
    extensions: Optional[List[str]] = None,
    can_choose_directories: bool = False,
    allows_multiple: bool = False,
) -> Dict[str, Any]:
    """Show a macOS Open File panel and return the chosen path(s).

    Args:
        title: Panel message text (shown as title).
        path: Initial directory to open.
        extensions: List of allowed file extensions, e.g. ["py", "txt"].
        can_choose_directories: Allow selecting directories.
        allows_multiple: Allow selecting multiple files.

    Returns:
        Dict with 'files' list of chosen paths, or 'cancelled' if dismissed.
    """
    import iterm2
    panel = iterm2.OpenPanel()
    if path:
        panel.path = path
    if extensions:
        panel.extensions = extensions
    if title:
        panel.message = title

    options = [iterm2.OpenPanel.Options.CAN_CHOOSE_FILES]
    if can_choose_directories:
        options.append(iterm2.OpenPanel.Options.CAN_CHOOSE_DIRECTORIES)
    if allows_multiple:
        options.append(iterm2.OpenPanel.Options.ALLOWS_MULTIPLE_SELECTION)
    panel.options = options

    result = await panel.async_run(connection)
    if result is None:
        return {"cancelled": True, "files": []}
    return {"cancelled": False, "files": result.files}


async def show_save_panel(
    connection,
    title: str = "Save",
    path: Optional[str] = None,
    filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Show a macOS Save File panel and return the chosen save path.

    Args:
        title: Panel message text.
        path: Initial directory.
        filename: Pre-filled filename.

    Returns:
        Dict with 'file' (chosen path) or 'cancelled' (bool).
    """
    import iterm2
    panel = iterm2.SavePanel()
    if path:
        panel.path = path
    if filename:
        panel.filename = filename
    if title:
        panel.message = title

    result = await panel.async_run(connection)
    if result is None:
        return {"cancelled": True, "file": None}
    return {"cancelled": False, "file": result.filename}
