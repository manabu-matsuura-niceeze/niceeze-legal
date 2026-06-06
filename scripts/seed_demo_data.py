"""
NiceEze UAT デモデータ投入スクリプト (Ver 1.0)
使用方法: python scripts/seed_demo_data.py
実行後: 各システムのデータ状態をコンソールに表示
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def seed_research():
    from src.research.res_a01 import PriceFetcher, PriceMatrix, PriceRecord
    from src.research.res_a02 import TrendFetcher

    # 価格データ30件（6キーワード × 5カテゴリ）
    keywords = ['トイレットペーパー', '洗剤', 'マスク', 'コーヒー', '電池', '歯ブラシ']
    categories = ['日用品・消耗品', '食品・飲料', '美容・健康', '家電・ガジェット', 'ホーム・インテリア']
    fetcher = PriceFetcher()
    for kw in keywords:
        matrix = fetcher.build_matrix(kw, '日用品・消耗品')
        print(f"  [RESEARCH] {kw}: {len(matrix.records)}件, 最安値={matrix.cheapest().supplier if matrix.cheapest() else 'N/A'}")

    # トレンドデータ
    trend_fetcher = TrendFetcher()
    for kw in keywords[:3]:
        trend = trend_fetcher.fetch(kw, '日用品・消耗品')
        print(f"  [TREND] {kw}: growth={trend.growth_score():.2f}, retention={trend.retention_score():.2f}")


def seed_surplus():
    from src.surplus_shift.gate_a import KeepaClient
    from src.surplus_shift.gate_b import GrossMarginCalc
    from src.surplus_shift.gate_c import InventoryScorer
    from src.surplus_shift.gate_d import CashFlowJudge, MonthlyCFInput
    from src.surplus_shift.negotiation_log import NegotiationLog

    # 商品5件（Gate A: 価格確認）
    client = KeepaClient()
    asins = ['B001234567', 'B002345678', 'B003456789', 'B004567890', 'B005678901']
    for asin in asins:
        snap = client.fetch(asin)
        print(f"  [GATE-A] {asin}: ¥{snap.amazon_price_jpy:,} rank={snap.sales_rank}")

    # 商談3件（draft/human_approved/sent）
    log = NegotiationLog()
    r1 = log.add_draft('2026-06', '【テスト交渉案1】余剰在庫転換提案ドラフト')
    r2 = log.add_draft('2026-06', '【テスト交渉案2】CF不足補填提案ドラフト')
    r3 = log.add_draft('2026-05', '【テスト交渉案3】先月分承認済み提案')
    log.human_approve(r2.record_id, '松浦CEO', notes='UAT確認用')
    log.human_approve(r3.record_id, '松浦CEO', notes='UAT確認用')
    log.mark_sent(r3.record_id)
    print(f"  [SURPLUS] 商談ログ: draft={len(log.get_by_status('draft'))}, approved={len(log.get_by_status('human_approved'))}, sent={len(log.get_by_status('sent'))}")


def seed_marketing():
    from src.marketing.content_generator import ContentGenerator, ContentInput
    from src.marketing.delivery_log import DeliveryLog

    gen = ContentGenerator()
    log = DeliveryLog()
    topics = [
        ('夏の洗剤トレンド', '日用品・消耗品', 0.8),
        ('コーヒー豆急成長', '食品・飲料', 0.9),
        ('マスク需要回復', '美容・健康', 0.6),
        ('電池・充電器特集', '家電・ガジェット', 0.7),
        ('歯ブラシEC市場', '美容・健康', 0.5),
    ]
    for topic, category, score in topics:
        inp = ContentInput(topic=topic, category=category, trend_score=score)
        content = gen.generate_all(inp)
        log.add('x_post', topic, category, len(content.x_full_text), status='draft')
        print(f"  [MARKETING] {topic}: X={len(content.x_full_text)}文字, YT台本={content.youtube_script[:20]}...")


def seed_gov():
    from src.gov.s10_coo_report import COOReportEngine
    from src.gov.finops_monitor import FinOpsMonitor
    from src.gov.ops_log_collector import OpsLogCollector

    engine = COOReportEngine()
    # KPI 3件
    engine.add_kpi('月次売上', 5_000_000, 4_200_000, '円', '2026-06')
    engine.add_kpi('配送完了率', 98.0, 96.5, '%', '2026-06')
    engine.add_kpi('顧客満足度', 4.5, 4.3, 'ポイント', '2026-06')
    # 予実 3件
    engine.add_budget('GCPコスト', 5000, 3200, '2026-06')
    engine.add_budget('人件費', 2_000_000, 1_980_000, '2026-06')
    engine.add_budget('広告費', 300_000, 285_000, '2026-06')
    # PMOタスク 3件
    engine.add_pmo_task('SBDS実装完了', 'G1', 'done', 'SBDS部', '2026-09-30')
    engine.add_pmo_task('SURPLUS SHIFT v14.2', 'G2', 'in_progress', 'SURPLUS部', '2026-11-30')
    engine.add_pmo_task('GOV S10完成', 'G3', 'todo', 'GOV部', '2027-01-31')
    report = engine.generate_report('2026-06')
    print(f"  [GOV] KPI達成: {report.kpi_summary()['achieved_count']}/3, 予算執行: {report.budget_summary()['total_actual_jpy']:,}円")

    # FinOps 3件
    monitor = FinOpsMonitor()
    monitor.record_cost('research', 800.0, 5000, '2026-06')
    monitor.record_cost('marketing', 600.0, 3000, '2026-06')
    monitor.record_cost('gov', 200.0, 1000, '2026-06')
    summary = monitor.monthly_summary('2026-06')
    print(f"  [FINOPS] 月次コスト: ¥{summary['total_cost_jpy']:,.0f}, 残予算: ¥{summary['budget_remaining_jpy']:,.0f}")


def seed_travel():
    from src.sbds.travel_qr import TravelQRManager
    from src.sbds.ai_support import AISupportCenter, SupportRequest

    mgr = TravelQRManager()
    # QR 10件
    hubs = [('TYO', 'OSA'), ('OSA', 'FUK'), ('FUK', 'TYO'), ('TYO', 'SAP'), ('NGO', 'TYO')]
    for i, (dep, arr) in enumerate(hubs * 2):
        qr = mgr.issue(f'BOOKING_{i+1:03d}_HASH', dep, arr, baggage_count=(i % 3) + 1)
        print(f"  [TRAVEL] QR発行: {qr.qr_id} {dep}→{arr} 荷物{qr.baggage_count}個 valid={qr.is_valid}")

    # AIサポート動作確認
    center = AISupportCenter()
    req = center.create_request('ja', 'baggage_tracking', '荷物の状態を確認したい', qr_id='demo_001')
    resp = center.respond(req)
    print(f"  [SUPPORT] 応答: {resp.response_text[:40]}...")


if __name__ == '__main__':
    print("=" * 60)
    print("NiceEze UAT デモデータ投入")
    print("=" * 60)
    sections = [
        ("RESEARCH（市場調査）", seed_research),
        ("SURPLUS SHIFT（余剰在庫）", seed_surplus),
        ("MARKETING（マーケティング）", seed_marketing),
        ("GOV（経営管理）", seed_gov),
        ("TRAVEL（手ぶら旅行）", seed_travel),
    ]
    for name, fn in sections:
        print(f"\n[{name}]")
        try:
            fn()
            print(f"  ✅ {name} 完了")
        except Exception as e:
            print(f"  ❌ {name} エラー: {e}")

    print("\n" + "=" * 60)
    print("デモデータ投入完了")
    print("次のステップ: bash scripts/start_all_staging.sh")
    print("=" * 60)
