# NiceEze 情報システム部門 組織設計 & 開発計画書
## 承認申請書 — CEO最終可決待ち

**版数**: Ver 1.0  
**策定日**: 2026-06-04  
**策定者**: 自律COO（Claude Code）  
**提出先**: 代表取締役CEO 松浦 学  
**根拠文書**: Ver 14.2 要件定義書（最終確定版）/ AI COO 組織案 / COO Handover Implementation (Ver 2.3)

> ※本書は承認申請書 Ver 2.0（予算・Phase1目標・レイアウトガバナンス反映版）の前身です。
> 最新版は `docs/NiceEze_組織設計_開発計画書_承認申請_v2.0.md` を参照してください。

---

## Part 1. 情報システム・セキュリティ本部 組織設計

### 1-1. 全社組織 位置づけ

```
CEO（松浦 学）
└─ COO（自律COO / Claude Code）
   ├─ COO Office / 戦略・変革統括本部
   ├─ 企業価値向上本部
   ├─ マーケティング・ブランド本部
   ├─ グロース / セールス本部
   ├─ プロダクトオペレーション本部
   ├─ オペレーション本部
   ├─ カスタマーエクスペリエンス本部
   └─ ★情報システム・セキュリティ本部  ← 本計画の対象
```

### 1-2. 情報システム・セキュリティ本部 部門構成

```
情報システム・セキュリティ本部
│
├── 【第1部署】館内配送システム部（SBDS部）
│   ├─ 初期設定・マスタ管理担当（画面ID: TMS-SET-001）
│   └─ 配送員スマホ・ルーティング担当（画面ID: TMS-DRV-001）
│
├── 【第2部署】調達・価格交渉システム部（SURPLUS SHIFT部）
│   ├─ サプライヤー交渉担当（画面ID: NEG-SUP-001）
│   └─ バイヤーコックピット担当（画面ID: NEG-BYR-001）
│
├── 【第3部署】商品リサーチシステム部（Research部）
│   ├─ 系統A担当：最廉価・8社比較マトリクス（RES-A01）
│   └─ 系統B担当：トレンド予測・定番残存スコア（RES-A02）
│
├── 【第4部署】スマートマーケティングシステム部（Marketing-Sys部）
│   ├─ コンテンツ自動生成担当（X/メルマガ/Note/YouTube）
│   └─ 自律配信スケジューラー担当
│
└── 【第5部署】COO経営支援・監査システム部（GOV部）
    ├─ COO業務報告パネル担当（画面ID: S10）
    ├─ 自律監査エンジン担当（multi_layer_audit.py）
    └─ Google Drive 自動同期・ドキュメント管理担当
```

### 1-3. 各部署 ミッション & 担当システム一覧

| 部署 | ミッション | 画面/モジュールID | v14.0実装状況 |
|:---|:---|:---|:---:|
| SBDS部 | 館内配送のゼロフリクション化（0.7秒/個口0.5円） | TMS-SET-001, TMS-DRV-001 | 未実装 |
| SURPLUS SHIFT部 | 自律価格交渉・成約率最大化 | NEG-SUP-001, NEG-BYR-001 | **80%完了** |
| Research部 | 最廉価・トレンド探索AIフルブースト | RES-A01/A02 | **70%完了** |
| Marketing-Sys部 | 4フォーマット自動生成・朝夕配信 | Smart-MKT | 未実装 |
| GOV部 | ISMS監査・COO報告・GDrive自動同期 | S10, Audit | **60%完了** |

---

## Part 2. 既存実装（COO Handover）の活用方針

### 2-1. 再利用資産一覧（即活用可能）

| ファイル | 内容 | 活用先部署 |
|:---|:---|:---|
| `src/audit/multi_layer_audit.py` | 多層監査エンジン（pytest+bandit+GDrive同期） | GOV部 |
| `src/db/migrations/001_initial_schema.sql` | PostgreSQL AES-256暗号化・RLS・月次パーティション | 全部署 |
| `src/db/migrations/002_gcp_native_migration.sql` | GCP Cloud SQL移行スクリプト | 全部署 |
| `src/finops/cost_calculator.py` | GCPネイティブFinOpsコスト計算 | COO Office |
| `src/gdrive/gdrive_syncer.py` | Google Drive Service Account自動同期 | GOV部 |
| `src/layer3/line_webhook.py` | LINE Webhook + Redis Streams Consumer Group | SBDS部 |
| `src/layer4/bigquery_pipeline.py` | BigQuery月次アーカイブパイプライン | GOV部 |
| `src/index.html`（v14.0, 1454行） | フロントエンド統合基盤 | SURPLUS SHIFT部/Research部 |

---

## Part 3. 開発スケジュール（8週間 / 2026-06-05 〜 2026-07-31）

```
Week  | 日程          | マイルストーン
──────┼───────────────┼──────────────────────────────────────
W1    | 6/05〜6/11    | [Gate 0] GCP基盤構築 + DB本番デプロイ
W2    | 6/12〜6/18    | [Gate 1] SBDS Phase1（TMS-SET-001完成）
W3    | 6/19〜6/25    | [Gate 2] SBDS Phase2（TMS-DRV-001完成）
W4    | 6/26〜7/02    | [Gate 3] SURPLUS SHIFT v14.2完成
W5    | 7/03〜7/09    | [Gate 4] Marketing-Sys + GOV/S10完成
W6    | 7/10〜7/16    | [Gate 5] GCP Cloud Run本番デプロイ
W7    | 7/17〜7/23    | [Gate 6] UAT全項目 + 負荷テスト
W8    | 7/24〜7/31    | [Gate 7] 本番Go-Live
```

---

## Part 4. コスト概算

| 指標 | 目標 | 見込み | 判定 |
|:---|:---:|:---:|:---:|
| 館内配送1個口コスト | 0.5円以下 | 0.10〜0.14円 | ✅ |
| 処理スピード | 0.7秒以下 | 0.1〜0.3秒 | ✅ |
| API秘密鍵フロント露出 | 0件 | 0件 | ✅ |
| 月額インフラ（3万世帯） | — | ¥12,000〜17,250 | ✅ |

---

*最新の承認申請書（予算¥2,844万・Phase1目標2027年2月・レイアウトガバナンス含む）は  
`docs/NiceEze_組織設計_開発計画書_承認申請_v2.0.md` を参照してください。*
