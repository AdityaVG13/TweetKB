from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .chrome_session import BOOKMARKS_URL

SESSION_NAMES = {
    "Local State",
    "Default/Cookies",
    "Default/Cookies-journal",
    "Default/Network/Cookies",
    "Default/Network/Cookies-journal",
    "Default/Local Storage",
    "Default/Session Storage",
    "Default/IndexedDB",
    "Default/Preferences",
    "Default/Secure Preferences",
    "Default/Login Data",
    "Default/Login Data-journal",
    "Default/Web Data",
    "Default/Web Data-journal",
}


def chrome_binary() -> Path:
    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    ]
    which = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("google-chrome-stable")
    if which:
        candidates.append(Path(which))
    for path in candidates:
        if path.exists():
            return path
    raise RuntimeError("Chrome/Chromium binary not found")


def clone_logged_in_profile(source: Path, dest: Path) -> Path:
    """Copy session files into an isolated user-data-dir. Never touches Singleton locks."""
    source = source.expanduser()
    dest = dest.expanduser()
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "Default").mkdir(parents=True, exist_ok=True)
    for name in SESSION_NAMES:
        src = source / name
        if not src.exists():
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns("Cache*", "Code Cache", "GPUCache"))
        else:
            shutil.copy2(src, target)
    return dest


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def launch_headless_chrome(user_data_dir: Path, url: str = BOOKMARKS_URL) -> tuple[subprocess.Popen[str], int]:
    port = _free_port()
    proc = subprocess.Popen(
        [
            str(chrome_binary()),
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            f"--user-data-dir={user_data_dir}",
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1) as resp:
                if resp.status == 200:
                    return proc, port
        except Exception:
            if proc.poll() is not None:
                raise RuntimeError("Headless Chrome exited before DevTools came up")
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError("Headless Chrome DevTools did not start")


def list_pages(port: int) -> list[dict[str, Any]]:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=3) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return [item for item in data if item.get("type") == "page"]


