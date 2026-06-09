#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../desktop"
if [ ! -d "node_modules" ]; then
  echo "desktop/node_modules 不存在。请先在 desktop/ 中运行 npm install。"
  exit 1
fi
npm run dev
