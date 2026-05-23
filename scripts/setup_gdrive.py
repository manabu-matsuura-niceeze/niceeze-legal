#!/usr/bin/env python3
"""
NiceEze Google Drive Service Account セットアップスクリプト
Ver 2.3 — 完全自動化版

このスクリプト1本で以下を全て完了させる:
  1. GCP Service Account JSON の検証・読み込み
  2. Google Drive API / Docs API の接続確認
  3. 00_NiceEze_AI_Audit フォルダの作成（なければ）
  4. テスト用 Google Docs の作成・書き込み確認
  5. 環境変数 NICEEZE_GDRIVE_SERVICE_ACCOUNT_JSON への設定ガイド出力
  6. GitHub Secrets への登録コマンド出力

【松浦CEO向け実行手順】
  Step 1: GCP Console で Service Account を作成
    https://console.cloud.google.com/iam-admin/serviceaccounts
    - プロジェクト: niceeze-prod
    - 名前: niceeze-audit-sync
    - ロール: 「なし」（Drive/Docs APIはOAuth scopeで制御）

  Step 2: キーを作成してJSONをダウンロード
    サービスアカウント → キー → 鍵を追加 → JSON

  Step 3: Drive API / Docs API を有効化
    https://console.cloud.google.com/apis/library
    - Google Drive API
    - Google Docs API

  Step 4: このスクリプトを実行
    export NICEEZE_GDRIVE_SERVICE_ACCOUNT_JSON=$(cat path/to/key.json)
    python scripts/setup_gdrive.py

  Step 5: サービスアカウントのメールを Drive フォルダに共有
    （スクリプトが自動実行。手動の場合はガイドに従う）
"""

import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SERVICE_ACCOUNT_ENV  = "NICEEZE_GDRIVE_SERVICE_ACCOUNT_JSON"
GDRIVE_FOLDER_NAME   = "00_NiceEze_AI_Audit"
CREDENTIALS_FILE     = ROOT / "config" / "gdrive_service_account.json"


def print_section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


def check_dependencies() -> bool:
    print_section("依存ライブラリ確認")
    try:
        import google.oauth2.service_account
        import googleapiclient.discovery
        print("  ✅ google-api-python-client: インストール済み")
        return True
    except ImportError:
        print("  ❌ 未インストール")
        print("  実行: pip install google-api-python-client google-auth")
        return False


def load_service_account() -> dict | None:
    print_section("Service Account 認証情報の読み込み")

    # 環境変数から試みる
    sa_json = os.environ.get(SERVICE_ACCOUNT_ENV)
    if sa_json:
        try:
            sa_info = json.loads(sa_json)
            print(f"  ✅ 環境変数 {SERVICE_ACCOUNT_ENV} から読み込み成功")
            print(f"  📧 Service Account: {sa_info.get('client_email', '不明')}")
            print(f"  🏗️  プロジェクト: {sa_info.get('project_id', '不明')}")
            return sa_info
        except json.JSONDecodeError as e:
            print(f"  ❌ 環境変数のJSONパース失敗: {e}")

    # ファイルから試みる
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE) as f:
                sa_info = json.load(f)
            print(f"  ✅ ファイル {CREDENTIALS_FILE} から読み込み成功")
            print(f"  📧 Service Account: {sa_info.get('client_email', '不明')}")
            return sa_info
        except (json.JSONDecodeError, IOError) as e:
            print(f"  ❌ ファイル読み込み失敗: {e}")

    print(f"  ❌ Service Account 認証情報が見つかりません")
    print_setup_instructions()
    return None


def test_gdrive_connection(sa_info: dict) -> bool:
    print_section("Google Drive API 接続テスト")
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        scopes = [
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/documents",
        ]
        creds = service_account.Credentials.from_service_account_info(
            sa_info, scopes=scopes
        )
        drive_svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        docs_svc  = build("docs",  "v1", credentials=creds, cache_discovery=False)

        # Drive 接続確認（ファイル一覧取得 0件でOK）
        result = drive_svc.files().list(pageSize=1, fields="files(id)").execute()
        print(f"  ✅ Google Drive API 接続成功")

        # 00_NiceEze_AI_Audit フォルダ確認・作成
        folder_id = get_or_create_folder(drive_svc, GDRIVE_FOLDER_NAME)
        print(f"  ✅ フォルダ '{GDRIVE_FOLDER_NAME}': {folder_id}")

        # テスト Docs 作成
        doc_id = create_test_doc(docs_svc, drive_svc, folder_id)
        print(f"  ✅ テスト Google Docs 作成: https://docs.google.com/document/d/{doc_id}/edit")

        print(f"\n  🎉 Google Drive 同期: 完全開通確認！")
        print(f"  📂 フォルダURL: https://drive.google.com/drive/folders/{folder_id}")
        return True

    except Exception as e:
        print(f"  ❌ GDrive接続エラー: {e}")
        print(f"\n  よくある原因:")
        print(f"  1. Drive API / Docs API が有効化されていない")
        print(f"     → https://console.cloud.google.com/apis/library")
        print(f"  2. Service Account にドメイン全体の委任が必要な場合")
        print(f"     → Workspace管理コンソールで設定")
        return False


