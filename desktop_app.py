import atexit
import socket
import subprocess
import sys
import time
from typing import Optional

try:
    import webview
except ImportError:
    print("pip install pywebview")
    raise SystemExit(1)


STREAMLIT_CMD = [
    "streamlit",
    "run",
    "app.py",
    "--server.port",
    "8501",
    "--server.headless",
    "true",
]
APP_URL = "http://localhost:8501"
WINDOW_TITLE = "stock-MING 交易工作台"
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900

_streamlit_proc: Optional[subprocess.Popen] = None


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _wait_for_streamlit(timeout_seconds: int = 60) -> bool:
    start = time.time()
    while time.time() - start < timeout_seconds:
        if _streamlit_proc and _streamlit_proc.poll() is not None:
            return False
        if _is_port_open("127.0.0.1", 8501):
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


def main() -> None:
    global _streamlit_proc
    _streamlit_proc = subprocess.Popen(STREAMLIT_CMD)
    atexit.register(_stop_streamlit)

    if not _wait_for_streamlit():
        _stop_streamlit()
        print("Streamlit did not start successfully on http://localhost:8501")
        raise SystemExit(1)

    window = webview.create_window(
        WINDOW_TITLE,
        APP_URL,
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
    )
    window.events.closed += lambda: _stop_streamlit()
    webview.start()
    _stop_streamlit()


if __name__ == "__main__":
    main()
