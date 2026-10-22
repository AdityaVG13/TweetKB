from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Key
from textual.message import Message
from textual.widgets import Footer, Input, Label, Static

from .digest import build_digest
from .graphview import ascii_flowchart, category_meters, mermaid_flowchart, sonar_scope
from .normalize import display_tweet_text
from .relations import related_bookmarks
from .search import SearchHit, search_bookmarks


class HitHighlighted(Message):
    def __init__(self, hit: SearchHit) -> None:
        self.hit = hit
        super().__init__()


class HitPane(Static):
    """Paint only the visible hit window. j/k still walk the full result."""

    can_focus = True
    BINDINGS = [
        Binding("j", "cursor_down", "down", show=False),
        Binding("k", "cursor_up", "up", show=False),
    ]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.hits: list[SearchHit] = []
        self.cursor = 0
        self.window_origin = 0
        self._painting = False

    def set_hits(self, hits: list[SearchHit]) -> None:
        self.hits = list(hits)
        self.cursor = 0
        self.window_origin = 0
        self._paint()

    def clear_hits(self) -> None:
        self.hits = []
        self.cursor = 0
        self.window_origin = 0
        self.update("")

    def _window(self) -> int:
        height = self.size.height
        if height <= 0:
            return 8
        return max(1, height // 2)

    def _paint(self) -> None:
        if self._painting:
            return
        self._painting = True
        try:
            self._paint_window()
        finally:
            self._painting = False

    def _paint_window(self) -> None:
        if not self.hits:
            self.update("")
            return
        window = self._window()
        if self.cursor < self.window_origin:
            self.window_origin = self.cursor
        elif self.cursor >= self.window_origin + window:
            self.window_origin = self.cursor - window + 1
        end = min(len(self.hits), self.window_origin + window)
        body = Text()
        for index in range(self.window_origin, end):
            hit = self.hits[index]
            selected = index == self.cursor
            mark = ">" if selected else " "
            snippet = display_tweet_text(hit.tweet_text or hit.snippet or "")[:72]
            handle = f"@{hit.author_handle}" if hit.author_handle else "-"
            style = "bold #3ee0c4" if selected else "#9fddd0"
            body.append(f"{mark} {hit.status_id}  {handle}  {hit.category or '-'}\n", style=style)
            body.append(f"  {snippet}\n", style=style)
        self.update(body)

    def on_resize(self, event: Any) -> None:
        if self._painting:
            return
        self._paint()

    def action_cursor_down(self) -> None:
        if not self.hits or self.cursor >= len(self.hits) - 1:
            return
        self.cursor += 1
        self._paint()
        self.post_message(HitHighlighted(self.hits[self.cursor]))

    def action_cursor_up(self) -> None:
        if not self.hits or self.cursor <= 0:
            return
        self.cursor -= 1
        self._paint()
        self.post_message(HitHighlighted(self.hits[self.cursor]))


class TweetKBApp(App[int]):
    TITLE = "TWEETKB"
    CSS = """
    Screen { background: #020b12; color: #c5ebe3; }
    Footer { background: #031018; color: #7aaea6; }
    #chrome { height: 1; padding: 0 1; color: #3ee0c4; background: #031820; }
    #search {
        background: #020b12;
        border: tall #1a4a44;
        color: #e7fff9;
        margin: 0 0 1 0;
    }
    #search:focus { border: tall #3ee0c4; }
    #body { height: 1fr; }
    #left, #mid, #right { height: 1fr; }
    #left { width: 1fr; }
    #mid { width: 1fr; }
    #right { width: 1fr; }
    .pane-label { height: 1; color: #7aaea6; padding: 0 1; text-style: bold; }
    #meters { height: 7; border: tall #1a4a44; padding: 0 1; color: #3ee0c4; }
    #hits { height: 1fr; border: tall #1a4a44; padding: 0 1; }
    #hits:focus { border: tall #3ee0c4; }
    #card_scroll, #graph_scroll { height: 1fr; border: tall #1a4a44; padding: 0 1; }
    #card { color: #e7fff9; }
    #graph { color: #9fddd0; }
    """
    BINDINGS = [
        Binding("ctrl+c", "quit", "quit", priority=True),
        Binding("escape", "escape", "esc", priority=True),
        Binding("tab", "focus_next", "tab", priority=True),
        Binding("shift+tab", "focus_previous", "tab", show=False, priority=True),
        Binding("slash", "focus_search", "search", key_display="/"),
        Binding("o", "open_tweet", "open tweet"),
        Binding("l", "open_link", "open link"),
        Binding("g", "toggle_graph", "related view"),
        Binding("question_mark", "show_help", "help", key_display="?"),
    ]

    def __init__(self, store: Any) -> None:
        super().__init__()
        self.store = store
        self.graph_mode = "ascii"
        self.center: SearchHit | None = None
        self.digest = build_digest(store, limit=8)
        self._neighbors: list = []
        self._hit_count = 0

    def compose(self) -> ComposeResult:
        yield Static(self._chrome_line(), id="chrome")
        yield Input(placeholder="search  ·  enter  ·  esc leaves the box  ·  ctrl+c quits", id="search")
        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield Static(self._meter_text(), id="meters")
                yield Label("HITS", classes="pane-label", id="hits_label")
                yield HitPane(id="hits")
            with Vertical(id="mid"):
                yield Label("TWEET  ·  enter opens", classes="pane-label")
                with VerticalScroll(id="card_scroll"):
                    yield Static("type a query and press enter", id="card")
            with Vertical(id="right"):
                yield Label("RELATED  ·  ascii", classes="pane-label", id="related_label")
                with VerticalScroll(id="graph_scroll"):
                    yield Static("related tweets for the selected hit", id="graph")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search", Input).focus()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if isinstance(self.focused, Input) and action in {"toggle_graph", "open_tweet", "open_link", "focus_search"}:
            return False
        return True

    def on_key(self, event: Key) -> None:
        if event.key == "enter" and self.focused is self.query_one("#hits"):
            self.action_open_tweet()
            event.stop()

    def action_focus_next(self) -> None:
        if isinstance(self.focused, Input):
            self.query_one("#hits", HitPane).focus()
        else:
            self.query_one("#search", Input).focus()

    def action_focus_previous(self) -> None:
        self.action_focus_next()

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_escape(self) -> None:
        if isinstance(self.focused, Input):
            hits = self.query_one("#hits", HitPane)
            if self._hit_count:
                hits.focus()
            else:
                self.exit(0)
            return
        self.exit(0)

    def action_show_help(self) -> None:
        self.notify(
            "esc quit (or leave search)  ·  tab panes  ·  enter open tweet  ·  l open link  ·  / search  ·  g related",
            timeout=5,
        )

    def action_toggle_graph(self) -> None:
        cycle = {"ascii": "mermaid", "mermaid": "map", "map": "ascii"}
        self.graph_mode = cycle.get(self.graph_mode, "ascii")
        self.query_one("#chrome", Static).update(self._chrome_line())
        related_label = self.query_one("#related_label", Label)
        related_label.update(f"RELATED  ·  {self.graph_mode}")
        self._paint_graph()

    def action_open_tweet(self) -> None:
        if isinstance(self.focused, Input):
            return
        hit = self.center
        if not hit or not hit.status_url:
            self.notify("no tweet URL on this hit", severity="warning", timeout=3)
            return
        from .cli import _open_urls

        _open_urls([hit.status_url])
        self.notify(f"opened tweet {hit.status_id}", timeout=2)

    def action_open_link(self) -> None:
        if isinstance(self.focused, Input):
            return
        hit = self.center
        if not hit:
            return
        url = next(iter(hit.outbound_links), None)
        if not url:
            self.notify("no outbound link — use enter for the tweet", severity="warning", timeout=3)
            return
        from .cli import _open_urls

        _open_urls([url])
        self.notify(f"opened {url}", timeout=2)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        query = (event.value or "").strip()
        hits_view = self.query_one("#hits", HitPane)
        hits_view.clear_hits()
        self.center = None
        self._neighbors = []
        if not query:
            self._hit_count = 0
            self.query_one("#chrome", Static).update(self._chrome_line())
            self.query_one("#hits_label", Label).update("HITS")
            self.query_one("#card", Static).update("type a query and press enter")
            self._paint_graph()
            return
        try:
            hits = search_bookmarks(self.store, query, limit=200)
        except ValueError as exc:
            self._hit_count = 0
            self.query_one("#card", Static).update(str(exc))
            return
        self._hit_count = len(hits)
        self.query_one("#chrome", Static).update(self._chrome_line())
        if not hits:
            self.query_one("#hits_label", Label).update("HITS  0")
            self.query_one("#card", Static).update(f"no matches for “{query}”")
            self.notify(f"no matches for {query}", severity="warning", timeout=3)
            self._paint_graph()
            return
        hits_view.set_hits(hits)
        self._select(hits[0], hits_view)
        hits_view.focus()
        self.notify(f"{self._hit_count} matches", timeout=2)

    def on_hit_highlighted(self, event: HitHighlighted) -> None:
        self._select(event.hit, self.query_one("#hits", HitPane))

    def _select(self, hit: SearchHit, pane: HitPane) -> None:
        self.center = hit
        self._show_card(hit)
        self._refresh_graph()
        self.query_one("#hits_label", Label).update(f"HITS  {pane.cursor + 1}/{len(pane.hits)}")

    def _chrome_line(self) -> str:
        total = self.digest.get("total") or 0
        review = self.digest.get("needs_review") or 0
        matches = f"  matches {self._hit_count}" if self._hit_count else ""
        return f"saved {total}  review {review}{matches}"

    def _meter_text(self) -> str:
        cats = self.digest.get("categories") or []
        return "categories\n" + category_meters(cats, width=14)

    def _show_card(self, hit: SearchHit) -> None:
        text = display_tweet_text(hit.tweet_text or "")
        links = "\n".join(hit.outbound_links) or "(no outbound links)"
        body = (
            f"{hit.status_id}  @{hit.author_handle or '-'}  {hit.category or '-'}\n\n"
            f"{text}\n\n"
            f"{hit.status_url}\n"
            f"{links}\n\n"
            "enter opens the tweet in your browser\n"
            "l opens the first outbound link"
        )
        self.query_one("#card", Static).update(body)

    def _refresh_graph(self) -> None:
        hit = self.center
        if hit is None:
            self._neighbors = []
            self._paint_graph()
            return
        self._neighbors = related_bookmarks(self.store, hit.status_id, limit=8)
        self._paint_graph()

    def _paint_graph(self) -> None:
        pane = self.query_one("#graph", Static)
        if self.center is None:
            pane.update("search first — related tweets show up here")
            return
        if not self._neighbors:
            pane.update("no related tweets (same url / domain / author)")
            return
        label = f"@{self.center.author_handle} {display_tweet_text(self.center.tweet_text or '')}"
        if self.graph_mode == "mermaid":
            pane.update(mermaid_flowchart(self.center.status_id, label, self._neighbors))
            return
        if self.graph_mode == "map":
            contacts = [
                (f"@{hit.author_handle}" if hit.author_handle else hit.status_id, hit.kind)
                for hit in self._neighbors[:8]
            ]
            pane.update(
                sonar_scope(
                    width=48,
                    height=16,
                    tick=0,
                    center_label=f"@{self.center.author_handle or '-'}",
                    contacts=contacts,
                )
            )
            return
        pane.update(ascii_flowchart(self.center.status_id, label, self._neighbors))


def run_tui(store) -> int:
    app = TweetKBApp(store)
    app.run()
    return 0
