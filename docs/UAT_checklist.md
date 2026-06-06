# NiceEze 自律経営執行システム UAT チェックリスト

**実施者**: 松浦学 CEO
**環境**: ステージング（localhost）
**対象デバイス**: iPhone（Safari） / PC（Chrome）
**実施日**: ___________

---

## 事前準備

1. [ ] PCでターミナルを開く
2. [ ] `bash scripts/start_all_staging.sh` を実行
3. [ ] 全6システムが「起動OK」と表示されるまで待つ（30秒程度）
4. [ ] ブラウザで `docs/staging_portal.html` を開く
5. [ ] スマホ確認の場合: PCのローカルIPをメモしておく
   ```
   ifconfig | grep "inet "
   ```
   ※ `192.168.x.x` 形式のIPをメモ（以降 `{PC_IP}` と記載）

---

## システム別チェックリスト

---

### 1. RESEARCH（市場調査システム） port 8080

#### PC確認

- [ ] **ヘルスチェック**
  ブラウザ: http://localhost:8080/health
  ```
  curl http://localhost:8080/health
  ```
  期待値: `{"status":"ok","module":"research","version":"1.0"}`

- [ ] **価格マトリクス取得**
  ブラウザ: http://localhost:8080/price?keyword=トイレットペーパー&category=日用品・消耗品
  ```
  curl "http://localhost:8080/price?keyword=トイレットペーパー&category=日用品・消耗品"
  ```
  期待値: 価格一覧のJSONが返る（keyword/category フィールドを含む）

- [ ] **トレンドスコア取得**
  ブラウザ: http://localhost:8080/trend?keyword=洗剤&category=日用品・消耗品
  ```
  curl "http://localhost:8080/trend?keyword=洗剤&category=日用品・消耗品"
  ```
  期待値: トレンドスコアのJSONが返る（score フィールドを含む）

- [ ] **期間指定トレンド取得**
  ```
  curl "http://localhost:8080/trend?keyword=シャンプー&category=日用品・消耗品&days=7"
  ```
  期待値: 7日分のトレンドデータが返る

- [ ] **存在しないパスの404確認**
  ```
  curl http://localhost:8080/unknown
  ```
  期待値: `{"error":"Not Found","path":"/unknown"}`

#### スマホ確認（PCのIPを使用）

- [ ] http://{PC_IP}:8080/health をSafariで開き 200 OK ・JSONが表示される

---

### 2. MARKETING（マーケティング自動化） port 8081

#### PC確認

- [ ] **ヘルスチェック**
  ブラウザ: http://localhost:8081/health
  ```
  curl http://localhost:8081/health
  ```
  期待値: `{"status":"ok","module":"marketing","version":"1.0"}`

- [ ] **配信ログサマリー取得**
  ブラウザ: http://localhost:8081/log/summary
  ```
  curl http://localhost:8081/log/summary
  ```
  期待値: 配信ログの集計JSONが返る

- [ ] **コンテンツ生成（POST）**
  ```
  curl -X POST http://localhost:8081/generate \
    -H "Content-Type: application/json" \
    -d '{"topic":"洗剤","category":"日用品・消耗品","tone":"professional","trend_score":0.8}'
  ```
  期待値: SNS投稿テキスト等を含むコンテンツJSONが返る

- [ ] **配信ログ追加（POST）**
  ```
  curl -X POST http://localhost:8081/log/add \
    -H "Content-Type: application/json" \
    -d '{"content_type":"x_post","topic":"洗剤","category":"日用品・消耗品","char_count":140}'
  ```
  期待値: 201 Created・追加されたレコードJSONが返る

- [ ] **X投稿（POST・モック確認）**
  ```
  curl -X POST http://localhost:8081/x/post \
    -H "Content-Type: application/json" \
    -d '{"text":"【UATテスト投稿】NiceEze自律システム稼働中 #NiceEze"}'
  ```
  期待値: 投稿結果のJSONが返る（モック環境では posted/mock フィールドを確認）

