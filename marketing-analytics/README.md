# NiceEze マーケティング KPI 自動収集システム

DEV-MKT-001 v1.0 — Phase 1実装済み

## Phase 1: X API + Drive保存 + Slack通知

```bash
# dry-runで動作確認
PYTHONPATH=. python src/main.py --dry-run

# テスト実行
PYTHONPATH=. python -m pytest tests/ --tb=short -q
```

## 必要な環境変数（GCP Secret Manager）

| 変数名 | 用途 |
|---|---|
| X_BEARER_TOKEN | X API Bearer Token |
| GOOGLE_DRIVE_SA_JSON | Drive書き込み用SA JSON |
| SLACK_WEBHOOK_URL | Slack Incoming Webhook |

## 実行スケジュール

GCP Cloud Run Jobs — 毎日 JST 06:00（UTC 21:00）
