"""Minimal, dependency-free HTML extraction using the stdlib parser."""
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


class PageParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_parts: list[str] = []
        self._in_title = False
        self.meta: dict[str, str] = {}
        self.canonical: str | None = None
        self.html_lang: str | None = None
        self.headings: list[tuple[int, str]] = []
        self._heading_level: int | None = None
        self._heading_parts: list[str] = []
        self.images: list[dict] = []
        self.links: list[dict] = []          # {href (absolute), text}
        self._link_href: str | None = None
        self._link_aria: str = ""
        self._link_parts: list[str] = []
        self.inputs: list[dict] = []
        self.label_fors: set[str] = set()
        self._text_parts: list[str] = []
        self._skip_text = 0  # inside script/style
        self.json_ld_types: list[str] = []
        self._in_json_ld = False
        self._json_ld_parts: list[str] = []
        self.has_breadcrumb = False

    # -- helpers ---------------------------------------------------------
    def _abs(self, href: str) -> str:
        return urljoin(self.base_url, href or "")

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        # Breadcrumb signal: any element labelled/classed as a breadcrumb trail
        marker = " ".join(str(v) for v in a.values()).lower()
        if "breadcrumb" in marker:
            self.has_breadcrumb = True
        if tag == "html":
            self.html_lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
        elif tag in ("script", "style"):
            self._skip_text += 1
            if tag == "script" and (a.get("type") or "").strip().lower() == "application/ld+json":
                self._in_json_ld = True
                self._json_ld_parts = []
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key and a.get("content") is not None:
                self.meta[key] = a["content"]
        elif tag == "link":
            if "canonical" in (a.get("rel") or "").lower() and a.get("href"):
                self.canonical = self._abs(a["href"])
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._heading_level = int(tag[1])
            self._heading_parts = []
        elif tag == "img":
            src = a.get("src", "")
            path = src.split("?")[0].split("#")[0].lower()
            fmt = path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
            self.images.append({"src": self._abs(src), "alt_present": "alt" in a,
                                "alt": a.get("alt", ""), "format": fmt,
                                "loading": (a.get("loading") or "").lower(),
                                "has_dims": bool(a.get("width") and a.get("height"))})
        elif tag == "a":
            self._link_href = a.get("href")
            self._link_aria = a.get("aria-label", "") or a.get("title", "")
            self._link_parts = []
        elif tag == "input":
            self.inputs.append({"id": a.get("id", ""), "type": (a.get("type") or "text").lower(),
                                "aria_label": a.get("aria-label", ""), "placeholder": a.get("placeholder", "")})
        elif tag == "label":
            if a.get("for"):
                self.label_fors.add(a["for"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in ("script", "style") and self._skip_text:
            self._skip_text -= 1
            if tag == "script" and self._in_json_ld:
                self._in_json_ld = False
                import json as _json
                try:
                    data = _json.loads("".join(self._json_ld_parts) or "{}")
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        if isinstance(item, dict) and item.get("@type"):
                            self.json_ld_types.append(str(item["@type"]))
                        if isinstance(item, dict) and isinstance(item.get("@graph"), list):
                            for g in item["@graph"]:
                                if isinstance(g, dict) and g.get("@type"):
                                    self.json_ld_types.append(str(g["@type"]))
                except Exception:
                    if self._json_ld_parts:
                        self.json_ld_types.append("(unparsed)")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._heading_level is not None:
            self.headings.append((self._heading_level, " ".join(self._heading_parts).strip()))
            self._heading_level = None
        elif tag == "a" and self._link_href is not None:
            href = self._link_href.strip()
            link_text = " ".join(self._link_parts).strip() or (self._link_aria or "").strip()
            if href and not href.startswith(("javascript:", "mailto:", "tel:", "#")):
                self.links.append({"href": self._abs(href), "text": link_text})
            elif href.startswith("#") or href == "":
                self.links.append({"href": href, "text": link_text, "anchor_only": True})
            self._link_href = None

    def handle_data(self, data):
        if self._in_json_ld:
            self._json_ld_parts.append(data)
        if self._in_title:
            self.title_parts.append(data)
        if self._heading_level is not None:
            self._heading_parts.append(data)
        if self._link_href is not None:
            self._link_parts.append(data)
        if not self._skip_text:
            self._text_parts.append(data)

    # -- derived -----------------------------------------------------------
    @property
    def title(self) -> str:
        return " ".join("".join(self.title_parts).split())

    @property
    def word_count(self) -> int:
        return len(" ".join(self._text_parts).split())


def same_host(url_a: str, url_b: str) -> bool:
    ha = (urlparse(url_a).hostname or "").lower().removeprefix("www.")
    hb = (urlparse(url_b).hostname or "").lower().removeprefix("www.")
    return ha == hb and ha != ""
