"""Keep the index fresh while you work: watchdog events -> debounce -> one incremental sync.

watchdog (https://pypi.org/project/watchdog/) uses inotify on Linux. Three things make a naive
"re-index on every event" handler fall over, and each has a line below:

1. Bursts. Saving one file in an editor can produce 3-6 events (a temp file, a rename, a
   modify). Copying a folder produces hundreds. -> events are collected and a sync runs only
   after `debounce` seconds of quiet.
2. Noise. Events for excluded paths (.git, .cache, editor swap files) must not even wake the
   indexer. -> each path is checked with the same is_excluded rules before it counts.
3. Moves and deletes. A rename is a delete of the old id plus an add of the new one. -> the
   handler does not try to interpret events: it only says "something changed", and sync()
   computes the real difference from a scan (stat only) and the manifest (plan_sync).

inotify has a per-user watch limit (fs.inotify.max_user_watches, often 65536 or more on
current distributions). A home folder with a huge tree may exceed it; watchdog then raises an
error. Fix: watch fewer roots, exclude big folders, raise the limit with sysctl, or use the
polling observer (--poll), which costs CPU instead of watches.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from . import hooks


class DebouncedChanges:
    """Collects changed paths; `due()` is True after `debounce` seconds without new events."""

    def __init__(self, roots: list[Path], exclude: list[str], debounce: float = 2.0,
                 clock: Callable[[], float] = time.monotonic):
        self.roots = [Path(r).expanduser().resolve() for r in roots]
        self.exclude = exclude
        self.debounce = debounce
        self.clock = clock
        self.pending: set[str] = set()
        self.ignored = 0
        self.last_event: Optional[float] = None
        self.lock = threading.Lock()

    def rel(self, path: str) -> Optional[str]:
        p = Path(path).resolve() if Path(path).exists() else Path(path)
        for r in self.roots:
            try:
                return p.relative_to(r).as_posix()
            except ValueError:
                continue
        return None

    def add(self, path: str, is_directory: bool = False) -> bool:
        rel = self.rel(path)
        if rel is None or rel in ("", "."):
            return False
        probe = rel + "/x" if is_directory else rel
        if hooks.get("is_excluded")(probe, self.exclude) is not None:
            self.ignored += 1
            return False
        with self.lock:
            self.pending.add(rel)
            self.last_event = self.clock()
        return True

    def due(self) -> bool:
        with self.lock:
            return bool(self.pending) and self.last_event is not None and \
                self.clock() - self.last_event >= self.debounce

    def take(self) -> set[str]:
        with self.lock:
            out, self.pending = self.pending, set()
            return out


def make_handler(changes: DebouncedChanges):
    from watchdog.events import FileSystemEventHandler

    class Handler(FileSystemEventHandler):
        def on_any_event(self, event):
            if event.event_type in ("opened", "closed_no_write"):
                return
            changes.add(event.src_path, event.is_directory)
            dest = getattr(event, "dest_path", "")
            if dest:
                changes.add(dest, event.is_directory)

    return Handler()


def watch(index, *, debounce: float = 2.0, poll: bool = False, stop: Optional[threading.Event] = None,
          on_sync: Optional[Callable] = None, tick: float = 0.25) -> None:
    """Run until `stop` is set (or Ctrl+C). Every quiet period with changes triggers index.sync()."""
    if poll:
        from watchdog.observers.polling import PollingObserver as Observer
    else:
        from watchdog.observers import Observer

    roots = [Path(r).expanduser() for r in index.s.roots]
    changes = DebouncedChanges(roots, index.s.exclude, debounce)
    observer = Observer()
    handler = make_handler(changes)
    for r in roots:
        observer.schedule(handler, str(r), recursive=True)
    observer.start()
    stop = stop or threading.Event()
    try:
        while not stop.is_set():
            time.sleep(tick)
            if changes.due():
                paths = changes.take()
                rep = index.sync()
                if on_sync:
                    on_sync(paths, rep)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join(timeout=5)
