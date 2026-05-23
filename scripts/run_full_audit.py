#!/usr/bin/env python3
"""
NiceEze 多層監査 フルランナー Ver 2.3
GCPネイティブ構成 / GitHub Actions対応版

使い方（ローカル）:
  python scripts/run_full_audit.py \\
    --task "Ver 2.3 Layer3実装完了" \\
    --summary "GCP一元化+LIFF通知連携"

使い方（GitHub Actions / NICEEZE_GDRIVE_SERVICE_ACCOUNT_JSON設定済み）:
  python scripts/run_full_audit.py \\
    --task "CI自動実行" --commit "abc1234"
  → 環境変数から自動的に本番GDriveSyncerを使用

使い方（FinOpsのみ）:
  python scripts/run_full_audit.py --finops-only
"""

import sys
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit.multi_layer_audit import (
    MultiLayerAuditOrchestrator,
    AuditStatus,
)
from src.gdrive.gdrive_syncer import get_syncer
from src.finops.cost_calculator import FinOpsCostEstimate, simulate_scale_costs

# ─────────────────────────────────────────────
# Layer3 移行完了後のデフォルト Gemini協議事項
# ─────────────────────────────────────────────
DEFAULT_GEMINI_NOTE = """【Ver 2.3 → Ver 3.0 (Layer4) への移行協議】

GCP完全一元化 + Layer3 LIFF通知連携の実装が完了しました。
次のLayer4（BigQueryアーカイブパイプライン）に向けて以下の協議を求めます。

1. OCR Stage2 モデル切り替えトリガー（松浦CEO決定：精度閾値95%厳格化）
   - Haiku（精度~88%）→ Sonnet（精度~97%）切り替え条件
   - 閾値: 95%未満の場合にSonnetへ自動エスカレーション
   - コスト影響: Haiku $0.05/荷物 → Sonnet $0.20/荷物（4倍）
   - 誤配送リスクと追加コストのトレードオフについてセカンドオピニオンを求めます

2. BigQuery月次アーカイブパイプライン設計
   - Cloud Scheduler + Cloud SQL → BigQuery Data Transfer Service
   - 対象: delivered & 3ヶ月超のpackagesパーティション
   - PII除去: packages_archive_candidates VIEW経由（address_encrypted除外済）

問題がなければ松浦CEOに最終承認（Layer4本番デプロイ）を仰ぎます。"""

DEFAULT_SPEC_CHECKLIST = [
    "個人情報の暗号化（AES-256）",
    "Row Level Security（RLS）の実装",
    "DBテーブル定義の完全性",
    "APIレート制限の実装",
    "FinOps予算枠（Inputs_Master.csv）との整合",
    "指数関数的スケール対応（パーティショニング）",
]


def parse_args():
    p = argparse.ArgumentParser(description="NiceEze 多層監査フルランナー Ver 2.3")
    p.add_argument("--task",       default="Ver 2.3 GCPネイティブ + Layer3 LIFF通知連携")
    p.add_argument("--summary",    default=(
        "GCPネイティブ構成確定（Cloud SQL + Memorystore Redis + Cloud Run）+ "
        "Layer3 LIFF通知連携（LinePushGuard 5防御ルール + LiffPullHandler PULL型更新）完全実装。"
        "テスト52件PASS。bandit HIGH=0 MEDIUM=0。FinOps 0.2938円/荷物（余裕94.1%）。"
    ))
    p.add_argument("--commit",     default="")
    p.add_argument("--mock-gdrive", action="store_true",
                   help="MockGDriveを強制使用（デフォルト: 環境変数あれば本番）")
    p.add_argument("--skip-gdrive", default="false")
    p.add_argument("--finops-only", action="store_true")
    p.add_argument("--gemini-note", default=DEFAULT_GEMINI_NOTE)
    return p.parse_args()


def run_finops_simulation():
    print("\n" + "="*60)
    print("  NiceEze FinOps スケールシミュレーション（GCPネイティブ）")
    print("="*60)
    est = FinOpsCostEstimate()
    print("\n" + est.report_text())
    print("\n## 📈 指数関数的スケール別コスト試算\n")
    print(f"{'世帯数':>12} {'荷物/月':>12} {'円/荷物':>10} {'月額(万円)':>12} {'5円の壁':>8}")
    print("-" * 60)
    for r in simulate_scale_costs(est):
        wall    = "✅" if r["finops_cleared"] else "❌"
        monthly = r["total_monthly_jpy"] / 10_000
        print(
            f"{r['households']:>12,} {r['monthly_packages']:>12,} "
            f"{r['cost_per_pkg_jpy']:>9.4f}円 {monthly:>11.1f}万円 {wall:>8}"
        )


def main():
    args = parse_args()

    if args.finops_only:
        run_finops_simulation()
        return

    # GDriveSyncer: 環境変数あれば本番、なければMock
    use_mock = args.mock_gdrive or args.skip_gdrive.lower() == "true"
    syncer   = get_syncer(use_mock=use_mock)

    est = FinOpsCostEstimate()

    orch   = MultiLayerAuditOrchestrator(gdrive_syncer=syncer)
    report = orch.run(
        task_name              = args.task,
        implementation_summary = args.summary,
        cost_estimate          = est.to_dict(),
        spec_checklist         = DEFAULT_SPEC_CHECKLIST,
        gemini_note            = args.gemini_note,
        project_root           = str(ROOT),
    )

    # ── サマリー出力 ──
    print("\n" + "─"*60)
    print("  📊 Ver 2.3 監査完了サマリー")
    print("─"*60)
    print(f"  タスク      : {report.task_name[:60]}")
    print(f"  総合判定    : {report.overall_status}")
    print(f"  Layer1      : {report.layer1.status}")
    print(f"  Layer2      : {report.layer2.status}")
    print(f"  テスト結果  : {report.layer1.passed_tests}/{report.layer1.total_tests} PASS")
    print(f"  脆弱性      : {report.layer1.vulnerability_count} 件")
    print(f"  FinOps      : {est.cost_per_package_jpy:.4f}円/荷物（余裕{est.headroom_pct}%）")
    if report.gdrive_doc_url:
        print(f"  GDrive URL  : {report.gdrive_doc_url}")
    print("─"*60)

    run_finops_simulation()

    if report.overall_status == AuditStatus.FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
