#!/usr/bin/env python3
"""Local web console for Sherlock (email / name / Canadian phone / username).

Runs a small HTTP server on 127.0.0.1 and serves sherlock_web.html. Probes are
made server-side by the stock Sherlock engine, which is why this cannot be a
static GitHub Pages site or a sandboxed artifact (browsers block cross-site
probing via CORS).

    python sherlock_web.py            # opens http://127.0.0.1:8000
    python sherlock_web.py --port 9000 --no-browser
"""
import argparse
import json
import os
import re
import threading
import time
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import sherlock_console as sc
from sherlock_project.notify import QueryNotify
from sherlock_project.result import QueryStatus

HERE = os.path.dirname(os.path.abspath(__file__))
KINDS = ("username", "email", "name", "phone")

ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}   # extended by --allow-host
JOBS = {}
JOBS_LOCK = threading.Lock()
_SITE_CACHE = {}


class Job:
    def __init__(self, kind, value, settings):
        self.id = uuid.uuid4().hex[:10]
        self.kind, self.value, self.settings = kind, value, settings
        self.status = "running"          # running | done | cancelled | error
        self.error = None
        self.candidates = []             # [{candidate, confidence, hits, checked}]
        self.extras = {}
        self.rows = []                   # every site check
        self.done = 0
        self.total = 0
        self.sites = 0
        self.started = time.time()
        self.finished = None
        self.cancel = threading.Event()
        self.saved_to = None

    def public(self, full=True):
        hits = sum(1 for r in self.rows if r["status"] == "Claimed")
        d = {"id": self.id, "kind": self.kind, "value": self.value, "status": self.status,
             "error": self.error, "done": self.done, "total": self.total, "sites": self.sites,
             "hits": hits, "started": self.started, "finished": self.finished,
             "elapsed": round((self.finished or time.time()) - self.started, 1)}
        if full:
            d.update(candidates=self.candidates, extras=self.extras, rows=self.rows,
                     method=sc.METHOD_NOTES[self.kind], saved_to=self.saved_to)
        return d


def get_sites(settings):
    key = (settings.remote, settings.nsfw, tuple(sorted(x.lower() for x in settings.sites)))
    if key not in _SITE_CACHE:
        _SITE_CACHE[key] = sc.load_sites(settings)
    return _SITE_CACHE[key]


def run_job(job):
    s = job.settings
    try:
        cands, extras = sc.build_candidates(job.kind, job.value, s)
        job.extras = extras
        job.candidates = [{"candidate": c, "confidence": conf, "hits": 0, "checked": False}
                          for c, conf in cands]
        job.total = len(cands)
        site_data = get_sites(s)
        job.sites = len(site_data)
        g = extras.get("gravatar", "")
        if g.startswith("http"):
            job.rows.append({"candidate": job.value, "confidence": sc.CONF_HIGH, "site": "Gravatar",
                             "url": g, "status": "Claimed", "http_status": 200,
                             "response_time_s": None, "context": None})
        for i, (user, conf) in enumerate(cands):
            if job.cancel.is_set():
                job.status = "cancelled"
                break
            res = sc.sherlock(user, site_data, sc.ConsoleNotify(),
                              proxy=s.proxy, timeout=s.timeout)
            n = 0
            for site, r in res.items():
                st = r["status"]
                claimed = st.status == QueryStatus.CLAIMED
                n += claimed
                job.rows.append({
                    "candidate": user, "confidence": conf, "site": site,
                    "url": r["url_user"], "status": st.status.value,
                    "http_status": r.get("http_status"),
                    "response_time_s": st.query_time,
                    "context": st.context})
            job.candidates[i].update(hits=n, checked=True)
            job.done = i + 1
        else:
            job.status = "done"
    except Exception as e:  # noqa: BLE001 - surfaced to UI
        job.status, job.error = "error", str(e)
    finally:
        job.finished = time.time()
        if job.status in ("done", "cancelled") and job.rows:
            try:
                hits = [{k: r[k] for k in ("candidate", "confidence", "site", "url",
                                            "http_status", "response_time_s")}
                        for r in job.rows if r["status"] == "Claimed"]
                job.saved_to = sc.write_reports(
                    job.kind, job.value, [(c["candidate"], c["confidence"]) for c in job.candidates],
                    hits, job.extras, s, job.status == "cancelled")
            except OSError:
                pass


