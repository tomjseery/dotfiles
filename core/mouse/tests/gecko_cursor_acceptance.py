#!/usr/bin/env python3
"""Standalone native Firefox cursor acceptance, outside pytest auto discovery.

Every run uses a temporary profile and an owned headless Firefox process. The
profile alone disables APZ autoscroll for deterministic main-thread scrolling.
--source injects the candidate chrome script; --installed instead requires its
startup marker before any injection. System/Marionette access is enabled only
for the test process. No existing browser or profile is used.
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from urllib.parse import quote

type Json = str | int | float | bool | dict[str, Json] | list[Json] | None
SOURCE = Path(__file__).resolve().parents[1] / "apps/gecko/native-cursor.cfg"
MARKER = "return window.__dotfilesAutoscrollCursor === true;"
STATE = """
const browser = gBrowser.selectedBrowser;
const popup = browser._autoScrollPopup;
return {state: popup?.state ?? null, opacity: popup?.style.opacity ?? null,
        active: !!browser._autoScrollBrowsingContext,
        calls: window.__cursorAcceptanceCalls.slice()};
"""


class AcceptanceError(Exception):
    """A browser observation did not satisfy the acceptance contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


def as_object(value: Json) -> dict[str, Json]:
    if not isinstance(value, dict):
        raise AcceptanceError(f"expected browser result object, received {value!r}")
    return value


class Marionette:
    def __init__(self, connection: socket.socket) -> None:
        self.connection = connection
        self.counter = 0
        self.handshake = self.read()

    def read(self) -> Json:
        length = bytearray()
        while True:
            char = self.connection.recv(1)
            if not char:
                raise AcceptanceError("Marionette closed before its frame header")
            if char == b":":
                break
            length.extend(char)
            require(len(length) <= 10 and char.isdigit(), "invalid frame length")
        size = int(length)
        require(0 < size <= 8_000_000, "Marionette frame exceeds the probe limit")
        data = bytearray()
        while len(data) < size:
            chunk = self.connection.recv(size - len(data))
            require(bool(chunk), "Marionette closed inside a frame")
            data.extend(chunk)
        return cast(Json, json.loads(data))

    def command(self, name: str, params: Mapping[str, object]) -> Json:
        self.counter += 1
        data = json.dumps([0, self.counter, name, params]).encode()
        self.connection.sendall(str(len(data)).encode() + b":" + data)
        response = self.read()
        if not isinstance(response, list):
            raise AcceptanceError("Marionette returned a non-list reply")
        require(
            len(response) == 4 and response[:2] == [1, self.counter],
            "unexpected reply id",
        )
        require(response[2] is None, f"{name} failed: {response[2]!r}")
        return response[3]

    def script(self, source: str) -> Json:
        result = as_object(
            self.command("WebDriver:ExecuteScript", {"script": source, "args": []})
        )
        return result.get("value")

    def context(self, value: str) -> None:
        self.command("Marionette:SetContext", {"value": value})

    def pointer(self, x: int, y: int, button: int | None = None) -> None:
        actions: list[dict[str, object]] = [
            {
                "type": "pointerMove",
                "duration": 100,
                "origin": "viewport",
                "x": x,
                "y": y,
            },
        ]
        if button is not None:
            actions += [
                {"type": "pointerDown", "button": button},
                {"type": "pointerUp", "button": button},
            ]
        self.command(
            "WebDriver:PerformActions",
            {
                "actions": [
                    {
                        "type": "pointer",
                        "id": "acceptance-mouse",
                        "parameters": {"pointerType": "mouse"},
                        "actions": actions,
                    }
                ]
            },
        )

    def escape(self) -> None:
        self.command(
            "WebDriver:PerformActions",
            {
                "actions": [
                    {
                        "type": "key",
                        "id": "acceptance-keyboard",
                        "actions": [
                            {"type": "keyDown", "value": "\ue00c"},
                            {"type": "keyUp", "value": "\ue00c"},
                        ],
                    }
                ]
            },
        )

    def wait(self, source: str, description: str) -> Json:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = self.script(source)
            if result:
                return result
            time.sleep(0.05)
        raise AcceptanceError(
            f"timed out waiting for {description}; state={self.script(STATE)!r}"
        )


