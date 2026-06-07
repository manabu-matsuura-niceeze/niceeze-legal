#!/usr/bin/env python3
"""NiceEze マーケティング KPI 自動収集 Phase 1
X API + Google Drive保存 + Slack通知

Usage:
  python src/main.py             # 本番実行（前日のKPIを取得）
  python src/main.py --dry-run   # ドライラン（APIコールなし・モックデータ）
"""
import argparse
import logging
import sys
from datetime import datetime

from src.config import get_jst_yesterday, JST
from src.collectors.twitter import TwitterCollector
from src.alerting.threshold import check_thresholds
from src.reporter.markdown import generate_report
from src.reporter.drive import DriveReporter
from src.reporter.notifier import SlackNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main(dry_run: bool = False) -> int:
    logger.info(f"marketing-analytics Phase 1 起動 (dry_run={dry_run})")
    date = get_jst_yesterday()
    logger.info(f"対象日: {date.strftime('%Y-%m-%d')} JST")

    # 1. X API KPI取得
    tw_collector = TwitterCollector(dry_run=dry_run)
    tw_kpi = tw_collector.collect(date)
    logger.info(f"Twitter収集完了: followers={tw_kpi.followers}, eng={tw_kpi.engagement_rate}%")

    kpi_data = {
        "twitter": {
            "followers": tw_kpi.followers,
            "impressions": tw_kpi.impressions,
            "likes": tw_kpi.likes,
            "retweets": tw_kpi.retweets,
            "replies": tw_kpi.replies,
            "tweet_count": tw_kpi.tweet_count,
            "engagement_rate": tw_kpi.engagement_rate,
            "error": tw_kpi.error,
        }
    }

    # 2. アラート判定
    alerts = check_thresholds(kpi_data)
    logger.info(f"アラート判定完了: {len(alerts)}件")

    # 3. Markdownレポート生成
    report_md = generate_report(date, kpi_data, alerts)
    logger.info("レポート生成完了")

    # 4. Drive保存
    filename = f"MKT_KPI_{date.strftime('%Y%m%d')}.md"
    subfolder = f"Marketing_KPI/{date.strftime('%Y-%m')}"
    drive = DriveReporter(dry_run=dry_run)
    drive_url = drive.upload(filename, report_md, subfolder)
    logger.info(f"Drive保存完了: {drive_url}")

    # 5. Slackアラート通知
    notifier = SlackNotifier(dry_run=dry_run)
    if alerts:
        notifier.send_alert(alerts, date, drive_url)
        logger.info("Slackアラート送信完了")
    else:
        logger.info("アラートなし → Slack通知スキップ")

    # 6. 全件失敗チェック
    if tw_kpi.error and not dry_run:
        notifier.send_failure_alert(f"Twitter: {tw_kpi.error}")

    logger.info("processing complete")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NiceEze Marketing KPI Collector")
    parser.add_argument("--dry-run", action="store_true", help="モックデータで実行（API不使用）")
    args = parser.parse_args()
    sys.exit(main(dry_run=args.dry_run))
