"""
NiceEze デモシナリオAPI
シナリオ: 田中花子が羽田空港でトランク1個を預け、東京都内ホテルで受け取る
stdlib only — port 8087
"""
import json
import time
import hashlib
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Gate D: admin_approval_required は常に True — 変更禁止
# ---------------------------------------------------------------------------
_ADMIN_APPROVAL_REQUIRED = True  # Gate D constraint — do not modify


def _get_admin_approval_required():
    """Gate D: Always returns True. Must not be overridden."""
    return _ADMIN_APPROVAL_REQUIRED


DEMO_TRAVELER = {
    "name": "田中花子",
    "name_en": "Hanako Tanaka",
    "departure_hub": "羽田空港",
    "arrival_hub": "新宿ヒルトンホテル",
    "baggage_count": 1,
    "baggage_size": "large",
}

SCENARIO_STEPS = [
    "step1_checkin",       # チェックイン・QR発行
    "step2_hub_dispatch",  # HUB発送
    "step3_in_transit",    # 配送中
    "step4_arrived",       # ホテル到着
    "step5_unlocked",      # ラック解錠（管理者承認後）
]

_STEP_LABELS = [
    {"step": "step1_checkin",      "label": "羽田空港 受付完了",   "label_en": "Check-in Complete",        "time": "10:30"},
    {"step": "step2_hub_dispatch", "label": "羽田HUB 発送",        "label_en": "Haneda HUB Dispatched",    "time": "12:00"},
    {"step": "step3_in_transit",   "label": "東京都内 配送中",     "label_en": "In Transit (Tokyo area)",  "time": "13:00"},
    {"step": "step4_arrived",      "label": "ホテル到着",          "label_en": "Hotel Arrived",            "time": "14:30"},
    {"step": "step5_unlocked",     "label": "ラック解錠済み",      "label_en": "Rack Unlocked",            "time": "14:45"},
]

# In-memory store: scenario_id -> {current_step_index, qr_id, ...}
_scenarios = {}
_lock = threading.Lock()


def _make_scenario_id():
    raw = str(time.time()).encode()
    return "DEMO-" + hashlib.sha256(raw).hexdigest()[:8].upper()


def _make_qr_id():
    raw = str(time.time() + 1).encode()
    return "DEMO-QR-" + hashlib.sha256(raw).hexdigest()[:6].upper()


def _build_timeline(current_step_index):
    timeline = []
    for i, meta in enumerate(_STEP_LABELS):
        timeline.append({
            "step": meta["step"],
            "label": meta["label"],
            "label_en": meta["label_en"],
            "done": i <= current_step_index,
            "time": meta["time"],
        })
    return timeline


def _build_response(scenario):
    step_index = scenario["step_index"]
    return {
        "scenario_id": scenario["scenario_id"],
        "current_step": SCENARIO_STEPS[step_index],
        "traveler": dict(DEMO_TRAVELER),
        "qr_id": scenario["qr_id"],
        "status_timeline": _build_timeline(step_index),
        "admin_approval_required": _get_admin_approval_required(),
    }


def _start_scenario(body_bytes):
    scenario_id = _make_scenario_id()
    qr_id = _make_qr_id()
    scenario = {
        "scenario_id": scenario_id,
        "qr_id": qr_id,
        "step_index": 0,
    }
    with _lock:
        _scenarios[scenario_id] = scenario
        _scenarios[qr_id] = scenario  # Also accessible by QR ID
    return _build_response(scenario)


def _get_scenario(scenario_id):
    with _lock:
        scenario = _scenarios.get(scenario_id)
    if scenario is None:
        return None
    return _build_response(scenario)


def _next_step(scenario_id):
    with _lock:
        scenario = _scenarios.get(scenario_id)
        if scenario is None:
            return None
        max_index = len(SCENARIO_STEPS) - 1
        if scenario["step_index"] < max_index:
            scenario["step_index"] += 1
    return _build_response(scenario)


def _reset_all():
    with _lock:
        _scenarios.clear()
    return {"status": "reset", "admin_approval_required": _get_admin_approval_required()}


class _DemoHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # noqa: D401
        pass  # Suppress default access log

    def _send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return self.rfile.read(length)
        return b""

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/health":
            self._send_json(200, {"status": "ok", "admin_approval_required": _get_admin_approval_required()})
            return

        # GET /api/v1/demo/scenario/{id}
        prefix = "/api/v1/demo/scenario/"
        if path.startswith(prefix):
            sid = path[len(prefix):]
            if sid and "/" not in sid:
                result = _get_scenario(sid)
                if result is None:
                    self._send_json(404, {"error": "scenario not found"})
                else:
                    self._send_json(200, result)
                return

        self._send_json(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/v1/demo/scenario/start":
            body = self._read_body()
            result = _start_scenario(body)
            self._send_json(200, result)
            return

        if path == "/api/v1/demo/scenario/reset":
            result = _reset_all()
            self._send_json(200, result)
            return

        # POST /api/v1/demo/scenario/{id}/next
        if "/next" in path:
            parts = path.split("/")
            if len(parts) >= 6 and parts[-1] == "next":
                sid = parts[-2]
                result = _next_step(sid)
                if result is None:
                    self._send_json(404, {"error": "scenario not found"})
                else:
                    self._send_json(200, result)
                return

        self._send_json(404, {"error": "not found"})


def run_server(host="127.0.0.1", port=8087):  # nosec B104 — override with env/args for production
    """Start the demo scenario HTTP server."""
    server = HTTPServer((host, port), _DemoHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
