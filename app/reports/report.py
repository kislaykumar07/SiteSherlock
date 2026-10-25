"""Standalone HTML report for a scan (printable to PDF from the browser)."""
import html


def _e(s):
    return html.escape(str(s or ""))


def render_html_report(scan: dict) -> str:
    rows = "".join(
        f"<tr><td>{_e(f['id'])}</td><td>{_e(f['severity'].upper())}</td><td>{_e(f['category'])}</td>"
        f"<td><b>{_e(f['rule_id'].replace('_',' '))}</b><br>{_e(f['evidence'])}<br><i>Fix: {_e(f['recommendation'])}</i></td>"
        f"<td>{_e(f['page_url'])}</td></tr>"
        for f in scan["findings"]) or "<tr><td colspan='5'>No issues detected in this scan.</td></tr>"
    summary = scan.get("summary", {}).get("text", "")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>SiteSherlock Report — {_e(scan['root_url'])}</title>
<style>body{{font-family:Arial,sans-serif;margin:32px;color:#14213d}}h1{{margin-bottom:4px}}
.score{{font-size:42px;font-weight:700}}table{{border-collapse:collapse;width:100%;margin-top:16px}}
td,th{{border:1px solid #ccc;padding:8px;font-size:13px;vertical-align:top;text-align:left}}
.small{{color:#555;font-size:12px}}@media print{{body{{margin:12px}}}}</style></head><body>
<h1>SiteSherlock AI — Website Audit Report</h1>
<p class="small">Site: {_e(scan['root_url'])} · Scan ID: {_e(scan.get('scan_id',''))} · Date: {_e(scan.get('created_at',''))} · Pages checked: {scan['pages_checked']}</p>
<p class="score">{scan['score']['overall']} / 100 health score</p>
<p>{_e(summary)}</p>
<table><tr><th>ID</th><th>Severity</th><th>Category</th><th>Finding &amp; fix</th><th>Page</th></tr>{rows}</table>
<p class="small">Automated checks cover only part of website quality and accessibility, and this report is
not a security audit or an SEO guarantee. Performance figures are response-time signals from this scan,
not full Core Web Vitals. Verify fixes with a re-scan.</p>
</body></html>"""
