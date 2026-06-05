# NiceEze RESEARCH・MARKETING 本番デプロイチェックリスト

## 事前確認（ステージング）

- [ ] 全テスト Pass: test_research.py (38件) / test_marketing_integration.py (30件) / test_surplus_gate.py (37件)
- [ ] bandit 0件確認: bandit -r src/ → High:0 Medium:0 Low:0
- [ ] RESEARCH API /health レスポンス確認
- [ ] MARKETING API /health レスポンス確認
- [ ] RESEARCH /price?keyword=test&category=食品・飲料 200 OK
- [ ] MARKETING POST /generate 200 OK (X投稿140字以内確認)
- [ ] Docker healthcheck HEALTHY確認 (research + marketing)
- [ ] nginx proxy /api/research/health → 200 OK
- [ ] nginx proxy /api/marketing/health → 200 OK
- [ ] レスポンスタイム 0.7秒以内確認

## セキュリティ確認（ISMS ISO/IEC 27001:2022）

- [ ] .env.production に実シークレット含まれていないことを確認
- [ ] GCP Secret Manager にKEEPA_API_KEY登録確認（松浦CEO操作）
- [ ] Cloud Run IAM設定確認（最小権限原則）
- [ ] HTTPS設定確認（TLS 1.2以上）
- [ ] API認証設定確認（Cloud Run Identity）
- [ ] PII含まれていないことの最終確認

## FinOps確認

- [ ] ステージング月額コスト試算 ¥5,000以内確認
- [ ] Cloud Run Min instances = 0 設定確認（コスト最小化）
- [ ] FINOPS_MONTHLY_LIMIT_JPY=5000 環境変数設定確認

## 本番デプロイ（CEO承認後のみ実行）

- [ ] **松浦CEO最終承認取得（必須）**
- [ ] GitHub Actions: Deploy to Production 手動トリガー実行
- [ ] Cloud Run デプロイ完了確認
- [ ] 本番 /health エンドポイント確認
- [ ] 監視アラート設定確認（Cloud Monitoring）

## ロールバック手順

- 直前のCloud Runリビジョンに切り戻し: gcloud run services update-traffic
- CHANGELOG_JA.md にロールバック記録

---
**ステータス**: ステージング完了待ち → 本番デプロイ承認待ち（松浦CEO）
**作成日**: 2026-06-05
**作成者**: 自律COO（Claude Code）
