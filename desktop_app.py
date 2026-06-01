import atexit
import inspect
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import webview
except ImportError as exc:
    print(
        "pywebview import failed. The package name is pywebview, "
        "but the import name is webview.",
        file=sys.stderr,
    )
    print(f"Python executable: {sys.executable}", file=sys.stderr)
    print("Run: python -m pip install pywebview", file=sys.stderr)
    print(f"Original error: {exc}", file=sys.stderr)
    raise SystemExit(1)


PORT_CANDIDATES = [8501, 8502, 8503, 8504, 8505]
WINDOW_TITLE = "stock-MING 交易工作台"
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900
PROJECT_ROOT = Path(__file__).resolve().parent
ICON_PATH = PROJECT_ROOT / "assets" / "stock_ming_icon.svg"

_streamlit_proc: Optional[subprocess.Popen] = None


def _is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) != 0


def _wait_for_streamlit(port: int, timeout_seconds: int = 60) -> bool:
    start = time.time()
    while time.time() - start < timeout_seconds:
        if _streamlit_proc and _streamlit_proc.poll() is not None:
            return False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def _stop_streamlit() -> None:
    global _streamlit_proc
    if not _streamlit_proc:
        return

    if _streamlit_proc.poll() is None:
        _streamlit_proc.terminate()
        try:
            _streamlit_proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            _streamlit_proc.kill()
            _streamlit_proc.wait(timeout=5)

    _streamlit_proc = None


def _signal_handler(signum: int, _frame: object) -> None:
    _stop_streamlit()
    raise SystemExit(130 if signum == signal.SIGINT else 1)


def _build_streamlit_cmd(port: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
        "--client.toolbarMode",
        "minimal",
    ]


def _supports_icon_argument() -> bool:
    try:
        return "icon" in inspect.signature(webview.create_window).parameters
    except (TypeError, ValueError):
        return False


def main() -> None:
    global _streamlit_proc

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    atexit.register(_stop_streamlit)
    selected_port: Optional[int] = None

    for port in PORT_CANDIDATES:
        if not _is_port_available("127.0.0.1", port):
            continue

        app_url = f"http://localhost:{port}"
        print(f"Starting Streamlit on {app_url}")
        _streamlit_proc = subprocess.Popen(_build_streamlit_cmd(port), cwd=PROJECT_ROOT)

        if _wait_for_streamlit(port):
            selected_port = port
            break

        _stop_streamlit()

    if selected_port is None:
        ports_text = ", ".join(str(port) for port in PORT_CANDIDATES)
        print(
            f"Unable to start Streamlit on ports {ports_text}. "
            "Ports may be occupied or unavailable. Please free one and retry."
        )
        raise SystemExit(1)

    app_url = f"http://localhost:{selected_port}"

    window_kwargs = {
        "width": WINDOW_WIDTH,
        "height": WINDOW_HEIGHT,
    }
    if ICON_PATH.exists() and _supports_icon_argument():
        window_kwargs["icon"] = str(ICON_PATH)

    window = webview.create_window(
        WINDOW_TITLE,
        app_url,
        **window_kwargs,
    )
    window.events.closed += lambda: _stop_streamlit()

    try:
        webview.start()
    finally:
        _stop_streamlit()


if __name__ == "__main__":
    main()
