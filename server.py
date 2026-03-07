#!/usr/bin/env python3
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
DB_PATH = ROOT / "data" / "shoes.db"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env(ROOT / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")
SITE_NAME = os.getenv("SITE_NAME", "Shoes Storage")


def db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = db_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        PRAGMA foreign_keys=ON;

        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone TEXT NOT NULL,
            spot TEXT NOT NULL,
            photo_data TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(zone, spot)
        );

        CREATE TABLE IF NOT EXISTS boxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_data TEXT,
            color TEXT,
            form TEXT,
            special_features TEXT,
            visual_fingerprint TEXT,
            note TEXT,
            location_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(location_id) REFERENCES locations(id)
        );

        CREATE TABLE IF NOT EXISTS shoe_pairs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            photo_data TEXT,
            season TEXT NOT NULL,
            type TEXT NOT NULL,
            color TEXT,
            gender_style TEXT,
            status TEXT NOT NULL,
            box_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(box_id) REFERENCES boxes(id)
        );

        CREATE TABLE IF NOT EXISTS storage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shoe_pair_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(shoe_pair_id) REFERENCES shoe_pairs(id)
        );
        """
    )
    conn.commit()
    conn.close()


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def parse_json_body(handler: SimpleHTTPRequestHandler):
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length else b"{}"
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def write_json(handler: SimpleHTTPRequestHandler, code: int, payload: dict):
    encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    try:
        handler.send_response(code)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(encoded)))
        handler.end_headers()
        handler.wfile.write(encoded)
    except (BrokenPipeError, ConnectionResetError):
        # Browser may cancel in-flight requests (tab close/reload/navigation).
        # Treat it as a disconnected client, not a server failure.
        return


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row) if row else {}


def safe_json_parse(value: str):
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return parsed
    except (TypeError, json.JSONDecodeError):
        pass
    return []


def call_openrouter_vision(image_data_url: str, object_type: str):
    if not OPENROUTER_API_KEY:
        return {
            "ok": False,
            "error": "OPENROUTER_API_KEY не задан. Добавьте ключ в .env"
        }

    schema_hint = {
        "shoe": {
            "name": "",
            "season": "зима|весна|лето|осень",
            "type": "",
            "color": "",
            "gender_style": "",
        },
        "box": {
            "color": "",
            "form": "",
            "special_features": [""],
            "visual_fingerprint": "",
        },
        "location": {
            "zone": "",
            "spot": "",
        },
    }

    prompt = (
        "Ты помощник по учету обуви. Определи характеристики объекта по фото. "
        "Верни строго JSON без markdown. Используй только русский язык. "
        f"Тип объекта: {object_type}. Схема: {json.dumps(schema_hint.get(object_type, {}), ensure_ascii=False)}"
    )

    body = {
        "model": OPENROUTER_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
    }

    req = urllib.request.Request(
        f"{OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": SITE_URL,
            "X-Title": SITE_NAME,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            payload = json.loads(raw)
            text = payload["choices"][0]["message"]["content"]
            parsed = json.loads(text)
            return {"ok": True, "data": parsed}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": f"OpenRouter HTTP {exc.code}: {detail}"}
    except Exception as exc:
        return {"ok": False, "error": f"Ошибка запроса OpenRouter: {exc}"}


class AppHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            # Ignore abrupt client disconnects during static file/API response writes.
            return

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            write_json(self, 200, {"ok": True, "time": now_iso()})
            return

        if path == "/api/config":
            write_json(
                self,
                200,
                {
                    "ok": True,
                    "model": OPENROUTER_MODEL,
                    "openrouter_enabled": bool(OPENROUTER_API_KEY),
                },
            )
            return

        if path == "/api/locations":
            conn = db_conn()
            rows = conn.execute(
                "SELECT id, zone, spot, photo_data, created_at FROM locations ORDER BY zone, spot"
            ).fetchall()
            conn.close()
            write_json(self, 200, {"ok": True, "items": [row_to_dict(r) for r in rows]})
            return

        if path == "/api/shoe-pairs":
            query = parse_qs(parsed.query)
            q = (query.get("query", [""])[0] or "").strip().lower()
            season = (query.get("season", [""])[0] or "").strip().lower()
            status = (query.get("status", [""])[0] or "").strip().lower()

            clauses = []
            params = []

            if season:
                clauses.append("LOWER(sp.season)=?")
                params.append(season)
            if status:
                clauses.append("LOWER(sp.status)=?")
                params.append(status)
            if q:
                like = f"%{q}%"
                clauses.append("(LOWER(sp.name) LIKE ? OR LOWER(sp.type) LIKE ? OR LOWER(sp.color) LIKE ? OR LOWER(sp.season) LIKE ?)")
                params.extend([like, like, like, like])

            where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            sql = f"""
                SELECT sp.id, sp.name, sp.photo_data, sp.season, sp.type, sp.color, sp.gender_style, sp.status,
                       b.id AS box_id, b.photo_data AS box_photo,
                       l.id AS location_id, l.zone, l.spot,
                       sp.updated_at
                FROM shoe_pairs sp
                JOIN boxes b ON sp.box_id = b.id
                JOIN locations l ON b.location_id = l.id
                {where_sql}
                ORDER BY sp.updated_at DESC
            """

            conn = db_conn()
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            write_json(self, 200, {"ok": True, "items": [row_to_dict(r) for r in rows]})
            return

        m = re.match(r"^/api/shoe-pairs/(\d+)$", path)
        if m:
            pair_id = int(m.group(1))
            conn = db_conn()
            pair = conn.execute(
                """
                SELECT sp.*, b.photo_data AS box_photo, b.color AS box_color, b.form AS box_form,
                       b.special_features, b.visual_fingerprint,
                       l.zone, l.spot
                FROM shoe_pairs sp
                JOIN boxes b ON sp.box_id = b.id
                JOIN locations l ON b.location_id = l.id
                WHERE sp.id=?
                """,
                (pair_id,),
            ).fetchone()
            events = conn.execute(
                "SELECT id, event_type, details, created_at FROM storage_events WHERE shoe_pair_id=? ORDER BY id DESC",
                (pair_id,),
            ).fetchall()
            conn.close()
            if not pair:
                write_json(self, 404, {"ok": False, "error": "Пара обуви не найдена"})
                return
            data = row_to_dict(pair)
            data["special_features"] = safe_json_parse(data.get("special_features"))
            data["events"] = [row_to_dict(e) for e in events]
            write_json(self, 200, {"ok": True, "item": data})
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = parse_json_body(self)
        if body is None:
            write_json(self, 400, {"ok": False, "error": "Некорректный JSON"})
            return

        if path == "/api/ai/analyze":
            image = (body.get("image_data") or "").strip()
            object_type = (body.get("object_type") or "shoe").strip()
            if not image:
                write_json(self, 400, {"ok": False, "error": "image_data обязателен"})
                return
            result = call_openrouter_vision(image, object_type)
            code = 200 if result.get("ok") else 502
            write_json(self, code, result)
            return

        if path == "/api/locations":
            zone = (body.get("zone") or "").strip()
            spot = (body.get("spot") or "").strip()
            photo_data = body.get("photo_data")
            if not zone or not spot:
                write_json(self, 400, {"ok": False, "error": "Поля zone и spot обязательны"})
                return
            conn = db_conn()
            existing = conn.execute("SELECT id FROM locations WHERE zone=? AND spot=?", (zone, spot)).fetchone()
            if existing:
                location_id = existing["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO locations(zone, spot, photo_data, created_at) VALUES(?,?,?,?)",
                    (zone, spot, photo_data, now_iso()),
                )
                location_id = cur.lastrowid
                conn.commit()
            conn.close()
            write_json(self, 200, {"ok": True, "id": location_id})
            return

        if path == "/api/boxes":
            photo_data = body.get("photo_data")
            color = body.get("color", "")
            form = body.get("form", "")
            special_features = body.get("special_features", [])
            visual_fingerprint = body.get("visual_fingerprint", "")
            note = body.get("note", "")
            location_id = body.get("location_id")
            if not location_id:
                write_json(self, 400, {"ok": False, "error": "location_id обязателен"})
                return

            conn = db_conn()
            cur = conn.execute(
                """
                INSERT INTO boxes(photo_data, color, form, special_features, visual_fingerprint, note, location_id, created_at)
                VALUES(?,?,?,?,?,?,?,?)
                """,
                (
                    photo_data,
                    color,
                    form,
                    json.dumps(special_features, ensure_ascii=False),
                    visual_fingerprint,
                    note,
                    int(location_id),
                    now_iso(),
                ),
            )
            box_id = cur.lastrowid
            conn.commit()
            conn.close()
            write_json(self, 201, {"ok": True, "id": box_id})
            return

        if path == "/api/shoe-pairs":
            required = ["season", "type", "status", "box_id"]
            missing = [k for k in required if not body.get(k)]
            if missing:
                write_json(self, 400, {"ok": False, "error": f"Отсутствуют поля: {', '.join(missing)}"})
                return

            conn = db_conn()
            cur = conn.execute(
                """
                INSERT INTO shoe_pairs(name, photo_data, season, type, color, gender_style, status, box_id, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    body.get("name", ""),
                    body.get("photo_data"),
                    body.get("season"),
                    body.get("type"),
                    body.get("color", ""),
                    body.get("gender_style", ""),
                    body.get("status"),
                    int(body.get("box_id")),
                    now_iso(),
                    now_iso(),
                ),
            )
            pair_id = cur.lastrowid
            conn.execute(
                "INSERT INTO storage_events(shoe_pair_id, event_type, details, created_at) VALUES(?,?,?,?)",
                (pair_id, "store", json.dumps({"box_id": body.get("box_id")}, ensure_ascii=False), now_iso()),
            )
            conn.commit()
            conn.close()
            write_json(self, 201, {"ok": True, "id": pair_id})
            return

        m = re.match(r"^/api/shoe-pairs/(\d+)/(retrieve|store)$", path)
        if m:
            pair_id = int(m.group(1))
            action = m.group(2)
            new_status = "в использовании" if action == "retrieve" else "хранится"
            conn = db_conn()
            changed = conn.execute(
                "UPDATE shoe_pairs SET status=?, updated_at=? WHERE id=?",
                (new_status, now_iso(), pair_id),
            ).rowcount
            if changed == 0:
                conn.close()
                write_json(self, 404, {"ok": False, "error": "Пара обуви не найдена"})
                return
            conn.execute(
                "INSERT INTO storage_events(shoe_pair_id, event_type, details, created_at) VALUES(?,?,?,?)",
                (pair_id, action, json.dumps(body, ensure_ascii=False), now_iso()),
            )
            conn.commit()
            conn.close()
            write_json(self, 200, {"ok": True})
            return

        write_json(self, 404, {"ok": False, "error": "Маршрут не найден"})


if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), AppHandler)
    print(f"Server started on http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")
