#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"

cd "$PROJECT_ROOT" || {
  echo "Failed to enter project directory: $PROJECT_ROOT"
  exit 1
}

if [ ! -d "${PROJECT_ROOT}/.venv" ]; then
  echo "stock-MING 启动失败：未找到虚拟环境目录：${PROJECT_ROOT}/.venv"
  echo "请先在项目目录创建虚拟环境，并安装 requirements.txt。"
  exit 1
fi

if [ ! -e "$PYTHON_BIN" ]; then
  echo "stock-MING 启动失败：未找到 Python 解释器：$PYTHON_BIN"
  echo "请检查 .venv 是否完整，或重新创建虚拟环境。"
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
