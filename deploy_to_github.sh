#!/bin/bash
# ============================================================
# NiceEze — Mac一発全自動デプロイスクリプト
# 使い方: ZIPを解凍した niceeze/ フォルダ内で実行
#   bash deploy_to_github.sh
# ============================================================
set -euo pipefail

# ── 色付きログ ──────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
head() { echo -e "\n${BOLD}${CYAN}$1${NC}"; echo "────────────────────────────────────────"; }

head "NiceEze GitHub 一発デプロイスクリプト"

# ── Step 0: 実行場所の確認 ──────────────────────────────────
if [ ! -f "requirements.txt" ] || [ ! -d "src" ]; then
  err "このスクリプトは niceeze/ フォルダの中から実行してください。
  例: cd ~/Downloads/niceeze && bash deploy_to_github.sh"
fi
log "実行ディレクトリ確認: $(pwd)"

# ── Step 1: GitHub リポジトリURLの入力 ──────────────────────
head "Step 1: GitHubリポジトリURLの確認"
echo ""
echo "  GitHubで空のリポジトリを作成し、そのURLを入力してください。"
echo "  例: https://github.com/matsuura-ceo/niceeze"
echo "  (まだ作成していない場合は https://github.com/new から作成してください)"
echo ""
read -rp "  GitHubリポジトリURL: " REPO_URL

