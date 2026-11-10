"""Versioned progress events and a quiet interactive renderer."""

from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
import unicodedata
from typing import Any, TextIO


PROTOCOL_PREFIX = "TPL_PROGRESS_V1\t"
LEGACY_PREFIX = "MORADINS_PROGRESS_V1\t"
VALID_MODES = {"auto", "plain", "json", "off"}
VALID_EVENTS = {"start", "progress", "complete", "warning", "error", "finish"}
MAX_EVENT_BYTES = 8192
MAX_TEXT_LENGTH = 512


def sanitize_progress_text(value: object, limit: int = MAX_TEXT_LENGTH) -> str:
    clean = "".join(" " if unicodedata.category(ch).startswith("C") else ch for ch in str(value))
    return " ".join(clean.split())[:limit]


def _unicode_supported(stream: TextIO) -> bool:
    try:
        "⠹█░✓".encode(getattr(stream, "encoding", None) or "ascii")
    except (LookupError, UnicodeEncodeError):
        return False
    return True


def _valid_event(value: object) -> bool:
    if (not isinstance(value, dict) or type(value.get("schema_version")) is not int
            or value["schema_version"] != 1 or value.get("event") not in VALID_EVENTS):
        return False
    if any(not isinstance(value.get(key), str) for key in ("phase", "action", "item")):
        return False
    if "detail" in value and not isinstance(value["detail"], str):
        return False
    current, total = value.get("current"), value.get("total")
    if any(not isinstance(n, int) or isinstance(n, bool) or not 0 <= n <= 100_000 for n in (current, total)):
        return False
    return total == 0 or current <= total


def parse_child_progress(line: str) -> dict[str, Any] | None:
    """Accept the shared wire format and the GB10 compatibility prefix."""
    prefix = next((p for p in (PROTOCOL_PREFIX, LEGACY_PREFIX) if line.startswith(p)), None)
    if prefix is None or len(line.encode("utf-8")) > MAX_EVENT_BYTES:
        return None
    try:
        value = json.loads(line[len(prefix):])
    except (ValueError, UnicodeError):
        return None
    if not _valid_event(value):
        return None
    return {
        "schema_version": 1,
        "event": value["event"],
        "phase": sanitize_progress_text(value["phase"]),
        "action": sanitize_progress_text(value["action"]),
        "item": sanitize_progress_text(value["item"]),
        "current": value["current"],
        "total": value["total"],
        **({"detail": sanitize_progress_text(value["detail"])} if value.get("detail") is not None else {}),
    }


