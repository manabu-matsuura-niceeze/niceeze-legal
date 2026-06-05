#!/usr/bin/env bash
# =============================================================================
# NiceEze 自律経営執行システム — GCP IaC セットアップスクリプト
# 用途: 技術責任者が1コマンドで全GCP設定を完了する
# 実行方法:
#   export GCP_PROJECT_ID=serene-bonbon-236821
#   bash docs/deploy/GCP_SETUP_AUTO.sh
#
# 作成日: 2026-06-05
# 作成者: 自律COO（Claude Code）
# =============================================================================

set -euo pipefail

# =============================================================================
# 変数定義
# =============================================================================
PROJECT_ID="${GCP_PROJECT_ID:-serene-bonbon-236821}"
PROJECT_NUMBER="172953916843"
REGION="asia-northeast1"
AR_REPO="niceeze-app"           # Artifact Registry リポジトリ名
SA_NAME="niceeze-deployer"      # サービスアカウント名
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

# =============================================================================
# 前提条件チェック
# =============================================================================
echo ""
echo "=== 前提条件チェック ==="

# gcloud コマンドの存在確認
if ! command -v gcloud &>/dev/null; then
  echo "[ERROR] gcloud コマンドが見つかりません。Google Cloud SDK をインストールしてください。"
  echo "  参考: https://cloud.google.com/sdk/docs/install"
  exit 1
fi
echo "[OK] gcloud コマンド確認"

# GCP_PROJECT_ID 環境変数の設定確認
if [[ -z "${GCP_PROJECT_ID:-}" ]]; then
  echo "[ERROR] 環境変数 GCP_PROJECT_ID が設定されていません。"
  echo "  実行前に以下を設定してください:"
  echo "  export GCP_PROJECT_ID=serene-bonbon-236821"
  exit 1
fi
echo "[OK] GCP_PROJECT_ID=${PROJECT_ID}"

# gcloud 認証確認
if ! gcloud auth print-access-token &>/dev/null; then
  echo "[ERROR] GCP 認証が完了していません。以下を実行してください:"
  echo "  gcloud auth login"
  exit 1
fi
echo "[OK] GCP 認証確認"

# プロジェクト設定
gcloud config set project "${PROJECT_ID}" --quiet
echo "[OK] プロジェクト設定: ${PROJECT_ID}"

# =============================================================================
# Step 1: 必要API 6種の有効化
# =============================================================================
echo ""
echo "=== Step 1: 必要API の有効化 ==="

APIS=(
  "cloudresourcemanager.googleapis.com"
  "artifactregistry.googleapis.com"
  "run.googleapis.com"
  "containerregistry.googleapis.com"
  "secretmanager.googleapis.com"
  "cloudbuild.googleapis.com"
)

for API in "${APIS[@]}"; do
  echo "  有効化中: ${API} ..."
  gcloud services enable "${API}" --project="${PROJECT_ID}" --quiet
  echo "[OK] ${API} 有効化完了"
done

# =============================================================================
# Step 2: サービスアカウント作成・IAMロール付与
# =============================================================================
echo ""
echo "=== Step 2: サービスアカウント作成・IAMロール付与 ==="

# SA作成（既存の場合はスキップ）
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="NiceEze Deployer" \
  --project="${PROJECT_ID}" 2>/dev/null || echo "[SKIP] SA already exists: ${SA_EMAIL}"

echo "[OK] サービスアカウント確認: ${SA_EMAIL}"

# IAMロール5種付与
ROLES=(
  "roles/run.admin"
  "roles/artifactregistry.writer"
  "roles/secretmanager.secretAccessor"
  "roles/cloudbuild.builds.builder"
  "roles/storage.admin"
)

for ROLE in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" --quiet
  echo "[OK] ${ROLE} 付与完了"
done

# =============================================================================
# Step 3: Artifact Registry リポジトリ作成
# =============================================================================
echo ""
echo "=== Step 3: Artifact Registry リポジトリ作成 ==="

gcloud artifacts repositories create "${AR_REPO}" \
  --repository-format=docker \
  --location="${REGION}" \
  --description="NiceEze Docker images" \
  --project="${PROJECT_ID}" 2>/dev/null || echo "[SKIP] Repository already exists: ${AR_REPO}"

echo "[OK] Artifact Registry: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"

# =============================================================================
# Step 4: Cloud Run サービス初期作成
# 初期化のみ（実際のイメージはCI/CDで更新）
# 最小権限原則: --no-allow-unauthenticated 推奨だが、初期確認のため allow-unauthenticated
# =============================================================================
echo ""
echo "=== Step 4: Cloud Run サービス初期作成 ==="

# --- RESEARCH サービス ---
echo "  niceeze-research サービスを確認中..."
if gcloud run services describe niceeze-research \
    --region="${REGION}" \
    --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "[SKIP] niceeze-research は既存です"
