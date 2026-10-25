# SiteSherlock AI — Find website problems. Know what to fix next.

**Live demo:** https://sitesherlock.vercel.app
**Video walkthrough:** see the "Watch how it works" section on the live site.

SiteSherlock AI is an AI-powered website audit platform. Enter any website URL and it
safely crawls up to 10 pages, runs **33 deterministic checks**, and produces a
transparent health score with a prioritised, evidence-based fix list.

## What it checks

| Area | Checks |
| --- | --- |
| Broken & unsafe links | 404s, unreachable targets, plain-http links |
| SEO & metadata | Titles, descriptions, canonicals, Open Graph, structured data |
| Launch readiness | robots.txt, XML sitemap, honest 404 behaviour |
| Accessibility | Alt text, labelled form fields, link text, page language |
| Content structure | One H1 per page, heading order, thin content |
| Performance & images | Response time, page weight, WebP/AVIF, lazy loading, image dimensions |
| Usability & safety signals | Mobile viewport, HTTPS, protective headers |

Every finding carries its evidence, severity, a plain-English explanation and a
recommended fix. The AI summary layer only explains findings — it never invents
detections, and summaries are rejected if they cite a finding that does not exist.

## Highlights

- **100/100 on its own audit.** The live site passes every one of its own checks
  (robots.txt, sitemap, canonical, OG/Twitter meta, JSON-LD schema, security
  headers, branded 404 page).
- **SSRF-safe bounded crawl.** Private/loopback/link-local addresses are blocked
  on every fetch and redirect; pages, depth, size and time are all capped.
- **Fast.** Parallel link checks and a cached DNS safety check keep a typical
  scan around one second.
- **Honest limits.** Performance figures are response-time signals, not full Core
  Web Vitals; this is not a security audit and does not guarantee rankings.

## Tech stack

Python, FastAPI, vanilla HTML/CSS/JavaScript, SQLite. No heavy dependencies — the
HTML parser is Python's standard library.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then open http://localhost:8000. Set `GROQ_API_KEY` to switch the summary layer
from the built-in deterministic engine to a Groq LLM (output is still validated
against real finding IDs).

## Deploy

This repository is the exact code deployed to Vercel (`framework: fastapi`).
Static files live in `public/`, the FastAPI app in `app/` (entrypoint
`app/main.py`), and scan history uses SQLite in `/tmp` on serverless with a
non-fatal fallback so a storage failure never breaks a scan.

## Project structure

```
app/
  main.py            FastAPI entrypoint + branded 404 handler
  crawler/           bounded safe crawler + stdlib HTML parser
  scanners/rules.py  33 deterministic rules + transparent scoring
  ai/summarizer.py   grounded summary engine (deterministic / Groq)
  db/store.py        SQLite scan history
  reports/report.py  standalone HTML report export
public/              frontend (index.html, styles.css, app.js) + SEO files
```

## Pricing (illustrative)

Free ₹0 · Pro ₹499/month · Agency ₹1,499/month — billing is not switched on;
the live site is a portfolio build.

---

Portfolio project by [Kislay Kumar](https://www.linkedin.com/in/kislay-kumar-8113683a7).
Only scan websites you own or have permission to test.
