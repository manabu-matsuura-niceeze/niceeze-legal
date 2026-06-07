# NiceEze マーケティング KPI 自動収集システム

Phase 1: X API + Google Drive保存 + Slack通知

## セットアップ

```bash
pip install -r requirements.txt
```

## 環境変数

| 変数名 | 説明 |
|--------|------|
| X_BEARER_TOKEN | X API v2 Bearer Token |
| GOOGLE_DRIVE_SA_JSON | Google Drive Service Account JSON |
| SLACK_WEBHOOK_URL | Slack Incoming Webhook URL |
| DRIVE_FOLDER_ID_AUDIT | Google Drive フォルダID |

## 実行

```bash
# ドライラン（API不使用）
python src/main.py --dry-run

# 本番実行
python src/main.py
```

## テスト

```bash
PYTHONPATH=marketing-analytics python -m pytest marketing-analytics/tests/ --tb=short -q
```
