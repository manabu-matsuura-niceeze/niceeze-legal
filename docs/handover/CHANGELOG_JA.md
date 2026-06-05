# NiceEze 自律経営執行システム — 変更履歴（日本語）

**管理者**: 自律COO（Claude Code）  
**リポジトリ**: manabu-matsuura-niceeze/niceeze-legal  
**更新ルール**: 全変更を即時コミット。Gate完了時はGoogleDrive（00_NiceEze_AI_Audit）へも同期。

---

## [G0-001] 2026-06-04 — 組織設計・レイアウトガバナンス初期構築

### 追加
- `docs/ui/LAYOUT_MASTER.md` (Ver 1.0) — 全7画面レイアウト正本
  - TMS-SET-001, TMS-DRV-001, RES-A01, RES-A02, NEG-SUP-001, NEG-BYR-001, S10
  - font-mono tabular-nums 強制テーブル
  - GeminiのUI権限範囲明記（UI実装禁止・監査/FinOps許可）
- `.github/workflows/layout-guard.yml` — レイアウト保護CI
  - font-mono tabular-nums チェック
  - plan-locked クラス整合性チェック
  - LAYOUT_MASTER未更新でのUI変更をビルド失敗
- `docs/NiceEze_組織設計_開発計画書_承認申請_v2.0.md` — CEO承認申請書
  - 総開発費 ¥2,844万（補助金活用後 ¥1,293万）
  - Phase 1完了目標 2027年2月（3万世帯）
  - Gate制 G0〜G4

### 既存ファイル（Gate 0以前から存在）
- `src/audit/multi_layer_audit.py` (Ver 2.2) — 多層監査エンジン
- `src/db/migrations/001_initial_schema.sql` — PostgreSQL AES-256+RLS
- `src/db/migrations/002_gcp_native_migration.sql` — GCP Cloud SQL移行
- `src/finops/cost_calculator.py` (Ver 2.3) — GCPネイティブFinOps
- `src/gdrive/gdrive_syncer.py` (Ver 2.2) — Google Drive自動同期
- `src/layer3/line_webhook.py` (Ver 2.4) — LINE Webhook + Redis Streams
- `src/layer4/bigquery_pipeline.py` — BigQuery月次アーカイブ

### Google Driveアップロード（00_NiceEze_AI_Audit）
- `NiceEze_システム監査報告書_ISMS適合_SHA256署名_v14.0.md` (ID: 17BSX6EtHV83u8K-KCW4kY_ZF04uN2hra)
- `NiceEze_自律経営執行システムv14.0_実装完了報告書.md` (ID: 1HlAlBOWFVr-nw5bU1YhytxkfJ-nRV-7S)
- `NiceEze_情報システム部門_組織設計_開発計画書_承認申請_v14.2.md` (ID: 1-M5bL__k71cMW730hKhLt7-b4MPqWQEM)

### CEO承認
- **2026-06-05**: PR#2 正式承認・開発着手Go
  - 5部署体制・予算・Phase1目標・GCPサーバーレス・LAYOUT_MASTER 全承認
  - 絶対ルール確定: Gate制厳守 / レイアウト固定 / GeminiのUI禁止 / 不明点即報告

---

## [G0-002] 2026-06-04 — Ver.14.2照合差異レポート作成（Gate 1前必須）

### 追加
- `docs/handover/CHANGELOG_JA.md` — 本ファイル
- `docs/reports/NiceEze_差異照合レポート_v142_vs_v140_20260604.md` — 3ファイル照合レポート
- Google Driveアップロード（00_NiceEze_AI_Audit）: 上記差異レポート

---

## [G1-001] 2026-06-04 — SBDS初期実装（TMS-SET-001 / TMS-DRV-001）

### 追加
- `src/sbds/tms_set_001.py`: 建物マスタ・フロアグリッドエディタ バックエンド
- `src/sbds/tms_drv_001.py`: 配送員スマホ・ルーティングモジュール
- `src/sbds/static/tms_set_001.html`: TMS-SET-001 フロントエンド
- `src/sbds/static/tms_drv_001.html`: TMS-DRV-001 フロントエンド

