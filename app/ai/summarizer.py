"""Grounded AI explanation layer (Blueprint section 5).

Rule: the summary may ONLY reference real finding IDs from the scanner.
Default engine is a deterministic grounded writer (works offline, never
hallucinates). If GROQ_API_KEY is set in the environment, an LLM pass is
attempted and validated — every finding ID it cites must exist, otherwise
the deterministic summary is used.
"""
import json
import os
import urllib.request
from collections import Counter

SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _priority(findings):
    def key(f):
        impact = {"critical": 4, "high": 3, "medium": 2, "low": 1}[f["severity"]]
        effort = {"Low": 3, "Medium": 2, "High": 1}[f.get("effort", "Low")]
        return (-(impact * 10 + effort), f["id"])
    return sorted(findings, key=key)


def deterministic_summary(scan: dict) -> dict:
    findings = scan["findings"]
    sev = Counter(f["severity"] for f in findings)
    cats = Counter(f["category"] for f in findings)
    top = _priority(findings)[:5]
    quick_wins = [f for f in _priority(findings) if f.get("effort") == "Low" and f["severity"] in ("high", "medium")][:6]
    n_pages = scan["pages_checked"]
    if not findings:
        text = (f"Good news — no issues were detected on the {n_pages} page(s) checked. "
                "That does not guarantee a perfect site: automated checks cover only part of "
                "accessibility and quality, so a human review is still recommended.")
    else:
        worst_cat = cats.most_common(1)[0][0] if cats else "general"
        text = (f"SiteSherlock checked {n_pages} page(s) and found {len(findings)} issue(s): "
                f"{sev.get('high',0)} high, {sev.get('medium',0)} medium and {sev.get('low',0)} low severity. "
                f"The biggest problem area is {worst_cat}. "
                f"Start with {top[0]['rule_id'].replace('_',' ').lower()} on {top[0]['page_url']} "
                f"({top[0]['id']}) — it is the highest-impact fix found. "
                "Fix high-severity items first, then re-scan to verify they are gone.")
    return {"text": text, "engine": "grounded-rules",
            "top_priorities": [{"id": f["id"], "rule_id": f["rule_id"], "severity": f["severity"],
                                "effort": f["effort"], "page_url": f["page_url"],
                                "recommendation": f["recommendation"]} for f in top],
            "quick_wins": [{"id": f["id"], "rule_id": f["rule_id"], "page_url": f["page_url"]} for f in quick_wins]}


def llm_summary(scan: dict) -> dict | None:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return None
    base = deterministic_summary(scan)
    facts = [{"id": f["id"], "rule": f["rule_id"], "severity": f["severity"],
              "page": f["page_url"], "evidence": f["evidence"][:160]} for f in scan["findings"][:30]]
    prompt = ("You are SiteSherlock's report writer. Using ONLY the findings JSON below, write a "
              "plain-English executive summary of 90-130 words for a small business owner. Cite finding "
              "IDs like [F-003] for every claim. Do not invent issues, scores, or guarantees.\n"
              f"Health score: {scan['score']['overall']}/100. Pages checked: {scan['pages_checked']}.\n"
              f"Findings: {json.dumps(facts)}")
    body = json.dumps({"model": "openai/gpt-oss-120b", "max_tokens": 500,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=body,
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read())
        text = data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
    valid_ids = {f["id"] for f in scan["findings"]}
    import re
    cited = set(re.findall(r"F-\d{3}", text))
    if cited and not cited.issubset(valid_ids):
        return None  # hallucinated citation -> reject
    base["text"] = text
    base["engine"] = "groq-llm (grounded, citations validated)"
    return base


def summarize(scan: dict) -> dict:
    return llm_summary(scan) or deterministic_summary(scan)
