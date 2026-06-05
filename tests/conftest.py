"""pytest 共通フィクスチャ — E2E テスト用サーバー起動/停止"""
from __future__ import annotations

import threading
import time
from http.server import HTTPServer

import pytest


@pytest.fixture(scope="session")
def research_server():
    """RESEARCH APIサーバーをバックグラウンドで起動"""
    from src.research.api import ResearchHandler
    server = HTTPServer(("127.0.0.1", 18080), ResearchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield "http://127.0.0.1:18080"
    server.shutdown()


@pytest.fixture(scope="session")
def marketing_server():
    """MARKETING APIサーバーをバックグラウンドで起動"""
    from src.marketing.api import MarketingHandler
    server = HTTPServer(("127.0.0.1", 18081), MarketingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield "http://127.0.0.1:18081"
    server.shutdown()


@pytest.fixture(scope="session")
def gov_server():
    """GOV APIサーバーをバックグラウンドで起動"""
    from src.gov.api import GovHandler
    server = HTTPServer(("127.0.0.1", 18082), GovHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield "http://127.0.0.1:18082"
    server.shutdown()
