"""MelodySheet Windows launcher.

Started by the Inno Setup-installed shortcut. Boots a single FastAPI process
on 127.0.0.1, opens the default browser at it, and keeps running until the
user closes the console window or quits via the tray menu.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

DEFAULT_PORT = 8765  # avoid 8000/3000 to dodge collisions with dev tooling


def _running_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _resource_root() -> Path:
    if _running_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def _ensure_runtime_paths() -> None:
    """Make sure runtime dirs (storage, jobs) live under the user's profile
    rather than Program Files (which is read-only without admin)."""
    appdata = os.getenv("APPDATA") or os.getenv("XDG_DATA_HOME") or str(Path.home() / ".melodysheet")
    base = Path(appdata) / "MelodySheet"
    storage = base / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MELODYSHEET_STORAGE_PATH", str(storage))

    # Bundled ffmpeg lives next to the frozen exe; surface it on PATH so the
    # subprocess call in music_processing finds it.
    if _running_frozen():
        bundled = _resource_root() / "ffmpeg"
        if bundled.exists():
            os.environ["PATH"] = str(bundled) + os.pathsep + os.environ.get("PATH", "")

    # CORS isn't strictly needed when serving frontend same-origin, but allow
    # the bundled frontend to talk to the API explicitly anyway.
    os.environ.setdefault(
        "MELODYSHEET_CORS_ORIGINS",
        f"http://127.0.0.1:{DEFAULT_PORT},http://localhost:{DEFAULT_PORT}",
    )

    # Point the static frontend resolver at the bundle.
    web_dir = _resource_root() / "web"
    if web_dir.exists():
        os.environ.setdefault("MELODYSHEET_WEB_DIR", str(web_dir))


def _pick_port(preferred: int) -> int:
    for candidate in (preferred, preferred + 1, preferred + 2, preferred + 3, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", candidate))
            except OSError:
                continue
            return probe.getsockname()[1]
    return preferred


def _open_browser_when_ready(port: int) -> None:
    deadline = time.monotonic() + 30
    target = f"http://127.0.0.1:{port}/"
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                webbrowser.open(target, new=2)
                return
        except OSError:
            time.sleep(0.25)


def main() -> int:
    _ensure_runtime_paths()
    port = _pick_port(DEFAULT_PORT)

    # When frozen, the bundled `apps/api` is the importable working dir.
    if _running_frozen():
        api_dir = _resource_root() / "apps" / "api"
        if api_dir.exists():
            sys.path.insert(0, str(api_dir))

    import uvicorn

    threading.Thread(target=_open_browser_when_ready, args=(port,), daemon=True).start()

    print(f"MelodySheet running on http://127.0.0.1:{port}/")
    print("Close this window to stop the app.")
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
