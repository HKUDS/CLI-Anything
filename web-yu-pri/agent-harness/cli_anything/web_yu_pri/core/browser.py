"""Playwright backend for the real Web Yu-pri web application."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .items import ItemLine, build_contents_plan

LOGIN_URL = "https://mgr.post.japanpost.jp/C30P01Action.do"
CONTENTS_URL = "https://mgr.post.japanpost.jp/M060800.do"

SELECTORS = {
    "item_description": "#M060800_itemBean_pkg",
    "item_value": "#M060800_itemBean_cost_value",
    "item_quantity": "#M060800_itemBean_num_value",
    "item_country": "#M060800_itemBean_couCd",
    "item_hs_code": "#M060800_itemBean_hsCode",
    "package_type": "#M060800_shippingBean_pkgType",
    "total_value": "#M060800_shippingBean_pkgTotalPrice_value",
    "danger": "#M060800_ShippingBean_danger",
}

ADD_ITEM_COMMAND = "itemAdd2"


def default_profile_dir() -> Path:
    return Path.home() / ".cli-anything-web-yu-pri" / "profile"


def selector_report() -> dict[str, Any]:
    return {
        "login_url": LOGIN_URL,
        "contents_url": CONTENTS_URL,
        "selectors": SELECTORS,
        "add_item_command": ADD_ITEM_COMMAND,
    }


def doctor(profile_dir: str | Path | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "profile_dir": str(Path(profile_dir).expanduser() if profile_dir else default_profile_dir()),
        "login_url": LOGIN_URL,
        "contents_url": CONTENTS_URL,
        "playwright_available": False,
        "notes": [],
    }
    try:
        import playwright  # noqa: F401

        result["playwright_available"] = True
    except Exception as exc:  # pragma: no cover - depends on runtime environment
        result["notes"].append(f"playwright import failed: {exc}")
    return result


@contextmanager
def browser_session(
    profile_dir: str | Path | None = None,
    headless: bool = False,
    browser_channel: str | None = None,
) -> Iterator[tuple[Any, Any]]:
    """Launch a persistent browser context and yield (page, context)."""

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - dependency exercised via CLI doctor
        raise RuntimeError(
            "playwright is required. Install with: pip install cli-anything-web-yu-pri"
        ) from exc

    user_data_dir = Path(profile_dir).expanduser() if profile_dir else default_profile_dir()
    user_data_dir.mkdir(parents=True, exist_ok=True)

    playwright = sync_playwright().start()
    context = None
    errors: list[str] = []
    channels = [browser_channel] if browser_channel else ["msedge", "chrome", None]
    try:
        for channel in channels:
            try:
                kwargs: dict[str, Any] = {
                    "headless": headless,
                    "args": ["--disable-blink-features=AutomationControlled"],
                }
                if channel:
                    kwargs["channel"] = channel
                context = playwright.chromium.launch_persistent_context(
                    str(user_data_dir),
                    **kwargs,
                )
                break
            except PlaywrightError as exc:
                label = channel or "bundled-chromium"
                errors.append(f"{label}: {exc}")
        if context is None:
            detail = " | ".join(errors) if errors else "no browser channels attempted"
            raise RuntimeError(f"could not launch Chromium/Edge browser: {detail}")

        page = context.pages[0] if context.pages else context.new_page()
        yield page, context
    finally:
        if context is not None:
            context.close()
        playwright.stop()


def open_login(
    url: str = LOGIN_URL,
    profile_dir: str | Path | None = None,
    headless: bool = False,
    browser_channel: str | None = None,
) -> dict[str, Any]:
    with browser_session(profile_dir=profile_dir, headless=headless, browser_channel=browser_channel) as (
        page,
        _context,
    ):
        page.goto(url, wait_until="domcontentloaded")
        return inspect_page(page)


def inspect_url(
    url: str = LOGIN_URL,
    profile_dir: str | Path | None = None,
    headless: bool = False,
    browser_channel: str | None = None,
) -> dict[str, Any]:
    with browser_session(profile_dir=profile_dir, headless=headless, browser_channel=browser_channel) as (
        page,
        _context,
    ):
        page.goto(url, wait_until="domcontentloaded")
        return inspect_page(page)


def capture_snapshot(
    url: str,
    output: str | Path,
    html_output: str | Path | None = None,
    profile_dir: str | Path | None = None,
    headless: bool = False,
    browser_channel: str | None = None,
) -> dict[str, Any]:
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_path = Path(html_output).expanduser().resolve() if html_output else None
    if html_path:
        html_path.parent.mkdir(parents=True, exist_ok=True)

    with browser_session(profile_dir=profile_dir, headless=headless, browser_channel=browser_channel) as (
        page,
        _context,
    ):
        page.goto(url, wait_until="domcontentloaded")
        page.screenshot(path=str(output_path), full_page=True)
        if html_path:
            html_path.write_text(page.content(), encoding="utf-8")
        info = inspect_page(page)
        info["screenshot"] = str(output_path)
        if html_path:
            info["html"] = str(html_path)
        return info


def inspect_page(page: Any) -> dict[str, Any]:
    """Return cheap, JSON-safe page facts."""

    selector_presence = {
        name: page.locator(selector).count() > 0 for name, selector in SELECTORS.items()
    }
    return {
        "url": page.url,
        "title": page.title(),
        "has_contents_form": all(
            selector_presence[key]
            for key in ("item_description", "item_value", "item_quantity", "total_value")
        ),
        "selectors": selector_presence,
    }


def fill_contents(
    items: list[ItemLine],
    total_value: int | None = None,
    value_mode: str = "line",
    url: str = CONTENTS_URL,
    profile_dir: str | Path | None = None,
    package_type: str | None = None,
    danger: bool | None = None,
    headless: bool = False,
    browser_channel: str | None = None,
    delay_ms: int = 500,
) -> dict[str, Any]:
    """Fill the known Web Yu-pri contents form and add each item line."""

    plan = build_contents_plan(items, total_value=total_value, value_mode=value_mode)
    with browser_session(profile_dir=profile_dir, headless=headless, browser_channel=browser_channel) as (
        page,
        _context,
    ):
        page.goto(url, wait_until="domcontentloaded")
        _require_selector(page, SELECTORS["item_description"])

        if package_type:
            _set_value(page, SELECTORS["package_type"], package_type)
        if danger is not None:
            _set_boolean(page, SELECTORS["danger"], danger)

        added: list[dict[str, Any]] = []
        for item in items:
            _fill_item(page, item)
            before = _body_fingerprint(page)
            _run_submit_command(page, ADD_ITEM_COMMAND)
            _wait_after_submit(page, before=before, delay_ms=delay_ms)
            added.append(
                {
                    "description": item.description,
                    "value": item.value,
                    "quantity": item.quantity,
                    "country": item.country,
                    "hs_code": item.hs_code,
                }
            )

        _set_value(page, SELECTORS["total_value"], str(plan["declared_total"]))
        info = inspect_page(page)
        verification = _verify_descriptions(page, [item.description for item in items])
        return {
            "status": "filled",
            "plan": plan,
            "added": added,
            "page": info,
            "verification": verification,
            "safety": {
                "final_submit_clicked": False,
                "message": "Contents were filled only; final shipment confirmation is not clicked.",
            },
        }


def build_dry_run(
    items: list[ItemLine],
    total_value: int | None = None,
    value_mode: str = "line",
    package_type: str | None = None,
    danger: bool | None = None,
) -> dict[str, Any]:
    plan = build_contents_plan(items, total_value=total_value, value_mode=value_mode)
    return {
        "dry_run": True,
        "plan": plan,
        "selectors": SELECTORS,
        "add_item_command": ADD_ITEM_COMMAND,
        "package_type": package_type,
        "danger": danger,
        "safety": {
            "browser_launched": False,
            "final_submit_clicked": False,
        },
    }


def _fill_item(page: Any, item: ItemLine) -> None:
    _set_value(page, SELECTORS["item_description"], item.description)
    _set_value(page, SELECTORS["item_value"], str(item.value))
    _set_value(page, SELECTORS["item_quantity"], str(item.quantity))
    if item.country:
        _set_value(page, SELECTORS["item_country"], item.country)
    if item.hs_code:
        _set_value(page, SELECTORS["item_hs_code"], item.hs_code)


def _require_selector(page: Any, selector: str, timeout_ms: int = 15_000) -> None:
    try:
        page.wait_for_selector(selector, timeout=timeout_ms)
    except Exception as exc:
        info = {
            "url": page.url,
            "title": page.title(),
            "expected_selector": selector,
        }
        raise RuntimeError(
            "Web Yu-pri contents form was not found. "
            f"Page facts: {json.dumps(info, ensure_ascii=False)}"
        ) from exc


def _set_value(page: Any, selector: str, value: str) -> None:
    locator = page.locator(selector)
    if locator.count() == 0:
        return
    try:
        tag_name = locator.first.evaluate("el => el.tagName.toLowerCase()")
        if tag_name == "select":
            locator.first.select_option(value)
        else:
            locator.first.fill(str(value))
    except Exception:
        locator.first.evaluate(
            """(el, value) => {
                el.value = value;
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            }""",
            str(value),
        )


def _set_boolean(page: Any, selector: str, value: bool) -> None:
    locator = page.locator(selector)
    if locator.count() == 0:
        return
    try:
        input_type = locator.first.evaluate("el => (el.type || '').toLowerCase()")
        if input_type in {"checkbox", "radio"}:
            locator.first.set_checked(value)
            return
    except Exception:
        pass
    locator.first.evaluate(
        """(el, value) => {
            el.checked = Boolean(value);
            el.value = value ? '1' : '';
            el.dispatchEvent(new Event('change', {bubbles: true}));
        }""",
        value,
    )


def _run_submit_command(page: Any, command: str) -> None:
    page.evaluate(
        """command => {
            if (typeof window.submitCommand === 'function') {
                window.submitCommand(command);
                return;
            }
            throw new Error('submitCommand is not available on this page');
        }""",
        command,
    )


def _wait_after_submit(page: Any, before: str, delay_ms: int) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10_000)
    except Exception:
        pass
    deadline = time.time() + 10
    while time.time() < deadline:
        time.sleep(max(delay_ms, 100) / 1000)
        if _body_fingerprint(page) != before:
            return


def _body_fingerprint(page: Any) -> str:
    try:
        return page.evaluate(
            """() => {
                const text = document.body ? document.body.innerText : '';
                const inputs = Array.from(document.querySelectorAll('input,select,textarea'))
                    .slice(0, 200)
                    .map(el => `${el.id || el.name || ''}:${el.value || ''}`)
                    .join('|');
                return `${location.href}|${text.length}|${inputs.length}|${inputs}`;
            }"""
        )
    except Exception:
        return f"{page.url}:{time.time()}"


def _verify_descriptions(page: Any, descriptions: list[str]) -> dict[str, Any]:
    body_text = page.evaluate("() => document.body ? document.body.innerText : ''")
    found = [description for description in descriptions if description in body_text]
    missing = [description for description in descriptions if description not in body_text]
    return {
        "descriptions_found": found,
        "descriptions_missing": missing,
        "all_found": not missing,
    }