def child_progress_event(event: dict[str, Any], *, force: bool = False, stream: TextIO | None = None) -> None:
    """Emit data for the root orchestrator; children never draw terminal lines."""
    if not force and os.environ.get("TPL_PROGRESS_PROTOCOL") != "1":
        return
    payload = {"schema_version": 1, **event}
    if not _valid_event(payload):
        raise ValueError("invalid_progress_event")
    safe = {
        key: sanitize_progress_text(payload[key]) if key in {"phase", "action", "item", "detail"} else payload[key]
        for key in ("schema_version", "event", "phase", "action", "item", "current", "total", "detail")
        if key in payload
    }
    encoded = PROTOCOL_PREFIX + json.dumps(safe, ensure_ascii=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > MAX_EVENT_BYTES:
        raise ValueError("progress_event_too_large")
    print(encoded, file=stream or sys.stderr, flush=True)


def _display_width(text: str) -> int:
    return sum(2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1 for ch in text)


def _fit(text: str, width: int, unicode_ok: bool) -> str:
    if _display_width(text) <= width:
        return text
    suffix = "…" if unicode_ok else ">"
    remaining = max(1, width - 1)
    output = ""
    for ch in text:
        columns = 2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1
        if columns > remaining:
            break
        output += ch
        remaining -= columns
    return output + suffix


class ProgressReporter:
    """One progress line on a TTY; concise phase events elsewhere."""

    def __init__(self, mode: str = "auto", *, stream: TextIO | None = None,
                 terminal_width: int | None = None, is_tty: bool | None = None,
                 unicode_supported: bool | None = None, heartbeat_seconds: float = 30) -> None:
        if mode not in VALID_MODES:
            raise ValueError(f"unsupported progress mode: {mode}")
        self.stream = stream if stream is not None else sys.stderr
        tty = self.stream.isatty() if is_tty is None else is_tty
        self.mode = "tty" if mode == "auto" and tty else "plain" if mode == "auto" else mode
        self.terminal_width = terminal_width
        self.unicode = _unicode_supported(self.stream) if unicode_supported is None else unicode_supported
        self.heartbeat_seconds = heartbeat_seconds
        self.current = 0
        self.total = 0
        self.phase = "prepare"
        self.action = "PREPARE"
        self.item = ""
        self._start = time.monotonic()
        self._last_plain = self._start
        self._last_phase = ""
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._visible = False
        self._paused = False
        self._finished = False
        self._spinner = 0

    def __enter__(self) -> ProgressReporter:
        if self.mode == "tty":
            self._thread = threading.Thread(target=self._animate, daemon=True, name="tpl-progress")
            self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.finish(success=exc is None, detail=str(exc) if exc else None)

    def _write(self, text: str) -> None:
        try:
            self.stream.write(text)
            self.stream.flush()
        except (BrokenPipeError, OSError):
            self.mode = "off"
            self._visible = False

    def _event(self, name: str, detail: str | None = None) -> dict[str, Any]:
        value: dict[str, Any] = {"schema_version": 1, "event": name, "phase": self.phase,
                                 "action": self.action, "item": self.item,
                                 "current": self.current, "total": self.total}
        if detail:
            value["detail"] = sanitize_progress_text(detail)
        return value

    def _emit(self, name: str, detail: str | None = None) -> None:
        if self.mode == "off":
            return
        if self.mode == "tty":
            self._render()
        elif self.mode == "json":
            self._write(json.dumps(self._event(name, detail), ensure_ascii=False, separators=(",", ":")) + "\n")
        else:
            now = time.monotonic()
            if name not in {"warning", "error", "finish", "complete"} and self.phase == self._last_phase and now - self._last_plain < self.heartbeat_seconds:
                return
            self._last_phase, self._last_plain = self.phase, now
            count = f"{self.current}/{self.total} " if self.total else ""
            suffix = f": {sanitize_progress_text(detail)}" if detail else ""
            self._write(f"[{name}] {count}{self.action} {self.item}{suffix}\n")

    def _animate(self) -> None:
        while not self._stop.wait(0.1):
            with self._lock:
                if not self._paused:
                    self._spinner += 1
                    self._render()

    def _render(self) -> None:
        if self._paused or self.mode != "tty":
            return
        spinner = ("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏" if self.unicode else "|/-\\")[self._spinner % (10 if self.unicode else 4)]
        elapsed = int(time.monotonic() - self._start)
        elapsed_text = f"{elapsed // 3600}:{elapsed % 3600 // 60:02d}:{elapsed % 60:02d}" if elapsed >= 3600 else f"{elapsed // 60:02d}:{elapsed % 60:02d}"
        if self.total:
            fraction = min(1, self.current / self.total)
            filled = int(18 * fraction)
            bar = ("█" * filled + "░" * (18 - filled)) if self.unicode else ("#" * filled + "-" * (18 - filled))
            amount = f"{int(fraction * 100):3d}% [{bar}] {self.current}/{self.total}  "
        else:
            amount = ""
        separator = "·" if self.unicode else "-"
        line = f"{spinner} {amount}{self.action} {separator} {self.item}  {elapsed_text}"
        width = self.terminal_width or shutil.get_terminal_size(fallback=(80, 24)).columns
        self._write("\r\x1b[2K" + _fit(line, max(2, width - 1), self.unicode))
        self._visible = self.mode == "tty"

    def _clear(self) -> None:
        if self._visible:
            self._write("\r\x1b[2K")
            self._visible = False

    def pause(self) -> None:
        with self._lock:
            self._paused = True
            self._clear()

    def resume(self) -> None:
        with self._lock:
            self._paused = False
            self._render()

    def begin(self, action: str, item: str, *, phase: str, current: int | None = None,
              total: int | None = None, detail: str | None = None) -> None:
        with self._lock:
            if total is not None:
                self.total = max(0, total)
            self.current = max(0, current if current is not None else self.current + 1)
            if self.total:
                self.current = min(self.current, self.total)
            self.action, self.item, self.phase = map(sanitize_progress_text, (action, item, phase))
            self._emit("start", detail)

    def update(self, action: str, item: str, *, phase: str) -> None:
        with self._lock:
            self.action, self.item, self.phase = map(sanitize_progress_text, (action, item, phase))
            self._emit("progress")

    def complete(self, *, detail: str | None = None) -> None:
        with self._lock:
            self._emit("complete", detail)

    def warning(self, detail: str, *, item: str | None = None) -> None:
        with self._lock:
            if item is not None:
                self.item = sanitize_progress_text(item)
            self._emit("warning", detail)

    def child(self, event: dict[str, Any]) -> None:
        if not _valid_event(event):
            raise ValueError("invalid_progress_event")
        with self._lock:
            self.current, self.total = event["current"], event["total"]
            self.action, self.item, self.phase = map(sanitize_progress_text, (event["action"], event["item"], event["phase"]))
            self._emit(event["event"], event.get("detail"))

    def finish(self, *, success: bool, detail: str | None = None) -> None:
        if self._finished:
            return
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        with self._lock:
            self._finished = True
            if self.mode == "tty":
                self._clear()
                mark = "✓" if success and self.unicode else "OK" if success else "!"
                self._write(f"{mark} {sanitize_progress_text(detail or ('Complete' if success else 'Failed'))}\n")
            else:
                self._emit("finish" if success else "error", detail or ("Complete" if success else "Failed"))