---

## [G0-004] 2026-06-04 — CEO確定判断5件反映 + TECH-20260604-002提出

### 確定判断
- 判断①C: note.com → G4以降保留
- 判断②B: YouTube → 台本まで自動生成、アップロードは手動
- 判断④A: DWG対応 → 恒久的対象外（DXFのみ）
- 判断⑤A: AR精度 → ±50cm許容
- 判断⑥A: PWAフォールバック → LIFF非対応時はPWA別URL

---

## [INST-001] 2026-06-04 — ドキュメント自動生成体制構築 + SBDS 5ドキュメント v1.0

### 追加
- `docs/SBDS/SBDS_BRD_v1.0.docx` / `SRS_v1.0.docx` / `SEQ_v1.0.pptx` / `UI_v1.0.pptx` / `PHASE_v1.0.pptx`

---

## [SPECIAL-001] 2026-06-04 — RESEARCH・MARKETING 特急レーン MVP実装完了

### 追加（RESEARCH部）
- `src/research/res_a01.py` / `res_a02.py` / `static/res_a01.html` / `static/res_a02.html`

### 追加（MARKETING部）
- `src/marketing/news_crawler.py` / `content_generator.py` / `scheduler.py` / `static/smart_mkt.html`

---

## [NOTIFY-001] 2026-06-05 — 報連相体制アップグレード

### 確定事項
- 通知体制: このチャット（claude.ai）への都度即時報告のみ（確定）
- Gmail通知: 恒久的に廃止

---

## [DRIVE-001] 2026-06-05 — Drive フォルダ構成完全版構築

### 追加フォルダ（01_NiceEze_Master_Docs 配下）
- `00_MANAGEMENT/` / `SURPLUS_SHIFT/` / `RESEARCH/` / `MARKETING/` / `GOV/`

---

## [NOTIFY-002] 2026-06-05 — Gmail通知モジュール削除・通知体制確定

### 削除
- `src/notifications/gmail_notifier.py`

---

## [G1-002] 2026-06-05 — DXFインポート・WebXR AR・PWAフォールバック実装

### 更新
- `src/sbds/static/tms_set_001.html` — DXFフルパーサー / launchAR() WebXR / PWA対応

### 追加（SBDS G1）
- `src/sbds/static/ar_measure.html` — WebXR ARCore計測画面
- `src/sbds/static/manifest.json` — PWAマニフェスト
- `src/sbds/static/sw.js` — サービスワーカー
- `src/sbds/static/pwa_qr.html` — PWAフォールバック案内

### 追加（MARKETING特急）
- `src/marketing/delivery_log.py` — 配信ログモジュール（SHA-256 id / stdlib only）

### 追加（RESEARCH特急）
- `src/research/static/research_dashboard.html` — 統合リサーチダッシュボード

---

## [INST-002] 2026-06-05 — SURPLUS_SHIFT 5種ドキュメント v1.0

### 追加
- `docs/SURPLUS_SHIFT/SURPLUS_SHIFT_BRD/SRS/SEQ/UI/PHASE_v1.0.docx/.pptx`

---

## [SPECIAL-002] 2026-06-05 — RESEARCH MVP完成・MARKETING結合テスト完了・15種ドキュメント生成

### 追加
- `src/research/api.py` / `tests/test_research.py` (38テスト)
- `src/marketing/api.py` / `tests/test_marketing_integration.py` (30テスト)
- `docs/RESEARCH/` 5種 / `docs/MARKETING/` 5種 / `docs/GOV/` 5種 — 計15種完結

---

## [INST-003] 2026-06-05 — GOV部 5種ドキュメント v1.0

### 追加
- `docs/GOV/GOV_BRD/SRS/SEQ/UI/PHASE_v1.0.docx/.pptx`
- **25種ドキュメント全完結**（SBDS/SURPLUS_SHIFT/RESEARCH/MARKETING/GOV 各5種）

---

## [G2-001] 2026-06-05 — SURPLUS SHIFT Gate A〜D 判定ロジック実装

