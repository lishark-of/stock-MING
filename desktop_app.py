import atexit
import argparse
import html
import inspect
import os
import signal
import socket
import subprocess
import sys
import time
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional


PORT_CANDIDATES = [8501, 8502, 8503, 8504, 8505]
WINDOW_TITLE = "stock-MING 交易工作台"
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900
PROJECT_ROOT = Path(__file__).resolve().parent
ICON_PATH = PROJECT_ROOT / "assets" / "stock_ming_icon.svg"
STREAMLIT_START_TIMEOUT_SECONDS = 60
PREFLIGHT_TIMEOUT_SECONDS = 5
TAIL_LINES = 80
TAIL_CHARS = 12000

_streamlit_proc: Optional[subprocess.Popen] = None
_streamlit_log_handles: list[Any] = []
_streamlit_log_paths: dict[str, Path] = {}


class StartupError(RuntimeError):
    def __init__(
        self,
        reason: str,
        suggestions: Optional[list[str]] = None,
        debug_info: Optional[list[str]] = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.suggestions = suggestions or []
        self.debug_info = debug_info or []


def tail_text(text: str, max_lines: int = TAIL_LINES, max_chars: int = TAIL_CHARS) -> str:
    if not text:
        return ""
    lines = text.splitlines()[-max_lines:]
    tailed = "\n".join(lines)
    if len(tailed) > max_chars:
        return tailed[-max_chars:]
    return tailed


def _tail_file(path: Optional[Path], max_lines: int = TAIL_LINES, max_chars: int = TAIL_CHARS) -> str:
    if not path or not path.exists():
        return ""

    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(size - max_chars * 4, 0))
            content = handle.read().decode("utf-8", errors="replace")
    except OSError as exc:
        return f"无法读取日志尾部：{exc}"

    return tail_text(content, max_lines=max_lines, max_chars=max_chars)


def _startup_log_dir() -> Path:
    if sys.platform == "darwin":
        preferred_dir = Path.home() / "Library" / "Logs" / "stock-MING"
    else:
        preferred_dir = Path(tempfile.gettempdir()) / "stock-MING"

    try:
        preferred_dir.mkdir(parents=True, exist_ok=True)
        return preferred_dir
    except OSError:
        fallback_dir = Path(tempfile.gettempdir()) / "stock-MING"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir


def _new_streamlit_log_paths(port: int) -> dict[str, Path]:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_dir = _startup_log_dir()
    return {
        "stdout": log_dir / f"streamlit-{port}-{timestamp}.out.log",
        "stderr": log_dir / f"streamlit-{port}-{timestamp}.err.log",
    }


def _is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) != 0


def find_available_port(host: str = "127.0.0.1") -> Optional[int]:
    for port in PORT_CANDIDATES:
        if _is_port_available(host, port):
            return port
    return None


def _wait_for_streamlit(port: int, timeout_seconds: int = STREAMLIT_START_TIMEOUT_SECONDS) -> bool:
    url = f"http://127.0.0.1:{port}/"
    start = time.time()
    while time.time() - start < timeout_seconds:
        if _streamlit_proc and _streamlit_proc.poll() is not None:
            return False
        try:
            request = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request, timeout=1.0) as response:
                if 200 <= response.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    return True
        except Exception:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.5)
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    return True
        time.sleep(0.5)
    return False


def _flush_streamlit_logs() -> None:
    for handle in _streamlit_log_handles:
        try:
            handle.flush()
        except OSError:
            pass


def _close_streamlit_logs() -> None:
    global _streamlit_log_handles
    for handle in _streamlit_log_handles:
        try:
            handle.close()
        except OSError:
            pass
    _streamlit_log_handles = []


def _stop_streamlit() -> None:
    global _streamlit_proc
    if not _streamlit_proc:
        _close_streamlit_logs()
        return

    if _streamlit_proc.poll() is None:
        _streamlit_proc.terminate()
        try:
            _streamlit_proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            _streamlit_proc.kill()
            _streamlit_proc.wait(timeout=5)

    _streamlit_proc = None
    _close_streamlit_logs()


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


