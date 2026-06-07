"""Google Drive KPIレポート保存モジュール
google-api-python-client を使用
Service Account JSON は GOOGLE_DRIVE_SA_JSON 環境変数から取得
"""
import json
import os
from src.config import get_secret, DRIVE_FOLDER_ID_AUDIT

class DriveReporter:
    def __init__(self, dry_run: bool = False):
        self._dry_run = dry_run
        self._service = None
        if not dry_run:
            self._service = self._build_service()

    def _build_service(self):
        """Google Drive API サービスを構築"""
        try:
            from googleapiclient.discovery import build  # type: ignore
            from google.oauth2 import service_account    # type: ignore
            sa_json = get_secret("GOOGLE_DRIVE_SA_JSON")
            if not sa_json:
                return None
            info = json.loads(sa_json)
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/drive.file"]
            )
            return build("drive", "v3", credentials=creds)
        except Exception:  # noqa: BLE001
            return None

    def upload(self, filename: str, content: str, subfolder_path: str) -> str:
        """
        Driveにファイルをアップロード（同名上書き）
        Returns: file URL または dry-run メッセージ
        """
        if self._dry_run or self._service is None:
            print(f"[DRY-RUN] Drive保存: {subfolder_path}/{filename}")
            return f"[DRY-RUN] {subfolder_path}/{filename}"

        folder_id = self._get_or_create_folder(subfolder_path)
        file_id = self._find_existing(filename, folder_id)
        
        from googleapiclient.http import MediaInMemoryUpload  # type: ignore
        media = MediaInMemoryUpload(content.encode("utf-8"), mimetype="text/markdown")
        
        if file_id:
            self._service.files().update(fileId=file_id, media_body=media).execute()
            return f"https://drive.google.com/file/d/{file_id}/view"
        else:
            meta = {"name": filename, "parents": [folder_id]}
            result = self._service.files().create(body=meta, media_body=media, fields="id").execute()
            return f"https://drive.google.com/file/d/{result['id']}/view"

    def _get_or_create_folder(self, subfolder_path: str) -> str:
        """サブフォルダを取得または作成（階層対応）"""
        parent_id = DRIVE_FOLDER_ID_AUDIT
        for name in subfolder_path.split("/"):
            parent_id = self._find_or_create_single_folder(name, parent_id)
        return parent_id

    def _find_or_create_single_folder(self, name: str, parent_id: str) -> str:
        q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and '{parent_id}' in parents and trashed=false"
        res = self._service.files().list(q=q, fields="files(id)").execute()
        files = res.get("files", [])
        if files:
            return files[0]["id"]
        meta = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
        result = self._service.files().create(body=meta, fields="id").execute()
        return result["id"]

    def _find_existing(self, filename: str, folder_id: str) -> str:
        q = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
        res = self._service.files().list(q=q, fields="files(id)").execute()
        files = res.get("files", [])
        return files[0]["id"] if files else ""
