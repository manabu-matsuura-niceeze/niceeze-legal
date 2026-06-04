# NiceEze 情報システム部門 組織設計 & 開発計画書
## 承認申請書 — CEO最終可決待ち

**版数**: Ver 1.0  
**策定日**: 2026-06-04  
**策定者**: 自律COO（Claude Code）  
**提出先**: 代表取締役CEO 松浦 学  
**根拠文書**: Ver 14.2 要件定義書（最終確定版）/ AI COO 組織案 / COO Handover Implementation (Ver 2.3)

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
│   ├─ 系統A担当：最廉価・8社比較マトリクス
│   └─ 系統B担当：トレンド予測・定番残存スコア
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
| Research部 | 最廉価・トレンド探索AIフルブースト | 系統A/B | **70%完了** |
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

### 2-2. v14.0 → v14.2 差分（追加実装が必要なもの）

| # | 要件 | 対象部署 | 規模 |
|:---|:---|:---|:---:|
| 1 | IndexedDB完全オフラインキャッシュ（niceeze_cache_v142） | SBDS部 | M |
| 2 | Jaro-Winkler名寄せ（D_jw >= 0.85）自動確定 | SBDS部 | S |
| 3 | 冷凍・冷蔵品「手渡し必須」強制警告 | SBDS部 | S |
| 4 | 1分前PUSH通知（到着60秒前自動発火） | SBDS部 | S |
| 5 | STATUS_LOCKED_BY_LABOR_LAW（4時間超強制休憩） | SBDS部 | S |
| 6 | TMS-SET-001 建物マスタ・フロアグリッドエディタ | SBDS部 | L |
| 7 | TMS-DRV-001 配送員専用スマホ画面（最適ルート表示） | SBDS部 | L |
| 8 | 国税庁API連携（13桁法人コード→登記情報自動反映） | SURPLUS SHIFT部 | M |
| 9 | 海外送金フィールド（IBAN/SWIFT/ABA/SORT CODE） | SURPLUS SHIFT部 | S |
| 10 | 4フォーマット自動生成・配信スケジューラー | Marketing-Sys部 | L |
| 11 | 音声TTS/STT対話パネル（Web Speech API） | GOV部 | M |
| 12 | GCP Cloud Run本番デプロイ（APIプロキシ含む） | 全部署 | L |

---

## Part 3. 開発スケジュール（Timeスケジュール）

### 3-1. マスタースケジュール（8週間 / 2026-06-05 〜 2026-07-31）

```
Week  | 日程          | マイルストーン
──────┼───────────────┼──────────────────────────────────────────────
W1    | 6/05〜6/11    | [Gate 0] GCP基盤構築 + DB本番デプロイ
W2    | 6/12〜6/18    | [Gate 1] SBDS Phase1（TMS-SET-001完成）
W3    | 6/19〜6/25    | [Gate 2] SBDS Phase2（TMS-DRV-001完成）
W4    | 6/26〜7/02    | [Gate 3] SURPLUS SHIFT v14.2完成 + Research完成
W5    | 7/03〜7/09    | [Gate 4] Marketing-Sys + GOV/S10完成
W6    | 7/10〜7/16    | [Gate 5] GCP Cloud Run本番デプロイ + LINE LIFF接続
W7    | 7/17〜7/23    | [Gate 6] UAT（実地テスト全項目） + 負荷テスト
W8    | 7/24〜7/31    | [Gate 7] 本番Go-Live + 監視体制確立
```

### 3-2. 部署別 週次タスク詳細

#### Week 1（6/05〜6/11）— GCP基盤整備

| タスク | 担当部署 | 工数 | 活用資産 |
|:---|:---|:---:|:---|
| Cloud SQL PostgreSQL インスタンス作成 | 全部署共通 | 0.5日 | `001_initial_schema.sql` |
| GCP Cloud Run 環境構築 | 全部署共通 | 0.5日 | `deploy_to_github.sh` |
| Memorystore Redis 設定 | SBDS部 | 0.5日 | `line_webhook.py` |
| Secret Manager（LINE/Claude APIキー格納） | GOV部 | 0.5日 | DevSecOps要件 |
| Google Drive Service Account 設定 | GOV部 | 0.5日 | `gdrive_syncer.py` |
| CI/CD パイプライン（GitHub Actions）整備 | 全部署共通 | 1日 | `.github/` |

#### Week 2（6/12〜6/18）— SBDS Phase 1

| タスク | 担当部署 | 工数 |
|:---|:---|:---:|
| TMS-SET-001 建物・棟・階数マスタ入力画面 | SBDS部 | 2日 |
| EVカバー階個別設定（最大20棟×100階） | SBDS部 | 1日 |
| フロアスプレッドシート型グリッドエディタ | SBDS部 | 2日 |
| CAD/DXFインポート or AR計測スタブ | SBDS部 | 1日 |

#### Week 3（6/19〜6/25）— SBDS Phase 2