#### スマホ確認

- [ ] http://{PC_IP}:8081/health をSafariで開き 200 OK ・JSONが表示される

---

### 3. GOV（経営管理システム） port 8082

#### PC確認

- [ ] **ヘルスチェック**
  ブラウザ: http://localhost:8082/health
  ```
  curl http://localhost:8082/health
  ```
  期待値: `{"status":"ok","module":"gov","version":"1.0"}`

- [ ] **COOレポート取得**
  ブラウザ: http://localhost:8082/coo/report/2026-06
  ```
  curl http://localhost:8082/coo/report/2026-06
  ```
  期待値: COOレポートのJSONが返る（month/kpis/budgets フィールドを含む）

- [ ] **FinOpsサマリー取得**
  ブラウザ: http://localhost:8082/finops/summary/2026-06
  ```
  curl http://localhost:8082/finops/summary/2026-06
  ```
  期待値: コスト集計JSONが返る（月額¥5,000以内の範囲か確認）

- [ ] **FinOpsアラート確認**
  ブラウザ: http://localhost:8082/finops/alerts
  ```
  curl http://localhost:8082/finops/alerts
  ```
  期待値: アラート一覧のJSON配列が返る（空配列も正常）

- [ ] **OpsヘルスステータスR取得**
  ブラウザ: http://localhost:8082/ops/health
  ```
  curl http://localhost:8082/ops/health
  ```
  期待値: 各サービスのヘルス状態を示すJSON配列が返る

- [ ] **KPI登録（POST）**
  ```
  curl -X POST http://localhost:8082/coo/kpi \
    -H "Content-Type: application/json" \
    -d '{"kpi_name":"配送完了率","target":98.0,"actual":96.5,"unit":"%","month":"2026-06"}'
  ```
  期待値: 201 Created・登録されたKPIレコードが返る

#### スマホ確認

- [ ] http://{PC_IP}:8082/health をSafariで開き 200 OK ・JSONが表示される

---

### 4. TRAVEL（手ぶら旅行サービス） port 8083

> **補足**: `python -m src.sbds.travel_api` で起動。SBDSと連携した旅行者向け事前配送サービス。

#### PC確認

- [ ] **ヘルスチェック**
  ブラウザ: http://localhost:8083/health
  ```
  curl http://localhost:8083/health
  ```
  期待値: `{"status":"ok"}` または `{"status":"ok","module":"travel"}` 形式のJSON

- [ ] **サービス起動ログ確認**
  ターミナルで `python -m src.sbds.travel_api` 実行時に
  起動メッセージが表示されることを確認

- [ ] **存在しないパスの404確認**
  ```
  curl http://localhost:8083/unknown
  ```
  期待値: 404 Not Found レスポンスが返る

- [ ] **レスポンスヘッダー確認（CORS）**
  ```
  curl -v http://localhost:8083/health 2>&1 | grep -i "access-control"
  ```
  期待値: `Access-Control-Allow-Origin: *` ヘッダーが含まれる

- [ ] **同時アクセス確認**
  ```
  curl http://localhost:8083/health & curl http://localhost:8083/health & wait
  ```
  期待値: 両方のリクエストが正常に200を返す

#### スマホ確認

- [ ] http://{PC_IP}:8083/health をSafariで開き 200 OK ・JSONが表示される

---

### 5. SBDS（配送管理システム） port 8084

> **補足**: `python -m src.sbds.tms_server` で起動。館内ラストワンマイル配送のTMS。

#### PC確認

- [ ] **ヘルスチェック**
  ブラウザ: http://localhost:8084/health
  ```
  curl http://localhost:8084/health
  ```
  期待値: `{"status":"ok"}` または `{"status":"ok","module":"sbds"}` 形式のJSON

- [ ] **サービス起動ログ確認**
  ターミナルで `python -m src.sbds.tms_server` 実行時に
  TMS起動メッセージが表示されることを確認

