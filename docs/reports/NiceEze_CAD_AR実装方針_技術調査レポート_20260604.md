# NiceEze CAD/DXFインポート & AR計測 — ブラウザ制限・実装方針 技術調査レポート

**レポートID**: TECH-20260604-001  
**作成日**: 2026-06-04  
**作成者**: 自律COO（Claude Code）  
**提出先**: 代表取締役CEO 松浦 学 / 00_NiceEze_AI_Audit  
**調査対象**: TMS-SET-001の「CAD/DXFインポート」「AR計測起動」ボタン — ブラウザ制限確認と現実的実装方針

---

## 1. 調査サマリー（結論先出し）

| 機能 | ブラウザ対応 | 推奨実装方針 | Gate |
|:---|:---:|:---|:---:|
| DXFファイルインポート（解析） | ✅ 可能 | dxf-parser.js（クライアントサイド） | G1 |
| CADファイル（.dwg）インポート | ⚠️ 制限あり | Cloud Run変換サーバー経由（dwg→dxf） | G2 |
| AR計測（スマホカメラ） | ⚠️ 制限あり | WebXR Device API（Chrome Android/iOS Safari） | G1〜G2 |
| AR計測（LiDAR活用） | ❌ ブラウザ不可 | iOS Native App必須（将来対応） | G4以降 |

---

## 2. CAD/DXFインポート 詳細調査

### 2-1. DXFファイル（.dxf）— ブラウザで解析可能

**DXFとは**: AutoCADの公開フォーマット（テキストベース）。

**ブラウザ制限**: なし。DXFはテキストファイルのため、FileReader APIで読み取り、JavaScriptで解析可能。

**推奨ライブラリ**: `dxf-parser`（MIT License、npmパッケージ）

```
対応要素:
  ✅ ENTITIES（LINE, ARC, CIRCLE, POLYLINE, LWPOLYLINE, TEXT, MTEXT）
  ✅ BLOCKS（部屋区画として読み取り）
  ✅ LAYERS（棟・フロア別レイヤー分離）
  ✅ INSERT（ブロック参照）
  ⚠️ 3D要素（MESH, SOLID）→ 2D平面図に変換が必要
```

**実装フロー（TMS-SET-001）**:

```
配送スタッフが建物管理会社からDXFを受領
     ↓
ブラウザで「CAD/DXFインポート」ボタン押下
     ↓
FileReader API → DXFテキスト読み込み（クライアントサイド）
     ↓
dxf-parser.js → POLYLINE / LWPOLYLINE を解析
     ↓
部屋区画 → RoomRecord自動生成
  ├─ 棟名: DXFレイヤー名から抽出
  ├─ 部屋番号: TEXT/MTEXT エンティティから抽出
  ├─ 専有面積(㎡): POLYLINE面積計算（Shoelace公式）
  └─ EV出口距離(m): EV位置エンティティからの距離計算
     ↓
フロアグリッドエディタに自動投入 → 手動確認・修正
```

**精度と制約**:
- 図面品質に依存。汚いDXFは手動修正必要。
- 部屋番号がDXF内にTEXTとして記載されていない場合は手動入力が必要。

**実装コスト**: 低〜中（ライブラリ活用で2〜3日）

---

### 2-2. DWGファイル（.dwg）— Cloud Run変換が必要

**DWGとは**: AutoCADのバイナリ独自フォーマット。仕様は非公開。

**ブラウザ制限**: DWGのJavaScript解析は**ブラウザでは事実上不可能**（バイナリ独自仕様、ライセンス問題）。

**推奨対応**: Cloud Run変換サーバー（G2対応）

```
クライアント → POST /api/convert/dwg→dxf（DWGファイルアップロード）
     ↓
[Cloud Run] ODA File Converter（無料版）または LibreCAD CLI
     ↓
DXFファイル返却 → クライアントで dxf-parser.js 解析
```

**注意**: ODA File Converterは商用利用に別途確認が必要。LibreCADはGPLv2。G2実装時にCEO承認要。

**実装コスト**: 中（Cloud Run設定含め3〜5日）

---

## 3. AR計測 詳細調査

### 3-1. WebXR Device API — ブラウザAR（標準技術）

**対応状況**（2026年6月時点）:

| ブラウザ/OS | WebXR対応 | ARサポート | 備考 |
|:---|:---:|:---:|:---|
| Chrome Android 90+ | ✅ | ✅ ARCore | Androidのみ |
| Safari iOS 16+ | ✅ 部分 | ✅ ARKit | WebXR Hit Test対応 |
| Chrome iOS | ❌ | ❌ | AppleのWKWebView制限 |
| Firefox | ⚠️ | ⚠️ | Nightly限定 |
| LINE LIFF（WebView） | ⚠️ | 要検証 | LINEのWebView制限で動作不保証 |

