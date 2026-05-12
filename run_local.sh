#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export PYTHONUSERBASE="$PWD/.python-user"

if ! python3 - <<'PY'
import importlib.util

required = {
    "streamlit": "streamlit",
    "yfinance": "yfinance",
    "pandas": "pandas",
    "numpy": "numpy",
    "akshare": "akshare",
    "supabase": "supabase",
    "openai": "openai",
    "feedparser": "feedparser",
    "beautifulsoup4": "bs4",
    "requests": "requests",
}

missing = [pkg for pkg, module in required.items() if importlib.util.find_spec(module) is None]
if missing:
    print("缺少依赖：" + ", ".join(missing))
    print("正在安装 requirements.txt ...")
    raise SystemExit(1)
PY
then
  python3 -m pip install -r requirements.txt
fi

python3 -m streamlit run app.py --server.port 8502