- [ ] **存在しないパスの404確認**
  ```
  curl http://localhost:8084/unknown
  ```
  期待値: 404 Not Found レスポンスが返る

- [ ] **レスポンスヘッダー確認（CORS）**
  ```
  curl -v http://localhost:8084/health 2>&1 | grep -i "access-control"
  ```
  期待値: `Access-Control-Allow-Origin: *` ヘッダーが含まれる

- [ ] **静的ファイル確認（tms_drv_001.html）**
  ブラウザ: http://localhost:8084/
  TMS配送ダッシュボード画面が表示されることを確認
  （`src/sbds/static/tms_drv_001.html` が提供される）

#### スマホ確認

- [ ] http://{PC_IP}:8084/health をSafariで開き 200 OK ・JSONが表示される
- [ ] http://{PC_IP}:8084/ でTMS画面がスマホ表示されることを確認

---

### 6. SURPLUS SHIFT（余剰在庫転換） port 8085

> **補足**: `python -m src.surplus_shift.surplus_server` で起動。Keepa連携・Gate A〜D マルチゲート審査フロー。

#### PC確認

- [ ] **ヘルスチェック**
  ブラウザ: http://localhost:8085/health
  ```
  curl http://localhost:8085/health
  ```
  期待値: `{"status":"ok"}` または `{"status":"ok","module":"surplus_shift"}` 形式のJSON

- [ ] **サービス起動ログ確認**
  ターミナルで `python -m src.surplus_shift.surplus_server` 実行時に
  起動メッセージが表示されることを確認

- [ ] **存在しないパスの404確認**
  ```
  curl http://localhost:8085/unknown
  ```
  期待値: 404 Not Found レスポンスが返る

- [ ] **価格スナップショット取得（Gate A Keepa連携）**
  ```
  curl "http://localhost:8085/price?asin=B08XYZ1234"
  ```
  または
  ```
  curl http://localhost:8085/gate/a/price
  ```
  期待値: PriceSnapshot形式のJSONが返る（モック or Keepa実データ）

- [ ] **ゲート審査フロー確認（Gate A〜D）**
  ```
  curl -X POST http://localhost:8085/gate/evaluate \
    -H "Content-Type: application/json" \
    -d '{"asin":"B08XYZ1234","title":"テスト商品","stock_qty":10,"cost_jpy":500}'
  ```
  期待値: ゲート通過/不通過の判定結果JSONが返る

#### スマホ確認

- [ ] http://{PC_IP}:8085/health をSafariで開き 200 OK ・JSONが表示される

---

## 統合確認

### ポータル画面確認
- [ ] `docs/staging_portal.html` をChromeで開く — 全6カードが表示される
- [ ] `docs/staging_portal.html` をiPhone Safariで開く — 1カラムで正常表示される
- [ ] 各カードの「▶ 起動確認」ボタンをタップ — `/health` が新しいタブで開く
- [ ] スマホでの表示: 文字が読みやすいサイズか確認（16px以上推奨）

### デモデータ確認
- [ ] `python scripts/seed_demo_data.py` を実行（存在する場合）
- [ ] RESEARCH: デモ商品で `/price` を確認
- [ ] GOV: デモ月（2026-06）で `/coo/report/2026-06` を確認

---

## 確認完了サイン

| 項目 | 結果 |
|------|------|
| 全システム /health OK | ☐ OK / ☐ NG |
| スマホ（iPhone Safari）表示確認 | ☐ OK / ☐ NG |
| ポータル画面表示確認 | ☐ OK / ☐ NG |
| デモデータ投入確認 | ☐ OK / ☐ NG / ☐ スキップ |

- [ ] 全システム /health OK
- [ ] スマホ表示確認（staging_portal.html）
- [ ] デモデータ投入確認（seed_demo_data.py 実行後）
- [ ] **CEOサイン**: __________________ &nbsp; **日時**: __________________

---

*本チェックリストは NiceEze 自律経営執行システム UAT 専用です。*
*問い合わせ: manabu.matsuura@niceeze.com*