def _start_streamlit_process(port: int) -> subprocess.Popen:
    global _streamlit_log_handles, _streamlit_log_paths

    _streamlit_log_paths = _new_streamlit_log_paths(port)
    stdout_handle = _streamlit_log_paths["stdout"].open("w", encoding="utf-8", errors="replace")
    stderr_handle = _streamlit_log_paths["stderr"].open("w", encoding="utf-8", errors="replace")
    _streamlit_log_handles = [stdout_handle, stderr_handle]

    return subprocess.Popen(
        _build_streamlit_cmd(port),
        cwd=PROJECT_ROOT,
        stdout=stdout_handle,
        stderr=stderr_handle,
    )


def check_streamlit_import(python_executable: Path) -> None:
    try:
        completed = subprocess.run(
            [str(python_executable), "-c", "import streamlit"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=PREFLIGHT_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise StartupError(
            "Streamlit 导入检查超时。",
            suggestions=[
                "请确认当前 Python 环境没有被损坏。",
                "可以尝试重新安装依赖：python -m pip install -r requirements.txt",
            ],
            debug_info=[f"timeout: {exc}"],
        ) from exc
    except OSError as exc:
        raise StartupError(
            "无法运行 Python 解释器进行 Streamlit 检查。",
            suggestions=["请确认 Python 解释器存在且可执行。"],
            debug_info=[str(exc)],
        ) from exc

    if completed.returncode != 0:
        debug_info = [
            f"return code: {completed.returncode}",
            f"stdout tail:\n{tail_text(completed.stdout)}",
            f"stderr tail:\n{tail_text(completed.stderr)}",
        ]
        raise StartupError(
            "Streamlit 未安装或无法导入。",
            suggestions=[
                "请在项目虚拟环境中安装依赖：.venv/bin/python -m pip install -r requirements.txt",
                "如果使用系统 Python 启动，请确认该 Python 环境已安装 streamlit。",
            ],
            debug_info=debug_info,
        )


def _check_project_venv_if_used(python_executable: Path) -> None:
    venv_dir = PROJECT_ROOT / ".venv"
    venv_python = venv_dir / "bin" / "python"
    python_text = str(python_executable)
    using_project_venv = str(venv_dir) in python_text

    if not using_project_venv:
        return

    if not venv_dir.exists():
        raise StartupError(
            "未找到项目虚拟环境目录 .venv。",
            suggestions=["请先在项目目录创建虚拟环境并安装依赖。"],
            debug_info=[f"expected venv: {venv_dir}"],
        )
    if not venv_python.exists():
        raise StartupError(
            "未找到 .venv/bin/python。",
            suggestions=["请重新创建虚拟环境，或检查 .venv 是否完整。"],
            debug_info=[f"expected python: {venv_python}"],
        )
    if not os.access(venv_python, os.X_OK):
        raise StartupError(
            ".venv/bin/python 不可执行。",
            suggestions=["请修复虚拟环境权限，或重新创建 .venv。"],
            debug_info=[f"expected python: {venv_python}"],
        )


def run_preflight_checks() -> dict[str, Any]:
    debug_info = [
        f"project root: {PROJECT_ROOT}",
        f"python executable: {sys.executable}",
    ]

    if not PROJECT_ROOT.exists() or not PROJECT_ROOT.is_dir():
        raise StartupError(
            "无法识别 stock-MING 项目目录。",
            suggestions=["请确认 desktop_app.py 位于 stock-MING 项目根目录。"],
            debug_info=debug_info,
        )

    if not (PROJECT_ROOT / "desktop_app.py").exists():
        raise StartupError(
            "项目目录中缺少 desktop_app.py。",
            suggestions=["请确认当前目录是完整的 stock-MING 仓库。"],
            debug_info=debug_info,
        )

    app_path = PROJECT_ROOT / "app.py"
    if not app_path.exists():
        raise StartupError(
            "项目目录中缺少 app.py，无法启动 Streamlit 主应用。",
            suggestions=["请确认仓库完整，或恢复 app.py 后重试。"],
            debug_info=debug_info + [f"expected app: {app_path}"],
        )

    python_executable = Path(sys.executable)
    if not python_executable.exists():
        raise StartupError(
            "当前 Python 解释器不存在。",
            suggestions=["请使用有效的 Python 环境重新启动 stock-MING。"],
            debug_info=debug_info,
        )
    if not os.access(python_executable, os.X_OK):
        raise StartupError(
            "当前 Python 解释器不可执行。",
            suggestions=["请检查 Python 文件权限，或改用项目 .venv/bin/python 启动。"],
            debug_info=debug_info,
        )

    _check_project_venv_if_used(python_executable)
    check_streamlit_import(python_executable)

    selected_port = find_available_port()
    if selected_port is None:
        ports_text = ", ".join(str(port) for port in PORT_CANDIDATES)
        raise StartupError(
            f"端口 {ports_text} 都已被占用，无法启动本地桌面服务。",
            suggestions=[
                "请关闭占用这些端口的旧 stock-MING 或 Streamlit 进程。",
                "释放任一端口后重新启动。",
            ],
            debug_info=debug_info + [f"checked ports: {ports_text}"],
        )

    return {
        "project_root": PROJECT_ROOT,
        "python_executable": python_executable,
        "selected_port": selected_port,
        "log_dir": _startup_log_dir(),
    }


def _format_startup_error(error: StartupError) -> str:
    lines = [
        "stock-MING 启动失败",
        "",
        f"失败原因：{error.reason}",
    ]
    if error.suggestions:
        lines.append("")
        lines.append("建议操作：")
        lines.extend(f"- {suggestion}" for suggestion in error.suggestions)
    if error.debug_info:
        lines.append("")
        lines.append("调试信息：")
        lines.extend(error.debug_info)
    return "\n".join(lines)


def render_startup_error_html(error: StartupError) -> str:
    suggestions_html = "".join(
        f"<li>{html.escape(suggestion)}</li>" for suggestion in error.suggestions
    ) or "<li>请检查终端输出后重新启动。</li>"
    debug_text = "\n".join(error.debug_info)
    debug_html = ""
    if debug_text:
        debug_html = f"""
        <details>
          <summary>调试信息</summary>
          <pre>{html.escape(debug_text)}</pre>
        </details>
        """

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>stock-MING 启动失败</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f6f7f9;
      color: #17202a;
    }}
    main {{
      max-width: 760px;
      margin: 56px auto;
      padding: 32px;
      background: #ffffff;
      border: 1px solid #dde2ea;
      border-radius: 10px;
      box-shadow: 0 18px 48px rgba(15, 23, 42, 0.10);
    }}
    h1 {{
      margin: 0 0 18px;
      font-size: 26px;
      letter-spacing: 0;
    }}
    h2 {{
      margin-top: 26px;
      font-size: 16px;
    }}
    .reason {{
      padding: 14px 16px;
      border-radius: 8px;
      background: #fff5f2;
      border: 1px solid #f1c9bd;
      color: #7a2f1b;
      line-height: 1.6;
    }}
    li {{
      margin: 8px 0;
      line-height: 1.55;
    }}
    details {{
      margin-top: 22px;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 260px;
      overflow: auto;
      padding: 14px;
      background: #111827;
      color: #e5e7eb;
      border-radius: 8px;
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>stock-MING 启动失败</h1>
    <div class="reason">{html.escape(error.reason)}</div>
    <h2>建议操作</h2>
    <ul>{suggestions_html}</ul>
    <p>如果问题持续存在，请把调试信息交给 Codex 继续排查。</p>
    {debug_html}
  </main>
</body>
</html>"""


def _load_webview() -> Any:
    try:
        import webview as webview_module
    except Exception as exc:
        raise StartupError(
            "pywebview 未安装或无法导入。",
            suggestions=[
                "请在项目虚拟环境中安装 pywebview：.venv/bin/python -m pip install pywebview",
                "如果使用系统 Python 启动，请确认该 Python 环境能 import webview。",
            ],
            debug_info=[f"python executable: {sys.executable}", f"original error: {exc}"],
        ) from exc
    return webview_module


def show_startup_error(error: StartupError) -> None:
    try:
        webview_module = _load_webview()
    except StartupError as webview_error:
        print(_format_startup_error(error), file=sys.stderr)
        print("\n错误窗口无法打开：", file=sys.stderr)
        print(_format_startup_error(webview_error), file=sys.stderr)
        return

    try:
        webview_module.create_window(
            "stock-MING 启动失败",
            html=render_startup_error_html(error),
            width=760,
            height=620,
        )
        webview_module.start()
    except Exception as exc:
        print(_format_startup_error(error), file=sys.stderr)
        print(f"\n错误窗口显示失败：{exc}", file=sys.stderr)


def _streamlit_failure_error(port: int, timed_out: bool = False) -> StartupError:
    _flush_streamlit_logs()
    return_code = _streamlit_proc.poll() if _streamlit_proc else None
    stdout_path = _streamlit_log_paths.get("stdout")
    stderr_path = _streamlit_log_paths.get("stderr")
    reason = (
        "Streamlit 启动超时，桌面窗口没有等到本地服务。"
        if timed_out
        else "Streamlit 子进程启动后立即退出。"
    )
    debug_info = [
        f"port: {port}",
        f"return code: {return_code}",
        f"stdout log: {stdout_path}",
        f"stderr log: {stderr_path}",
        f"stdout tail:\n{_tail_file(stdout_path)}",
        f"stderr tail:\n{_tail_file(stderr_path)}",
    ]
    return StartupError(
        reason,
        suggestions=[
            "请查看调试信息中的 Streamlit 输出尾部。",
            "如果缺少依赖，请重新安装 requirements.txt。",
            "如果 app.py 有语法错误，请修复后重试。",
        ],
        debug_info=debug_info,
    )


def _supports_icon_argument(webview_module: Any) -> bool:
    try:
        return "icon" in inspect.signature(webview_module.create_window).parameters
    except (TypeError, ValueError):
        return False


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="stock-MING desktop launcher")
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="run startup preflight checks without launching Streamlit or pywebview",
    )
    return parser.parse_args(argv)


def _print_diagnose_success(preflight: dict[str, Any]) -> None:
    print("stock-MING 启动诊断通过")
    print(f"项目目录：{preflight['project_root']}")
    print(f"Python：{preflight['python_executable']}")
    print(f"可用端口：{preflight['selected_port']}")
    print(f"日志目录：{preflight['log_dir']}")
    print("诊断模式未启动 Streamlit，也未打开桌面窗口。")


def main(argv: Optional[list[str]] = None) -> None:
    global _streamlit_proc

    args = _parse_args(argv)
    if args.diagnose:
        try:
            preflight = run_preflight_checks()
        except StartupError as exc:
            print(_format_startup_error(exc), file=sys.stderr)
            raise SystemExit(1) from exc
        _print_diagnose_success(preflight)
        return

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    atexit.register(_stop_streamlit)

    try:
        preflight = run_preflight_checks()
    except StartupError as exc:
        show_startup_error(exc)
        raise SystemExit(1) from exc

    selected_port = preflight["selected_port"]
    app_url = f"http://127.0.0.1:{selected_port}"
    print(f"Starting Streamlit on {app_url}")
    print(f"Startup logs: {_startup_log_dir()}")

    try:
        _streamlit_proc = _start_streamlit_process(selected_port)
    except OSError as exc:
        show_startup_error(
            StartupError(
                "无法启动 Streamlit 子进程。",
                suggestions=["请确认 Python 环境可用，并重新安装 Streamlit 依赖。"],
                debug_info=[str(exc)],
            )
        )
        _stop_streamlit()
        raise SystemExit(1) from exc

    if not _wait_for_streamlit(selected_port):
        timed_out = bool(_streamlit_proc and _streamlit_proc.poll() is None)
        error = _streamlit_failure_error(selected_port, timed_out=timed_out)
        _stop_streamlit()
        show_startup_error(error)
        raise SystemExit(1)

    try:
        webview_module = _load_webview()
    except StartupError as exc:
        show_startup_error(exc)
        _stop_streamlit()
        raise SystemExit(1) from exc

    window_kwargs = {
        "width": WINDOW_WIDTH,
        "height": WINDOW_HEIGHT,
    }
    if ICON_PATH.exists() and _supports_icon_argument(webview_module):
        window_kwargs["icon"] = str(ICON_PATH)

    window = webview_module.create_window(
        WINDOW_TITLE,
        app_url,
        **window_kwargs,
    )
    window.events.closed += lambda: _stop_streamlit()

    try:
        webview_module.start()
    finally:
        _stop_streamlit()


if __name__ == "__main__":
    main()