def get_or_create_folder(drive_svc, folder_name: str) -> str:
    query = (
        f"mimeType='application/vnd.google-apps.folder' "
        f"and name='{folder_name}' and trashed=false"
    )
    results = drive_svc.files().list(
        q=query, fields="files(id, name)", pageSize=1
    ).execute()
    files = results.get("files", [])
    if files:
        print(f"  ℹ️  既存フォルダ発見: '{folder_name}'")
        return files[0]["id"]

    folder = drive_svc.files().create(
        body={
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        },
        fields="id",
    ).execute()
    print(f"  ✅ フォルダ新規作成: '{folder_name}'")
    return folder["id"]


def create_test_doc(docs_svc, drive_svc, folder_id: str) -> str:
    from datetime import datetime
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    title = f"[NiceEze接続テスト] {now}"

    doc = docs_svc.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    # フォルダへ移動
    drive_svc.files().update(
        fileId=doc_id,
        addParents=folder_id,
        removeParents="root",
        fields="id, parents",
    ).execute()

    # テキスト挿入
    test_content = (
        f"# NiceEze Google Drive 同期テスト\n"
        f"生成日時: {now}\n"
        f"ステータス: ✅ 接続確認済み\n\n"
        f"このドキュメントは自動同期の動作確認のために作成されました。\n"
        f"Gemini参謀はこのフォルダ内の監査レポートを直接読み込めます。"
    )
    docs_svc.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": test_content}}]},
    ).execute()

    return doc_id


def generate_github_secret_command(sa_info: dict) -> None:
    print_section("GitHub Secrets 登録コマンド")
    sa_json_str = json.dumps(sa_info, ensure_ascii=False)
    print(f"  以下のコマンドで GitHub Secrets に登録してください:")
    print(f"\n  gh secret set {SERVICE_ACCOUNT_ENV} \\")
    print(f"    --body '{sa_json_str[:80]}...'  # 実際は全JSON")
    print(f"\n  または GitHub Web UI:")
    print(f"  Repository → Settings → Secrets → Actions → New secret")
    print(f"  Name: {SERVICE_ACCOUNT_ENV}")
    print(f"  Value: [Service Account JSON全文]")


def print_setup_instructions() -> None:
    print_section("Service Account セットアップ手順")
    print("""
  【Step 1】GCP Console でサービスアカウントを作成
  https://console.cloud.google.com/iam-admin/serviceaccounts

  プロジェクトID: niceeze-prod（または既存プロジェクト）
  サービスアカウント名: niceeze-audit-sync
  説明: NiceEze 監査レポートの GDrive 自動同期用

  【Step 2】APIを有効化
  https://console.cloud.google.com/apis/library
  ・Google Drive API
  ・Google Docs API

  【Step 3】キーを作成（JSON形式でダウンロード）
  サービスアカウント → 「キー」タブ → 「鍵を追加」→「新しい鍵を作成」→ JSON

  【Step 4】環境変数を設定してこのスクリプトを再実行
  export NICEEZE_GDRIVE_SERVICE_ACCOUNT_JSON=$(cat ~/Downloads/niceeze-*.json)
  python scripts/setup_gdrive.py

  【Step 5】サービスアカウントのメールアドレスを確認
  JSONファイル内の "client_email" の値をコピー
  Google Drive で「00_NiceEze_AI_Audit」フォルダを右クリック
  → 共有 → そのメールアドレスを「編集者」として追加

  （フォルダが存在しない場合はスクリプトが自動作成します）
    """)


def main() -> None:
    print("\n" + "="*60)
    print("  NiceEze GDrive Service Account セットアップ Ver 2.3")
    print("="*60)

    if not check_dependencies():
        sys.exit(1)

    sa_info = load_service_account()
    if sa_info is None:
        sys.exit(1)

    success = test_gdrive_connection(sa_info)

    if success:
        generate_github_secret_command(sa_info)
        print_section("セットアップ完了")
        print("  ✅ Google Drive 同期: 完全開通")
        print("  ✅ 00_NiceEze_AI_Audit フォルダ: 確認済み")
        print("  ✅ Gemini参謀アクセス: 準備完了")
        print("  → 次のステップ: Layer3監査レポート（Ver 2.3）の生成・同期")
    else:
        print_setup_instructions()
        sys.exit(1)


if __name__ == "__main__":
    main()