@contextmanager
def browser_session(firefox: str) -> Iterator[Marionette]:
    with tempfile.TemporaryDirectory(prefix="gecko-cursor-acceptance-") as temporary:
        profile = Path(temporary)
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        (profile / "user.js").write_text(
            f'user_pref("marionette.port", {port});\n'
            'user_pref("browser.shell.checkDefaultBrowser", false);\n'
            'user_pref("apz.autoscroll.enabled", false);\n',
            encoding="utf-8",
        )
        log_path = profile / "browser.log"
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [
                    firefox,
                    "--headless",
                    "--no-remote",
                    "--profile",
                    str(profile),
                    "--marionette",
                    "--allow-system-access",
                    "about:blank",
                ],
                stdout=log,
                stderr=log,
                env={**os.environ, "MOZ_REMOTE_ALLOW_SYSTEM_ACCESS": "1"},
            )
            try:
                deadline = time.monotonic() + 15
                connection = None
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise AcceptanceError(
                            f"owned Firefox exited {process.returncode}"
                        )
                    try:
                        connection = socket.create_connection(
                            ("127.0.0.1", port), timeout=0.3
                        )
                    except OSError:
                        time.sleep(0.1)
                    else:
                        break
                if connection is None:
                    raise AcceptanceError("owned Firefox Marionette startup timeout")
                with connection:
                    connection.settimeout(15)
                    client = Marionette(connection)
                    client.command("WebDriver:NewSession", {"capabilities": {}})
                    yield client
                    client.command("Marionette:Quit", {"flags": ["eAttemptQuit"]})
            except (AcceptanceError, OSError, ValueError) as error:
                raise AcceptanceError(
                    f"{error}\nBrowser log:\n"
                    + log_path.read_text(encoding="utf-8")[-3000:]
                ) from error
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()


