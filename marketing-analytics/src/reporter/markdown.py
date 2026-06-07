"""Markdownレポート生成モジュール"""
from datetime import datetime
from src.config import JST, APP_VERSION

WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]

def generate_report(date: datetime, kpi_data: dict, alerts: list) -> str:
    """日次KPIレポートをMarkdown文字列で生成する"""
    weekday = WEEKDAY_JA[date.weekday()]
    date_str = date.strftime(f"%Y年%m月%d日（{weekday}）")
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S JST")
    
    tw = kpi_data.get("twitter", {})
    
    lines = [
        "# NiceEze マーケティング KPI 日次報告",
        "",
        f"**報告日**: {date_str}  ",
        f"**生成日時**: {now_jst}  ",
        f"**生成者**: marketing-analytics v{APP_VERSION}（自動）  ",
        "",
        "---",
        "",
        "## X（旧Twitter）",
        "",
    ]
    
    if tw.get("error"):
        lines.append(f"> ⚠️ 取得失敗: {tw['error']}")
    else:
        prev_followers = tw.get("prev_followers", tw.get("followers", 0))
        follower_diff = tw.get("followers", 0) - prev_followers
        diff_str = f"+{follower_diff}" if follower_diff >= 0 else str(follower_diff)
        lines += [
            "| 指標 | 当日 | 前日比 | 備考 |",
            "|------|------|--------|------|",
            f"| インプレッション | {tw.get('impressions', 'N/A'):,} | - | - |",
            f"| フォロワー | {tw.get('followers', 'N/A'):,} | {diff_str} | - |",
            f"| エンゲージメント率 | {tw.get('engagement_rate', 'N/A')}% | - | - |",
            f"| 投稿数 | {tw.get('tweet_count', 'N/A')}件 | - | - |",
        ]
    
    # Meta / YouTube / Note (Phase 2〜4)
    for section, label in [("meta", "Instagram / Facebook"), ("youtube", "YouTube"), ("note", "Note")]:
        lines += ["", f"## {label}", "", "> 📋 Phase 2〜4 で実装予定", ""]
    
    # PR TIMES
    lines += ["## メディア掲載（PR TIMES）", "", "> N/A（手動入力）", ""]
    
    # アラート
    lines += ["---", "", "## KPIアラート", ""]
    if alerts:
        for alert in alerts:
            lines.append(f"⚠️ **{alert.message}**  ")
        lines.append("")
        lines.append("→ コンテンツ見直し推奨。翌日の施策を確認してください。")
    else:
        lines.append("✅ 全KPI目標値クリア")
    
    # 翌日アクション
    lines += [
        "",
        "---",
        "",
        "## 翌日のアクション（手動記入）",
        "",
        "- [ ] ",
    ]
    
    return "\n".join(lines)
