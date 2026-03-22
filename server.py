import os
import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

PORT = int(os.environ.get('PORT', 8080))
DB   = os.path.join(os.path.dirname(__file__), 'emotions.db')

# ── database setup ──────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS entries (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                ts       TEXT    NOT NULL UNIQUE,
                date     TEXT    NOT NULL,
                time     TEXT    NOT NULL,
                score    INTEGER NOT NULL,
                emotions TEXT    NOT NULL
            )
        ''')
        conn.commit()

# ── request handler ─────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silent logs

    def send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type',  'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, mime):
        with open(path, 'rb') as f:
            body = f.read()
        self.send_response(200)
        self.send_header('Content-Type',  mime)
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin',  '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path   = parsed.path

        # serve frontend
        if path in ('/', '/index.html'):
            html = os.path.join(os.path.dirname(__file__), 'index.html')
            if os.path.exists(html):
                self.send_file(html, 'text/html; charset=utf-8')
            else:
                self.send_json(404, {'error': 'index.html not found'})
            return

        # GET /entries?days=30
        if path == '/entries':
            qs   = parse_qs(parsed.query)
            days = int(qs.get('days', ['365'])[0])
            with get_db() as conn:
                rows = conn.execute(
                    "SELECT * FROM entries WHERE date >= date('now', ? || ' days') ORDER BY ts DESC",
                    (f'-{days}',)
                ).fetchall()
            result = [
                {
                    'ts':       r['ts'],
                    'date':     r['date'],
                    'time':     r['time'],
                    'score':    r['score'],
                    'emotions': json.loads(r['emotions'])
                }
                for r in rows
            ]
            self.send_json(200, result)
            return

        self.send_json(404, {'error': 'not found'})

    def do_POST(self):
        if self.path != '/entries':
            self.send_json(404, {'error': 'not found'})
            return
        length = int(self.headers.get('Content-Length', 0))
        body   = json.loads(self.rfile.read(length).decode('utf-8'))
        ts       = body['ts']
        date     = body['date']
        time     = body['time']
        score    = body['score']
        emotions = json.dumps(body['emotions'], ensure_ascii=False)
        try:
            with get_db() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO entries (ts,date,time,score,emotions) VALUES (?,?,?,?,?)",
                    (ts, date, time, score, emotions)
                )
                conn.commit()
            self.send_json(200, {'ok': True})
        except Exception as e:
            self.send_json(500, {'error': str(e)})

    def do_DELETE(self):
        # DELETE /entries?ts=2026-03-22T08:30
        parsed = urlparse(self.path)
        if parsed.path != '/entries':
            self.send_json(404, {'error': 'not found'})
            return
        qs = parse_qs(parsed.query)
        ts = qs.get('ts', [None])[0]
        if not ts:
            self.send_json(400, {'error': 'missing ts'})
            return
        with get_db() as conn:
            conn.execute("DELETE FROM entries WHERE ts = ?", (ts,))
            conn.commit()
        self.send_json(200, {'ok': True})


if __name__ == '__main__':
    init_db()
    print(f'Сървърът работи на порт {PORT}')
    HTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
