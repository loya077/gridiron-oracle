"""Tiny local server: serves web/ and data/, and saves slider settings."""
import argparse
import json
import os
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .teams import ROOT
from .refresh import save_settings, load_settings

WEB = os.path.join(ROOT, "web")
DATA = os.path.join(ROOT, "data")


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        p = path.split("?", 1)[0].split("#", 1)[0]
        if p.startswith("/data/"):
            name = os.path.basename(p)
            if name in ("app.json", "ledger.json"):
                return os.path.join(DATA, name)
            return os.path.join(DATA, "__nope__")
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.startswith("/api/settings"):
            return self._json(load_settings())
        return super().do_GET()

    def do_POST(self):
        if not self.path.startswith("/api/settings"):
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
            self._json(save_settings(body))
        except Exception as e:
            self.send_error(400, str(e))

    def _json(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, fmt, *args):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8642)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)
    if not os.path.exists(os.path.join(DATA, "app.json")):
        print("No data yet — run `make refresh` (or `python3 -m oracle refresh`) first.")
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), partial(Handler, directory=WEB))
    url = "http://127.0.0.1:%d/" % args.port
    print("Gridiron Oracle running at %s  (Ctrl+C to stop)" % url)
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
