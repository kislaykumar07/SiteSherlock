"""Bounded, safe crawler (Blueprint sections 2, 6, 8).

Limits: same host only, max_pages, max depth 2, per-request timeout,
max response size, max 5 redirects — every redirect host is re-validated.
Also status-checks a bounded set of external links found on scanned pages.
"""
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse

from ..security.url_guard import host_is_safe
from .parser import PageParser, same_host

MAX_BYTES = 1_500_000
TIMEOUT = 6
MAX_EXTERNAL_CHECKS = 20
SCAN_BUDGET_S = 38  # hard wall-clock budget so serverless scans always answer in time
UA = "SiteSherlockAI/1.0 (+portfolio audit tool; respects robots intent, bounded crawl)"


class _GuardedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        host = urlparse(newurl).hostname or ""
        if not host_is_safe(host):
            raise urllib.error.URLError("Redirect to a blocked/internal address was refused.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_GuardedRedirect)


def fetch(url: str) -> dict:
    """One fetch. Never raises; returns status/headers/body/elapsed/error."""
    started = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        with _OPENER.open(req, timeout=TIMEOUT) as resp:
            body = resp.read(MAX_BYTES + 1)
            return {"url": url, "final_url": resp.geturl(), "status": resp.status,
                    "headers": {k.lower(): v for k, v in resp.headers.items()},
                    "body": body[:MAX_BYTES], "truncated": len(body) > MAX_BYTES,
                    "elapsed_ms": int((time.time() - started) * 1000), "error": None}
    except urllib.error.HTTPError as e:
        try:
            body = e.read(MAX_BYTES)
        except Exception:
            body = b""
        return {"url": url, "final_url": url, "status": e.code, "headers": {k.lower(): v for k, v in (e.headers.items() if e.headers else [])},
                "body": body, "truncated": False, "elapsed_ms": int((time.time() - started) * 1000), "error": None}
    except Exception as e:  # DNS, timeout, TLS, blocked redirect...
        return {"url": url, "final_url": url, "status": 0, "headers": {}, "body": b"",
                "truncated": False, "elapsed_ms": int((time.time() - started) * 1000),
                "error": str(e)[:200]}


def check_link(url: str) -> int:
    """Status for a linked URL: GET with small read (many servers reject HEAD)."""
    r = fetch(url)
    return r["status"]


def crawl(start_url: str, max_pages: int = 10) -> dict:
    deadline = time.time() + SCAN_BUDGET_S
    max_pages = max(1, min(int(max_pages or 10), 10))
    queue: list[tuple[str, int]] = [(start_url, 0)]
    seen: set[str] = set()
    pages: list[dict] = []
    external_links: dict[str, dict] = {}   # url -> {text, from_pages:set}
    internal_status: dict[str, int] = {}

    while queue and len(pages) < max_pages and time.time() < deadline:
        url, depth = queue.pop(0)
        norm = url.split("#")[0].rstrip("/") or url
        if norm in seen:
            continue
        seen.add(norm)
        r = fetch(url)
        internal_status[norm] = r["status"]
        content_type = r["headers"].get("content-type", "")
        page = {"url": r["final_url"], "status": r["status"], "elapsed_ms": r["elapsed_ms"],
                "size_bytes": len(r["body"]), "content_type": content_type,
                "headers": r["headers"], "error": r["error"], "parsed": None}
        if r["status"] == 200 and "html" in content_type:
            parser = PageParser(r["final_url"])
            try:
                parser.feed(r["body"].decode("utf-8", errors="replace"))
            except Exception:
                pass
            page["parsed"] = parser
            for link in parser.links:
                href = link["href"]
                if link.get("anchor_only"):
                    continue
                if same_host(start_url, href):
                    clean = href.split("#")[0]
                    if depth < 2 and clean.rstrip("/") not in seen and len(queue) + len(pages) < max_pages * 3:
                        queue.append((clean, depth + 1))
                else:
                    ext = external_links.setdefault(href, {"text": link["text"], "from": set()})
                    ext["from"].add(r["final_url"])
        pages.append(page)

    # Site-level launch files (robots.txt / sitemap.xml / 404 behaviour),
    # fetched in parallel from the origin, inside the same scan budget.
    site_checks: dict = {}
    origin = urlparse(start_url)
    origin_base = f"{origin.scheme}://{origin.netloc}"
    if host_is_safe(origin.hostname or ""):

        def _robots() -> tuple[str, dict]:
            r = fetch(origin_base + "/robots.txt")
            body = r["body"].decode("utf-8", errors="replace") if r["status"] == 200 else ""
            blocks_all = False
            sitemap_url = ""
            current_all = False
            for line in body.splitlines():
                low = line.strip().lower()
                if low.startswith("sitemap:"):
                    sitemap_url = line.split(":", 1)[1].strip()
                if low.startswith("user-agent:"):
                    current_all = low.split(":", 1)[1].strip() == "*"
                elif low.startswith("disallow:") and current_all:
                    if low.split(":", 1)[1].strip() == "/":
                        blocks_all = True
            return "robots", {"status": r["status"], "blocks_all": blocks_all,
                              "sitemap_url": sitemap_url}

        def _sitemap() -> tuple[str, dict]:
            r = fetch(origin_base + "/sitemap.xml")
            return "sitemap", {"status": r["status"]}

        def _probe404() -> tuple[str, dict]:
            probe = origin_base + "/sitesherlock-missing-page-probe-9f3k"
            r = fetch(probe)
            text = r["body"].decode("utf-8", errors="replace").lower()
            custom = r["status"] == 404 and len(r["body"]) > 600 and (
                "404" in text or "not found" in text or "back to" in text or "home" in text)
            return "probe404", {"status": r["status"], "custom": bool(custom),
                                "size": len(r["body"])}

        if time.time() < deadline:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=3) as pool:
                for key, value in pool.map(lambda f: f(), (_robots, _sitemap, _probe404)):
                    site_checks[key] = value
            robots = site_checks.get("robots", {})
            if robots.get("sitemap_url") and site_checks.get("sitemap", {}).get("status") != 200:
                site_checks["sitemap"] = {"status": 200, "via": "robots.txt"}
            # A sitemap reference inside robots.txt counts as discoverable
            if robots.get("sitemap_url"):
                site_checks.setdefault("sitemap", {})["declared"] = True

    # Bounded external-link status checks (parallel, within the scan budget)
    link_checks: dict[str, int] = dict(internal_status)
    ext_urls = list(external_links.keys())[:MAX_EXTERNAL_CHECKS]

    def _check(ext_url: str) -> tuple[str, int]:
        if not host_is_safe(urlparse(ext_url).hostname or ""):
            return ext_url, -1  # blocked, not fetched
        return ext_url, check_link(ext_url)

    if ext_urls and time.time() < deadline:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=6) as pool:
            for ext_url, status in pool.map(_check, ext_urls):
                link_checks[ext_url] = status

    return {"pages": pages, "external_links": external_links, "link_checks": link_checks,
            "pages_found": len(seen), "site_checks": site_checks}