def acceptance(client: Marionette, source: Path | None) -> dict[str, object]:
    client.context("chrome")
    result: dict[str, object] = {"mode": "source" if source else "installed"}
    result["version"] = client.script("return Services.appinfo.version;")
    startup_marker = client.script(MARKER)
    if source is None:
        require(startup_marker is True, "installed startup cursor marker is absent")
    else:
        require(
            startup_marker is not True,
            "startup already installed an observer; use --installed",
        )
        require(
            client.script(source.read_text(encoding="utf-8") + "\n" + MARKER) is True,
            "candidate source did not attach its observer",
        )
    result["startup_marker"] = startup_marker
    require(
        client.script(
            "return typeof window.setCursor === 'function' && !!window.gBrowser;"
        )
        is True,
        "Firefox chrome cursor/tab APIs are unavailable",
    )
    prefs = as_object(
        client.script(
            """return {auto:Services.prefs.getBoolPref('general.autoScroll'),
                     paste:Services.prefs.getBoolPref('middlemouse.paste')};"""
        )
    )
    require(
        prefs == {"auto": True, "paste": False},
        f"native mouse preferences differ: {prefs}",
    )
    result["preferences"] = prefs
    client.script("""
window.__cursorAcceptanceCalls = [];
const original = window.setCursor.bind(window);
window.setCursor = cursor => {
  window.__cursorAcceptanceCalls.push(cursor);
  return original(cursor);
};
""")
    client.context("content")
    html = (
        '<html><body style="height:5000px">'
        '<a id="test-link" href="about:blank">Test link</a></body></html>'
    )
    client.command("WebDriver:Navigate", {"url": "data:text/html," + quote(html)})
    link = as_object(
        client.script(
            """const r=document.getElementById('test-link').getBoundingClientRect();
return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)};"""
        )
    )
    require(type(link["x"]) is int and type(link["y"]) is int, "invalid link geometry")
    client.pointer(cast(int, link["x"]), cast(int, link["y"]), 1)
    client.context("chrome")
    client.wait("return gBrowser.tabs.length === 2;", "native middle-click link tab")
    require(
        client.script("return window.__cursorAcceptanceCalls.length;") == 0,
        "middle-click link activated cursor presentation",
    )
    result["link_tabs"] = 2
    # Exercise real middle-click tab close, rather than calling removeTab().
    tab = as_object(
        client.script(
            """const r=gBrowser.tabs[1].getBoundingClientRect();
return {x:Math.round(r.x+r.width/2), y:Math.round(r.y+r.height/2)};"""
        )
    )
    require(type(tab["x"]) is int and type(tab["y"]) is int, "invalid tab geometry")
    client.pointer(cast(int, tab["x"]), cast(int, tab["y"]), 1)
    client.wait("return gBrowser.tabs.length === 1;", "native middle-click tab close")
    require(
        client.script("return window.__cursorAcceptanceCalls.length;") == 0,
        "middle-click tab close activated cursor presentation",
    )
    result["middle_click_tab_close"] = True
    client.context("content")
    client.pointer(300, 200, 1)
    client.context("chrome")
    client.wait(
        """return gBrowser.selectedBrowser._autoScrollPopup?.state === 'open'
               && window.__cursorAcceptanceCalls.includes('n-resize');""",
        "native popup and initial arrow",
    )
    start = as_object(client.script(STATE))
    require(
        start["active"] is True and start["opacity"] == "0",
        f"native popup was not active and transparent: {start}",
    )
    result["start"] = start
    client.script(
        """window.dispatchEvent(new MouseEvent('mousemove', {
  screenX:gBrowser.selectedBrowser._startX,
  screenY:gBrowser.selectedBrowser._startY+200, bubbles:true}));"""
    )
    client.wait(
        "return window.__cursorAcceptanceCalls.at(-1) === 's-resize';", "downward arrow"
    )
    result["move"] = client.script(STATE)
    origin = as_object(
        client.script(
            """return {x:gBrowser.selectedBrowser._startX,
                  y:gBrowser.selectedBrowser._startY};"""
        )
    )
    client.context("content")
    # Feed Firefox's own native main-thread autoscroller, never scrollTo().
    client.script(
        f"""document.dispatchEvent(new MouseEvent('mousemove',{{
  screenX:{origin["x"]}, screenY:{origin["y"]}+200,bubbles:true}}));"""
    )
    client.pointer(300, 400)
    scroll_y = client.wait(
        "return window.scrollY > 0 ? window.scrollY : false;", "native page scrolling"
    )
    require(
        isinstance(scroll_y, (int, float)) and scroll_y > 0,
        "native scrolling made no progress",
    )
    result["scroll_y"] = scroll_y
    client.context("chrome")
    client.escape()
    client.wait(
        """return gBrowser.selectedBrowser._autoScrollPopup?.state === 'closed'
               && window.__cursorAcceptanceCalls.at(-1) === 'auto';""",
        "native Escape cancellation and cursor restoration",
    )
    stop = as_object(client.script(STATE))
    require(
        stop["active"] is False and stop["opacity"] == "",
        f"native cleanup did not restore popup opacity: {stop}",
    )
    result["stop"] = stop
    result["passed"] = True
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--source", type=Path, default=SOURCE)
    mode.add_argument("--installed", action="store_true")
    parser.add_argument("--firefox", default=shutil.which("firefox"))
    parser.add_argument(
        "--json", action="store_true", help="Print a compact JSON result"
    )
    args = parser.parse_args()
    if args.firefox is None:
        parser.error("Firefox is unavailable; pass --firefox PATH")
    try:
        with browser_session(args.firefox) as client:
            result = acceptance(client, None if args.installed else args.source)
    except AcceptanceError as error:
        if args.json:
            print(
                json.dumps(
                    {"passed": False, "failure": str(error)}, separators=(",", ":")
                )
            )
        else:
            print(f"Firefox native cursor acceptance failed: {error}")
        raise SystemExit(1) from error
    print(
        json.dumps(result, separators=(",", ":"))
        if args.json
        else json.dumps(result, indent=2)
    )


if __name__ == "__main__":
    main()
