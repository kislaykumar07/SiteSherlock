"""Built-in demo scan: a fictional shop site with known issues, so the
dashboard can be explored without scanning a live site."""
from .scanners.rules import score

_RAW = [
    ("LINK_BROKEN", "https://demo-shop.example/", "Links", "high", "Low", 0.98,
     "Link to https://demo-shop.example/offers-2023 returned HTTP 404.",
     "A link points to a page that does not load successfully.",
     "Fix the link target, restore the missing page, or remove the link."),
    ("TITLE_MISSING", "https://demo-shop.example/contact", "SEO & Metadata", "high", "Low", 0.99,
     "No <title> text found.",
     "A page without a title shows a blank label in search results and tabs.",
     "Add a unique, descriptive title of roughly 30-60 characters."),
    ("VIEWPORT_MISSING", "https://demo-shop.example/contact", "Usability", "high", "Low", 0.99,
     "No viewport meta tag found.",
     "Without it the page may render zoomed-out and hard to use on phones.",
     "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">."),
    ("DESC_MISSING", "https://demo-shop.example/", "SEO & Metadata", "medium", "Low", 0.99,
     "No meta description found.",
     "Search engines will invent a snippet from page text — often a poor one.",
     "Add a 120-160 character meta description."),
    ("IMG_ALT_MISSING", "https://demo-shop.example/", "Accessibility", "medium", "Low", 0.97,
     "Image without alt attribute: https://demo-shop.example/img/banner.jpg",
     "Screen readers cannot describe images without alt text.",
     "Add short, meaningful alt text to content images."),
    ("LANG_MISSING", "https://demo-shop.example/products", "Accessibility", "medium", "Low", 0.99,
     "<html> tag has no lang attribute.",
     "Screen readers may pronounce the page with the wrong language rules.",
     "Add lang=\"en\" (or the real language) to the <html> tag."),
    ("NO_H1", "https://demo-shop.example/products", "Content Structure", "medium", "Low", 0.98,
     "No <h1> heading found on the page.",
     "The page's main topic is unclear to visitors and search engines.",
     "Add one clear <h1> stating the page's main topic."),
    ("SLOW_RESPONSE", "https://demo-shop.example/products", "Performance Signals", "medium", "Medium", 0.8,
     "Server response took 3,240 ms during this scan.",
     "Slow responses push visitors away. This is a signal, not full Core Web Vitals.",
     "Check hosting performance and caching; re-measure with PageSpeed Insights."),
    ("CANONICAL_MISSING", "https://demo-shop.example/contact", "SEO & Metadata", "low", "Low", 0.9,
     "No <link rel=\"canonical\"> found.",
     "Duplicate versions of the page may compete in search.",
     "Add a canonical link to the preferred URL."),
    ("HEADING_SKIP", "https://demo-shop.example/", "Content Structure", "low", "Low", 0.92,
     "Heading level jumps from h1 to h3.",
     "Skipped levels confuse screen-reader navigation.",
     "Use heading levels in order without skipping."),
    ("SITEMAP_MISSING", "https://demo-shop.example/", "SEO & Metadata", "medium", "Low", 0.9,
     "No /sitemap.xml found and robots.txt does not declare one.",
     "A sitemap hands search engines a clean list of your pages so new and deep pages get discovered faster.",
     "Generate a sitemap.xml, place it at the root, and reference it in robots.txt."),
    ("IMG_NO_LAZY", "https://demo-shop.example/", "Performance Signals", "low", "Low", 0.85,
     "6 below-the-top image(s) load eagerly without loading=\"lazy\".",
     "Lazy loading defers off-screen images so the visible part of the page renders faster.",
     "Add loading=\"lazy\" to below-the-fold images (keep the main hero image eager)."),
]


def demo_scan() -> dict:
    findings = [{"id": f"F-{i:03d}", "rule_id": r[0], "page_url": r[1], "category": r[2],
                 "severity": r[3], "effort": r[4], "confidence": r[5], "evidence": r[6],
                 "explanation": r[7], "recommendation": r[8]} for i, r in enumerate(_RAW, 1)]
    pages = [
        {"url": "https://demo-shop.example/", "status": 200, "elapsed_ms": 420, "size_bytes": 48210,
         "title": "Demo Shop — Home", "word_count": 640},
        {"url": "https://demo-shop.example/products", "status": 200, "elapsed_ms": 3240, "size_bytes": 91200,
         "title": "Products", "word_count": 210},
        {"url": "https://demo-shop.example/contact", "status": 200, "elapsed_ms": 380, "size_bytes": 12100,
         "title": "", "word_count": 95},
    ]
    scan = {"root_url": "https://demo-shop.example", "pages_checked": 3, "pages": pages,
            "findings": findings, "score": score(findings, pages), "demo": True}
    from .ai.summarizer import deterministic_summary
    scan["summary"] = deterministic_summary(scan)
    return scan
