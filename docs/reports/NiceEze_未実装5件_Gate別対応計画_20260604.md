# NiceEze 未実装5件 Gate別対応計画書

**レポートID**: PLAN-20260604-001  
**作成日**: 2026-06-04  
**作成者**: 自律COO（Claude Code）  
**提出先**: 代表取締役CEO 松浦 学 / 00_NiceEze_AI_Audit  
**根拠**: 差異照合レポート（DIFF-20260604-001）❌未実装6件のうちG0完了済1件を除く残り5件

---

## 対象: 未実装5件 一覧

差異レポートの❌未実装6件のうち、G0で完了済の「レイアウトガバナンス（LAYOUT_MASTER）」を除く5件が対象。

| # | 差異レポートID | 項目 | 部署 | Gate |
|:--|:---|:---|:---|:---:|
| 1 | 項目7 | Cloud Run proxy経由のClaude API呼出 | GOV部/全部署 | G4 |
| 2 | 項目15 | STATUS_LOCKED_BY_LABOR_LAW | SBDS部 | G1 ✅解消済 |
| 3 | 項目23 | 15ヶ国語i18n完全対応 | SURPLUS SHIFT部 | G2 |
| 4 | 項目26 | X/メルマガ/Note/YouTube 4フォーマット自動生成 | Marketing-Sys部 | G3 |
| 5 | 項目27 | 朝夕自律配信スケジューラー | Marketing-Sys部 | G3 |

> ※ 項目15（STATUS_LOCKED_BY_LABOR_LAW）は G1-001コミット（2026-06-04）で実装完了。残り4件。

---

## Gate別 対応計画詳細

---

### G1（2026/09末）— **残0件** ✅

**STATUS_LOCKED_BY_LABOR_LAW**は本日（2026-06-04）G1-001コミットで実装完了。

| 実装内容 | ファイル | 状態 |
|:---|:---|:---:|
| WorkSession.check_labor_law() | `src/sbds/tms_drv_001.py` | ✅ 完了 |
| 4時間ロックバナー | `src/sbds/static/tms_drv_001.html` | ✅ 完了 |
| 残り時間タイマー（1秒更新） | `src/sbds/static/tms_drv_001.html` | ✅ 完了 |

---

### G2（2026/11末）— **1件**

#### 項目23: 15ヶ国語i18n完全対応（SURPLUS SHIFT部）

**現状**: v14.0では一部言語のみ対応（英語/日本語/中国語推定）

**対応方針**:

```
対応15言語:
  日本語(ja) / 英語(en) / 中国語簡体(zh-CN) / 中国語繁体(zh-TW)
  韓国語(ko) / タイ語(th) / ベトナム語(vi) / インドネシア語(id)
  マレー語(ms) / ポルトガル語(pt) / スペイン語(es) / フランス語(fr)
  ドイツ語(de) / アラビア語(ar) / ヒンディー語(hi)
```

**実装タスク**:

| タスク | 難易度 | 工数目安 |
|:---|:---:|:---:|
| `src/i18n/` ディレクトリ作成 + 言語JSONファイル15件 | 中 | 1日 |
| NEG-SUP-001 UI テキストを全てi18nキーに置換 | 中 | 2日 |
| NEG-BYR-001 UI テキストを全てi18nキーに置換 | 中 | 2日 |
| 言語切替セレクタ実装（ヘッダー右上） | 低 | 0.5日 |
| 右横書き（RTL）対応: アラビア語 `dir="rtl"` | 高 | 1日 |
| 翻訳テスト（機械翻訳検証） | 中 | 1日 |

**G2通過条件**: 15言語でUI表示が崩れない / RTL正常動作 / bandit全通過

---

### G3（2027/01末）— **2件**

#### 項目26: X/メルマガ/Note/YouTube 4フォーマット自動生成（Marketing-Sys部）

**現状**: v14.0未実装

**アーキテクチャ設計**:

```
入力: 商品情報 / トレンドスコア（RES-A02連携）
  ↓
[Cloud Run] Marketing-Sys API
  ├─ Claude API（プロキシ経由） → コンテンツ生成
  ├─ フォーマット別テンプレート適用
  │   ├─ X投稿: 140字以内 + ハッシュタグ
  │   ├─ メルマガ: HTML形式 + 件名
  │   ├─ Note: Markdown形式 + アイキャッチ
  │   └─ YouTube: タイトル + 概要欄 + タグ
  └─ 生成コンテンツ → Firestore保存
```

**実装タスク**:

| タスク | 難易度 | 工数目安 |
|:---|:---:|:---:|
| `src/marketing/content_generator.py` — Claude API連携 | 中 | 2日 |
| 4フォーマット テンプレートエンジン | 中 | 2日 |
| Smart-MKT UI（コンテンツプレビュー画面） | 中 | 2日 |
| RES-A02トレンドスコア連携 | 中 | 1日 |
| 生成コンテンツの承認ワークフロー（COO確認） | 低 | 1日 |