def make_settings(opts):
    s = sc.Settings()
    s.color = False
    try:
        s.timeout = float(opts.get("timeout", 30))
        if not 1 <= s.timeout <= 120:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("timeout must be between 1 and 120 seconds")
    s.proxy = (opts.get("proxy") or "").strip() or None
    s.nsfw = bool(opts.get("nsfw"))
    s.gravatar = bool(opts.get("gravatar", True))
    s.remote = bool(opts.get("remote"))
    try:
        s.max_variants = max(1, min(30, int(opts.get("max_variants", 12))))
    except (TypeError, ValueError):
        raise ValueError("max_variants must be an integer")
    s.sites = [x for x in re.split(r"[,\n]+", opts.get("sites") or "") if x.strip()]
    s.sites = [x.strip() for x in s.sites]
    return s


class Handler(BaseHTTPRequestHandler):
    server_version = "SherlockWeb/1.0"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _host_ok(self):
        # Defends against DNS rebinding: only answer to loopback host names.
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip("[]")
        return host in ALLOWED_HOSTS or any(
            h.startswith("*.") and host.endswith(h[1:]) for h in ALLOWED_HOSTS)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(HERE, "sherlock_web.html"), "rb") as fh:
                return self._send(200, fh.read(), "text/html; charset=utf-8")
        if path == "/api/jobs":
            with JOBS_LOCK:
                jobs = sorted(JOBS.values(), key=lambda j: -j.started)
            return self._send(200, [j.public(False) for j in jobs])
        m = re.fullmatch(r"/api/jobs/(\w+)", path)
        if m and m.group(1) in JOBS:
            return self._send(200, JOBS[m.group(1)].public())
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return self._send(403, {"error": "bad host"})
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            return self._send(415, {"error": "JSON required"})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(min(n, 65536)) or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._send(400, {"error": "invalid JSON"})
        path = self.path.split("?", 1)[0]
        if path == "/api/search":
            kind, value = body.get("kind"), (body.get("value") or "").strip()
            if kind not in KINDS or not value or len(value) > 200:
                return self._send(400, {"error": "kind and value (<=200 chars) required"})
            try:
                settings = make_settings(body.get("options") or {})
                sc.build_candidates(kind, value, _no_net(settings))  # validate input only
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            job = Job(kind, value, settings)
            with JOBS_LOCK:
                JOBS[job.id] = job
            threading.Thread(target=run_job, args=(job,), daemon=True).start()
            return self._send(202, {"id": job.id})
        m = re.fullmatch(r"/api/jobs/(\w+)/cancel", path)
        if m and m.group(1) in JOBS:
            JOBS[m.group(1)].cancel.set()
            return self._send(200, {"ok": True})
        self._send(404, {"error": "not found"})


def _no_net(settings):
    """Copy of settings with the network Gravatar call disabled (validation only)."""
    import copy
    s = copy.copy(settings)
    s.gravatar = False
    return s


def main():
    p = argparse.ArgumentParser(description="Sherlock web console")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--allow-host", action="append", default=[],
                   help="extra Host header to accept, e.g. 192.168.1.20 or *.app.github.dev "
                        "(needed for phone/LAN/Codespaces access; the UI has no login)")
    a = p.parse_args()
    ALLOWED_HOSTS.update(h.lower() for h in a.allow_host)
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    url = f"http://{'127.0.0.1' if a.host == '0.0.0.0' else a.host}:{a.port}"  # noqa: S104
    print(f"Sherlock web console: {url}   (Ctrl-C to stop)")
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