### CEO承認
- Gate D A案確定（実数値設定）
- 自律商談制約: AIは交渉案作成・提示まで。最終送信は必ず人間担当者が承認後実行

### 追加
- `src/surplus_shift/gate_a.py` — KeepaClient + PriceSnapshot
- `src/surplus_shift/gate_b.py` — GrossMarginCalc（GO/CONDITIONAL/NO_GO）
- `src/surplus_shift/gate_c.py` — InventoryScorer（surplus_risk: low/medium/high）
- `src/surplus_shift/gate_d.py` — CashFlowJudge（human_approval_required=True 変更禁止）
- `tests/test_surplus_gate.py` — 37テスト全Pass

---

## [DEPLOY-001] 2026-06-05 — RESEARCH・MARKETING 本番デプロイ準備完了

### 追加
- `docker-compose.prod.yml` / `docker/research.Dockerfile` / `docker/marketing.Dockerfile`
- `nginx.conf` / `.env.production` / `docs/deploy/DEPLOY_CHECKLIST.md`
- `.github/workflows/ci.yml` / `deploy-staging.yml` / `deploy-production.yml`

---

## [DEPLOY-002] 2026-06-05 — 本番デプロイ承認・ゲート全通過

### CEO承認
- 松浦CEO承認: 2026年6月5日付 本番デプロイ実行承認

### デプロイゲート確認（全通過）
| ゲート | 内容 | 結果 |
|:---|:---|:---:|
| ゲート1 | 全テスト131件 | ✅ Pass |
| ゲート2 | bandit High:0 / Medium:0 | ✅ Pass |
| ゲート3 | RESEARCH /health | ✅ OK |
| ゲート4 | MARKETING /health | ✅ OK |

---

## [DEPLOY-003] 2026-06-05 — 本番デプロイ作業記録・GCP→エンジニア委任

### 実施内容
- GitHub Actions `deploy-production.yml` でGCP Cloud Runへの本番デプロイ試行（Run#1〜Run#11）

### 失敗原因の変遷と解決記録

| Run# | 失敗ステップ | 原因 |
|---|---|---|
| #1〜#2 | test_audit | pytest未使用（unittest形式で0件） → `pytest`に修正 |
| #3 | GCP認証 | GCP_SA_KEYがバイナリ（不正JSON） → JSON再設定 |
| #4 | GCP IAM | SAにservices.list権限なし → Editorロール付与 |
| #5〜#7 | docker push | Artifact Registry API無効 → API有効化ステップ追加 |
| #8 | API有効化 | ビリングアカウント未リンク → CEOがビリングリンク実施 |
| #9〜#10 | GCP API確認 | Cloud Resource Manager API無効 → 5つのAPI有効化指示 |
| #11 | — | 調査継続中 |

### 決定事項（松浦CEO 2026-06-05 20:05 JST承認）
- **GCP本番デプロイはエンジニアに委任**
- `docs/deploy/GCP_SETUP_REQUIRED.md` にエンジニア向け手順書作成
- 暫定案としてRailway切り替えを用意

### 追加ファイル
- `docs/deploy/GCP_SETUP_REQUIRED.md` — エンジニア向けGCP設定手順書
  - プロジェクト: serene-bonbon-236821（番号: 172953916843）
  - 必要API 6種・IAMロール5種・SAキー作成手順・Cloud Runデプロイコマンド
- `railway.toml` — Railway代替デプロイ設定（RESEARCH・MARKETING両サービス）
- `.github/workflows/deploy-production.yml` — Railway CLI版に書き換え済み
  - `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` 追加

### CI/テスト状況（全Pass継続）
| スイート | テスト数 | 結果 |
|---|---|---|
| test_research | 38 | ✅ |
| test_marketing_integration | 30 | ✅ |
| test_surplus_gate | 37 | ✅ |
| test_audit | 26 | ✅ |
| bandit | High:0 / Medium:0 | ✅ |

---

## [G2-002] 2026-06-05 — SURPLUS SHIFT UIフロント実装完了

