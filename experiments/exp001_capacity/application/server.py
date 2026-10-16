import os
#!/usr/bin/env python3
"""EXP-001: lightweight HTTP workload for capacity experiments."""

import hashlib
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from urllib.parse import parse_qs, urlparse

HOST = os.getenv("HTTP_HOST", "127.0.0.1")
PORT = int(os.getenv("HTTP_PORT", "8080"))
MAX_ITERATIONS = 10000

stats = {
    "requests": 0,
    "errors": 0,
    "total_latency_ms": 0.0,
}
stats_lock = Lock()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        start = time.perf_counter()
        status = 200
        parsed = urlparse(self.path)

        try:
            if parsed.path == "/health":
                response = {"status": "healthy"}

            elif parsed.path == "/work":
                params = parse_qs(parsed.query)
                iterations = int(params.get("iterations", ["1000"])[0])

                if not 1 <= iterations <= MAX_ITERATIONS:
                    raise ValueError("iterations out of allowed range")

                digest = b"exp001"
                for _ in range(iterations):
                    digest = hashlib.sha256(digest).digest()

                response = {
                    "iterations": iterations,
                    "result": digest.hex()[:16],
                }

            elif parsed.path == "/metrics":
                with stats_lock:
                    snapshot = stats.copy()

                response = {
                    **snapshot,
                    "avg_latency_ms": round(
                        snapshot["total_latency_ms"] / snapshot["requests"], 3
                    ) if snapshot["requests"] else 0.0,
                }

            else:
                status = 404
                response = {"error": "endpoint not found"}

        except (ValueError, TypeError):
            status = 400
            response = {"error": "invalid request"}

        elapsed_ms = (time.perf_counter() - start) * 1000

        with stats_lock:
            stats["requests"] += 1
            stats["errors"] += int(status >= 400)
            stats["total_latency_ms"] += elapsed_ms

        payload = json.dumps(response).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"EXP-001 server listening on http://{HOST}:{PORT}", flush=True)
    server.serve_forever()