class DevTools:
    def __init__(self, ws_url: str):
        parsed = urlparse(ws_url)
        self._sock = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=20)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        upgrade = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        self._sock.sendall(upgrade.encode("ascii"))
        header = b""
        while b"\r\n\r\n" not in header:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise RuntimeError("DevTools websocket closed during handshake")
            header += chunk
        if b"101" not in header.split(b"\r\n", 1)[0]:
            raise RuntimeError("DevTools websocket handshake failed")
        leftover = header.split(b"\r\n\r\n", 1)[1]
        self._buf = leftover
        self._next_id = 1

    def close(self) -> None:
        try:
            self._sock.close()
        except Exception:
            pass

    def call(self, method: str, **params: Any) -> Any:
        msg_id = self._next_id
        self._next_id += 1
        self._send(json.dumps({"id": msg_id, "method": method, "params": params}))
        while True:
            payload = json.loads(self._recv())
            if payload.get("id") == msg_id:
                if "error" in payload:
                    raise RuntimeError(payload["error"])
                return payload.get("result")

    def evaluate(self, expression: str) -> Any:
        result = self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
        return (result or {}).get("result", {}).get("value")

    def _send(self, text: str) -> None:
        data = text.encode("utf-8")
        header = bytearray()
        header.append(0x81)
        length = len(data)
        mask = os.urandom(4)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack(">H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack(">Q", length))
        header.extend(mask)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self._sock.sendall(header + masked)

    def _recv(self) -> str:
        while True:
            if len(self._buf) >= 2:
                b1, b2 = self._buf[0], self._buf[1]
                opcode = b1 & 0x0F
                masked = b2 & 0x80
                length = b2 & 0x7F
                idx = 2
                if length == 126:
                    if len(self._buf) < 4:
                        self._buf += self._sock.recv(4096)
                        continue
                    length = struct.unpack(">H", self._buf[2:4])[0]
                    idx = 4
                elif length == 127:
                    if len(self._buf) < 10:
                        self._buf += self._sock.recv(4096)
                        continue
                    length = struct.unpack(">Q", self._buf[2:10])[0]
                    idx = 10
                if masked:
                    if len(self._buf) < idx + 4:
                        self._buf += self._sock.recv(4096)
                        continue
                    mask = self._buf[idx : idx + 4]
                    idx += 4
                else:
                    mask = b""
                if len(self._buf) < idx + length:
                    self._buf += self._sock.recv(max(4096, idx + length - len(self._buf)))
                    continue
                payload = self._buf[idx : idx + length]
                self._buf = self._buf[idx + length :]
                if mask:
                    payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
                if opcode == 0x8:
                    raise RuntimeError("DevTools websocket closed")
                if opcode == 0x1:
                    return payload.decode("utf-8")
                continue
            more = self._sock.recv(4096)
            if not more:
                raise RuntimeError("DevTools websocket closed")
            self._buf += more


def collect_headless(
    extractor_js: str,
    *,
    profile_root: Path,
    clone_dir: Path,
    limit: int | None,
    batch_size: int,
    wait_seconds: float,
    all_bookmarks: bool,
    known_status_ids: set[str],
    stop_at_existing: bool,
    known_streak: int = 8,
) -> dict[str, Any]:
    clone_logged_in_profile(profile_root, clone_dir)
    proc, port = launch_headless_chrome(clone_dir)
    devtools: DevTools | None = None
    try:
        deadline = time.time() + 25
        page = None
        while time.time() < deadline and page is None:
            pages = list_pages(port)
            page = next(
                (
                    item
                    for item in pages
                    if "/i/history" in item.get("url", "")
                    or "/i/bookmarks" in item.get("url", "")
                    or item.get("webSocketDebuggerUrl")
                ),
                None,
            )
            if page is None:
                time.sleep(0.3)
        if not page or not page.get("webSocketDebuggerUrl"):
            raise RuntimeError("Headless Chrome has no inspectable page")
        devtools = DevTools(page["webSocketDebuggerUrl"])
        url = str(devtools.evaluate("location.href") or "")
        if "flow/login" in url:
            return {"login_required": True, "url": url, "items": [], "batches": 0}
        if "/i/history" not in url and "/i/bookmarks" not in url:
            devtools.evaluate(f"location.href = {json.dumps(BOOKMARKS_URL)}")
            time.sleep(3)
            url = str(devtools.evaluate("location.href") or "")
            if "flow/login" in url:
                return {"login_required": True, "url": url, "items": [], "batches": 0}
        known_json = json.dumps({status_id: True for status_id in sorted(known_status_ids)})
        devtools.evaluate(
            "window.__tweetkbSeen = {}; window.__tweetkbOrder = []; "
            f"window.__tweetkbKnown = {known_json}; window.scrollTo(0, 0)"
        )
        from .collect_stop import decide_scroll_stop, merge_batch

        max_batches = 5000 if all_bookmarks else 200
        target = None if all_bookmarks else int(limit or 100)
        stagnant = 0
        batches = 0
        order: list[str] = []
        collected: dict[str, dict[str, Any]] = {}
        metrics: dict[str, Any] = {}
        while batches < max_batches:
            raw = devtools.evaluate(extractor_js)
            if isinstance(raw, str):
                try:
                    batch_items = json.loads(raw)
                except json.JSONDecodeError:
                    batch_items = []
            elif isinstance(raw, list):
                batch_items = raw
            else:
                batch_items = []
            batches += 1
            order, collected, added = merge_batch(order, collected, batch_items)
            current_count = len(order)
            ordered_ids = order
            new_count = sum(1 for status_id in ordered_ids if status_id not in known_status_ids)
            metrics = devtools.evaluate(
                "({scroll_y: Math.round(window.scrollY), page_height: document.documentElement.scrollHeight, visible_articles: document.querySelectorAll('article').length})"
            ) or {}
            if added == 0:
                stagnant += 1
            else:
                stagnant = 0
            decision = decide_scroll_stop(
                ordered_ids,
                known_status_ids,
                empty_scrolls=stagnant,
                known_streak=known_streak,
                limit=target,
                stop_at_existing=stop_at_existing,
            )
            print(
                f"tweetkb progress: seen={current_count} new={new_count} added={added} batches={batches} "
                f"scroll_y={metrics.get('scroll_y', 0)} visible_articles={metrics.get('visible_articles', 0)} "
                f"stop={decision.reason}",
                file=sys.stderr,
                flush=True,
            )
            if decision.stop:
                break
            devtools.evaluate(
                """(() => {
  const articles = document.querySelectorAll('article');
  const last = articles[articles.length - 1];
  if (last) last.scrollIntoView({block: 'end', inline: 'nearest'});
  const col = document.querySelector('[data-testid="primaryColumn"]') || document.scrollingElement;
  if (col && col !== last) col.scrollBy(0, 1400);
  return articles.length;
})()"""
            )
            from .collect_pace import sleep_seconds

            time.sleep(sleep_seconds(wait_seconds, batches, all_bookmarks=all_bookmarks))
        items = [collected[status_id] for status_id in order]
        return {"items": items, "batches": batches, **metrics}
    finally:
        if devtools:
            devtools.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