else
  echo "  niceeze-research を初期デプロイ中..."
  gcloud run deploy niceeze-research \
    --image="gcr.io/cloudrun/hello" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --platform=managed \
    --allow-unauthenticated \
    --port=8080 \
    --memory=512Mi \
    --cpu=1 \
    --max-instances=3 \
    --set-env-vars="MODULE=research" \
    --quiet
  echo "[OK] niceeze-research デプロイ完了"
fi

# --- MARKETING サービス ---
echo "  niceeze-marketing サービスを確認中..."
if gcloud run services describe niceeze-marketing \
    --region="${REGION}" \
    --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "[SKIP] niceeze-marketing は既存です"
else
  echo "  niceeze-marketing を初期デプロイ中..."
  gcloud run deploy niceeze-marketing \
    --image="gcr.io/cloudrun/hello" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --platform=managed \
    --allow-unauthenticated \
    --port=8080 \
    --memory=512Mi \
    --cpu=1 \
    --max-instances=3 \
    --set-env-vars="MODULE=marketing" \
    --quiet
  echo "[OK] niceeze-marketing デプロイ完了"
fi

# --- GOV サービス ---
echo "  niceeze-gov サービスを確認中..."
if gcloud run services describe niceeze-gov \
    --region="${REGION}" \
    --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "[SKIP] niceeze-gov は既存です"
else
  echo "  niceeze-gov を初期デプロイ中..."
  gcloud run deploy niceeze-gov \
    --image="gcr.io/cloudrun/hello" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --platform=managed \
    --allow-unauthenticated \
    --port=8082 \
    --memory=512Mi \
    --cpu=1 \
    --max-instances=3 \
    --set-env-vars="MODULE=gov" \
    --quiet
  echo "[OK] niceeze-gov デプロイ完了"
fi

# =============================================================================
# Step 5: Secret Manager — KEEPA_API_KEY 登録手順出力
# =============================================================================
echo ""
echo "============================================================"
echo "  【手動操作必要】Secret Manager への API KEY 登録手順"
echo "============================================================"
echo ""
echo "以下のコマンドを実行してKEEPA_API_KEYを登録してください:"
echo ""
echo "  echo -n 'YOUR_KEEPA_API_KEY' | \\"
echo "  gcloud secrets create KEEPA_API_KEY \\"
echo "    --data-file=- \\"
echo "    --project=${PROJECT_ID}"
echo ""
echo "既存のシークレットを更新する場合:"
echo "  echo -n 'YOUR_KEEPA_API_KEY' | \\"
echo "  gcloud secrets versions add KEEPA_API_KEY \\"
echo "    --data-file=- \\"
echo "    --project=${PROJECT_ID}"
echo ""
echo "同様にRakuten/Yahoo APIキーも登録:"
echo "  RAKUTEN_APP_ID / YAHOO_CLIENT_ID"
echo "============================================================"

# =============================================================================
# Step 6: GitHub Actions用 SA キー出力案内
# =============================================================================
echo ""
echo "============================================================"
echo "  【手動操作必要】GitHub Secrets への SA KEY 登録手順"
echo "============================================================"
echo ""
echo "サービスアカウントキーを生成してGitHub Secretsに登録:"
echo ""
echo "  gcloud iam service-accounts keys create /tmp/sa-key.json \\"
echo "    --iam-account=${SA_EMAIL} \\"
echo "    --project=${PROJECT_ID}"
echo ""
echo "  # Base64エンコードしてコピー:"
echo "  cat /tmp/sa-key.json | base64 -w0"
echo ""
echo "  # GitHub Secrets に GCP_SA_KEY として登録:"
echo "  # https://github.com/manabu-matsuura-niceeze/niceeze-legal/settings/secrets/actions"
echo ""
echo "  rm /tmp/sa-key.json  # セキュリティ: 使用後は削除"
echo "============================================================"

# =============================================================================
# 完了サマリー表示
# =============================================================================
echo ""
echo "============================================================"
echo "  GCP セットアップ完了サマリー"
echo "============================================================"
echo "  プロジェクト    : ${PROJECT_ID}"
echo "  リージョン      : ${REGION}"
echo "  Artifact Registry: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"
echo "  SA Email        : ${SA_EMAIL}"
echo "  Cloud Run (RESEARCH) : https://niceeze-research-XXXX-an.a.run.app"
echo "  Cloud Run (MARKETING): https://niceeze-marketing-XXXX-an.a.run.app"
echo "  Cloud Run (GOV)      : https://niceeze-gov-XXXX-an.a.run.app"
echo ""
echo "  次のステップ:"
echo "  1. Secret Manager に API KEY を登録（上記手順参照）"
echo "  2. GitHub Secrets に GCP_SA_KEY を登録（上記手順参照）"
echo "  3. GitHub Actions deploy-production を実行"
echo "============================================================"
