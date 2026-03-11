import cgi
import html
import json
import os
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from copilot_core import HaloClient, HaloConfig, KBSuggester

APP_ROOT = Path(__file__).parent
UPLOAD_DIR = APP_ROOT / "uploads"
KB_PATH = APP_ROOT / "kb_articles.json"
UPLOAD_DIR.mkdir(exist_ok=True)

kb = KBSuggester(KB_PATH)


def render_index() -> bytes:
    return b"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><title>Service Desk Copilot</title>
<style>body{font-family:Arial,sans-serif;max-width:840px;margin:40px auto;}textarea{width:100%;min-height:120px;}button{padding:8px 12px;border-radius:6px;cursor:pointer;}</style>
</head><body>
<h1>Service Desk Co-Pilot Agent</h1>
<p>Describe your issue and optionally attach a screenshot. We'll suggest HALO KB fixes first.</p>
<form action='/suggest' method='post' enctype='multipart/form-data'>
<label for='issue'>Issue description</label><br/><textarea id='issue' name='issue' required></textarea><br/><br/>
<label for='screenshot'>Attach screenshot (optional)</label><br/><input id='screenshot' name='screenshot' type='file' accept='image/*'/><br/><br/>
<button type='submit'>Get suggested fixes</button>
</form></body></html>"""


def render_results(issue: str, suggestions: list[dict], screenshot_path: str | None) -> bytes:
    if suggestions:
        cards = "".join(
            f"<div style='border:1px solid #ddd;border-radius:10px;padding:12px;margin:12px 0'>"
            f"<h3>{html.escape(item['title'])}</h3>"
            f"<p>{html.escape(item['summary'])}</p>"
            f"<p><strong>Try this:</strong> {html.escape(item['fix_steps'])}</p>"
            f"<p><strong>KB URL:</strong> <a href='{html.escape(item['url'])}' target='_blank'>{html.escape(item['url'])}</a></p>"
            "</div>"
            for item in suggestions
        )
    else:
        cards = "<p>No close KB matches were found. You can create a ticket directly.</p>"

    screenshot_value = html.escape(screenshot_path or "")
    issue_value = html.escape(issue)
    page = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Suggested Fixes</title>
<style>body{{font-family:Arial,sans-serif;max-width:840px;margin:40px auto;}}button{{padding:8px 12px;border-radius:6px;cursor:pointer;}}</style>
</head><body>
<h2>Try these HALO KB suggestions</h2>
{cards}
<hr/>
<h3>Still not fixed?</h3>
<p>Click the button below to create a HALO ticket automatically.</p>
<form action='/create-ticket' method='post'>
<input type='hidden' name='issue' value='{issue_value}'/>
<input type='hidden' name='screenshot_path' value='{screenshot_value}'/>
<button type='submit'>Create HALO ticket</button>
</form></body></html>"""
    return page.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def _send_html(self, body: bytes, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            self._send_html(render_index())
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self):
        if self.path == "/suggest":
            form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST"})
            issue = (form.getfirst("issue") or "").strip()
            screenshot_path = None

            screenshot = form["screenshot"] if "screenshot" in form else None
            if screenshot is not None and getattr(screenshot, "filename", None):
                filename = f"{uuid.uuid4()}_{Path(screenshot.filename).name}"
                out = UPLOAD_DIR / filename
                with out.open("wb") as f:
                    f.write(screenshot.file.read())
                screenshot_path = str(out)

            suggestions = kb.suggest(issue) if issue else []
            self._send_html(render_results(issue, suggestions, screenshot_path))
            return

        if self.path == "/create-ticket":
            length = int(self.headers.get("Content-Length", "0"))
            data = self.rfile.read(length).decode("utf-8")
            fields = parse_qs(data)
            issue = (fields.get("issue", [""])[0]).strip()
            screenshot_path = fields.get("screenshot_path", [""])[0] or None

            config = HaloConfig.from_env()
            if not config:
                self._send_json(
                    {
                        "status": "dry-run",
                        "message": "HALO credentials are missing; set env vars to enable live ticket creation.",
                        "ticket_preview": {
                            "summary": issue[:120],
                            "details": issue,
                            "screenshot": screenshot_path,
                        },
                    }
                )
                return

            client = HaloClient(config)
            created = client.create_ticket(summary=issue[:120], details=issue, screenshot_path=screenshot_path)
            self._send_json({"status": "created", "ticket": created}, code=201)
            return

        self.send_error(HTTPStatus.NOT_FOUND)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Service Desk Copilot running on http://0.0.0.0:{port}")
    server.serve_forever()
