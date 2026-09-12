from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Static

from .digest import build_digest
from .graphview import ascii_flowchart, category_meters, mermaid_flowchart, sonar_scope
from .normalize import display_tweet_text
from .relations import related_bookmarks
from .search import SearchHit, search_bookmarks


class HitItem(ListItem):
    def __init__(self, hit: SearchHit) -> None:
        snippet = display_tweet_text(hit.tweet_text or hit.snippet or "")[:72]
        handle = f"@{hit.author_handle}" if hit.author_handle else "-"
        super().__init__(Label(f"{hit.status_id}  {handle}  {hit.category or '-'}\n{snippet}"))
        self.hit = hit


class TweetKBApp(App[int]):
    TITLE = "TWEETKB"
    CSS = """
    Screen { background: #020b12; color: #9fddd0; }
    Header { background: #020b12; color: #3ee0c4; }
    Footer { background: #031018; color: #4d7a74; }
    #chrome { height: auto; padding: 0 1; color: #3ee0c4; background: #031820; }
    #search { background: #020b12; border: tall #0e3a36; color: #c8fff4; }
    #meters { height: 8; border: tall #0e3a36; padding: 0 1; color: #3ee0c4; }
    #hits { border: tall #0e3a36; }
    #card { border: tall #3ee0c4; padding: 0 1; color: #d7fff7; }
    #graph { border: tall #0e3a36; padding: 0 1; color: #3ee0c4; }
    ListItem { padding: 0 1; color: #7aaea6; }
    ListItem.-highlight { background: #04332e; color: #3ee0c4; }
    """
    BINDINGS = [
        Binding("q", "quit", "quit"),
        Binding("slash", "focus_search", "search", key_display="/"),
        Binding("g", "toggle_graph", "related view"),
        Binding("enter", "open_related", "related", show=False),
        Binding("o", "open_tweet", "open tweet"),
    ]

    def __init__(self, store: Any) -> None:
        super().__init__()
        self.store = store
        self.graph_mode = "ascii"
        self.center: SearchHit | None = None
        self.digest = build_digest(store, limit=8)
        self._neighbors: list = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield Static(self._chrome_line(), id="chrome")
        yield Input(placeholder="search  rust   from:handle   link:github.com", id="search")
        with Horizontal():
            with Vertical():
                yield Static(self._meter_text(), id="meters")
                yield ListView(id="hits")
            yield Static("search, then pick a hit", id="card")
            yield Static("related tweets for the selected hit", id="graph")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search", Input).focus()

    def action_focus_search(self) -> None:
        self.query_one("#search", Input).focus()

    def action_toggle_graph(self) -> None:
        cycle = {"ascii": "mermaid", "mermaid": "map", "map": "ascii"}
        self.graph_mode = cycle.get(self.graph_mode, "ascii")
        self._paint_graph()

    def action_open_related(self) -> None:
        self._refresh_graph()

    def action_open_tweet(self) -> None:
        hit = self.center
        if not hit or not hit.status_url:
            return
        from .cli import _open_urls

        _open_urls([hit.status_url])

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        query = (event.value or "").strip()
        hits_view = self.query_one("#hits", ListView)
        await hits_view.clear()
        if not query:
            self.query_one("#card", Static).update("type a search")
            return
        try:
            hits = search_bookmarks(self.store, query, limit=40)
        except ValueError as exc:
            self.query_one("#card", Static).update(str(exc))
            return
        if not hits:
            self.query_one("#card", Static).update("no matches")
            return
        for hit in hits:
            await hits_view.append(HitItem(hit))
        hits_view.index = 0
        self.center = hits[0]
        self._show_card(hits[0])
        self._refresh_graph()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, HitItem):
            self.center = item.hit
            self._show_card(item.hit)
            self._refresh_graph()

    def _chrome_line(self) -> str:
        total = self.digest.get("total") or 0
        review = self.digest.get("needs_review") or 0
        return (
            f"TWEETKB    saved {total}    needs_review {review}    "
            f"related={self.graph_mode}    / search  g related view  o open  q"
        )

    def _meter_text(self) -> str:
        cats = self.digest.get("categories") or []
        return "categories\n" + category_meters(cats, width=14)

    def _show_card(self, hit: SearchHit) -> None:
        text = display_tweet_text(hit.tweet_text or "")
        links = "\n".join(hit.outbound_links)
        body = (
            f"{hit.status_id}  @{hit.author_handle or '-'}  {hit.category or '-'}\n"
            f"{text}\n"
            f"{hit.status_url}\n"
            f"{links}"
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
            pane.update("related tweets for the selected hit")
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
