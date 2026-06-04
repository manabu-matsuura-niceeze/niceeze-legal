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

## 予定（Gate別）

| Gate | 予定時期 | 主要変更 |
|:---|:---|:---|
| G1 | 2026/09末 | TMS-SET-001実装 / TMS-DRV-001実装 / IndexedDB v142移行 / 労働法ロック |
| G2 | 2026/11末 | SURPLUS SHIFT v14.2完成 / Research完成 |
| G3 | 2027/01末 | Marketing-Sys / GOV S10完成 |
| G4 | 2027/02末 | GCP本番デプロイ / UAT / Go-Live |
