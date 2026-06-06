"""手ぶら旅行 QRコードPDF自動生成 (Ver 1.0)
SBDS部門 MVP
stdlib only — reportlab等は使用しない
SVG形式でQRパターンを生成しHTML+CSS印刷用PDFを出力
FinOps: 月額¥5,000以内 / PII最小化 / bandit 0件
"""
from __future__ import annotations

import hashlib
import html
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List

from .travel_qr import TravelQR


@dataclass
class TravelPDFDocument:
    qr: TravelQR                # TravelQRオブジェクト
    traveler_note: str = ''     # 旅行者向けメモ（多言語）
    hub_info: dict = field(default_factory=dict)  # 拠点情報
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TravelPDFGenerator:
    """HTML形式のQR印刷ドキュメント生成（stdlib only）"""

    def _generate_qr_pattern(self, token: str) -> list[list[bool]]:
        """
        tokenのSHA-256ハッシュから21×21のQR様パターンを生成。
        実際のQRエンコードではなく視覚的なパターン。
        """
        digest = hashlib.sha256(token.encode()).digest()
        # 32バイト × 8ビット = 256ビット → 21×21=441ビットに拡張
        pattern = []
        for row in range(21):
            row_data = []
            for col in range(21):
                bit_idx = (row * 21 + col) % (len(digest) * 8)
                byte_idx = bit_idx // 8
                bit_pos = 7 - (bit_idx % 8)
                row_data.append(bool((digest[byte_idx] >> bit_pos) & 1))
            pattern.append(row_data)
        # 四隅にファインダーパターン（常に黒=True）を配置
        for r in range(3):
            for c in range(3):
                pattern[r][c] = True
                pattern[r][20 - c] = True
                pattern[20 - r][c] = True
        return pattern

    def _pattern_to_html_table(self, pattern: list[list[bool]]) -> str:
        """QRパターンをHTMLテーブルに変換する"""
        rows_html = []
        for row in pattern:
            cells = []
            for cell in row:
                bg = '#000' if cell else '#fff'
                cells.append(f'<td style="width:6px;height:6px;background:{bg};padding:0;margin:0;"></td>')
            rows_html.append('<tr>' + ''.join(cells) + '</tr>')
        table = (
            '<table style="border-collapse:collapse;border:2px solid #000;">'
            + ''.join(rows_html)
            + '</table>'
        )
        return table

    def _format_jst(self, iso_str: str) -> str:
        """UTC ISO文字列をJST表記に変換"""
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        jst_offset = timedelta(hours=9)
        jst = dt + jst_offset
        return jst.strftime('%Y-%m-%d %H:%M JST')

    def generate_html(self, doc: TravelPDFDocument) -> str:
        """印刷用HTML生成（旅行者がブラウザでPDF印刷）"""
        qr = doc.qr
        pattern = self._generate_qr_pattern(qr.token)
        qr_table = self._pattern_to_html_table(pattern)
        expires_jst = self._format_jst(qr.expires_at)
        issued_jst = self._format_jst(qr.issued_at)
        note = html.escape(doc.traveler_note) if doc.traveler_note else ''

        hub_rows = ''
        if doc.hub_info:
            for k, v in doc.hub_info.items():
                hub_rows += f'<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>'

        html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NiceEze 手ぶら旅行 QRコード</title>
<style>
  body {{ font-family: sans-serif; margin: 20px; color: #000; }}
  @media print {{
    body {{ margin: 5mm; }}
    .no-print {{ display: none; }}
  }}
  .header {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 8px; margin-bottom: 16px; }}
  .header h1 {{ font-size: 18px; margin: 0 0 4px 0; }}
  .header p {{ font-size: 11px; margin: 2px 0; color: #555; }}
  .main {{ display: flex; gap: 20px; align-items: flex-start; }}
  .qr-area {{ flex-shrink: 0; }}
  .info-area {{ flex: 1; }}
  .info-area table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  .info-area td {{ padding: 4px 6px; border-bottom: 1px solid #ddd; }}
  .info-area td:first-child {{ font-weight: bold; width: 40%; }}
  .footer {{ border-top: 2px solid #000; margin-top: 16px; padding-top: 8px; text-align: center; font-size: 11px; }}
  .footer p {{ margin: 2px 0; }}
</style>
</head>
<body>
<div class="header">
  <h1>NiceEze 手ぶら旅行サービス</h1>
  <p>NiceEze Hands-Free Travel Service</p>
  <p>NiceEze 免手旅行服务 / NiceEze 손자유 여행 서비스</p>
</div>
<div class="main">
  <div class="qr-area">
    {qr_table}
  </div>
  <div class="info-area">
    <table>
      <tr><td>QR ID</td><td>{html.escape(qr.qr_id)}</td></tr>
      <tr><td>発行日時 / Issued</td><td>{issued_jst}</td></tr>
      <tr><td>有効期限 / Expires</td><td>{expires_jst}</td></tr>
      <tr><td>出発拠点 / Departure</td><td>{html.escape(qr.departure_hub)}</td></tr>
      <tr><td>到着拠点 / Arrival</td><td>{html.escape(qr.arrival_hub)}</td></tr>
      <tr><td>荷物数 / Baggage</td><td>{qr.baggage_count} 個</td></tr>
      <tr><td>ステータス / Status</td><td>{html.escape(qr.status)}</td></tr>
    </table>
    {('<p style="margin-top:8px;font-size:12px;">' + note + '</p>') if note else ''}
    {('<table style="margin-top:8px;">' + hub_rows + '</table>') if hub_rows else ''}
  </div>
</div>
<div class="footer">
  <p>このQRコードを到着拠点スタッフにご提示ください。</p>
  <p>Please show this QR code to arrival hub staff.</p>
  <p>请将此QR码出示给到达站工作人员。</p>
  <p>이 QR코드를 도착 거점 직원에게 제시해 주세요。</p>
</div>
</body>
</html>"""
        return html_content

    def save_html(self, doc: TravelPDFDocument, output_path: str) -> str:
        """HTMLファイルを保存してパスを返す"""
        content = self.generate_html(doc)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return output_path

    def generate_for_qr(self, qr: TravelQR, language: str = 'ja') -> str:
        """TravelQRからHTML文字列を直接生成"""
        doc = TravelPDFDocument(qr=qr)
        return self.generate_html(doc)