### 追加
- `src/surplus_shift/static/surplus_gate_ui.html` (1311行) — Gate A〜D 操作画面
  - タブナビ: Gate A / B / C / D（アンバー下線）
  - Gate A: ASIN入力 → モック価格テーブル（tabular-nums）
  - Gate B: 仕入れ価格/販売価格 → 粗利率 + GO/CONDITIONAL/NO_GO バッジ
  - Gate C: 在庫数/日次販売数 → demand_score + surplus_risk バッジ
  - Gate D: 7項目CF入力 → 月末残高（¥200,000未満で赤字表示）+ 交渉案テキストエリア
    - アンバー枠「【AI交渉案 — 送信前に必ず人間担当者が確認・承認すること】」
    - 赤字「自動送信禁止」警告 / コピーボタンのみ（送信ボタンなし）
  - IndexedDB niceeze_cache_v142 / 「佐藤」0件確認済み

---

---

## [DEPLOY-003] 2026-06-05 — 本番デプロイ作業記録・GCP→エンジニア委任

### 実施内容
- GitHub Actions `deploy-production.yml` を使ってGCP Cloud Runへの本番デプロイを試行（Run#1〜Run#11）
- 各Runの失敗原因と対処を記録

### 失敗原因の変遷と解決記録

| Run# | 失敗ステップ | 原因 | 対処 |
|---|---|---|---|
| #1〜#2 | test_audit | pytest未使用（unittest形式で0件） | `pytest tests/test_audit.py`に修正 |
| #3 | GCP認証 | GCP_SA_KEYがバイナリ（不正JSON） | CEOがJSONで再設定 |
| #4 | GCP IAM | SAにservices.list権限なし | CEOがEditorロール付与 |
| #5〜#7 | docker push | Artifact Registry API無効 | ワークフローにAPI有効化ステップ追加 |
| #8 | API有効化 | ビリングアカウント未リンク | CEOがビリングリンク実施 |
| #9〜#10 | GCP API確認 | Cloud Resource Manager API無効 | 5つのAPI有効化を指示 |
| #11 | 未確認 | — | — |

### 決定事項（松浦CEO 2026-06-05承認）
- GCP本番デプロイはエンジニアに委任
- `docs/deploy/GCP_SETUP_REQUIRED.md` にエンジニア向け手順書を作成
- 暫定案としてRailway切り替えを用意（`railway.toml` 追加済み）

### 追加ファイル
- `docs/deploy/GCP_SETUP_REQUIRED.md` — エンジニア向けGCP設定手順書
  - プロジェクト: serene-bonbon-236821（番号: 172953916843）
  - 必要API 6種、IAMロール5種、SAキー作成手順、Cloud Runデプロイコマンド
- `railway.toml` — Railway代替デプロイ設定（RESEARCH・MARKETING両サービス）
- `.github/workflows/deploy-production.yml` — Railway CLI版に書き換え済み

### CI/テスト状況（全Pass継続）
- test_research: 38件 ✅
- test_marketing_integration: 30件 ✅
- test_surplus_gate: 37件 ✅
- test_audit: 26件 ✅
- bandit: High:0 / Medium:0 ✅

---

## [G2-003] 2026-06-05 — Research実API連携 + 自律商談フロー実装

### 追加・更新
- `src/research/res_a01.py` Ver 1.1 — PriceFetcher 実API連携追加
  - `RAKUTEN_API_ENDPOINT` / `YAHOO_API_ENDPOINT` 定数追加
  - `__init__()`: KEEPA_API_KEY / RAKUTEN_APP_ID / YAHOO_CLIENT_ID 環境変数読み込み
  - `_mock_record()`: モック生成メソッドに切り出し
  - `_fetch_rakuten()`: 楽天市場商品検索API呼び出し（urllib stdlib only）
  - `_fetch_yahoo()`: Yahoo!ショッピング商品検索API呼び出し
  - `fetch()`: supplier別APIルーティング（全てモックフォールバック付き）
- `src/surplus_shift/negotiation_log.py`（新規）— 自律商談フロー履歴管理
  - `NegotiationRecord`: draft→human_approved→sent ワークフロー
  - `NegotiationLog`: add_draft / human_approve / mark_sent / reject メソッド
  - `mark_sent()`: `human_approved` ステータス必須チェック（自動送信防止）
  - `human_approval_required: True` を全to_dict()に含む
