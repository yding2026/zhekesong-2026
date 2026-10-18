# 本地工作台。只监听本机，页面和接口都不回显密钥。

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.ima_client import credentials_configured
from agent.pipeline import run

STATIC = ROOT / "static"
HOST = "127.0.0.1"
PORT = 8765


def load_dotenv():
    path = ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/status":
            self._send_json({"configured": credentials_configured(), "kb_query": "任德耀新建华为PC知识库"})
            return
        if path == "/":
            path = "/index.html"
        target = (STATIC / path.lstrip("/")).resolve()
        if not str(target).startswith(str(STATIC.resolve())) or not target.is_file():
            self.send_error(404)
            return
        kind = "text/plain; charset=utf-8"
        if target.suffix == ".html":
            kind = "text/html; charset=utf-8"
        elif target.suffix == ".css":
            kind = "text/css; charset=utf-8"
        elif target.suffix == ".js":
            kind = "text/javascript; charset=utf-8"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/api/run":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or "0")
        if length > 100_000:
            self.send_error(413)
            return
        raw = self.rfile.read(length).decode("utf-8")
        try:
            task = json.loads(raw or "{}")
        except json.JSONDecodeError:
            self._send_json({"status": "need_more", "questions": ["请求格式不正确。"]}, status=400)
            return
        self._send_json(run(task))

    def _send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        return


def main():
    load_dotenv()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("工作台已启动：http://%s:%s" % (HOST, PORT))
    server.serve_forever()


if __name__ == "__main__":
    main()
