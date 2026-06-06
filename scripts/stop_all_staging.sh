#!/usr/bin/env bash
# 全サービス停止スクリプト
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="${ROOT}/logs/staging/.pids"

echo "NiceEze ステージング環境 停止..."
if [ -f "${PID_FILE}" ]; then
    while IFS=: read -r name pid port; do
        if kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" && echo "  停止: ${name} (PID ${pid})"
        fi
    done < "${PID_FILE}"
    rm -f "${PID_FILE}"
fi
echo "停止完了"
