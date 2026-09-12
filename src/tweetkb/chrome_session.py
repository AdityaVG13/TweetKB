from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass

BOOKMARKS_URL = "https://x.com/i/history"
COLLECTION_PATHS = ("/i/history", "/i/bookmarks")


def is_collection_url(url: str) -> bool:
    return any(path in url for path in COLLECTION_PATHS)


@dataclass(frozen=True)
class ChromeTab:
    window: int
    tab: int
    url: str


class ChromeSessionError(RuntimeError):
    pass


def run_osascript(source: str, timeout: int = 60) -> str:
    proc = subprocess.run(
        ["osascript"],
        input=source,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=timeout,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        if "Executing JavaScript through AppleScript is turned off" in err:
            raise ChromeSessionError(
                "Chrome blocks Apple Events JavaScript. Enable "
                "View > Developer > Allow JavaScript from Apple Events, then rerun collect."
            )
        raise ChromeSessionError(err or "osascript failed")
    return (proc.stdout or "").strip()


def list_tabs(app: str) -> list[ChromeTab]:
    script = f"""
    tell application {json.dumps(app)}
      set out to ""
      set wi to 0
      repeat with w in windows
        set wi to wi + 1
        set ti to 0
        repeat with t in tabs of w
          set ti to ti + 1
          set out to out & wi & "\\t" & ti & "\\t" & (URL of t) & linefeed
        end repeat
      end repeat
      return out
    end tell
    """
    text = run_osascript(script)
    tabs: list[ChromeTab] = []
    for line in text.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        tabs.append(ChromeTab(window=int(parts[0]), tab=int(parts[1]), url=parts[2]))
    return tabs


def find_bookmarks_tab(app: str) -> ChromeTab | None:
    tabs = list_tabs(app)
    for tab in tabs:
        if "/i/history" in tab.url:
            return tab
    for tab in tabs:
        if is_collection_url(tab.url):
            return tab
    return None


def ensure_bookmarks_tab(app: str, wait_seconds: float = 2.0) -> ChromeTab:
    existing = find_bookmarks_tab(app)
    if existing:
        return existing
    script = f"""
    tell application {json.dumps(app)}
      open location {json.dumps(BOOKMARKS_URL)}
    end tell
    """
    run_osascript(script)
    deadline = time.time() + 25
    while time.time() < deadline:
        found = find_bookmarks_tab(app)
        if found:
            time.sleep(wait_seconds)
            return found
        time.sleep(0.4)
    raise ChromeSessionError(
        "Could not open X bookmarks in Chrome. Open https://x.com/i/history and rerun collect."
    )


def eval_js(app: str, tab: ChromeTab, expression: str, timeout: int = 60) -> str:
    script = f"""
    tell application {json.dumps(app)}
      tell tab {tab.tab} of window {tab.window}
        execute javascript {json.dumps(expression)}
      end tell
    end tell
    """
    return run_osascript(script, timeout=timeout)
