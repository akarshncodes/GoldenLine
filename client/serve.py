#!/usr/bin/env python3
"""Tiny static file server for the GoldenLine client — like `python3 -m http.server`
but sends `Cache-Control: no-store` on every response.

The plain http.server lets the browser aggressively cache `<script src>` / CSS,
which repeatedly served stale copies of edited files during development (see the
project's "tooling gotchas"). This makes every reload fetch fresh.

Usage:  python3 serve.py [port]     (default 5180)
"""
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):  # quieter logs
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5180
    print(f"GoldenLine client on http://localhost:{port}  (no-store)")
    ThreadingHTTPServer(("127.0.0.1", port), NoCacheHandler).serve_forever()
