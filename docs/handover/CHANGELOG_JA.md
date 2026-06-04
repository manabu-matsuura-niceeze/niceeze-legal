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
  - BuildingSpec / EVSpec / RoomRecord / BuildingMaster データモデル
  - Firestore CRUD リポジトリ（BuildingMasterRepository）
  - 最適ルーティング距離計算（calculate_routing_distance）
- `src/sbds/tms_drv_001.py`: 配送員スマホ・ルーティングモジュール
  - Jaro-Winkler名寄せエンジン（D_jw ≥ 0.85）
  - **IndexedDB v142**（`niceeze_cache_v142` / IDB_VERSION=142）— v14.0の v140から移行
  - **STATUS_LOCKED_BY_LABOR_LAW**（4時間連続作業ロック）
  - 1分前PULL通知判定（should_send_pull_notify）
  - 最適配送ルーティングソート（クレーム最後尾）
- `src/sbds/static/tms_set_001.html`: TMS-SET-001 フロントエンド
  - LAYOUT_MASTER.md 3ゾーン準拠（上部スペック入力/中央グリッド/下部保存）
  - IndexedDB v142 保存・読み込み
  - font-mono tabular-nums tracking-tight 強制
- `src/sbds/static/tms_drv_001.html`: TMS-DRV-001 フロントエンド
  - 冷凍/冷蔵警告（赤字大文字「ロッカー格納禁止：手渡し必須」）
  - クレーム要注意フラグ（同フロア最後尾ソート）
  - ETA残り時間リアルタイム表示（1秒更新）
  - 労働法ロックバナー（4時間超で表示）
  - **「佐藤」禁止事項違反 解消済** — 全箇所「配送スタッフ」に統一

### 禁止事項対応
- 🔴「佐藤」固有名詞: 差異レポートで検出 → 本実装では全箇所「配送スタッフ」に統一 ✅

---

## [G0-004] 2026-06-04 — CEO確定判断5件反映 + TECH-20260604-002提出

### 更新
- `docs/reports/NiceEze_未実装5件_Gate別対応計画_20260604.md` Rev.2
  - 判断①C: note.com → G4以降保留
  - 判断②B: YouTube → 構成案・台本まで自動生成、アップロードは手動
  - 判断④A: DWG対応 → 恒久的対象外（DXFのみ）
  - 判断⑤A: AR精度 → ±50cm許容（WebXRで達成可能）
  - 判断⑥A: PWAフォールバック → LIFF非対応時はPWA別URL + 導線設計をG1スコープに追加

### 追加
- `docs/reports/NiceEze_iOS_Android比較調査レポート_TECH-20260604-002.md`
  - A案（Android優先）vs B案（iOS/Android同時）の詳細比較
  - 技術的制約: Safari iOS WebXR / ARKit実装差分 / iOS15フォールバック工数
  - Gate影響: A案=G1確実完了、B案=1〜2週間遅延リスク
  - 自律COO推奨: **A案（Android優先）**
  - 松浦CEO最終判断待ち（判断③）

### Google Driveアップロード（00_NiceEze_AI_Audit）
- `NiceEze_未実装5件_Gate別対応計画_20260604` Rev.2 更新
- `NiceEze_iOS_Android比較調査レポート_TECH-20260604-002` 新規

---

## [INST-001] 2026-06-04 — ドキュメント自動生成体制構築 + SBDS 5ドキュメント v1.0

### 追加
- `docs/instructions/DOC_GEN_INSTRUCTION_v1.0.md` — CEO発行指示書（25ドキュメント体制）
- `scripts/gen_sbds_brd.py` / `gen_sbds_srs.py` / `gen_sbds_pptx.py` — docx/pptx生成スクリプト
- `docs/SBDS/SBDS_BRD_v1.0.docx` (42,070 bytes)
- `docs/SBDS/SBDS_SRS_v1.0.docx` (43,259 bytes)
- `docs/SBDS/SBDS_SEQ_v1.0.pptx` (40,831 bytes)
- `docs/SBDS/SBDS_UI_v1.0.pptx` (38,729 bytes)
- `docs/SBDS/SBDS_PHASE_v1.0.pptx` (38,551 bytes)

### Google Drive
- GDrive SBDS subfolder作成: `1oLP5qKza7JH2VjZ-ukRbv1pfeUkEZlP9`（5ファイルアップロード予定）

---

## [SPECIAL-001] 2026-06-04 — RESEARCH・MARKETING 特急レーン MVP実装完了

### CEO承認
- 松浦CEO承認: 2026年6月5日付 特急ローンチ指示
- RESEARCH・MARKETINGを通常レーンから切り離し独立並列開発

### 追加（RESEARCH部）
- `src/research/__init__.py` — モジュール初期化
- `src/research/res_a01.py` — 8社価格マトリクス（PriceRecord/PriceMatrix/PriceFetcher）
  - SHA-256キャッシュキー / bandit 0件 / PII不使用
- `src/research/res_a02.py` — トレンドスコア（growth/bestseller/retention/is_staple）
  - RETENTION_THRESHOLD=0.6 / S_retention ≥ 0.6 → 定番判定
- `src/research/static/res_a01.html` — RES-A01 UI（LAYOUT_MASTER準拠）
  - 8社固定マトリクス / font-mono tabular-nums 全数値列 / IndexedDB v142 / 競合5品ドリルダウン
- `src/research/static/res_a02.html` — RES-A02 UI（LAYOUT_MASTER準拠）
  - 8カテゴリチップ / 3モード切替 / S_retention font-mono / TODO自動起票

### 追加（MARKETING部）
- `src/marketing/__init__.py` — モジュール初期化
- `src/marketing/news_crawler.py` — Google News RSS 8カテゴリクローラー
  - SHA-256 article_id（md5廃止・bandit B324解消）/ モックフォールバック
- `src/marketing/content_generator.py` — 4フォーマット自動生成
  - X(140文字) / メルマガHTML / Note Markdown / YouTube台本（手動アップロード）
- `src/marketing/scheduler.py` — 朝8:00/夜19:00 Cloud Functions エントリポイント
  - cron "0 23 * * *"(朝JST) / "0 10 * * *"(夜JST) / FinOps月額¥0（MVP）
- `src/marketing/static/smart_mkt.html` — SMART-MKT UI（LAYOUT_MASTER準拠）
  - 4フォーマットタブ切替 / トーン選択 / HTMLプレビュー / コピーボタン

### ハードゲート自己承認
- PII不使用: ✅ / FinOps¥5,000以内: ✅（MVP¥0） / LAYOUT_MASTER準拠: ✅ / bandit 0件: ✅

### 進捗報告
- `docs/reports/NiceEze_特急レーン初回進捗報告_20260604.md` — 提出

---

## 予定（Gate別）

| Gate | 予定時期 | 主要変更 |
|:---|:---|:---|
| G1 | 2026/09末 | TMS-SET-001実装 / TMS-DRV-001実装 / IndexedDB v142移行 / 労働法ロック |
| G2 | 2026/11末 | SURPLUS SHIFT v14.2完成 / Research完成 |
| G3 | 2027/01末 | Marketing-Sys / GOV S10完成 |
| G4 | 2027/02末 | GCP本番デプロイ / UAT / Go-Live |