- `src/surplus_shift/__init__.py` — NegotiationLog / NegotiationRecord エクスポート追加
- `tests/test_surplus_gate.py` — TestNegotiationLog 11テスト追加（計48テスト）

### Gate D制約維持確認
- `human_approval_required=True` 変更禁止（`__setattr__`ガード継続）
- 自動送信禁止ワークフロー: `mark_sent()` が `human_approved` ステータス必須
- AIは交渉案作成・提示まで。最終送信は必ず人間担当者が承認後に手動実行

### CI/テスト状況（全Pass）
- test_surplus_gate: **48件** ✅（37 → 48、+11件）
- test_research: 38件 ✅
- bandit: High:0 / Medium:0 ✅

### コミット
- SHA: 7675f58（`feat: Research実API連携 + 自律商談フロー実装 (G2-003)`）

---

## [G2-004] 2026-06-05 — MARKETING X投稿API連携 + スケジューラーStep3完成

### 追加・更新
- `src/marketing/x_poster.py`（新規）— X(Twitter) API v2 OAuth 1.0a投稿クライアント
  - 5環境変数（X_BEARER_TOKEN/X_API_KEY/X_API_SECRET/X_ACCESS_TOKEN/X_ACCESS_TOKEN_SECRET）
  - 未設定時は自動モックモード
  - stdlib only（`urllib.request` + `hmac` + `hashlib`）
  - 140文字超トランケート / エラー時モックフォールバック
- `src/marketing/scheduler.py` — Step3 X投稿実行追加
  - `XPoster.post()` 呼び出し → `DeliveryLog.add()` 記録
  - `ScheduleRun.x_posts_sent` カウント追加
- `src/marketing/api.py` — POST `/x/post` エンドポイント追加
- `tests/test_marketing_integration.py` — TestXPoster 9テスト追加（計39件）

### CI/テスト状況（全Pass）
- test_marketing_integration: **39件** ✅（+9件）
- bandit: High:0 / Medium:0 ✅

---

## [G2-005] 2026-06-05 — GOVモジュール実装（S10/FinOps/稼働ログ）

### 追加
- `src/gov/s10_coo_report.py` — S10 COO業務報告エンジン
  - KPIRecord: 達成率・達成判定
  - BudgetRecord: 予実差異・執行率
  - PMOTask: gate別タスク管理（G0〜G4）、ステータス管理
  - COOReport: 月次レポート生成・kpi/budget/pmoサマリー
- `src/gov/finops_monitor.py` — FinOps監視エンジン
  - 1配送¥0.5超アラート（`cost_per_delivery_exceeded`）
  - 月次予算80%消化警告（`monthly_budget_warning`）
  - 月次予算¥5,000超過アラート（`monthly_budget_exceeded`）
- `src/gov/ops_log_collector.py` — 稼働ログ収集エンジン
  - 対象: sbds/surplus_shift/research/marketing/gov（5サービス）
  - ログレベル: info/warning/error
  - `health_status()`: サービス別ヘルス状態（is_healthy: error件数0判定）
- `src/gov/api.py` — GOV HTTP API（Cloud Run）
  - GET/POST各種エンドポイント（COO/FinOps/OpsLog）
- `src/gov/__init__.py` — 全クラスエクスポート
- `tests/test_gov.py` — 35テスト（COO14/FinOps10/OpsLog11）

### CI/テスト状況（全Pass）
- test_gov: **35件** ✅（新規）
- bandit: High:0 / Medium:0 ✅

---

## 予定（Gate別）

| Gate | 予定時期 | 主要変更 |
|:---|:---|:---|
| G1 | 2026/09末 | TMS-SET-001実装 / TMS-DRV-001実装 / IndexedDB v142移行 / 労働法ロック |
| G2 | 2026/11末 | SURPLUS SHIFT v14.2完成 / Research完成 |
| G3 | 2027/01末 | Marketing-Sys / GOV S10完成 |
| G4 | 2027/02末 | GCP本番デプロイ / UAT / Go-Live |
