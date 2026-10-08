#!/usr/bin/env python3
"""Real send_email executor. The worker calls this only after Approve.

    python examples/mailer_sink.py
    TOOL_EXECUTOR_URL=http://host.docker.internal:8092 docker compose up -d worker

Reject and approval timeout never reach this process. Replace the print
with your SMTP or Gmail call; a non-2xx response fails the run.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Mailer(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        params = body.get("params") or {}
        print(
            json.dumps(
                {
                    "to": params.get("to"),
                    "subject": params.get("subject"),
                    "body": params.get("body"),
                }
            ),
            flush=True,
        )
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8092), Mailer)
    print("mailer listening on http://0.0.0.0:8092", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