# URL形式の簡易チェック
if [[ ! "$REPO_URL" =~ ^https://github\.com/.+/.+ ]]; then
  err "URLが正しくありません。https://github.com/ユーザー名/リポジトリ名 の形式で入力してください。"
fi
log "リポジトリURL: $REPO_URL"

# ── Step 2: git コマンド確認 ────────────────────────────────
head "Step 2: Git 環境確認"
if ! command -v git &>/dev/null; then
  err "git がインストールされていません。
  Xcode Command Line Tools をインストールしてください:
    xcode-select --install"
fi
log "git バージョン: $(git --version)"

# ── Step 3: GitHub CLI または Personal Access Token の選択 ──
head "Step 3: GitHub 認証方法の選択"
echo ""
echo "  推奨: GitHub CLI（gh）を使う方法 — ブラウザで1クリック認証"
echo ""

AUTH_METHOD=""
if command -v gh &>/dev/null; then
  echo "  → GitHub CLI (gh) が見つかりました。ブラウザ認証を使用します。"
  AUTH_METHOD="gh"
  # 未認証なら認証フローを起動
  if ! gh auth status &>/dev/null 2>&1; then
    warn "GitHub CLIの認証が必要です。ブラウザが開きます..."
    gh auth login --web --git-protocol https
  fi
  log "GitHub CLI 認証済み"
else
  warn "GitHub CLI (gh) が見つかりません。Personal Access Token を使用します。"
  AUTH_METHOD="token"
  echo ""
  echo "  GitHub Personal Access Token (PAT) が必要です。"
  echo "  まだ作成していない場合:"
  echo "    1. https://github.com/settings/tokens/new を開く"
  echo "    2. Expiration: 7 days"
  echo "    3. Scopes: repo にチェック"
  echo "    4. Generate token をクリックしてコピー"
  echo ""
  read -rsp "  Personal Access Token を貼り付け（入力は非表示）: " GH_TOKEN
  echo ""
  if [ -z "$GH_TOKEN" ]; then
    err "トークンが入力されませんでした。"
  fi
  log "トークン入力確認"
fi

# ── Step 4: git 初期化 & コミット ───────────────────────────
head "Step 4: Git 初期化 & 全ファイルをコミット"

# 既存の .git があれば削除して再初期化
if [ -d ".git" ]; then
  warn "既存の .git ディレクトリを削除して再初期化します..."
  rm -rf .git
fi

git init -b main
log "git init 完了 (ブランチ: main)"

# git config（グローバル未設定の場合のみ）
if ! git config user.email &>/dev/null; then
  read -rp "  Gitメールアドレス（GitHub登録済みのもの）: " GIT_EMAIL
  git config user.email "$GIT_EMAIL"
fi
if ! git config user.name &>/dev/null; then
  read -rp "  Git名前: " GIT_NAME
  git config user.name "$GIT_NAME"
fi

git add -A
log "全ファイルをステージング"

git commit -m "feat: NiceEze Ver 2.3 初期デプロイ

- GCPネイティブ構成（Cloud SQL + Memorystore Redis + Cloud Run）
- Layer3 LIFF通知連携（LinePushGuard + LiffPullHandler）
- 多層監査エンジン Ver 2.2（pytest 52件 / bandit HIGH=0 MEDIUM=0）
- GitHub Actions ワークフロー（Layer1-3 + CEO承認ゲート）
- Google Drive 自動同期（00_NiceEze_AI_Audit）
- FinOps: 0.2938円/荷物（5円の壁余裕94.1%）"
log "コミット完了"

# ── Step 5: リモート設定 & プッシュ ─────────────────────────
head "Step 5: GitHub へプッシュ"

# リモートURLを認証方法に合わせて設定
if [ "$AUTH_METHOD" = "token" ]; then
  # トークンをURLに埋め込む（ローカルのみ・push后すぐ削除）
  GITHUB_USER=$(echo "$REPO_URL" | sed 's|https://github.com/||' | cut -d'/' -f1)
  REPO_NAME=$(echo "$REPO_URL" | sed 's|https://github.com/||' | cut -d'/' -f2 | sed 's/\.git$//')
  REMOTE_URL="https://${GH_TOKEN}@github.com/${GITHUB_USER}/${REPO_NAME}.git"
else
  REMOTE_URL="$REPO_URL"
fi

git remote add origin "$REMOTE_URL"
log "リモート設定: $REPO_URL"

git push -u origin main --force
log "プッシュ完了"

# トークンURLをクリーン（セキュリティ: 認証情報をremoteから削除）
if [ "$AUTH_METHOD" = "token" ]; then
  git remote set-url origin "$REPO_URL"
  log "セキュリティ: リモートURLからトークンを削除"
fi

# ── Step 6: Actions起動確認 ─────────────────────────────────
head "Step 6: GitHub Actions 起動確認"

ACTIONS_URL="${REPO_URL}/actions"
echo ""
log "プッシュ成功！GitHub Actions が自動起動します。"
echo ""
echo -e "  ${BOLD}▼ 今すぐActionsを確認${NC}"
echo "  $ACTIONS_URL"
echo ""
echo "  ブラウザで開く（Mac）:"
echo "  open $ACTIONS_URL"
echo ""

# macOS なら自動でブラウザを開く
if command -v open &>/dev/null; then
  read -rp "  ブラウザでActions画面を自動で開きますか？ [Y/n]: " OPEN_BROWSER
  if [[ "${OPEN_BROWSER:-Y}" =~ ^[Yy]$ ]]; then
    open "$ACTIONS_URL"
    log "ブラウザを開きました"
  fi
fi

# ── 完了サマリー ──────────────────────────────────────────────
head "🎉 デプロイ完了"
echo ""
echo -e "  ${GREEN}${BOLD}全ファイルが GitHub main ブランチに反映されました。${NC}"
echo ""
echo "  ▼ GitHub Actions が自動実行する内容"
echo "  1. 🔍 Layer1: pytest 52件 + bandit + pip-audit"
echo "  2. 🧠 Layer2: FinOps監査（0.2938円/荷物）+ RLS/PII検証"
echo "  3. ☁️  Layer3: 監査レポート生成 → Google Drive 00_NiceEze_AI_Audit へ同期"
echo "  4. 🔐 CEO承認ゲート: Approve後に本番デプロイ"
echo ""
echo "  ▼ Actions画面"
echo "  $ACTIONS_URL"
echo ""
echo "  ▼ GDrive同期結果の確認"
echo "  Actions完了後、Summaryに Google Docs URLが表示されます。"
echo ""