**制約**: **LINE LIFF（WebView）ではWebXR動作が保証されない**。LINEのWebViewはChrome/Safariの全APIに対応していない場合あり。

**できること**（WebXR Hit Test API）:
```
カメラで平面を認識 → タップで距離計測
  ✅ 床面・壁面の平面認識
  ✅ 2点間距離の計測（EV出口距離に使用）
  ✅ 計測値をフォームに自動入力
```

**実装フロー**:

```
TMS-SET-001「AR計測起動」ボタン → WebXR Session開始
     ↓
カメラ映像上にARオーバーレイ表示
     ↓
ユーザーが2点タップ → 距離計測（Hit Test）
     ↓
計測値（EV出口距離）→ フロアグリッドの選択行に自動入力
     ↓
WebXR Session終了 → TMS-SET-001画面に戻る
```

**実装コスト**: 中〜高（WebXR初期学習コスト含め5〜7日）

---

### 3-2. LiDAR活用（高精度計測）— ブラウザ不可

**制限**: iPhoneのLiDARセンサーへのWebブラウザからのアクセスは**Apple非公開API**のため不可。

**唯一の対応方法**: iOS Native App（Swift）またはReact Native。

**判断**: G4（本番Go-Live）以降の将来対応とし、現フェーズでは対象外。LINE Mini App（LIFF）での標準カメラAR（WebXR）に絞る。

---

## 4. TMS-SET-001 実装ロードマップ

### G1（2026/09末）— ブラウザDXF解析 + WebXR基本

| 機能 | 実装内容 | 難易度 | 工数 |
|:---|:---|:---:|:---:|
| DXF解析エンジン | dxf-parser.js統合、部屋自動抽出 | 中 | 3日 |
| WebXR計測（Android Chrome） | Hit Test API、距離計測UI | 中 | 5日 |
| LIFF対応確認 | LINE WebView動作テスト | 中 | 1日 |
| PWAフォールバック | WebXR非対応時の手動入力ガイド | 低 | 1日 |

### G2（2026/11末）— DWG変換サーバー

| 機能 | 実装内容 | 難易度 | 工数 |
|:---|:---|:---:|:---:|
| DWG→DXF変換 | Cloud Run + ODA/LibreCAD | 高 | 5日 |
| 変換精度テスト | 実物件DXF10件でテスト | 中 | 2日 |

---

## 5. 松浦CEO 確認事項（要件定義待ち）

| # | 確認事項 | 推奨回答 |
|:--|:---|:---|
| 1 | AR計測対象デバイスはAndroid/iOSどちらを優先するか？ | Android優先（WebXR安定）→ iOS追加 |
| 2 | DWG対応は必須か（管理会社はDXFで提供可能か）？ | 不明。DXF提供を先行し、DWG対応はG2で判断 |
| 3 | AR計測精度の許容誤差は？（WebXRで±5〜10cm程度） | FinOps目標（0.7秒以下）には影響なし |
| 4 | LINE LIFF内でのAR計測が動作しない場合、PWAアプリ別提供を許容するか？ | 確認要 |

---

## 6. リスク評価

| リスク | 影響 | 確率 | 対策 |
|:---|:---|:---:|:---|
| LINE LIFF内でWebXR動作しない | TMS-SET-001のAR機能無効 | 中 | PWA（スタンドアロン）でAR提供 |
| DXF品質が低く自動抽出精度が出ない | 手動入力工数増加 | 高 | フォールバック手動入力UI完備 |
| WebXR計測精度 ±10cm超 | EV距離精度不足 | 低 | 手動補正フォームで対応 |
| ODA Converterライセンス問題 | DWG変換機能遅延 | 中 | G2でLibreCAD代替を並行評価 |

---

## 7. 総評・推奨アクション

**G1での推奨実装**:
1. DXF解析（`dxf-parser.js`）— ブラウザ完結で安全・低コスト
2. WebXR計測（Android Chrome優先）— LAYOUT_MASTER準拠の計測UI

**G1スタブ（現状）からの移行**: `tms_set_001.html`の`importCAD()` / `launchAR()`関数を実装に置き換え。インターフェースは既に設定済み。

**CAD/ARに関するFinOps影響**: なし。クライアントサイドDXF解析はGCPコスト0円。WebXRもブラウザAPIのためコスト0円。

---

*本レポートはTMS-SET-001スタブ実装（G1-001コミット）に基づき、G1完全実装の設計根拠として作成されました。*  
*技術状況の変化（LINE LIFF API更新等）により随時更新します。*
