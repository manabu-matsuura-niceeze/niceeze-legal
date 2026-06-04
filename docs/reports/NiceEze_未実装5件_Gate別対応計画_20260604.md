# NiceEze 未実装5件 Gate別対応計画書

**レポートID**: PLAN-20260604-001  
**作成日**: 2026-06-04  
**最終更新**: 2026-06-04（Rev.2 — CEO確定判断5件反映）  
**作成者**: 自律COO（Claude Code）  
**提出先**: 代表取締役CEO 松浦 学 / 00_NiceEze_AI_Audit  
**根拠**: 差異照合レポート（DIFF-20260604-001）❌未実装6件のうちG0完了済1件を除く残り5件

---

## CEO確定判断 反映履歴（Rev.2）

| 判断# | 項目 | 決定内容 | 反映箇所 |
|:--|:---|:---|:---|
| 判断① | note.com | **C案確定: G4以降保留** | G4対応候補に移動 |
| 判断② | YouTube | **B案確定: 構成案・台本まで自動生成、アップロードは手動** | G3計画更新 |
| 判断④ | DWG対応 | **A案確定: DXFのみ対応、DWGは対象外** | CAD計画からDWG削除 |
| 判断⑤ | AR精度 | **A案確定: 許容誤差±50cm以内** | G1技術仕様に反映 |
| 判断⑥ | PWAフォールバック | **A案確定: LIFF非対応時はPWA別URL提供（導線設計もG1スコープ）** | G1スコープ拡張 |
| 判断③ | iOS/Android | **追加調査中: TECH-20260604-002を提出済** | 松浦CEO最終判断待ち |

---

## 対象: 未実装 一覧（Rev.2更新後）

| # | 項目 | 部署 | Gate | 状態 |
|:--|:---|:---|:---:|:---:|
| 1 | Cloud Run proxy経由のClaude API呼出 | GOV部/全部署 | G4 | ⏳ |
| 2 | STATUS_LOCKED_BY_LABOR_LAW | SBDS部 | G1 | ✅ 完了 |
| 3 | 15ヶ国語i18n完全対応 | SURPLUS SHIFT部 | G2 | ⏳ |
| 4 | X/メルマガ/YouTube 3フォーマット自動生成（Note除く） | Marketing-Sys部 | G3 | ⏳ |
| 5 | 朝夕自律配信スケジューラー（X/メルマガ/YouTube） | Marketing-Sys部 | G3 | ⏳ |
| 6 | note.com対応 | Marketing-Sys部 | G4候補 | 🔵 保留 |

---

## Gate別 対応計画詳細

---

### G1（2026/09末）— SBDS完成

#### STATUS_LOCKED_BY_LABOR_LAW ✅ 完了（G1-001 / 2026-06-04）

| 実装内容 | ファイル | 状態 |
|:---|:---|:---:|
| WorkSession.check_labor_law() | `src/sbds/tms_drv_001.py` | ✅ |
| 4時間ロックバナー | `src/sbds/static/tms_drv_001.html` | ✅ |

#### DXFインポート（判断④A確定: DXFのみ/DWG対象外）

**実装仕様**:
```
ライブラリ: dxf-parser.js（MIT License / ブラウザ完結 / GCPコスト¥0）
対応フォーマット: .dxf のみ（.dwg は恒久的対象外）
抽出項目: 棟名(LAYER) / 部屋番号(TEXT/MTEXT) / 専有面積(POLYLINE面積) / EV出口距離(距離計算)
```

| タスク | 難易度 | 工数 |
|:---|:---:|:---:|
| dxf-parser.js統合 + FileReader連携 | 低 | 1日 |
| POLYLINE → RoomRecord自動抽出ロジック | 中 | 2日 |
| 抽出結果プレビュー + 手動修正UI | 低 | 1日 |

#### WebXR AR計測（判断⑤A: ±50cm許容 / 判断⑥A: PWAフォールバック確定）

**実装仕様**:
```
API: WebXR Device API + Hit Test API
精度目標: ±50cm以内（WebXRで達成可能）
優先デバイス: 判断③ CEO最終判断待ち（TECH-20260604-002参照）
LIFF非対応時: PWA別URL提供 + 導線設計（案内文・QRコード）
```

| タスク | 難易度 | 工数 | 備考 |
|:---|:---:|:---:|:---|
| WebXR Hit Test API実装 | 中 | 5日 | 判断③後に着手 |
| ±50cm精度テスト | 中 | 1日 | |
| PWA別URL設定（`/ar`ルート） | 低 | 0.5日 | |
| LIFF→PWA導線: 案内文 + QRコード生成 | 低 | 1日 | 判断⑥A |

**G1通過条件**: SBDS全機能実機テスト / IndexedDB v142動作 / 0.7秒以下 / DXF自動抽出デモ / WebXR ±50cm達成（判断③確定後）

---

### G2（2026/11末）— SURPLUS SHIFT + Research完成

#### 項目23: 15ヶ国語i18n完全対応（SURPLUS SHIFT部）

```
対応15言語:
  日本語(ja) / 英語(en) / 中国語簡体(zh-CN) / 中国語繁体(zh-TW)
  韓国語(ko) / タイ語(th) / ベトナム語(vi) / インドネシア語(id)
  マレー語(ms) / ポルトガル語(pt) / スペイン語(es) / フランス語(fr)
  ドイツ語(de) / アラビア語(ar) / ヒンディー語(hi)
```

| タスク | 難易度 | 工数 |
|:---|:---:|:---:|
| `src/i18n/` + 言語JSONファイル15件 | 中 | 1日 |
| NEG-SUP-001 / NEG-BYR-001 i18nキー置換 | 中 | 4日 |
| 言語切替セレクタ（ヘッダー右上） | 低 | 0.5日 |
| RTL対応: アラビア語 `dir="rtl"` | 高 | 1日 |
| 翻訳テスト | 中 | 1日 |