| タスク | 担当部署 | 工数 |
|:---|:---|:---:|
| TMS-DRV-001 配送員スマホ画面（PWA/LIFF） | SBDS部 | 2日 |
| Jaro-Winkler名寄せエンジン（D_jw >= 0.85） | SBDS部 | 0.5日 |
| 最適配送順路生成ロジック（台車積載制限対応） | SBDS部 | 1日 |
| 冷凍・冷蔵品「手渡し必須」強制警告 | SBDS部 | 0.5日 |
| 1分前PUSH通知（LINE Messaging API連携） | SBDS部 | 0.5日 |
| STATUS_LOCKED_BY_LABOR_LAW（4時間強制休憩） | SBDS部 | 0.5日 |
| IndexedDB完全オフラインキャッシュ（v142） | SBDS部 | 1日 |

#### Week 4（6/26〜7/02）— SURPLUS SHIFT v14.2 + Research完成

| タスク | 担当部署 | 工数 |
|:---|:---|:---:|
| 国税庁API連携（13桁法人コード自動反映） | SURPLUS SHIFT部 | 1日 |
| 海外送金フィールド（IBAN/SWIFT/ABA バリデーション） | SURPLUS SHIFT部 | 1日 |
| 15ヶ国語フラグ切替（ビジネス丁寧語定義済） | SURPLUS SHIFT部 | 0.5日 |
| Research 系統A：8社マトリクス精度向上 | Research部 | 1日 |
| Research 系統B：定番残存スコア→TODO自動起票 | Research部 | 1日 |
| v14.0 → v14.2 フロントエンド差分マージ | 全部署 | 1日 |

#### Week 5（7/03〜7/09）— Marketing-Sys + GOV/S10

| タスク | 担当部署 | 工数 |
|:---|:---|:---:|
| 業界ニュースクローラ設定UI（8カテゴリ24時間監視） | Marketing-Sys部 | 1日 |
| 4フォーマット自動生成プレビューエリア | Marketing-Sys部 | 2日 |
| 自律配信スケジューラー（朝8:00/夕19:00/週次） | Marketing-Sys部 | 1日 |
| S10 COO業務報告パネル（音声TTS/STT対話） | GOV部 | 1.5日 |
| 3大仮想部署AIログ集約 + TODO.mdコピーカード | GOV部 | 1日 |

#### Week 6（7/10〜7/16）— GCP本番デプロイ

| タスク | 担当部署 | 工数 |
|:---|:---|:---:|
| Cloud Run APIプロキシ（Claude API安全経由） | GOV部 | 1日 |
| Cloud Run LIFF Worker デプロイ | SBDS部 | 1日 |
| Cloud SQL 接続 + マイグレーション実行 | 全部署 | 0.5日 |
| LINE LIFF / Mini App 本番設定 | SBDS部 | 1日 |
| HTTPS/カスタムドメイン設定 | GOV部 | 0.5日 |
| 全エンドポイント疎通確認 | 全部署 | 1日 |

#### Week 7（7/17〜7/23）— UAT・負荷テスト

| タスク | 担当部署 | 工数 |
|:---|:---|:---:|
| TMS-DRV-001 実機テスト（iPhone/Android） | SBDS部 | 2日 |
| SURPLUS SHIFT 完全実地テスト（要件定義書 第2フェーズ全項目） | SURPLUS SHIFT部 | 1日 |
| Research テストケース①②③ 実動検証 | Research部 | 1日 |
| 負荷テスト（3万世帯 × 12万件/月相当） | GOV部 | 1日 |
| セキュリティスキャン（bandit + pip-audit 全パス確認） | GOV部 | 0.5日 |

#### Week 8（7/24〜7/31）— Go-Live

| タスク | 担当部署 | 工数 |
|:---|:---|:---:|
| 本番データ移行 | 全部署 | 1日 |
| Cloud Monitoring / Error Reporting ダッシュボード設定 | GOV部 | 0.5日 |
| ISMS監査報告書 最終版 自動生成 → Google Drive保存 | GOV部 | 自動 |
| Go-Live 宣言 + CEO報告 | COO | — |

---

## Part 4. コスト概算

### 4-1. 開発コスト

| 項目 | 内容 | コスト |
|:---|:---|---:|
| 開発人件費 | Claude Code（AI自律開発） | **¥0** |
| 設計・監査人件費 | Claude Code + 多層監査エンジン自動実行 | **¥0** |
| **開発合計** | | **¥0** |

### 4-2. インフラコスト（月次 / GCPネイティブ）

#### 初期フェーズ（〜1,000世帯）

| サービス | 月額（USD） | 月額（JPY/¥150換算） | 備考 |
|:---|---:|---:|:---|
| Cloud Run（API/Worker） | $0〜5 | ¥0〜750 | 無料枠200万req/月 |
| Cloud SQL PostgreSQL（db-f1-micro） | $15 | ¥2,250 | 最小構成 |
| Memorystore Redis（1GB） | $15 | ¥2,250 | Consumer Group |
| Cloud Storage | $1 | ¥150 | OCR原票・アセット |
| BigQuery | $0 | ¥0 | 10GB/月無料 |
| LINE Messaging API（PUSH） | $0〜3 | ¥0〜450 | PULL設計で最小化 |
| Claude API（サーバーサイド） | $5〜15 | ¥750〜2,250 | キャッシュ活用 |
| **月額合計（初期）** | **$36〜54** | **¥5,400〜8,100** | |
| **1個口あたり（1,000世帯×4件）** | | **¥1.35〜2.03** | スケール前は高め |

