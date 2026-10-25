"""SiteSherlock AI — FastAPI entry point.

Serves the frontend (same-origin) and the /v1 API:
  GET  /v1/health
  POST /v1/scan            {url, max_pages}
  GET  /v1/demo            built-in sample scan
  GET  /v1/scans           saved scan history
  GET  /v1/scans/{id}      one saved scan
  DELETE /v1/scans/{id}
  GET  /v1/scans/{id}/report   standalone HTML report
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.ai.summarizer import summarize
from app.crawler.crawler import crawl
from app.db import store
from app.demo import demo_scan
from app.reports.report import render_html_report
from app.scanners.rules import scan_pages, score
from app.security.url_guard import validate_url

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")

app = FastAPI(title="SiteSherlock AI", version="1.0.0")

# Branded 404 page — served for any non-API path that does not exist, so the
# site practises what it preaches (real 404 status + a helpful custom page).
_NOT_FOUND_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page not found (404) — SiteSherlock AI</title>
<style>body{margin:0;background:#0a0a0b;color:#f5f2ec;font-family:system-ui,sans-serif;
display:grid;place-items:center;min-height:100vh;text-align:center;padding:24px}
.code{font-family:Georgia,serif;font-style:italic;font-size:110px;color:#ffa582;line-height:1;margin:0}
h1{font-size:30px;margin:10px 0 8px}p{color:#8f8a7f;line-height:1.6;max-width:460px}
a.btn{display:inline-block;margin-top:18px;background:#f5f2ec;color:#12100d;font-weight:700;
text-decoration:none;padding:13px 26px;border-radius:10px}</style></head><body><main>
<p class="code">404</p><h1>This page is a missing clue.</h1>
<p>The page you asked for was not found — it may have moved, been renamed, or never existed
at all. Sherlock checked thoroughly. Head back to home and run a free website audit instead.</p>
<a class="btn" href="/">Back to home — run a free audit</a>
<p style="margin-top:22px;font-size:14px">Or jump to the <a href="/#checks" style="color:#ffa582">list of checks</a>
and the <a href="/#pricing" style="color:#ffa582">pricing section</a>.</p>
</main></body></html>"""


from starlette.exceptions import HTTPException as _StarletteHTTPException


@app.exception_handler(_StarletteHTTPException)
async def _http_exception_handler(request, exc):
    if exc.status_code == 404 and not request.url.path.startswith("/v1/"):
        return HTMLResponse(_NOT_FOUND_HTML, status_code=404)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


class ScanRequest(BaseModel):
    url: str
    max_pages: int = 10


@app.get("/v1/health")
def health():
    return {"status": "ok", "service": "sitesherlock", "version": "1.0.0",
            "llm_configured": bool(os.environ.get("GROQ_API_KEY"))}


@app.post("/v1/scan")
def run_scan(req: ScanRequest):
    url, error = validate_url(req.url)
    if error:
        return JSONResponse(status_code=400, content={"error": error})
    result = crawl(url, max_pages=req.max_pages)
    live_pages = [p for p in result["pages"]]
    if not live_pages or (live_pages[0]["status"] == 0 and live_pages[0]["error"]):
        return JSONResponse(status_code=422, content={
            "error": f"Could not fetch {url}. The site may be down, blocking automated checks, or timing out. "
                     "Try the homepage URL exactly as it opens in your browser."})
    findings = scan_pages(result)
    pages_out = []
    for p in live_pages:
        parsed = p["parsed"]
        pages_out.append({"url": p["url"], "status": p["status"], "elapsed_ms": p["elapsed_ms"],
                          "size_bytes": p["size_bytes"],
                          "title": parsed.title if parsed else "",
                          "word_count": parsed.word_count if parsed else 0})
    scan = {"root_url": url, "pages_checked": len(pages_out), "pages": pages_out,
            "findings": findings, "score": score(findings, live_pages), "demo": False}
    scan["summary"] = summarize(scan)
    try:
        scan["scan_id"] = store.save_scan(scan)
    except Exception as e:  # history storage must never fail the scan itself
        print(f"[sitesherlock] history save failed: {e!r}")
        scan["scan_id"] = None
    return scan


@app.get("/v1/demo")
def demo():
    return demo_scan()


@app.get("/v1/scans")
def history():
    return {"scans": store.list_scans()}


@app.get("/v1/scans/{scan_id}")
def one_scan(scan_id: str):
    scan = store.get_scan(scan_id)
    if not scan:
        return JSONResponse(status_code=404, content={"error": "Scan not found."})
    return scan


@app.delete("/v1/scans/{scan_id}")
def remove_scan(scan_id: str):
    return {"deleted": store.delete_scan(scan_id)}


@app.get("/v1/scans/{scan_id}/report", response_class=HTMLResponse)
def report(scan_id: str):
    scan = store.get_scan(scan_id)
    if not scan:
        return HTMLResponse("<h1>Scan not found</h1>", status_code=404)
    return HTMLResponse(render_html_report(scan),
                        headers={"Content-Disposition": f'attachment; filename="sitesherlock-report-{scan_id}.html"'})


if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
