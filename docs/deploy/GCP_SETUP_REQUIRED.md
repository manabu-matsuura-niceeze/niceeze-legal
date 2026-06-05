# GCP本番デプロイ設定手順書（エンジニア向け）

作成日: 2026-06-05  
作成者: NiceEze Code（松浦CEO指示）  
ステータス: **エンジニア対応待ち**

---

## 概要

NiceEze自律経営執行システム v14.2 の本番デプロイに必要なGCP設定手順。  
GitHub Actions ワークフロー (`deploy-production.yml`) がGCP Cloud Runへデプロイする。

---

## 1. GCPプロジェクト情報

| 項目 | 値 |
|---|---|
| プロジェクトID | `serene-bonbon-236821` |
| プロジェクト番号 | `172953916843` |
| リージョン | `asia-northeast1`（東京） |
| サービスアカウント | `niceeze-audit-sync@serene-bonbon-236821.iam.gserviceaccount.com` |

---

## 2. 必要なGCP API（全て有効化すること）

```bash
gcloud services enable cloudresourcemanager.googleapis.com --project=serene-bonbon-236821
gcloud services enable artifactregistry.googleapis.com --project=serene-bonbon-236821
gcloud services enable run.googleapis.com --project=serene-bonbon-236821
gcloud services enable containerregistry.googleapis.com --project=serene-bonbon-236821
gcloud services enable secretmanager.googleapis.com --project=serene-bonbon-236821
gcloud services enable cloudbuild.googleapis.com --project=serene-bonbon-236821
```

GCPコンソールからの有効化URL（ビリングリンク後に実行）:
- Cloud Resource Manager: https://console.developers.google.com/apis/api/cloudresourcemanager.googleapis.com/overview?project=172953916843
- Artifact Registry: https://console.developers.google.com/apis/api/artifactregistry.googleapis.com/overview?project=172953916843
- Cloud Run: https://console.developers.google.com/apis/api/run.googleapis.com/overview?project=172953916843

---

## 3. ビリングアカウント設定

```
GCPコンソール → 請求 → プロジェクトのリンク
対象: serene-bonbon-236821
※ビリングアカウントリンクなしではAPI有効化不可
```

---

## 4. サービスアカウントIAMロール設定

サービスアカウント `niceeze-audit-sync@serene-bonbon-236821.iam.gserviceaccount.com` に以下のロールを付与:

```bash
PROJECT=serene-bonbon-236821
SA=niceeze-audit-sync@serene-bonbon-236821.iam.gserviceaccount.com

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" \
  --role="roles/iam.serviceAccountUser"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" \
  --role="roles/serviceusage.serviceUsageAdmin"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA" \
  --role="roles/artifactregistry.admin"
```

---

## 5. サービスアカウントキー作成とGitHub Secrets登録

```bash
# キー作成
gcloud iam service-accounts keys create gcp-sa-key.json \
  --iam-account=niceeze-audit-sync@serene-bonbon-236821.iam.gserviceaccount.com

# キー内容を確認（JSONであること）
cat gcp-sa-key.json | head -5
# 先頭が { "type": "service_account" で始まることを確認
```

GitHubリポジトリ Settings → Secrets and variables → Actions:

| Secret名 | 値 |
|---|---|
| `GCP_SA_KEY` | `gcp-sa-key.json` の**中身全文**（ファイルパスではなくJSON文字列） |
| `KEEPA_API_KEY` | KeepaダッシュボードのAPIキー（Gate A実連携時） |

**注意**: キーファイル（gcp-sa-key.json）はGitにコミットしないこと。使用後削除。

---

## 6. Cloud Run デプロイ設定

### デプロイコマンド（参考）

```bash
# RESEARCH サービス
gcloud run deploy niceeze-research \
  --image gcr.io/serene-bonbon-236821/niceeze-research:latest \
  --region asia-northeast1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "NICEEZE_ENV=production,GCP_PROJECT_ID=serene-bonbon-236821" \
  --project serene-bonbon-236821

# MARKETING サービス
gcloud run deploy niceeze-marketing \
  --image gcr.io/serene-bonbon-236821/niceeze-marketing:latest \
  --region asia-northeast1 \
  --platform managed \
  --allow-unauthenticated \
  --port 8081 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --set-env-vars "NICEEZE_ENV=production,GCP_PROJECT_ID=serene-bonbon-236821" \
  --project serene-bonbon-236821
```

### ヘルスチェックURL（デプロイ後確認）

```bash
RESEARCH_URL=$(gcloud run services describe niceeze-research \
  --region asia-northeast1 --project serene-bonbon-236821 \
  --format 'value(status.url)')
curl -sf "$RESEARCH_URL/health"
# 期待レスポンス: {"status":"ok","module":"research","version":"1.0"}

MARKETING_URL=$(gcloud run services describe niceeze-marketing \
  --region asia-northeast1 --project serene-bonbon-236821 \
  --format 'value(status.url)')
curl -sf "$MARKETING_URL/health"
# 期待レスポンス: {"status":"ok","module":"marketing"}
```

---

## 7. GitHub Actions 本番デプロイトリガー手順

1. GitHub → `niceeze-legal` リポジトリ
2. Actions → `NiceEze Deploy — 本番（手動・CEO承認必須）`
3. `Run workflow` → Branch: `main`
4. 入力:
   - `承認者名`: 松浦学 CEO
   - `最終確認`: 本番デプロイを承認する
5. `Run workflow` 実行

---

## 8. FinOps上限（厳守）

| 項目 | 上限 |
|---|---|
| 月額合計 | ¥5,000 |
| 1配送あたり | ¥0.5 |
| Cloud Run min-instances | 0（アイドル時無課金） |

---

## 担当者へのお願い

設定完了後、松浦CEO（manabu.matsuura@niceeze.com）へ以下を報告:
- Cloud Run RESEARCH URL
- Cloud Run MARKETING URL
- /health エンドポイント疎通確認結果
