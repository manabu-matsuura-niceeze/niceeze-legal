"""Slack通知モジュール
アラート発生時のみ通知（通常完了時はDrive保存のみ）
"""
import json
import urllib.request
import urllib.error
from src.config import get_secret

SLACK_CHANNEL = "#marketing-alerts"

class SlackNotifier:
    def __init__(self, webhook_url: str = "", dry_run: bool = False):
        self._url = webhook_url or get_secret("SLACK_WEBHOOK_URL")
        self._dry_run = dry_run
        self._mock_mode = dry_run or not bool(self._url)

    def send_alert(self, alerts: list, date, drive_url: str = "") -> bool:
        """アラートリストをSlackに送信"""
        if not alerts:
            return True

        date_str = date.strftime("%Y-%m-%d")
        alert_lines = "\n".join(f"⚠️ {a.message}" for a in alerts)
        drive_line = f"詳細: {drive_url}" if drive_url else ""
        text = f"[NiceEze MKT Alert] {date_str}\n{alert_lines}"
        if drive_line:
            text += f"\n{drive_line}"

        if self._mock_mode:
            print(f"[DRY-RUN] Slack送信:\n{text}")
            return True

        payload = {"text": text, "channel": SLACK_CHANNEL}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self._url, data=body, method="POST")  # nosec B310
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                return resp.status == 200
        except Exception:  # noqa: BLE001
            return False

    def send_failure_alert(self, error_msg: str) -> bool:
        """全件取得失敗時の緊急アラート"""
        if self._mock_mode:
            print(f"[DRY-RUN] Slack緊急送信: {error_msg}")
            return True
        payload = {"text": f"⛔ [NiceEze MKT] 全KPI取得失敗\n{error_msg}", "channel": SLACK_CHANNEL}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self._url, data=body, method="POST")  # nosec B310
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                return resp.status == 200
        except Exception:  # noqa: BLE001
            return False
