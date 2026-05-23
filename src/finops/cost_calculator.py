"""
NiceEze FinOps コスト計算エンジン
Ver 2.3 — GCP完全一元化版

【Gemini参謀指摘による軌道修正】
  BEFORE: Supabase（DB） + Vercel（ホスティング）
  AFTER:  Cloud SQL PostgreSQL（DB） + Cloud Run（ホスティング） + Memorystore Redis

コスト構成（GCPネイティブ）:
  - Cloud SQL PostgreSQL（DB）
  - Cloud Run（API / OCR / LIFF Worker）
  - Memorystore for Redis（Redis Streams / キャッシュ）
  - Cloud Storage（OCR原票・アセット）
  - BigQuery（月次アーカイブ・分析）
  - LINE Messaging API（PUSH通知）
  - Claude API / Vertex AI（AI処理）
  - Cloud Monitoring + Error Reporting（監視）
"""

from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────
COST_CEILING_YEN        = 5.0
TARGET_HOUSEHOLDS       = 30_000
PACKAGES_PER_HOUSEHOLD  = 4
TARGET_MONTHLY_PACKAGES = TARGET_HOUSEHOLDS * PACKAGES_PER_HOUSEHOLD  # 120,000
USD_TO_JPY              = 150.0


@dataclass
class CostItem:
    name: str
    monthly_usd: float
    note: str = ""

    @property
    def monthly_jpy(self) -> float:
        return self.monthly_usd * USD_TO_JPY


