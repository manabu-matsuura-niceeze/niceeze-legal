"""
NiceEze Google Drive 自動同期モジュール
Ver 2.2

本番: Service Account 認証 → Google Docs として 00_NiceEze_AI_Audit フォルダへ新規作成
開発: MockGoogleDriveSyncer → ローカルファイルに保存しつつ本番相当のURLを模倣
"""

import os
import json
from pathlib import Path
from typing import Optional

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
]

GDRIVE_FOLDER_NAME  = "00_NiceEze_AI_Audit"
SERVICE_ACCOUNT_ENV = "NICEEZE_GDRIVE_SERVICE_ACCOUNT_JSON"
CREDENTIALS_FILE    = Path("./config/gdrive_service_account.json")


class GoogleDriveSyncer:
    """
    本番用。GCP Service Account で認証し、
    Markdown を Google Docs 形式に変換して Drive にアップロードする。

    セットアップ手順（松浦CEO向け）:
      1. GCP Console → IAM → サービスアカウント作成
      2. Drive API / Docs API 有効化
      3. JSON キーをダウンロード
      4. 環境変数 NICEEZE_GDRIVE_SERVICE_ACCOUNT_JSON に JSON 文字列をセット
         または ./config/gdrive_service_account.json に配置
      5. サービスアカウントのメールを 00_NiceEze_AI_Audit フォルダに「編集者」共有
    """

    def __init__(self, credentials):
        if not GDRIVE_AVAILABLE:
            raise RuntimeError(
                "google-api-python-client 未インストール。\n"
                "pip install google-api-python-client google-auth"
            )
        self.drive_svc = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self.docs_svc  = build("docs",  "v1", credentials=credentials, cache_discovery=False)

    @classmethod
    def from_env(cls) -> "GoogleDriveSyncer":
        sa_json = os.environ.get(SERVICE_ACCOUNT_ENV)
        if not sa_json:
            raise ValueError(f"環境変数 {SERVICE_ACCOUNT_ENV} が未設定")
        sa_info = json.loads(sa_json)
        creds   = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)
        return cls(creds)

    @classmethod
    def from_file(cls, path: str = None) -> "GoogleDriveSyncer":
        p = Path(path) if path else CREDENTIALS_FILE
        if not p.exists():
            raise FileNotFoundError(f"Service Account ファイルなし: {p}")
        creds = service_account.Credentials.from_service_account_file(str(p), scopes=SCOPES)
        return cls(creds)

    def upload_as_google_doc(self, content: str, filename: str,
                              folder_name: str = GDRIVE_FOLDER_NAME) -> str:
        folder_id = self._get_or_create_folder(folder_name)
        doc_title = f"[NiceEze監査] {filename}"

        # ① 空の Google Docs を作成
        doc = self.docs_svc.documents().create(body={"title": doc_title}).execute()
        doc_id = doc["documentId"]

        # ② 対象フォルダへ移動
        self.drive_svc.files().update(
            fileId=doc_id,
            addParents=folder_id,
            removeParents="root",
            fields="id, parents",
        ).execute()

        # ③ コンテンツ挿入 + 見出しスタイル適用
        self._write_markdown_to_doc(doc_id, content)

        return f"https://docs.google.com/document/d/{doc_id}/edit"

    def _get_or_create_folder(self, folder_name: str) -> str:
        query = (
            f"mimeType='application/vnd.google-apps.folder' "
            f"and name='{folder_name}' and trashed=false"
        )
        results = self.drive_svc.files().list(
            q=query, fields="files(id, name)", pageSize=1
        ).execute()
        files = results.get("files", [])
        if files:
            return files[0]["id"]
        folder = self.drive_svc.files().create(
            body={"name": folder_name, "mimeType": "application/vnd.google-apps.folder"},
            fields="id",
        ).execute()
        return folder["id"]

    def _write_markdown_to_doc(self, doc_id: str, markdown: str) -> None:
        requests = [{"insertText": {"location": {"index": 1}, "text": markdown}}]
        idx = 1
        style_requests = []
        for line in markdown.split("\n"):
            text_len = len(line) + 1
            if line.startswith("# "):
                style_requests.append(self._heading_style(idx, idx + text_len, "HEADING_1"))
            elif line.startswith("## "):
                style_requests.append(self._heading_style(idx, idx + text_len, "HEADING_2"))
            elif line.startswith("### "):
                style_requests.append(self._heading_style(idx, idx + text_len, "HEADING_3"))
            idx += text_len
        all_requests = requests + style_requests
        if all_requests:
            self.docs_svc.documents().batchUpdate(
                documentId=doc_id, body={"requests": all_requests}
            ).execute()

    @staticmethod
    def _heading_style(start: int, end: int, named_style: str) -> dict:
        return {
            "updateParagraphStyle": {
                "range": {"startIndex": start, "endIndex": end},
                "paragraphStyle": {"namedStyleType": named_style},
                "fields": "namedStyleType",
            }
        }


class MockGoogleDriveSyncer:
    """
    ローカル開発・テスト用モック。
    実ファイルを ./docs/audit/gdrive_mock/{folder_name}/ に保存し、
    本番相当のモック URL を返す。
    """

    MOCK_DIR = Path("./docs/audit/gdrive_mock")
    _MOCK_DOC_ID_COUNTER = 0

    def upload_as_google_doc(self, content: str, filename: str,
                              folder_name: str = GDRIVE_FOLDER_NAME) -> str:
        target = self.MOCK_DIR / folder_name
        target.mkdir(parents=True, exist_ok=True)

        out = target / f"{filename}.md"
        out.write_text(content, encoding="utf-8")

        # 擬似ドキュメントID（モック用途のみ。セキュリティ用途ではない）
        import hashlib
        mock_doc_id = "MOCK_" + hashlib.md5(str(out).encode(), usedforsecurity=False).hexdigest()[:16]
        mock_url = f"https://docs.google.com/document/d/{mock_doc_id}/edit"

        print(f"  [MockDrive] 📁 保存: {out}")
        return mock_url


def get_syncer(use_mock: bool = False) -> Optional[object]:
    """環境に応じてシンサーを返すファクトリ"""
    if use_mock:
        return MockGoogleDriveSyncer()
    if os.environ.get(SERVICE_ACCOUNT_ENV):
        try:
            return GoogleDriveSyncer.from_env()
        except Exception as e:
            print(f"⚠️  GDrive 認証失敗: {e} → MockSyncer に切り替え")
            return MockGoogleDriveSyncer()
    if CREDENTIALS_FILE.exists():
        try:
            return GoogleDriveSyncer.from_file()
        except Exception as e:
            print(f"⚠️  GDrive ファイル認証失敗: {e} → MockSyncer に切り替え")
            return MockGoogleDriveSyncer()
    print("ℹ️  GDrive 認証情報未設定 — MockGoogleDriveSyncer を使用")
    return MockGoogleDriveSyncer()
