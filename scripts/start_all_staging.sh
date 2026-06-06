#!/usr/bin/env bash
set -euo pipefail

# NiceEze 全システム一括起動スクリプト (Ver 1.0)
# 使用方法: bash scripts/start_all_staging.sh
# 停止方法: bash scripts/stop_all_staging.sh

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${ROOT}/logs/staging"
PID_FILE="${ROOT}/logs/staging/.pids"

mkdir -p "${LOG_DIR}"
> "${PID_FILE}"

echo "============================================================"
echo "  NiceEze ステージング環境 一括起動"
echo "  $(date '+%Y-%m-%d %H:%M:%S JST')"
echo "============================================================"
echo ""

# Python実行確認
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "❌ Python が見つかりません"
    exit 1
fi
PYTHON="${PYTHON:-$(command -v python3 || command -v python)}"

# ポート使用確認関数
check_port() {
    local port=$1
    if command -v lsof &>/dev/null; then
        lsof -ti:"${port}" >/dev/null 2>&1 && return 1 || return 0
    fi
    return 0
}

# サービス起動関数
start_service() {
    local name=$1
    local module=$2
    local port=$3
    local emoji=$4

    echo -n "  ${emoji} ${name} (port ${port}): 起動中..."

    if ! check_port "${port}"; then
        echo " ⚠️  ポート ${port} 使用中 — スキップ"
        return
    fi

    cd "${ROOT}"
    "${PYTHON}" -m "${module}" > "${LOG_DIR}/${name}.log" 2>&1 &
    local pid=$!
    echo "${name}:${pid}:${port}" >> "${PID_FILE}"

    # 起動待機（最大10秒）
    local i=0
    while [ $i -lt 10 ]; do
        sleep 1
        if curl -sf "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
            echo " ✅ OK (PID ${pid})"
            return
        fi
        i=$((i+1))
    done
    echo " ⚠️  /health タイムアウト（起動中の可能性）"
}

# 各サービス起動
start_service "RESEARCH"  "src.research.api"    8080 "🔍"
start_service "MARKETING" "src.marketing.api"   8081 "📣"
start_service "GOV"       "src.gov.api"         8082 "📊"
start_service "TRAVEL"    "src.sbds.travel_api" 8083 "✈️ "

echo ""
echo "  📦 SBDS (port 8084): 専用APIはG3実装予定 — スキップ"
echo "  ♻️  SURPLUS (port 8085): 専用APIはG3実装予定 — スキップ"

echo ""
echo "============================================================"
echo "  起動完了サマリー"
echo "============================================================"
echo ""
echo "  システム         URL"
echo "  ─────────────────────────────────────────────"
echo "  🔍 RESEARCH      http://localhost:8080/health"
echo "  📣 MARKETING     http://localhost:8081/health"
echo "  📊 GOV           http://localhost:8082/health"
echo "  ✈️  TRAVEL        http://localhost:8083/health"
echo "  📦 SBDS          未起動（G3予定）"
echo "  ♻️  SURPLUS       未起動（G3予定）"
echo ""
echo "  ポータル: open docs/staging_portal.html"
echo "  デモデータ: python scripts/seed_demo_data.py"
echo "  停止: bash scripts/stop_all_staging.sh"
echo ""
echo "  ログ: ${LOG_DIR}/"
echo "  PID: ${PID_FILE}"
echo "============================================================"
