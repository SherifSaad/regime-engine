"""
Phase 7 Step 2: File-watching for universe.json.
Schedulers auto-reload on change without restart.
"""
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UNIVERSE_PATH = PROJECT_ROOT / "universe.json"

# Set to True when universe.json is modified; schedulers check and reload
universe_changed = False


class UniverseWatcher(FileSystemEventHandler):
    """Watches universe.json for changes."""

    def on_modified(self, event):
        global universe_changed
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.name == "universe.json" and path.resolve() == UNIVERSE_PATH.resolve():
            universe_changed = True
            print("universe.json changed – reloading on next cycle...")


def start_universe_watcher() -> None:
    """Start watching universe.json. Run in a background thread."""
    watch_dir = str(UNIVERSE_PATH.parent)
    event_handler = UniverseWatcher()
    observer = Observer()
    observer.schedule(event_handler, path=watch_dir, recursive=False)
    observer.start()
    print("Watching universe.json for changes...")
    try:
        while observer.is_alive():
            observer.join(timeout=1)
    except Exception:
        observer.stop()
    observer.join()


def check_and_clear_universe_changed() -> bool:
    """Return True if universe changed, and clear the flag."""
    global universe_changed
    if universe_changed:
        universe_changed = False
        return True
    return False
