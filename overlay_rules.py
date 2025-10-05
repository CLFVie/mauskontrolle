from __future__ import annotations

import os
import sys
import threading
import time
from typing import Callable, Set

from PySide6 import QtCore, QtGui, QtWidgets

try:
    from pynput import keyboard
except Exception as exc:  # pragma: no cover
    keyboard = None  # type: ignore


class RulesOverlay(QtWidgets.QWidget):
    """Frameless, always-on-top overlay that shows control rules.

    The overlay is mouse-click-through to avoid interfering with gameplay.
    Visibility is controlled via a global hotkey (emitted from another thread).
    """

    def __init__(self) -> None:
        super().__init__()
        self._is_visible: bool = False
        self._build_ui()
        self._apply_window_flags()
        self._position_window()
        self.hide()

    def _build_ui(self) -> None:
        panel = QtWidgets.QFrame(self)
        panel_layout = QtWidgets.QVBoxLayout(panel)
        panel_layout.setContentsMargins(16, 14, 16, 14)
        panel_layout.setSpacing(8)

        title = QtWidgets.QLabel("Arena Control – Quick Rules")
        title.setStyleSheet("font-weight: 700; font-size: 16px; color: #E8EAED;")

        rules = QtWidgets.QLabel()
        rules.setTextFormat(QtCore.Qt.RichText)
        rules.setWordWrap(True)
        rules.setText(
            """
            <div style='color:#E8EAED; font-size:13px; line-height:1.35;'>
              <ul style='margin:0 0 0 16px; padding:0;'>
                <li><b>Survive first</b>: close if an intercept is possible.</li>
                <li><b>Edge-hug growth</b>: bite 3–6 deep, then close.</li>
                <li><b>Short, fat loops</b>: avoid long skinny runs.</li>
                <li><b>Two-turn return</b>: always 2 quick turns from safety.</li>
                <li><b>Extend only if</b>: T_close + 2 &lt; min T_intercept.</li>
                <li><b>Backcut kills</b>: cross behind outsiders, then close.</li>
                <li><b>Wall pinch</b>: cut perpendicularly near walls.</li>
                <li><b>Bait &amp; snap</b>: fake wide, snap to close.</li>
                <li><b>Don’t mirror pursuers</b>: angle toward your border.</li>
                <li><b>Perimeter sweep</b>: short rhythmic bites auto-punish.</li>
                <li><b>No greed</b>: never 10–15 deep early.</li>
              </ul>
              <div style='margin-top:10px; font-size:12px; color:#9AA0A6;'>
                Toggle overlay: <b>1</b>
              </div>
            </div>
            """
        )

        footer = QtWidgets.QLabel("Press 1 to show/hide. Press Ctrl+C in terminal to quit.")
        footer.setStyleSheet("font-size: 11px; color: #9AA0A6;")

        panel_layout.addWidget(title)
        panel_layout.addWidget(rules)
        panel_layout.addWidget(footer)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(panel)

        self.setStyleSheet(
            """
            QFrame {
                background: rgba(16, 18, 27, 200);
                border-radius: 10px;
                border: 1px solid rgba(255,255,255,0.06);
            }
            """
        )

        self.setFixedWidth(480)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

    def _apply_window_flags(self) -> None:
        flags = (
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        if sys.platform.startswith("linux"):
            # Avoid taskbar entry on some WMs
            flags |= QtCore.Qt.X11BypassWindowManagerHint
        self.setWindowFlags(flags)

    def _position_window(self) -> None:
        screen: QtGui.QScreen = QtWidgets.QApplication.primaryScreen()
        geo = screen.availableGeometry()
        margin = 24
        # Top-left corner
        x = geo.left() + margin
        y = geo.top() + margin
        self.move(x, y)

    @QtCore.Slot()
    def toggle_visibility(self) -> None:
        self._is_visible = not self._is_visible
        if self._is_visible:
            self.show()
            self.raise_()
            self.activateWindow()
        else:
            self.hide()


class HotkeyBridge(QtCore.QObject):
    toggleRequested = QtCore.Signal()


class KeyboardToggleListener:
    """Global hotkey listener using pynput.

    Listens for the '1' key and calls a callback. Debounced to avoid repeats.
    """

    def __init__(self, on_toggle: Callable[[], None]) -> None:
        self._on_toggle = on_toggle
        self._pressed: Set[object] = set()
        self._lock = threading.Lock()
        self._last_toggle_monotonic = 0.0
        self._debounce_seconds = 0.4
        self._listener: keyboard.Listener | None = None if keyboard is None else keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
            suppress=False,  # do not block the key from reaching apps
        )

    def start(self) -> None:
        if self._listener is None:
            print("[overlay] pynput not available. Install requirements or switch to X11.")
            return
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()

    def _on_press(self, key: object) -> None:
        with self._lock:
            self._pressed.add(key)
            if self._is_one_key():
                now = time.monotonic()
                if now - self._last_toggle_monotonic >= self._debounce_seconds:
                    self._last_toggle_monotonic = now
                    self._on_toggle()

    def _on_release(self, key: object) -> None:
        with self._lock:
            self._pressed.discard(key)

    def _is_one_key(self) -> bool:
        if keyboard is None:
            return False
        return any(
            isinstance(k, keyboard.KeyCode) and k.char == "1"
            for k in self._pressed
        )


def _warn_if_wayland() -> None:
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        print("[overlay] Detected Wayland session. Global hotkeys may not work due to compositor restrictions.")
        print("[overlay] If toggle doesn't work, try an X11 session or a compositor that permits global listeners.")


def main() -> int:
    _warn_if_wayland()

    app = QtWidgets.QApplication(sys.argv)
    overlay = RulesOverlay()

    bridge = HotkeyBridge()
    bridge.toggleRequested.connect(overlay.toggle_visibility)

    listener = KeyboardToggleListener(lambda: bridge.toggleRequested.emit())
    listener.start()

    # Show a brief toast-like hint the first time for discoverability
    # Start hidden by default; briefly show and hide after 2 seconds
    def initial_hint() -> None:
        overlay.toggle_visibility()
        QtCore.QTimer.singleShot(2000, overlay.toggle_visibility)

    QtCore.QTimer.singleShot(300, initial_hint)

    try:
        rc = app.exec()
    finally:
        listener.stop()
    return int(rc)


if __name__ == "__main__":
    raise SystemExit(main())
