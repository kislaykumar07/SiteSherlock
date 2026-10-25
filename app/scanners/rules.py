"""Deterministic rule scanners (Blueprint sections 5-6).

Every finding is structured evidence: rule_id, page_url, category, severity,
evidence, explanation, recommendation, confidence, effort.
The AI layer only explains these facts — it never invents detections.
"""
from urllib.parse import urlparse

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
SEVERITY_DEDUCT = {"critical": 10, "high": 6, "medium": 3, "low": 1}

META = {  # rule_id -> (category, severity, effort, explanation, recommendation)
    "SITE_NOT_HTTPS": ("Security Signals", "high", "Medium",
        "The site is not served over HTTPS, so visitor traffic is not encrypted and browsers mark it 'Not secure'.",
        "Install a TLS certificate (e.g. Let's Encrypt) and redirect all http:// traffic to https://."),
    "LINK_BROKEN": ("Links", "high", "Low",
        "A link points to a page that does not load successfully. Broken links waste visitor trust and search ranking signals.",
        "Fix the link target, restore the missing page, or remove the link."),
    "LINK_UNREACHABLE": ("Links", "medium", "Low",
        "A linked address could not be reached during the scan (timeout, DNS or blocked). This can be temporary, so verify before acting.",
        "Open the link manually to confirm; fix or remove it if it consistently fails."),
    "LINK_INSECURE": ("Links", "low", "Low",
        "This page links out over plain http://, which can trigger mixed-content warnings.",
        "Update the link to the https:// version of the destination."),
    "TITLE_MISSING": ("SEO & Metadata", "high", "Low",
        "A page without a <title> shows a blank or filename-style label in search results and browser tabs.",
        "Add a unique, descriptive title of roughly 30-60 characters to the page."),
    "TITLE_TOO_LONG": ("SEO & Metadata", "low", "Low",
        "Very long titles are truncated in search results, hiding the most important words.",
        "Shorten the title to about 60 characters, keeping keywords first."),
    "TITLE_DUPLICATE": ("SEO & Metadata", "medium", "Low",
        "Several scanned pages share the same title, so search engines and visitors cannot tell them apart.",
        "Give each page its own title that describes that page's content."),
    "DESC_MISSING": ("SEO & Metadata", "medium", "Low",
        "Without a meta description, search engines invent a snippet from page text — often a poor one.",
        "Add a 120-160 character meta description summarising the page and its benefit."),
    "DESC_TOO_LONG": ("SEO & Metadata", "low", "Low",
        "Long meta descriptions get cut off in search results.",
        "Trim the description to about 160 characters."),
    "DESC_DUPLICATE": ("SEO & Metadata", "low", "Low",
        "Several scanned pages share the same meta description.",
        "Write a page-specific description for each page."),
    "CANONICAL_MISSING": ("SEO & Metadata", "low", "Low",
        "No canonical URL was found, so duplicate versions of the page may compete in search.",
        "Add a <link rel=\"canonical\"> pointing to the preferred URL of the page."),
    "OG_MISSING": ("SEO & Metadata", "low", "Low",
        "Open Graph tags are missing, so shared links may appear with a random image and text on social media.",
        "Add og:title, og:description and og:image tags."),
    "IMG_ALT_MISSING": ("Accessibility", "medium", "Low",
        "Screen readers cannot describe images without alt text, and search engines lose that context. Alt quality still needs human judgement.",
        "Add short, meaningful alt text to content images (alt=\"\" only for purely decorative images)."),
    "NO_H1": ("Content Structure", "medium", "Low",
        "The page has no <h1>, so its main topic is unclear to visitors, screen readers and search engines.",
        "Add one clear <h1> that states the page's main topic."),
    "MULTIPLE_H1": ("Content Structure", "low", "Low",
        "Multiple <h1> headings weaken the page's content hierarchy.",
        "Keep one <h1> per page and demote the others to <h2>."),
    "HEADING_SKIP": ("Content Structure", "low", "Low",
        "Heading levels jump (for example h1 straight to h3), which confuses screen-reader navigation.",
        "Use heading levels in order without skipping."),
    "LANG_MISSING": ("Accessibility", "medium", "Low",
        "Without a lang attribute, screen readers may pronounce the page with the wrong language rules.",
        "Add lang=\"en\" (or the page's real language) to the <html> tag."),
    "VIEWPORT_MISSING": ("Usability", "high", "Low",
        "No viewport meta tag was found, so the page may render zoomed-out and hard to use on phones.",
        "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">."),
    "LINK_NO_TEXT": ("Accessibility", "medium", "Low",
        "A link with no readable text gives screen-reader users no idea where it goes.",
        "Add descriptive link text or an aria-label to the link."),
    "INPUT_NO_LABEL": ("Accessibility", "medium", "Low",
        "A form field without a label is hard to identify for screen-reader and voice-control users.",
        "Associate a <label> with the field, or add an aria-label."),
    "SLOW_RESPONSE": ("Performance Signals", "medium", "Medium",
        "The server took a long time to respond during this scan. Slow responses push visitors away. Full Core Web Vitals need a browser-based measurement, which this crawl does not claim.",
        "Check hosting performance, caching and server load; re-measure with PageSpeed Insights for detail."),
    "PAGE_HEAVY": ("Performance Signals", "low", "Medium",
        "The HTML document itself is large, which delays first rendering on slow connections.",
        "Reduce inline markup/scripts and defer non-critical resources."),
    "THIN_CONTENT": ("Content Structure", "low", "Medium",
        "Very little readable text was found, so the page may offer visitors and search engines too little to judge.",
        "Add clear, useful content that answers the visitor's reason for opening the page."),
    "HEADER_MISSING": ("Security Signals", "low", "Low",
        "A common protective response header was not present. This is a hardening signal, not proof the site is unsafe — SiteSherlock is not a security audit.",
        "Ask your host/developer about adding the header where it fits your stack."),
    "ROBOTS_MISSING": ("SEO & Metadata", "medium", "Low",
        "No robots.txt file was found. Search engines use it to know which parts of the site they may crawl; without it, crawlers guess.",
        "Add a robots.txt at the root of the domain that allows public pages and points to your sitemap."),
    "ROBOTS_BLOCKS_ALL": ("SEO & Metadata", "high", "Low",
        "The robots.txt file tells every search engine not to crawl any page (Disallow: /). The site can become invisible in search results.",
        "Remove the blanket Disallow: / rule so search engines can crawl public pages."),
    "SITEMAP_MISSING": ("SEO & Metadata", "medium", "Low",
        "No XML sitemap was found. A sitemap hands search engines a clean list of your pages so new and deep pages get discovered faster.",
        "Generate a sitemap.xml listing your public pages, place it at the root, and reference it in robots.txt."),
    "SOFT_404": ("Usability", "medium", "Low",
        "A deliberately wrong address returned a success status instead of a 404. Search engines may index these 'soft 404' pages, and visitors get no clear signal the page is gone.",
        "Configure the server to return a real 404 status for missing pages, ideally with a helpful custom error page."),
    "NO_CUSTOM_404": ("Usability", "low", "Low",
        "Missing pages fall back to a bare default server error with no branding or way back. A custom 404 page keeps lost visitors on the site.",
        "Create a branded 404 page with a search box or links to your main pages, and return it with a 404 status."),
    "SCHEMA_MISSING": ("SEO & Metadata", "low", "Low",
        "No structured data (JSON-LD schema) was found on the homepage. Schema helps search engines understand the business and can unlock richer result displays.",
        "Add JSON-LD schema — Organisation or LocalBusiness for the homepage, and types like Product, Article or FAQ where they fit."),
    "IMG_FORMAT_OLD": ("Performance Signals", "low", "Medium",
        "Several images use older JPEG/PNG formats. Modern formats such as WebP or AVIF are typically 25-50% smaller at the same quality, which speeds up the page.",
        "Convert content images to WebP (or AVIF) and serve those, keeping the originals as fallback if needed."),
    "IMG_NO_LAZY": ("Performance Signals", "low", "Low",
        "Several images load immediately even though they sit further down the page. Lazy loading defers off-screen images so the visible part of the page renders faster.",
        "Add loading=\"lazy\" to below-the-fold images (keep the main hero image eager)."),
    "IMG_NO_DIMS": ("Usability", "low", "Low",
        "Several images have no width/height attributes, so the browser cannot reserve space for them and page content jumps around while they load (layout shift).",
        "Add width and height attributes (or an aspect-ratio style) to images so space is reserved before they load."),
}


def _finding(rule_id, page_url, evidence, confidence=0.95):
    category, severity, effort, explanation, recommendation = META[rule_id]
    return {"rule_id": rule_id, "page_url": page_url, "category": category, "severity": severity,
            "effort": effort, "evidence": evidence, "explanation": explanation,
            "recommendation": recommendation, "confidence": confidence}


def scan_pages(crawl_result: dict) -> list[dict]:
    findings: list[dict] = []
    pages = crawl_result["pages"]
    link_checks = crawl_result["link_checks"]
    titles: dict[str, list[str]] = {}
    descs: dict[str, list[str]] = {}

    for page in pages:
        url = page["url"]
        parsed = page["parsed"]
        if url.startswith("http://"):
            findings.append(_finding("SITE_NOT_HTTPS", url, f"Page served over plain http: {url}"))
        # Security-signal headers (homepage-level signals, checked per page cheaply)
        for header, label in (("x-content-type-options", "X-Content-Type-Options"),
                              ("x-frame-options", "X-Frame-Options / frame-ancestors")):
            if header not in page["headers"] and page["status"] == 200:
                findings.append(_finding("HEADER_MISSING", url, f"Response header {label} not present on {url}", 0.7))
                break  # one header finding per page is enough signal
        if page["elapsed_ms"] > 2500:
            findings.append(_finding("SLOW_RESPONSE", url, f"Server response took {page['elapsed_ms']} ms during this scan.", 0.75))
        if page["size_bytes"] > 400_000:
            findings.append(_finding("PAGE_HEAVY", url, f"HTML document size: {round(page['size_bytes']/1024)} KB."))
        if parsed is None:
            continue
        titles.setdefault(parsed.title, []).append(url)
        desc = parsed.meta.get("description", "")
        if desc:
            descs.setdefault(desc, []).append(url)
        # Metadata
        if not parsed.title:
            findings.append(_finding("TITLE_MISSING", url, "No <title> text found."))
        elif len(parsed.title) > 60:
            findings.append(_finding("TITLE_TOO_LONG", url, f"Title is {len(parsed.title)} chars: “{parsed.title[:80]}…”"))
        if not desc:
            findings.append(_finding("DESC_MISSING", url, "No meta description found."))
        elif len(desc) > 160:
            findings.append(_finding("DESC_TOO_LONG", url, f"Meta description is {len(desc)} chars."))
        if not parsed.canonical:
            findings.append(_finding("CANONICAL_MISSING", url, "No <link rel=\"canonical\"> found.", 0.85))
        if "og:title" not in parsed.meta:
            findings.append(_finding("OG_MISSING", url, "No og:title meta tag found.", 0.85))
        # Accessibility / usability
        if not parsed.html_lang:
            findings.append(_finding("LANG_MISSING", url, "<html> tag has no lang attribute."))
        if "viewport" not in parsed.meta:
            findings.append(_finding("VIEWPORT_MISSING", url, "No viewport meta tag found."))
        missing_alt = [i for i in parsed.images if not i["alt_present"]]
        if missing_alt:
            findings.append(_finding("IMG_ALT_MISSING", url,
                f"{len(missing_alt)} image(s) without an alt attribute, e.g. {missing_alt[0]['src'][:110]}"))
        empty_links = [l for l in parsed.links if not l["text"]]
        if empty_links:
            findings.append(_finding("LINK_NO_TEXT", url,
                f"{len(empty_links)} link(s) with no readable text, e.g. pointing to {empty_links[0]['href'][:110]}", 0.9))
        unlabelled = [i for i in parsed.inputs
                      if i["type"] not in ("hidden", "submit", "button")
                      and not (i["id"] and i["id"] in parsed.label_fors)
                      and not i["aria_label"]]
        if unlabelled:
            first = unlabelled[0]
            findings.append(_finding("INPUT_NO_LABEL", url,
                f"{len(unlabelled)} form field(s) without a label or aria-label, e.g. type={first['type']}, id={first['id'] or '—'}.", 0.85))
        # Headings / content
        h1s = [h for h in parsed.headings if h[0] == 1]
        if not h1s:
            findings.append(_finding("NO_H1", url, "No <h1> heading found on the page."))
        elif len(h1s) > 1:
            findings.append(_finding("MULTIPLE_H1", url, f"{len(h1s)} <h1> headings found."))
        levels = [h[0] for h in parsed.headings]
        for a, b in zip(levels, levels[1:]):
            if b - a > 1:
                findings.append(_finding("HEADING_SKIP", url, f"Heading level jumps from h{a} to h{b}.", 0.9))
                break
        if parsed.word_count < 100:
            findings.append(_finding("THIN_CONTENT", url, f"Only about {parsed.word_count} words of readable text found.", 0.8))
        # Insecure outgoing links (aggregated per page)
        insecure = [l for l in parsed.links if l["href"].startswith("http://")]
        if insecure:
            findings.append(_finding("LINK_INSECURE", url,
                f"{len(insecure)} outgoing http:// link(s), e.g. {insecure[0]['href'][:110]}", 0.9))
        # Image delivery signals (aggregated per page, only when material)
        old_fmt = [i for i in parsed.images if i["format"] in ("jpg", "jpeg", "png")]
        if len(old_fmt) >= 3:
            findings.append(_finding("IMG_FORMAT_OLD", url,
                f"{len(old_fmt)} image(s) use JPEG/PNG instead of WebP/AVIF, e.g. {old_fmt[0]['src'][:110]}", 0.85))
        no_lazy = [i for i in parsed.images[3:] if i["loading"] != "lazy"]
        if len(no_lazy) >= 3:
            findings.append(_finding("IMG_NO_LAZY", url,
                f"{len(no_lazy)} below-the-top image(s) load eagerly without loading=\"lazy\".", 0.8))
        no_dims = [i for i in parsed.images if not i["has_dims"]]
        if len(no_dims) >= 3:
            findings.append(_finding("IMG_NO_DIMS", url,
                f"{len(no_dims)} image(s) have no width/height attributes, e.g. {no_dims[0]['src'][:110]}", 0.8))

    # Site-level launch files (robots.txt / sitemap / 404 behaviour) — homepage scope
    site_checks = crawl_result.get("site_checks") or {}
    root_url = pages[0]["url"] if pages else ""
    if site_checks:
        robots = site_checks.get("robots", {})
        if robots.get("status") not in (200,):
            findings.append(_finding("ROBOTS_MISSING", root_url,
                f"GET /robots.txt returned status {robots.get('status', 0)}.", 0.9))
        elif robots.get("blocks_all"):
            findings.append(_finding("ROBOTS_BLOCKS_ALL", root_url,
                "robots.txt contains 'User-agent: *' with 'Disallow: /'.", 0.95))
        sitemap = site_checks.get("sitemap", {})
        if sitemap.get("status") != 200 and not robots.get("sitemap_url"):
            findings.append(_finding("SITEMAP_MISSING", root_url,
                "No /sitemap.xml found and robots.txt does not declare one.", 0.9))
        probe = site_checks.get("probe404", {})
        if probe.get("status") == 200:
            findings.append(_finding("SOFT_404", root_url,
                "A deliberately non-existent page returned HTTP 200 instead of 404.", 0.9))
        elif probe.get("status") == 404 and not probe.get("custom"):
            findings.append(_finding("NO_CUSTOM_404", root_url,
                "The 404 response is a small default server page with no site content or navigation.", 0.7))
        first_parsed = pages[0]["parsed"] if pages else None
        if first_parsed is not None and not first_parsed.json_ld_types:
            findings.append(_finding("SCHEMA_MISSING", root_url,
                "No application/ld+json structured data found on the homepage.", 0.9))

    # Duplicate metadata across pages
    for title, urls in titles.items():
        if title and len(urls) > 1:
            for u in urls:
                findings.append(_finding("TITLE_DUPLICATE", u, f"Title “{title[:70]}” is shared by {len(urls)} scanned pages."))
    for desc, urls in descs.items():
        if len(urls) > 1:
            for u in urls:
                findings.append(_finding("DESC_DUPLICATE", u, f"Same meta description is shared by {len(urls)} scanned pages."))

    # Broken / unreachable links (from crawl status map + external checks)
    reported = set()
    for page in pages:
        parsed = page["parsed"]
        if parsed is None:
            continue
        for link in parsed.links:
            target = link["href"].split("#")[0]
            status = link_checks.get(target.rstrip("/"), link_checks.get(target))
            if status is None or (target, page["url"]) in reported:
                continue
            reported.add((target, page["url"]))
            if status >= 400:
                findings.append(_finding("LINK_BROKEN", page["url"],
                                         f"Link to {target[:110]} returned HTTP {status}.", 0.9))
            elif status == 0:
                findings.append(_finding("LINK_UNREACHABLE", page["url"],
                                         f"Link to {target[:110]} could not be reached during the scan.", 0.6))

    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["category"], f["rule_id"]))
    for i, f in enumerate(findings, start=1):
        f["id"] = f"F-{i:03d}"
    return findings


def score(findings: list[dict], pages: list[dict]) -> dict:
    """Transparent scoring: 100 minus severity deductions (floor 0),
    overall and per category. Not an SEO or security guarantee."""
    cats = ["SEO & Metadata", "Accessibility", "Links", "Performance Signals",
            "Content Structure", "Usability", "Security Signals"]
    per_cat = {c: 100 for c in cats}
    total_deduct = 0
    for f in findings:
        d = SEVERITY_DEDUCT[f["severity"]]
        total_deduct += d
        if f["category"] in per_cat:
            per_cat[f["category"]] = max(0, per_cat[f["category"]] - d * 2)
    return {"overall": max(0, 100 - total_deduct), "categories": per_cat}
