#!/usr/bin/env python3
"""Minimal CVMaker CLI over /api/v1 (Phase 5 definition of done). Stdlib only.

export CVMAKER_URL=http://localhost:8000      # default
export CVMAKER_TOKEN=<key from Settings -> API token>

python scripts/cvmaker_cli.py list
python scripts/cvmaker_cli.py render <cv-id> [--language es] [--style moderncv] [-o cv.pdf]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


class CVMakerClient:
    def __init__(self, base_url: str, token: str, poll_interval: float = 0.5, timeout: float = 60):
        self.base = base_url.rstrip("/") + "/api/v1"
        self.token = token
        self.poll_interval = poll_interval
        self.timeout = timeout

    def _request(self, method: str, url: str, payload: dict | None = None) -> tuple[int, bytes]:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Token {self.token}")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            raise SystemExit(
                f"{method} {url} -> HTTP {exc.code}: {exc.read().decode()[:300]}"
            ) from exc

    def _json(self, method: str, path_or_url: str, payload: dict | None = None) -> dict:
        url = path_or_url if path_or_url.startswith("http") else self.base + path_or_url
        return json.loads(self._request(method, url, payload)[1])

    def list_cvs(self) -> list[dict]:
        return self._json("GET", "/cvs/")["results"]

    def render_pdf(self, cv_id: str, language: str = "", style: str = "") -> bytes:
        render = self._json("POST", f"/cvs/{cv_id}/render/", {"language": language, "style": style})
        deadline = time.monotonic() + self.timeout
        while render["status"] not in ("done", "failed"):
            if time.monotonic() > deadline:
                raise SystemExit(
                    f"Render {render['id']} still {render['status']} after {self.timeout}s"
                )
            time.sleep(self.poll_interval)
            render = self._json("GET", f"/renders/{render['id']}/")
        if render["status"] == "failed":
            raise SystemExit(f"Render failed: {render['error']}")
        return self._request("GET", render["pdf_url"])[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List your CVs")
    render = sub.add_parser("render", help="Render a CV and save the PDF")
    render.add_argument("cv_id")
    render.add_argument("--language", default="")
    render.add_argument("--style", default="")
    render.add_argument("-o", "--output", default="cv.pdf")
    args = parser.parse_args(argv)

    token = os.environ.get("CVMAKER_TOKEN")
    if not token:
        parser.error("set CVMAKER_TOKEN (Settings -> API token)")
    client = CVMakerClient(os.environ.get("CVMAKER_URL", "http://localhost:8000"), token)

    if args.command == "list":
        for cv in client.list_cvs():
            langs = ", ".join(f"{s['code']} {s['done']}/{s['total']}" for s in cv["languages"])
            print(f"{cv['id']}  {cv['alias']:<20} {cv['theme'] or '-':<18} {langs}")
    else:
        pdf = client.render_pdf(args.cv_id, args.language, args.style)
        with open(args.output, "wb") as fh:
            fh.write(pdf)
        print(f"Saved {len(pdf):,} bytes to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