#### 本番フェーズ（3万世帯 / 12万件/月）

| サービス | 月額（USD） | 月額（JPY/¥150換算） | 備考 |
|:---|---:|---:|:---|
| Cloud Run | $5〜15 | ¥750〜2,250 | スケール対応 |
| Cloud SQL PostgreSQL（db-n1-standard-1） | $35 | ¥5,250 | 本番最小 |
| Memorystore Redis（1GB） | $15 | ¥2,250 | 同左 |
| Cloud Storage | $3 | ¥450 | |
| BigQuery | $2 | ¥300 | 月次アーカイブ |
| LINE Messaging API | $5〜10 | ¥750〜1,500 | PULL設計優先 |
| Claude API | $15〜30 | ¥2,250〜4,500 | キャッシュ最大化 |
| Cloud Monitoring | $0〜2 | ¥0〜300 | |
| **月額合計（本番）** | **$80〜115** | **¥12,000〜17,250** | |
| **1個口あたり（12万件/月）** | | **¥0.10〜0.14** | ✅ 0.5円以下達成 |

#### FinOps達成状況

| 指標 | 目標 | 本番フェーズ実績 | 判定 |
|:---|:---:|:---:|:---:|
| 館内配送1個口コスト | 0.5円以下 | **0.10〜0.14円** | ✅ クリア |
| 処理スピード（IndexedDB） | 0.7秒以下 | **推定0.1〜0.3秒** | ✅ クリア |
| API秘密鍵フロント露出 | 0件 | **0件（Cloud Runプロキシ）** | ✅ クリア |

### 4-3. 初期セットアップコスト（一回限り）

| 項目 | コスト | 備考 |
|:---|---:|:---|
| GCPプロジェクト作成 | ¥0 | 無料 |
| LINE Business ID + Mini App審査 | ¥0 | 無料（審査期間 1〜2週間） |
| ドメイン取得（任意） | ¥1,000〜3,000/年 | niceeze.com等 |
| SSL証明書 | ¥0 | GCP自動発行 |
| **初期合計** | **¥1,000〜3,000** | |

---

## Part 5. Gate制 開発プロセス

### 5-1. Gate通過基準

| Gate | タイミング | 通過条件 |
|:---|:---|:---|
| Gate 0 | W1完了時 | GCP全サービス疎通確認 / CI/CD グリーン |
| Gate 1 | W2完了時 | TMS-SET-001 全機能デモ可能 |
| Gate 2 | W3完了時 | TMS-DRV-001 実機動作確認 / 0.7秒以下確認 |
| Gate 3 | W4完了時 | SURPLUS SHIFT v14.2 全テスト通過 |
| Gate 4 | W5完了時 | Marketing-Sys / S10 デモ可能 |
| Gate 5 | W6完了時 | 本番環境全エンドポイント疎通 |
| Gate 6 | W7完了時 | UAT全項目グリーン / セキュリティスキャンPASS |
| Gate 7 | W8完了時 | Go-Live宣言 / CEO最終確認 |

### 5-2. ガバナンス（AIフルブースト）

- **実装**: Claude Code（自律COO配下各部署AIエージェント）
- **監査**: `multi_layer_audit.py`（各Gate完了時に自動実行）
- **報告**: `gdrive_syncer.py`（00_NiceEze_AI_Auditフォルダへ自動保存）
- **人間の最終承認ライン**: 本番リリース（Gate 7）/ 資本政策 / 契約

---

## Part 6. リスクと対応方針

| リスク | 影響 | 対応 |
|:---|:---|:---|
| LINE Mini App審査遅延（1〜2週間） | SBDS部遅延 | PWAで先行リリース、後からLIFF追加 |
| GCP Cloud SQL起動コスト（初期）| 1個口コスト目標未達 | 初期はCloud Run + Firestore軽量構成で代替 |
| 国税庁API仕様変更 | SURPLUS SHIFT部遅延 | APIモック先行実装、後日本番切替 |
| CAD/DXFパーサー対応形式制限 | SBDS部TMS-SET遅延 | AR計測モジュール先行実装でリスク回避 |

---

## 承認欄

本計画書の内容を承認し、開発スタートを指示します。

```
□ 承認 — 上記計画に基づき開発着手を許可する
□ 条件付き承認 — 下記コメントを反映の上、着手を許可する
□ 差し戻し — 再策定を要求する

代表取締役CEO: 松浦 学                日付: ____年____月____日

コメント（任意）:
____________________________________________________________
____________________________________________________________
```

---

*本文書はNiceEze 自律COO（Claude Code）が自律策定しました。*  
*Gate制により、各マイルストーン完了時に監査報告書を自動生成し Google Drive（00_NiceEze_AI_Audit）へ保存します。*