@dataclass
class FinOpsCostEstimate:
    """
    3万世帯スケール / GCPネイティブ構成のコスト見積もり

    【削除】Supabase Pro ($75/月) → Cloud SQL PostgreSQL ($65/月) に置換
    【削除】Vercel Pro ($20/月)   → Cloud Run に統合
    【追加】Memorystore Redis ($40/月) — Redis Streams for PULL型更新
    【追加】BigQuery ($5/月)          — 月次パーティションアーカイブ
    """
    db: CostItem = field(default_factory=lambda: CostItem(
        "Cloud SQL PostgreSQL (db-n2-standard-2)",
        monthly_usd=65.0,
        note="db-n2-standard-2 HA構成 $65/月。"
             "Cloud SQL Auth Proxy経由接続。自動バックアップ・PITR込み",
    ))
    redis: CostItem = field(default_factory=lambda: CostItem(
        "Memorystore for Redis (M1 1GB)",
        monthly_usd=40.0,
        note="Redis Streams: PULL型通知キュー + LLMレスポンスキャッシュ。"
             "LINE PUSH課金防御の中核コンポーネント",
    ))
    compute: CostItem = field(default_factory=lambda: CostItem(
        "Cloud Run (API + OCR Worker + LIFF Worker)",
        monthly_usd=35.0,
        note="min-instances=0 (コールドスタート許容)。"
             "API: 2vCPU/1GB、OCR: 1vCPU/512MB、LIFF: 1vCPU/256MB",
    ))
    ai_api: CostItem = field(default_factory=lambda: CostItem(
        "Claude API (Haiku優先 + Sonnet財務スポット)",
        monthly_usd=40.0,
        note="OCR Stage3: Haiku ($0.25/MTok) → Sonnetの1/12コスト。"
             "財務スポットのみSonnet ($3/MTok)。120K荷物/月想定",
    ))
    storage: CostItem = field(default_factory=lambda: CostItem(
        "Cloud Storage (OCR原票 24h TTL + 静的アセット)",
        monthly_usd=5.0,
        note="nearline: OCR一時保存 (24h自動削除)。"
             "standard: 静的アセット ~10GB",
    ))
    bigquery: CostItem = field(default_factory=lambda: CostItem(
        "BigQuery (月次アーカイブ + 分析クエリ)",
        monthly_usd=3.0,
        note="月次パーティションDETACH→BQエクスポート。"
             "ストレージ $0.02/GB、クエリ $5/TB（オンデマンド）",
    ))
    line_push: CostItem = field(default_factory=lambda: CostItem(
        "LINE Messaging API (PUSH最適化後)",
        monthly_usd=30.0,
        note="Redis Streams PULL型で重複排除後の推定通数。"
             "120K荷物 → 約45K PUSH/月 × $0.001 (¥0.15〜3/通)",
    ))
    monitoring: CostItem = field(default_factory=lambda: CostItem(
        "Cloud Monitoring + Error Reporting + Sentry",
        monthly_usd=10.0,
        note="GCP標準監視 + Sentry Pro。FinOpsアラート込み",
    ))
    other: CostItem = field(default_factory=lambda: CostItem(
        "その他 (Cloud DNS / KMS / IAM / CDN)",
        monthly_usd=7.0,
        note="Cloud Armor ($5) + KMS鍵管理 ($2)。"
             "egress: Cloud CDN経由で最小化",
    ))

    monthly_packages: int = TARGET_MONTHLY_PACKAGES

    # ── 計算プロパティ ──────────────────────────

    @property
    def all_items(self) -> list:
        return [
            self.db, self.redis, self.compute, self.ai_api,
            self.storage, self.bigquery, self.line_push,
            self.monitoring, self.other,
        ]

    @property
    def total_monthly_usd(self) -> float:
        return sum(i.monthly_usd for i in self.all_items)

    @property
    def total_monthly_jpy(self) -> float:
        return self.total_monthly_usd * USD_TO_JPY

    @property
    def cost_per_package_jpy(self) -> float:
        if self.monthly_packages == 0:
            return float("inf")
        return round(self.total_monthly_jpy / self.monthly_packages, 4)

    @property
    def finops_cleared(self) -> bool:
        return self.cost_per_package_jpy <= COST_CEILING_YEN

    @property
    def headroom_pct(self) -> float:
        return round(
            (COST_CEILING_YEN - self.cost_per_package_jpy) / COST_CEILING_YEN * 100, 1
        )

    def to_dict(self) -> dict:
        return {
            "db_cost_monthly_yen":      round(self.db.monthly_jpy),
            "api_cost_monthly_yen":     round(self.ai_api.monthly_jpy + self.compute.monthly_jpy),
            "storage_cost_monthly_yen": round(self.storage.monthly_jpy + self.bigquery.monthly_jpy),
            "monthly_packages":         self.monthly_packages,
        }

    def report_text(self) -> str:
        lines = [
            f"## GCPネイティブ FinOps コスト試算（3万世帯 = {self.monthly_packages:,}荷物/月）",
            "",
            "| コスト項目 | USD/月 | JPY/月 | 円/荷物 |",
            "|-----------|--------|--------|--------|",
        ]
        for item in self.all_items:
            per_pkg = round(item.monthly_jpy / self.monthly_packages, 4)
            lines.append(
                f"| {item.name} | ${item.monthly_usd:.0f} "
                f"| ¥{item.monthly_jpy:,.0f} | {per_pkg:.4f}円 |"
            )
        lines += [
            f"| **合計** | **${self.total_monthly_usd:.0f}** "
            f"| **¥{self.total_monthly_jpy:,.0f}** | **{self.cost_per_package_jpy:.4f}円** |",
            "",
            f"**1荷物あたりコスト**: {self.cost_per_package_jpy:.4f}円",
            f"**5円の壁**: {'✅ クリア' if self.finops_cleared else '❌ 超過'} "
            f"（余裕: {self.headroom_pct:.1f}%）",
            "",
            "### 軌道修正による変化",
            f"| 項目 | Before (Supabase/Vercel) | After (GCPネイティブ) |",
            f"|------|-------------------------|----------------------|",
            f"| DB | Supabase Pro $75 | Cloud SQL $65 (▲$10) |",
            f"| ホスティング | Vercel Pro $20 | Cloud Run統合済 |",
            f"| Redis | なし | Memorystore $40 (新規) |",
            f"| BigQuery | なし | $3 (新規・月次アーカイブ) |",
            f"| 合計 | $235/月 | ${self.total_monthly_usd:.0f}/月 |",
            f"| 円/荷物 | ¥0.29 | ¥{self.cost_per_package_jpy:.4f} ✅ |",
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────────
# スケール別シミュレーション（GCPネイティブ）
# ─────────────────────────────────────────────
def simulate_scale_costs(
    base_estimate: Optional["FinOpsCostEstimate"] = None,
    scale_points: list = None,
) -> list[dict]:
    if base_estimate is None:
        base_estimate = FinOpsCostEstimate()
    if scale_points is None:
        scale_points = [1_000, 5_000, 10_000, 30_000, 100_000, 500_000]

    results = []
    for households in scale_points:
        pkgs         = households * PACKAGES_PER_HOUSEHOLD
        scale_factor = (households / TARGET_HOUSEHOLDS) ** 0.72

        est = FinOpsCostEstimate(
            db=CostItem("Cloud SQL", base_estimate.db.monthly_usd * scale_factor),
            redis=CostItem("Memorystore", base_estimate.redis.monthly_usd * (scale_factor ** 0.6)),
            compute=CostItem("Cloud Run", base_estimate.compute.monthly_usd * scale_factor),
            ai_api=CostItem("Claude API", base_estimate.ai_api.monthly_usd * scale_factor),
            storage=CostItem("GCS", base_estimate.storage.monthly_usd * (scale_factor ** 0.5)),
            bigquery=CostItem("BigQuery", base_estimate.bigquery.monthly_usd * (scale_factor ** 0.4)),
            line_push=CostItem("LINE PUSH", base_estimate.line_push.monthly_usd * scale_factor),
            monitoring=CostItem("Monitoring", base_estimate.monitoring.monthly_usd),
            other=CostItem("Other", base_estimate.other.monthly_usd * (scale_factor ** 0.3)),
            monthly_packages=pkgs,
        )
        results.append({
            "households":        households,
            "monthly_packages":  pkgs,
            "cost_per_pkg_jpy":  est.cost_per_package_jpy,
            "total_monthly_jpy": round(est.total_monthly_jpy),
            "finops_cleared":    est.finops_cleared,
            "headroom_pct":      est.headroom_pct,
        })
    return results


if __name__ == "__main__":
    est = FinOpsCostEstimate()
    print(est.report_text())
    print("\n## スケール別シミュレーション（GCPネイティブ）")
    print(f"{'世帯数':>10} {'荷物/月':>10} {'円/荷物':>10} {'月額(万円)':>12} {'5円の壁':>8}")
    print("-" * 55)
    for r in simulate_scale_costs(est):
        wall    = "✅" if r["finops_cleared"] else "❌"
        monthly = r["total_monthly_jpy"] / 10_000
        print(
            f"{r['households']:>10,} {r['monthly_packages']:>10,} "
            f"{r['cost_per_pkg_jpy']:>9.4f}円 {monthly:>11.1f}万円 {wall:>8}"
        )
