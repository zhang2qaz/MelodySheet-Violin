"""MelodySheet Windows launcher.

Started by the Inno Setup-installed shortcut. Boots a single FastAPI process
on 127.0.0.1, opens the default browser at it, and keeps running until the
user closes the console window.

All stdout/stderr is tee'd to %APPDATA%/MelodySheet/launch.log so that even
if the console window flashes shut on an early crash we still have a trace
to debug from.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

DEFAULT_PORT = 8765  # avoid 8000/3000 to dodge collisions with dev tooling


def _running_frozen() -> bool:
    return getattr(sys, "frozen", False)


def _resource_root() -> Path:
    if _running_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def _appdata_dir() -> Path:
    """Platform-appropriate writable directory for logs + storage."""
    if sys.platform == "darwin":
        # macOS convention: per-user app data under ~/Library/Application Support
        base = Path.home() / "Library" / "Application Support" / "MelodySheet"
    elif os.name == "nt":
        appdata = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        base = Path(appdata) / "MelodySheet"
    else:
        # Linux: XDG_DATA_HOME or ~/.local/share
        xdg = os.getenv("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
        base = Path(xdg) / "MelodySheet"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _log_dir() -> Path:
    """macOS keeps logs separate from data; other OSes co-locate."""
    if sys.platform == "darwin":
        path = Path.home() / "Library" / "Logs" / "MelodySheet"
    else:
        path = _appdata_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


class _Tee:
    """Write to both the original stream (console) and a file."""

    def __init__(self, stream, log_file) -> None:
        self._stream = stream
        self._log = log_file

    def write(self, data: str) -> int:
        try:
            n = self._stream.write(data)
        except Exception:
            n = 0
        try:
            self._log.write(data)
            self._log.flush()
        except Exception:
            pass
        return n

    def flush(self) -> None:
        try:
            self._stream.flush()
        except Exception:
            pass
        try:
            self._log.flush()
        except Exception:
            pass

    def isatty(self) -> bool:
        try:
            return self._stream.isatty()
        except Exception:
            return False


def _install_log_capture() -> Path:
    log_path = _log_dir() / "launch.log"
    try:
        log_file = log_path.open("a", encoding="utf-8")
    except Exception:
        return log_path
    sys.stdout = _Tee(sys.stdout, log_file)
    sys.stderr = _Tee(sys.stderr, log_file)
    import datetime

    log_file.write("\n" + "=" * 70 + "\n")
    log_file.write(f"MelodySheet launch  {datetime.datetime.now().isoformat()}\n")
    log_file.write(f"frozen={_running_frozen()}  python={sys.version.split()[0]}  cwd={os.getcwd()}\n")
    log_file.write(f"_MEIPASS={getattr(sys, '_MEIPASS', '(not frozen)')}\n")
    log_file.write("=" * 70 + "\n")
    log_file.flush()
    return log_path


def _ensure_runtime_paths() -> None:
    storage = _appdata_dir() / "storage"
    storage.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MELODYSHEET_STORAGE_PATH", str(storage))

    if _running_frozen():
        bundled = _resource_root() / "ffmpeg"
        if bundled.exists():
            os.environ["PATH"] = str(bundled) + os.pathsep + os.environ.get("PATH", "")

    os.environ.setdefault(
        "MELODYSHEET_CORS_ORIGINS",
        f"http://127.0.0.1:{DEFAULT_PORT},http://localhost:{DEFAULT_PORT}",
    )

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
    log_path = _install_log_capture()
    try:
        print(f"[launcher] log -> {log_path}")
        _ensure_runtime_paths()
        port = _pick_port(DEFAULT_PORT)

        if _running_frozen():
            api_dir = _resource_root() / "apps" / "api"
            if api_dir.exists():
                sys.path.insert(0, str(api_dir))
                print(f"[launcher] inserted {api_dir} onto sys.path")
            else:
                print(f"[launcher] WARNING: expected api dir not found at {api_dir}")

        print("[launcher] importing uvicorn ...")
        import uvicorn
        print("[launcher] importing main:app ...")
        # Import the app object explicitly so any ImportError surfaces here
        # (rather than disappearing inside uvicorn's worker bootstrap).
        from main import app

        threading.Thread(target=_open_browser_when_ready, args=(port,), daemon=True).start()

        print(f"\nMelodySheet running on http://127.0.0.1:{port}/")
        print("Close this window to stop the app.\n")
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
        )
        return 0
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc()
        sys.stderr.write(
            "\n[launcher] FATAL — see " + str(log_path) + " for full trace.\n"
            "Press Enter to exit...\n"
        )
        try:
            input()
        except EOFError:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
