#!/usr/bin/env python3
"""Tiny dev server for the CV page.

- GET  /            serve index.html
- POST /save        write posted HTML back to index.html (git diff friendly)
- GET  /export-pdf  render index.html to A4 PDF via headless Chrome and return it

Usage: python3 server.py   ->  http://localhost:8787
"""
import os
import shutil
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = 8787

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    shutil.which("google-chrome"),
    shutil.which("chromium"),
]


def find_chrome():
    for path in CHROME_CANDIDATES:
        if path and os.path.exists(path):
            return path
    return None


def render_pdf():
    """Render index.html to PDF using headless Chrome; return file bytes."""
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError("Chrome/Chromium not found on this machine")
    fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    tmp_profile = tempfile.mkdtemp(prefix="cv_chrome_profile_")
    try:
        url = "file://" + os.path.join(ROOT, "index.html")
        subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                "--virtual-time-budget=2000",
                "--no-first-run",
                "--user-data-dir=" + tmp_profile,
                f"--print-to-pdf={tmp_path}",
                url,
            ],
            check=True,
            timeout=30,
            capture_output=True,
        )
        with open(tmp_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        shutil.rmtree(tmp_profile, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                with open(os.path.join(ROOT, "index.html"), "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except OSError:
                self._send(500, b"cannot read index.html")
        elif self.path == "/export-pdf":
            try:
                pdf = render_pdf()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition",
                                 'attachment; filename="Jason_Chen_Resume.pdf"')
                self.send_header("Content-Length", str(len(pdf)))
                self.end_headers()
                self.wfile.write(pdf)
            except Exception as e:  # noqa: BLE001 - return message to the page
                self._send(500, f"export failed: {e}".encode("utf-8"))
        else:
            self._send(404, b"not found")

    def do_POST(self):
        if self.path != "/save":
            self._send(404, b"not found")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(length)
            with open(os.path.join(ROOT, "index.html"), "wb") as f:
                f.write(data)
            self._send(200, b"saved")
        except (OSError, ValueError) as e:
            self._send(500, f"save failed: {e}".encode("utf-8"))

    def log_message(self, fmt, *args):
        pass  # keep console quiet


if __name__ == "__main__":
    print(f"CV server running at http://localhost:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
