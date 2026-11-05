"""Loopback-only demo API; requires real auth before network deployment."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from tutorAgent import TutorAgent, TutorError

_agent = None
_lock = Lock()


def get_agent():
    global _agent
    with _lock:
        if _agent is None:
            _agent = TutorAgent()
        return _agent


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/tutor/ask":
            return self.send_json(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 8192:
                return self.send_json(413, {"error": "Invalid request size."})
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict):
                return self.send_json(400, {"error": "Expected JSON object."})
            result = get_agent().ask(request.get("question"), request.get("course_id", "CS5342"))
            return self.send_json(200, result)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
            return self.send_json(400, {"error": "Invalid JSON request."})
        except TutorError as exc:
            return self.send_json(422, {"error": str(exc)})
        except Exception:
            self.log_error("Unexpected tutor service error")
            return self.send_json(503, {"error": "Local Tutor service unavailable."})


if __name__ == "__main__":
    print("Tutor API listening on http://127.0.0.1:8000/api/tutor/ask")
    ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