**G2通過条件**: 15言語UIテスト / RTL正常動作 / bandit全通過

---

### G3（2027/01末）— Marketing-Sys + GOV/S10完成

#### 項目26: 3フォーマット自動生成（判断①②反映版）

**確定仕様（判断①②）**:
- **X投稿**: 140字以内 + ハッシュタグ → **自動投稿（X API v2）**
- **メルマガ**: HTML形式 + 件名 → **自動送信（SendGrid）**
- **YouTube**: タイトル + 概要欄 + 台本 + 構成案 → **生成のみ、アップロードは手動**（判断②B確定）
- **note.com**: **G4以降保留**（判断①C確定）

**アーキテクチャ**:
```
入力: 商品情報 / トレンドスコア（RES-A02連携）
  ↓
[Cloud Run] Marketing-Sys API
  ├─ Claude API（G4プロキシ経由 / G3はSecretManager直接）
  ├─ X投稿: 140字 + ハッシュタグ生成
  ├─ メルマガ: HTML + 件名生成
  └─ YouTube: タイトル + 概要欄 + 台本 + 構成案 生成
       → COO確認パネルに表示 → 手動アップロード
```

| タスク | 難易度 | 工数 |
|:---|:---:|:---:|
| `src/marketing/content_generator.py` | 中 | 2日 |
| 3フォーマット テンプレートエンジン | 中 | 2日 |
| YouTube台本・構成案テンプレート | 中 | 1日 |
| Smart-MKT UI（プレビュー + COO承認） | 中 | 2日 |
| RES-A02トレンドスコア連携 | 中 | 1日 |

#### 項目27: 朝夕自律配信スケジューラー（X/メルマガのみ自動配信）

```
Cloud Scheduler（GCP）
  ├─ 朝6:00 JST → [Cloud Run] /marketing/schedule/morning
  └─ 夕18:00 JST → [Cloud Run] /marketing/schedule/evening
       ├─ X API v2 → 自動投稿
       ├─ SendGrid → 自動配信
       └─ YouTube用コンテンツ → COO確認パネルに格納（手動アップロード待ち）
```

| タスク | 難易度 | 工数 |
|:---|:---:|:---:|
| `src/marketing/scheduler.py` | 中 | 1日 |
| X API v2 自動投稿 | 中 | 1日 |
| SendGrid 自動配信 | 低 | 1日 |
| YouTube コンテンツ格納 + COO通知 | 低 | 1日 |
| 配信ログ → Firestore / BigQuery | 低 | 0.5日 |

**G3通過条件**: 3フォーマット生成デモ / YouTube台本プレビュー動作 / スケジューラー実機テスト / bandit全通過

---

### G4（2027/02末）— 本番デプロイ + 保留項目着手

#### 項目7: Cloud Run proxy経由のClaude API呼出（全部署共通）

```
フロントエンド → fetch('/api/claude') ← APIキーなし
[Cloud Run] claude-proxy
  ├─ GCP Secret Manager → ANTHROPIC_API_KEY
  ├─ レート制限（Redis Memorystore）
  ├─ キャッシュ（Firestore TTL 1時間）
  └─ Anthropic API → レスポンス返却
```

| タスク | 難易度 | 工数 |
|:---|:---:|:---:|
| `src/proxy/claude_proxy.py` | 中 | 2日 |
| Secret Manager連携 | 低 | 0.5日 |
| Redis キャッシュ層 | 中 | 1日 |
| 全画面プロキシ切替 | 中 | 2日 |
| 負荷テスト（3万世帯） | 高 | 2日 |

#### note.com対応（判断①C確定: G4候補）

**G4実装検討内容**:
```
2027年初頭時点でのnote.com API公開状況を再確認の上、以下を判断:
  ケースA: API公開 → note投稿自動生成 + 配信を追加
  ケースB: API未公開 → Markdown生成 + COO手動投稿URL通知（現行方針継続）
```
G4開始時（2027年1月末）に松浦CEOへ再判断を仰ぐ。

**G4通過条件**: APIキーフロント露出0件 / 実通信テスト / UAT全項目グリーン / 本番Go-Live

---

## 対応計画 サマリー表（Rev.2）

| 項目 | Gate | 予定時期 | 状態 | 確定根拠 |
|:---|:---:|:---|:---:|:---|
| STATUS_LOCKED_BY_LABOR_LAW | G1 | 2026/09末 | ✅ **完了** | G1-001 (2026-06-04) |
| DXFインポート（DWG除外確定） | G1 | 2026/09末 | ⏳ | 判断④A確定 |
| WebXR AR計測（±50cm/PWA導線） | G1 | 2026/09末 | ⏳ | 判断⑤⑥A確定 / 判断③待ち |
| 15ヶ国語i18n完全対応 | G2 | 2026/11末 | ⏳ | — |
| 3フォーマット自動生成 | G3 | 2027/01末 | ⏳ | 判断①②確定 |
| 朝夕配信スケジューラー | G3 | 2027/01末 | ⏳ | 判断①②確定 |
| Cloud Run proxyプロキシ | G4 | 2027/02末 | ⏳ | — |
| note.com対応 | G4候補 | 2027/02以降 | 🔵 保留 | 判断①C確定 |

---

## 未決事項（松浦CEO最終判断待ち）

| # | 項目 | 内容 | 提出資料 |
|:--|:---|:---|:---|
| 判断③ | iOS/Android対応範囲 | A案（Android優先）vs B案（同時対応） | TECH-20260604-002 |

---

*本計画書はCEO確定判断（判断①②④⑤⑥）を反映したRev.2です。*  
*判断③確定後にRev.3を発行します。*
