from __future__ import annotations

import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .database import connect, init_db
from .services import ServiceError
from . import services

ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"
HOST = "127.0.0.1"
PORT = 7070


class TlmHandler(BaseHTTPRequestHandler):
    server_version = "TLM/0.1"

    def do_GET(self) -> None:
        self.route("GET")

    def do_POST(self) -> None:
        self.route("POST")

    def do_PUT(self) -> None:
        self.route("PUT")

    def do_DELETE(self) -> None:
        self.route("DELETE")

    def route(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path.startswith("/api"):
                self.handle_api(method, path)
                return
            self.handle_static(path)
        except ServiceError as exc:
            self.json_response({"error": exc.message}, exc.status)
        except json.JSONDecodeError:
            self.json_response({"error": "请求 JSON 格式不正确"}, 400)
        except Exception as exc:  # pragma: no cover - server safety net
            self.json_response({"error": f"服务异常：{exc}"}, 500)

    def handle_api(self, method: str, path: str) -> None:
        body = self.read_json()
        with connect() as conn:
            if method == "GET" and path == "/api/health":
                self.json_response({"ok": True, "service": "tlm"})
                return
            if method == "GET" and path == "/api/systems":
                self.json_response({"systems": services.systems_payload(conn)})
                return
            if method == "POST" and path == "/api/systems":
                self.json_response({"system": services.create_system(conn, body)}, 201)
                return

            system_match = re.fullmatch(r"/api/systems/([^/]+)", path)
            if system_match:
                system_id = system_match.group(1)
                if method == "PUT":
                    self.json_response({"system": services.update_system(conn, system_id, body)})
                    return
                if method == "DELETE":
                    services.delete_system(conn, system_id)
                    self.json_response({"ok": True})
                    return

            account_list_match = re.fullmatch(r"/api/systems/([^/]+)/accounts", path)
            if account_list_match:
                system_id = account_list_match.group(1)
                if method == "GET":
                    self.json_response({"accounts": services.accounts_payload(conn, system_id)})
                    return
                if method == "POST":
                    self.json_response({"account": services.create_account(conn, system_id, body)}, 201)
                    return

            if method == "POST" and path == "/api/fill":
                self.json_response({"fill": services.fill(conn, body)}, 202)
                return

            status_match = re.fullmatch(r"/api/accounts/([^/]+)/status", path)
            if method == "GET" and status_match:
                self.json_response({"account": services.account_status(conn, status_match.group(1))})
                return

            account_match = re.fullmatch(r"/api/accounts/([^/]+)", path)
            if method == "PUT" and account_match:
                self.json_response({"account": services.update_account(conn, account_match.group(1), body)})
                return
            if method == "DELETE" and account_match:
                services.delete_account(conn, account_match.group(1))
                self.json_response({"ok": True})
                return

            release_match = re.fullmatch(r"/api/accounts/([^/]+)/release", path)
            if method == "POST" and release_match:
                self.json_response({"account": services.release_account(conn, release_match.group(1))})
                return

            lock_match = re.fullmatch(r"/api/accounts/([^/]+)/lock", path)
            if method == "POST" and lock_match:
                locked = bool(body.get("locked", True))
                self.json_response({"account": services.lock_account(conn, lock_match.group(1), locked)})
                return

            if method == "GET" and path == "/api/browser/guest-sessions":
                self.json_response(services.browser_payload(conn))
                return

            if method == "GET" and path == "/api/logs":
                self.json_response({"logs": services.logs_payload(conn)})
                return
            if method == "DELETE" and path == "/api/logs":
                deleted = services.clear_logs(conn)
                self.json_response({"ok": True, "deleted": deleted})
                return

        self.json_response({"error": "接口不存在"}, 404)

    def handle_static(self, path: str) -> None:
        if path == "/":
            file_path = FRONTEND_DIR / "index.html"
        else:
            file_path = (FRONTEND_DIR / path.lstrip("/")).resolve()
            if not str(file_path).startswith(str(FRONTEND_DIR.resolve())):
                self.send_error(HTTPStatus.FORBIDDEN)
                return
        if not file_path.exists() or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        content = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def json_response(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def run() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), TlmHandler)
    print(f"TLM running at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTLM stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
