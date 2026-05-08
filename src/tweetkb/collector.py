from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import textwrap
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .checkpoint import Checkpoint
from .db import Store
from .util import extract_status_id

BOOKMARKS_URL = "https://x.com/i/bookmarks"
DEFAULT_BROWSER_APP = os.environ.get("TWEETKB_BROWSER_APP", "Google Chrome")
DEFAULT_BROWSER_PROFILE = Path(
    os.environ.get("TWEETKB_BROWSER_PROFILE", str(Path.home() / "Library/Application Support/Google/Chrome"))
)
DEFAULT_BROWSER_DEBUG_PORT = int(os.environ.get("TWEETKB_BROWSER_DEBUG_PORT", "9222"))
BROWSER_HARNESS_PROFILE = Path.home() / ".browser-harness/chrome-profiles/default"


@dataclass
class CollectResult:
    saved: int
    seen: int
    batches: int
    changed: int = 0
    unchanged: int = 0
    login_required: bool = False
    needs_bookmarks_tab: bool = False
    debug_targets_empty: bool = False
    message: str = ""
    scroll_y: int = 0
    page_height: int = 0
    visible_articles: int = 0


class BrowserHarnessCollector:
    def __init__(
        self,
        store: Store,
        checkpoint: Checkpoint | None = None,
        executable: str = "browser-harness",
        browser_app: str = DEFAULT_BROWSER_APP,
        browser_profile: Path = DEFAULT_BROWSER_PROFILE,
        debug_port: int = DEFAULT_BROWSER_DEBUG_PORT,
    ):
        self.store = store
        self.checkpoint = checkpoint or Checkpoint()
        self.executable = executable
        self.browser_app = browser_app
        self.browser_profile = browser_profile
        self.debug_port = debug_port

    def ensure_available(self) -> None:
        if not shutil.which(self.executable):
            raise RuntimeError("browser-harness executable was not found on PATH")

    def ensure_managed_local_ready(self, url: str = BOOKMARKS_URL) -> None:
        self.ensure_available()
        proc = subprocess.run(
            [self.executable, "--launch-local", url],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            detail = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(f"browser-harness could not launch managed Chrome: {detail}")

    def open_login(self, normal_chrome: bool = False) -> None:
        self.ensure_available()
        if normal_chrome:
            subprocess.run(["open", "-a", self.browser_app, BOOKMARKS_URL], check=True)
        else:
            subprocess.run([self.executable, "--launch-local", BOOKMARKS_URL], check=True)

    def start_normal_chrome_debug(self, open_bookmarks: bool = True) -> None:
        start_normal_chrome_debug(
            open_bookmarks=open_bookmarks,
            browser_app=self.browser_app,
            browser_profile=self.browser_profile,
            debug_port=self.debug_port,
        )

    def collect(
        self,
        limit: int | None = 100,
        batch_size: int = 20,
        wait_seconds: float = 1.5,
        existing_tab: bool = False,
        normal_chrome: bool = False,
        apple_events: bool = False,
        all_bookmarks: bool = False,
        stop_at_existing: bool = True,
    ) -> CollectResult:
        self.ensure_available()
        known_status_ids = self._known_status_ids() if stop_at_existing else set()
        if apple_events:
            payload = self._collect_with_apple_events(
                limit=limit,
                batch_size=batch_size,
                wait_seconds=wait_seconds,
                all_bookmarks=all_bookmarks,
                known_status_ids=known_status_ids,
                stop_at_existing=stop_at_existing,
            )
            payload = self._apply_limit(payload, limit, all_bookmarks)
            return self._save_payload(payload)
        if not normal_chrome:
            self.ensure_managed_local_ready()
        script = self._browser_script(
            limit=limit,
            batch_size=batch_size,
            wait_seconds=wait_seconds,
            existing_tab=existing_tab,
            all_bookmarks=all_bookmarks,
            known_status_ids=known_status_ids,
            stop_at_existing=stop_at_existing,
        )
        env = os.environ.copy()
        if normal_chrome and "BU_CDP_WS" not in env:
            try:
                env["BU_CDP_WS"] = find_normal_chrome_cdp_ws(
                    profile_root=self.browser_profile,
                    debug_port=self.debug_port,
                    browser_app=self.browser_app,
                    auto_start_debug=True,
                )
            except RuntimeError as exc:
                if _apple_events_javascript_available(self.browser_app):
                    print(
                        f"normal-chrome: CDP unavailable ({exc}); falling back to Apple Events.",
                        flush=True,
                    )
                    payload = self._collect_with_apple_events(
                        limit=limit,
                        batch_size=batch_size,
                        wait_seconds=wait_seconds,
                        all_bookmarks=all_bookmarks,
                        known_status_ids=known_status_ids,
                        stop_at_existing=stop_at_existing,
                    )
                    payload = self._apply_limit(payload, limit, all_bookmarks)
                    return self._save_payload(payload)
                raise
        proc = self._run_browser_harness_script(script, env)
        if proc.returncode != 0:
            raise RuntimeError(f"browser-harness failed: {proc.stderr.strip() or proc.stdout.strip()}")
        payload = self._parse_payload(proc.stdout)
        if payload.get("login_required"):
            self.store.log_event("collect_login_required", "X login required", payload)
            return CollectResult(saved=0, seen=0, batches=0, login_required=True)
        if payload.get("needs_bookmarks_tab"):
            self.store.log_event("collect_needs_bookmarks_tab", "Open X bookmarks tab required", payload)
            return CollectResult(
                saved=0,
                seen=0,
                batches=0,
                needs_bookmarks_tab=True,
                debug_targets_empty=bool(payload.get("debug_targets_empty")),
                message=payload.get("message", ""),
            )

        return self._save_payload(payload)

    def _known_status_ids(self) -> set[str]:
        try:
            rows = self.store.conn.execute("SELECT status_id FROM bookmarks WHERE is_deleted = 0").fetchall()
        except Exception:
            return set()
        return {str(row["status_id"]) for row in rows if row["status_id"]}

    def _apply_limit(self, payload: dict[str, Any], limit: int | None, all_bookmarks: bool) -> dict[str, Any]:
        if all_bookmarks or limit is None:
            return payload
        items = payload.get("items")
        if isinstance(items, list):
            payload = dict(payload)
            payload["items"] = items[: int(limit)]
        return payload

    def _save_payload(self, payload: dict[str, Any]) -> CollectResult:
        saved = 0
        changed = 0
        unchanged = 0
        status_ids: list[str] = []
        captured_at_base = datetime.now(timezone.utc)
        for index, item in enumerate(payload.get("items", [])):
            item.setdefault("captured_at", (captured_at_base - timedelta(microseconds=index)).isoformat())
            upserted = self.store.upsert_bookmark_with_status(item)
            bookmark_id = upserted[0] if upserted else None
            status_id = item.get("status_id") or extract_status_id(item.get("status_url"))
            if status_id:
                status_ids.append(status_id)
            if bookmark_id:
                saved += 1
                if upserted and upserted[1]:
                    changed += 1
                else:
                    unchanged += 1
        self.checkpoint.add_seen(status_ids)
        self.store.log_event(
            "collect",
            f"Collected {saved} bookmarks",
            {
                "seen": len(status_ids),
                "changed": changed,
                "unchanged": unchanged,
                "batches": payload.get("batches", 0),
                "scroll_y": payload.get("scroll_y", 0),
                "page_height": payload.get("page_height", 0),
                "visible_articles": payload.get("visible_articles", 0),
            },
        )
        return CollectResult(
            saved=saved,
            seen=len(status_ids),
            changed=changed,
            unchanged=unchanged,
            batches=int(payload.get("batches", 0)),
            scroll_y=int(payload.get("scroll_y", 0) or 0),
            page_height=int(payload.get("page_height", 0) or 0),
            visible_articles=int(payload.get("visible_articles", 0) or 0),
        )

    def _run_browser_harness_script(self, script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        proc = subprocess.Popen(
            [self.executable],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        def read_stream(stream, sink: list[str], echo_progress: bool = False) -> None:
            for line in stream:
                sink.append(line)
                if echo_progress and line.startswith("tweetkb progress:"):
                    print(line, end="", flush=True)

        assert proc.stdout is not None
        assert proc.stderr is not None
        stdout_thread = threading.Thread(target=read_stream, args=(proc.stdout, stdout_lines, True), daemon=True)
        stderr_thread = threading.Thread(target=read_stream, args=(proc.stderr, stderr_lines, False), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        try:
            assert proc.stdin is not None
            proc.stdin.write(script)
            proc.stdin.close()
            returncode = proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            raise
        finally:
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
        return subprocess.CompletedProcess(
            args=[self.executable],
            returncode=returncode,
            stdout="".join(stdout_lines),
            stderr="".join(stderr_lines),
        )

    def _collect_with_apple_events(
        self,
        limit: int | None,
        batch_size: int,
        wait_seconds: float,
        all_bookmarks: bool = False,
        known_status_ids: set[str] | None = None,
        stop_at_existing: bool = True,
    ) -> dict[str, Any]:
        extractor_js = self._extractor_js()
        max_batches = 5000 if all_bookmarks else 200
        limit_check = "false" if all_bookmarks else f"currentCount >= {int(limit or 100)}"
        known_json = json.dumps({status_id: True for status_id in sorted(known_status_ids or set())})
        reset_js = (
            f"window.__tweetkbSeen = {{}}; window.__tweetkbOrder = []; "
            f"window.__tweetkbKnown = {known_json}; window.scrollTo(0, 0)"
        )
        stop_existing_check = (
            "newCount = previousNewCount and currentCount > 0" if all_bookmarks and stop_at_existing else "false"
        )
        script = f"""
        on run
          set collected to "{{}}"
          set batches to 0
          set stagnant to 0
          set existingStagnant to 0
          set previousCount to 0
          set previousNewCount to 0
          set metrics to "{{}}"
          tell application {json.dumps(self.browser_app)}
            if not (exists front window) then error "No Chrome window is open"
            tell active tab of front window
              repeat while batches < {max_batches}
                set pageUrl to execute javascript "location.href"
                if pageUrl contains "flow/login" then return "TWEETKB_JSON=" & "{{\\"login_required\\":true,\\"url\\":\\"" & pageUrl & "\\"}}"
                if batches = 0 then execute javascript {json.dumps(reset_js)}
                set rawItems to execute javascript {json.dumps(extractor_js)}
                set collected to rawItems
                set metrics to execute javascript "JSON.stringify({{scroll_y: Math.round(window.scrollY), page_height: document.documentElement.scrollHeight, visible_articles: document.querySelectorAll('article').length}})"
                set batches to batches + 1
                set currentCount to execute javascript "Object.keys(window.__tweetkbSeen || {{}}).length"
                set newCount to execute javascript "Object.keys(window.__tweetkbSeen || {{}}).filter(id => !(window.__tweetkbKnown || {{}})[id]).length"
                if {limit_check} then exit repeat
                if currentCount = previousCount then
                  set stagnant to stagnant + 1
                else
                  set stagnant to 0
                end if
                if {stop_existing_check} then
                  set existingStagnant to existingStagnant + 1
                else
                  set existingStagnant to 0
                end if
                if stagnant >= 10 then exit repeat
                if existingStagnant >= 5 then exit repeat
                set previousCount to currentCount
                set previousNewCount to newCount
                execute javascript "window.scrollBy(0, " & "{int(batch_size) * 220}" & ")"
                delay {float(wait_seconds)}
              end repeat
            end tell
          end tell
          return "TWEETKB_JSON=" & "{{\\"items\\":" & collected & ",\\"batches\\":" & batches & ",\\"metrics\\":" & metrics & "}}"
        end run
        """
        proc = subprocess.run(["osascript"], input=script, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            if "Executing JavaScript through AppleScript is turned off" in stderr:
                raise RuntimeError(
                    "Chrome blocks Apple Events JavaScript. In Chrome, enable: "
                    "View > Developer > Allow JavaScript from Apple Events. Then rerun:\n"
                    "uv run tweetkb collect --apple-events --limit 300 --batch-size 20"
                )
            raise RuntimeError(stderr or proc.stdout.strip())
        return self._parse_payload(proc.stdout)

    def _parse_payload(self, stdout: str) -> dict[str, Any]:
        for line in reversed(stdout.splitlines()):
            if line.startswith("TWEETKB_JSON="):
                payload = json.loads(line.removeprefix("TWEETKB_JSON="))
                metrics = payload.pop("metrics", None)
                if isinstance(metrics, dict):
                    payload.update(metrics)
                return payload
        raise RuntimeError(f"No TWEETKB_JSON payload found in browser-harness output: {stdout[-1000:]}")

    def _browser_script(
        self,
        limit: int | None,
        batch_size: int,
        wait_seconds: float,
        existing_tab: bool,
        all_bookmarks: bool = False,
        known_status_ids: set[str] | None = None,
        stop_at_existing: bool = True,
    ) -> str:
        extractor_js = self._extractor_js()
        return textwrap.dedent(
            """
@@SCRIPT_BODY@@
            """
        ).replace(
            "@@SCRIPT_BODY@@",
            self._browser_script_body(
                limit,
                batch_size,
                wait_seconds,
                existing_tab,
                extractor_js,
                all_bookmarks,
                known_status_ids or set(),
                stop_at_existing,
            ),
        )

    def _extractor_js(self) -> str:
        return r"""
(() => {
  const textOf = (node) => node ? (node.innerText || node.textContent || '').trim() : '';
  const abs = (href) => {
    try { return new URL(href, location.origin).href; } catch (_) { return href || ''; }
  };
  const articles = Array.from(document.querySelectorAll('article'));
  window.__tweetkbSeen = window.__tweetkbSeen || {};
  window.__tweetkbOrder = window.__tweetkbOrder || [];
  articles.map((article) => {
    const links = Array.from(article.querySelectorAll('a[href]')).map(a => abs(a.getAttribute('href'))).filter(Boolean);
    const statusUrl = links.find(h => /\/status\/\d+/.test(h)) || '';
    const statusMatch = statusUrl.match(/\/status\/(\d+)/);
    const userName = article.querySelector('[data-testid="User-Name"]');
    const userText = textOf(userName);
    const handleMatch = userText.match(/@([A-Za-z0-9_]+)/);
    const tweetTextNodes = Array.from(article.querySelectorAll('[data-testid="tweetText"]'));
    const tweetText = tweetTextNodes.map(textOf).filter(Boolean).join('\n\n') || textOf(article);
    const time = article.querySelector('time');
    const item = {
      status_url: statusUrl,
      status_id: statusMatch ? statusMatch[1] : '',
      author_name: userText.split('\n')[0] || '',
      author_handle: handleMatch ? handleMatch[1] : '',
      tweet_text: tweetText,
      raw_text: textOf(article),
      created_at: time ? (time.getAttribute('datetime') || '') : '',
      links: Array.from(new Set(links)).filter(h => !h.includes('/analytics'))
    };
    if (item.status_id && item.tweet_text) {
      if (!window.__tweetkbSeen[item.status_id]) window.__tweetkbOrder.push(item.status_id);
      window.__tweetkbSeen[item.status_id] = item;
    }
  });
  return JSON.stringify(window.__tweetkbOrder.map(id => window.__tweetkbSeen[id]).filter(Boolean));
})()
"""

    def _browser_script_body(
        self,
        limit: int | None,
        batch_size: int,
        wait_seconds: float,
        existing_tab: bool,
        extractor_js: str,
        all_bookmarks: bool = False,
        known_status_ids: set[str] | None = None,
        stop_at_existing: bool = True,
    ) -> str:
        target_limit = "None" if all_bookmarks else str(int(limit or 100))
        max_batches = 5000 if all_bookmarks else 200
        stagnant_limit = 10 if all_bookmarks else 5
        known_ids_literal = repr(sorted(known_status_ids or set()))
        stop_existing_enabled = bool(all_bookmarks and stop_at_existing)
        return textwrap.dedent(
            f"""
            import json, time
            def attach_existing_bookmarks_tab():
                targets = cdp("Target.getTargets").get("targetInfos", [])
                pages = [t for t in targets if t.get("type") == "page"]
                bookmarks = [
                    t for t in pages
                    if ("x.com/i/bookmarks" in t.get("url", "") or "twitter.com/i/bookmarks" in t.get("url", ""))
                ]
                if bookmarks:
                    return cdp("Target.attachToTarget", targetId=bookmarks[0]["targetId"], flatten=True)["sessionId"]
                return {{
                    "total_targets": len(targets),
                    "pages": [dict(title=p.get("title", ""), url=p.get("url", "")) for p in pages[:20]],
                }}

            target_session = None
            if {bool(existing_tab)!r}:
                attached = attach_existing_bookmarks_tab()
                target_session = attached if isinstance(attached, str) else None
                if not target_session:
                    total_targets = attached.get("total_targets", 0) if isinstance(attached, dict) else 0
                    print("TWEETKB_JSON=" + json.dumps({{
                        "needs_bookmarks_tab": True,
                        "debug_targets_empty": total_targets == 0,
                        "message": "CDP sees no Chrome targets" if total_targets == 0 else "CDP cannot see an x.com/i/bookmarks tab",
                        "pages": attached.get("pages", []) if isinstance(attached, dict) else [],
                    }}))
                    raise SystemExit(0)
            else:
                new_tab({BOOKMARKS_URL!r})
                wait_for_load(20)
            time.sleep(2)
            def eval_in_tab(expression):
                if target_session:
                    result = cdp("Runtime.evaluate", session_id=target_session, expression=expression, returnByValue=True, awaitPromise=True)
                    return result.get("result", {{}}).get("value")
                return js(expression)

            info_raw = eval_in_tab("JSON.stringify({{url:location.href,title:document.title}})")
            info = json.loads(info_raw or "{{}}")
            if "login" in info.get("url", "").lower() or "flow/login" in info.get("url", ""):
                print("TWEETKB_JSON=" + json.dumps({{"login_required": True, "url": info.get("url")}}))
            else:
                eval_in_tab("window.__tweetkbSeen = {{}}; window.__tweetkbOrder = []; window.scrollTo(0, 0)")
                seen = {{}}
                batches = 0
                stagnant = 0
                existing_stagnant = 0
                previous_new_count = 0
                metrics = {{}}
                target_limit = {target_limit}
                known_status_ids = set({known_ids_literal})
                while batches < {max_batches} and stagnant < {stagnant_limit}:
                    raw = eval_in_tab({extractor_js!r})
                    items = json.loads(raw or "[]")
                    before = len(seen)
                    for item in items:
                        if item.get("status_id"):
                            seen[item["status_id"]] = item
                    batches += 1
                    if len(seen) == before:
                        stagnant += 1
                    else:
                        stagnant = 0
                    new_count = sum(1 for status_id in seen if status_id not in known_status_ids)
                    if {stop_existing_enabled!r} and len(seen) > 0 and new_count == previous_new_count:
                        existing_stagnant += 1
                    else:
                        existing_stagnant = 0
                    metrics_raw = eval_in_tab("JSON.stringify({{scroll_y: Math.round(window.scrollY), page_height: document.documentElement.scrollHeight, visible_articles: document.querySelectorAll('article').length}})")
                    metrics = json.loads(metrics_raw or "{{}}")
                    print(
                        "tweetkb progress: seen={{}} new={{}} batches={{}} scroll_y={{}} page_height={{}} visible_articles={{}}".format(
                            len(seen),
                            new_count,
                            batches,
                            metrics.get("scroll_y", 0),
                            metrics.get("page_height", 0),
                            metrics.get("visible_articles", 0),
                        ),
                        flush=True,
                    )
                    if target_limit is not None and len(seen) >= target_limit:
                        break
                    if existing_stagnant >= 5:
                        break
                    previous_new_count = new_count
                    eval_in_tab("window.scrollBy(0, " + str({int(batch_size) * 220}) + ")")
                    time.sleep({float(wait_seconds)})
                items = list(seen.values())
                if target_limit is not None:
                    items = items[:target_limit]
                print("TWEETKB_JSON=" + json.dumps({{"items": items, "batches": batches, "metrics": metrics}}))
            """
        )


def find_normal_chrome_cdp_ws(
    profile_root: Path = DEFAULT_BROWSER_PROFILE,
    debug_port: int = DEFAULT_BROWSER_DEBUG_PORT,
    browser_app: str = DEFAULT_BROWSER_APP,
    auto_start_debug: bool = False,
) -> str:
    fixed_ws = find_cdp_ws_on_port(debug_port)
    if fixed_ws:
        return fixed_ws
    if auto_start_debug and not normal_chrome_has_debugging_flag(browser_app):
        print("normal-chrome: restarting Chrome with remote debugging and opening X bookmarks...", flush=True)
        start_normal_chrome_debug(
            open_bookmarks=True,
            browser_app=browser_app,
            browser_profile=profile_root,
            debug_port=debug_port,
        )
        ws = wait_for_normal_chrome_cdp_ws(profile_root, debug_port)
        if ws:
            return ws
        raise RuntimeError(
            "Chrome was restarted with remote debugging, but CDP is not reachable yet. "
            "If Chrome shows an `Allow remote debugging?` prompt, click Allow, then rerun collection."
        )
    port_file = profile_root / "DevToolsActivePort"
    if not port_file.exists():
        if auto_start_debug:
            print("normal-chrome: enabling remote debugging and opening X bookmarks...", flush=True)
            start_normal_chrome_debug(
                open_bookmarks=True,
                browser_app=browser_app,
                browser_profile=profile_root,
                debug_port=debug_port,
            )
            ws = wait_for_normal_chrome_cdp_ws(profile_root, debug_port)
            if ws:
                return ws
            raise RuntimeError(
                "Normal Chrome did not expose DevToolsActivePort. "
                "If Chrome shows an `Allow remote debugging?` prompt, click Allow, then rerun collection."
            )
        raise RuntimeError(
            "Normal Chrome does not expose DevToolsActivePort. Open chrome://inspect/#remote-debugging, "
            "enable remote debugging, click Allow if prompted, then retry."
        )
    lines = [line.strip() for line in port_file.read_text().splitlines() if line.strip()]
    if len(lines) < 2:
        raise RuntimeError(f"Invalid DevToolsActivePort file: {port_file}")
    if not normal_chrome_has_debugging_flag(browser_app):
        if auto_start_debug:
            print("normal-chrome: restarting Chrome with remote debugging and opening X bookmarks...", flush=True)
            start_normal_chrome_debug(
                open_bookmarks=True,
                browser_app=browser_app,
                browser_profile=profile_root,
                debug_port=debug_port,
            )
            ws = wait_for_normal_chrome_cdp_ws(profile_root, debug_port)
            if ws:
                return ws
            raise RuntimeError(
                "Chrome was restarted with remote debugging, but CDP is not reachable yet. "
                "If Chrome shows an `Allow remote debugging?` prompt, click Allow, then rerun collection."
            )
        raise RuntimeError(
            "Normal Chrome is not running with remote debugging. Quit Chrome, then start it with:\n"
            f"open -na '{browser_app}' --args --remote-debugging-port={debug_port} --remote-allow-origins='*'\n"
            "Then open https://x.com/i/bookmarks and rerun collection."
        )
    port = int(lines[0])
    if not is_port_open("127.0.0.1", port):
        if auto_start_debug:
            print("normal-chrome: remote debugging port is stale; restarting Chrome debug session...", flush=True)
            start_normal_chrome_debug(
                open_bookmarks=True,
                browser_app=browser_app,
                browser_profile=profile_root,
                debug_port=debug_port,
            )
            ws = wait_for_normal_chrome_cdp_ws(profile_root, debug_port)
            if ws:
                return ws
            raise RuntimeError(
                "Normal Chrome remote debugging is still unreachable. "
                "If Chrome shows an `Allow remote debugging?` prompt, click Allow, then rerun collection."
            )
        raise RuntimeError(
            f"Normal Chrome remote debugging port {port} is stale or closed. Run:\n"
            "uv run tweetkb chrome-debug\n"
            "Then log into X if needed and rerun collection."
        )
    return f"ws://127.0.0.1:{port}{lines[1]}"


def wait_for_normal_chrome_cdp_ws(
    profile_root: Path = DEFAULT_BROWSER_PROFILE,
    debug_port: int = DEFAULT_BROWSER_DEBUG_PORT,
    timeout_seconds: float = 30.0,
) -> str | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        fixed_ws = find_cdp_ws_on_port(debug_port)
        if fixed_ws:
            return fixed_ws
        port_file = profile_root / "DevToolsActivePort"
        if port_file.exists():
            try:
                lines = [line.strip() for line in port_file.read_text().splitlines() if line.strip()]
                if len(lines) >= 2:
                    port = int(lines[0])
                    if is_port_open("127.0.0.1", port):
                        return f"ws://127.0.0.1:{port}{lines[1]}"
            except (OSError, ValueError):
                pass
        time.sleep(0.5)
    return None


def find_cdp_ws_on_port(port: int) -> str | None:
    if not is_port_open("127.0.0.1", port):
        return None
    try:
        import urllib.request

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.0) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None
    ws = data.get("webSocketDebuggerUrl")
    return ws if isinstance(ws, str) and ws.startswith("ws://") else None


def normal_chrome_has_debugging_flag(browser_app: str = DEFAULT_BROWSER_APP) -> bool:
    try:
        proc = subprocess.run(
            ["ps", "axo", "command"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        return True
    for line in proc.stdout.splitlines():
        if f"/Applications/{browser_app}.app/Contents/MacOS/" not in line:
            continue
        if ".browser-harness/chrome-profiles" in line:
            continue
        if "--remote-debugging-port" in line:
            return True
    return False


def _apple_events_javascript_available(browser_app: str = DEFAULT_BROWSER_APP) -> bool:
    script = f'tell application {json.dumps(browser_app)} to tell active tab of front window to execute javascript "location.href"'
    proc = subprocess.run(
        ["osascript", "-e", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.returncode == 0 and bool(proc.stdout.strip())


def is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def start_normal_chrome_debug(
    open_bookmarks: bool = True,
    browser_app: str = DEFAULT_BROWSER_APP,
    browser_profile: Path = DEFAULT_BROWSER_PROFILE,
    debug_port: int = DEFAULT_BROWSER_DEBUG_PORT,
) -> None:
    for path in (
        browser_profile / "DevToolsActivePort",
        BROWSER_HARNESS_PROFILE / "DevToolsActivePort",
    ):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
    subprocess.run(
        ["osascript", "-e", f'tell application {json.dumps(browser_app)} to quit'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    subprocess.run(
        [
            "open",
            "-na",
            browser_app,
            "--args",
            f"--remote-debugging-port={debug_port}",
            "--remote-allow-origins=*",
        ],
        check=True,
    )
    if open_bookmarks:
        subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application {json.dumps(browser_app)} to activate',
                "-e",
                f'tell application {json.dumps(browser_app)} to open location "{BOOKMARKS_URL}"',
            ],
            check=False,
        )
