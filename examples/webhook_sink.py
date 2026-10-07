#!/usr/bin/env python3
"""Print approval pings. Point the worker at this process:

    python examples/webhook_sink.py
    APPROVAL_WEBHOOK_URL=http://host.docker.internal:8091 docker compose up -d worker
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Sink(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length)
        print(body.decode("utf-8") or "{}")
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8091), Sink)
    print("listening on http://0.0.0.0:8091")
    server.serve_forever()


if __name__ == "__main__":
    main()
