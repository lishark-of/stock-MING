#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ -n "${STOCK_MING_PYTHON:-}" ]; then
  PYTHON_BIN="$STOCK_MING_PYTHON"
elif [ -x "${PROJECT_ROOT}/.venv/bin/python" ]; then
  PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(python3 -c 'import sys; print(sys.executable)')"
else
  echo "stock-MING 启动失败：未找到可用 Python。"
  echo "请安装 Python 3，或设置 STOCK_MING_PYTHON=/path/to/python。"
  exit 1
fi

cd "$PROJECT_ROOT" || {
  echo "Failed to enter project directory: $PROJECT_ROOT"
  exit 1
}

if [ ! -e "$PYTHON_BIN" ]; then
  echo "stock-MING 启动失败：未找到 Python 解释器：$PYTHON_BIN"
  echo "请检查 STOCK_MING_PYTHON，或重新创建虚拟环境。"
  exit 1
fi

if [ ! -x "$PYTHON_BIN" ]; then
  echo "stock-MING 启动失败：Python 解释器不可执行：$PYTHON_BIN"
  echo "请修复权限，或重新创建虚拟环境。"
  exit 1
fi

"$PYTHON_BIN" -c "import webview" 2>/tmp/stock-ming-pywebview-error.log
if [ $? -ne 0 ]; then
  echo "stock-MING 启动失败：pywebview 未安装或无法导入。"
  echo "请运行："
  echo "$PYTHON_BIN -m pip install pywebview"
  cat /tmp/stock-ming-pywebview-error.log
  exit 1
fi

"$PYTHON_BIN" "$PROJECT_ROOT/desktop_app.py"