#### 項目27: 朝夕自律配信スケジューラー（Marketing-Sys部）

**現状**: v14.0未実装

**アーキテクチャ設計**:

```
Cloud Scheduler（GCP）
  ├─ 朝6:00 JST → Cloud Run /marketing/schedule/morning
  └─ 夕18:00 JST → Cloud Run /marketing/schedule/evening
       ↓
  各プラットフォームAPI呼出
  ├─ X API v2 (OAuth 2.0)
  ├─ メルマガ: SendGrid API
  ├─ Note: 手動投稿URL生成（API非公開のため）
  └─ YouTube: YouTube Data API v3
```

**実装タスク**:

| タスク | 難易度 | 工数目安 |
|:---|:---:|:---:|
| `src/marketing/scheduler.py` — Cloud Scheduler連携 | 中 | 1日 |
| X API v2 投稿モジュール | 中 | 1日 |
| SendGrid メルマガ配信モジュール | 低 | 1日 |
| YouTube Data API v3 連携 | 高 | 2日 |
| Note: 手動投稿リンク生成（API制約） | 低 | 0.5日 |
| 配信ログ → Firestore / BigQuery記録 | 低 | 0.5日 |

**松浦CEO要件定義待ち（不明点）**:
- Note（note.com）のAPI公開状況が不明。現時点では手動投稿URLを生成して配信スタッフへ通知する方針で進める予定。CEO確認要。

**G3通過条件**: 4フォーマット生成デモ可能 / 朝夕スケジューラー実機テスト / bandit全通過

---

### G4（2027/02末）— **1件**

#### 項目7: Cloud Run proxy経由のClaude API呼出（全部署共通）

**現状**: v14.0はモックAPI（`MOCK_CLAUDE_RESPONSE`）。v14.2でCloud Runプロキシ経由に移行。

**アーキテクチャ設計**:

```
フロントエンド（LIFF/PWA）
  ↓ fetch('/api/claude', { body: prompt })  ← APIキーなし
[Cloud Run] claude-proxy
  ├─ GCP Secret Manager → ANTHROPIC_API_KEY 取得
  ├─ レート制限（Redis Memorystore）
  ├─ キャッシュ（Firestore: TTL 1時間）
  └─ Anthropic API 呼出 → レスポンス返却

セキュリティ要件:
  ✅ フロントに APIキー露出 = 0件
  ✅ Secret Manager経由のみでキー参照
  ✅ Cloud Run サービスアカウント IAM最小権限
```

**実装タスク**:

| タスク | 難易度 | 工数目安 |
|:---|:---:|:---:|
| `src/proxy/claude_proxy.py` — Cloud Run Webサーバー | 中 | 2日 |
| Secret Manager連携 | 低 | 0.5日 |
| Redis キャッシュ層 | 中 | 1日 |
| フロントエンド全画面のClaude API呼出をプロキシ経由に変更 | 中 | 2日 |
| IAM最小権限設定 + bandit検証 | 中 | 1日 |
| 負荷テスト（3万世帯想定） | 高 | 2日 |

**G4通過条件**: APIキーフロント露出0件確認 / Claude API実通信テスト / UAT全項目グリーン / 本番Go-Live

---

## 対応計画 サマリー表

| 項目 | Gate | 予定時期 | 現状 | 備考 |
|:---|:---:|:---|:---:|:---|
| STATUS_LOCKED_BY_LABOR_LAW | G1 | 2026/09末 | ✅ **完了** | G1-001で実装済 |
| 15ヶ国語i18n完全対応 | G2 | 2026/11末 | ⏳ 未着手 | RTL対応が最難関 |
| 4フォーマット自動生成 | G3 | 2027/01末 | ⏳ 未着手 | RES-A02連携前提 |
| 朝夕配信スケジューラー | G3 | 2027/01末 | ⏳ 未着手 | Note API要件確認待ち |
| Cloud Run proxyプロキシ | G4 | 2027/02末 | ⏳ 未着手 | 本番移行直前に実装 |

---

## 未決事項（松浦CEO要件定義待ち）

1. **Note（note.com）API**: 2026年6月時点でPublic APIは非公開。手動投稿URLを生成してLINE通知する代替案で進めてよいか確認要。
2. **YouTube**: 動画コンテンツの自動アップロードか、テキスト概要欄のみか。範囲確認要。

---

*本計画書は差異照合レポート（DIFF-20260604-001）に基づき策定されました。*  
*Gate通過時に本計画書の対応状況を更新します。*
