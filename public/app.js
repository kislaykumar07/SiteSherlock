/* SiteSherlock AI frontend — talks to the FastAPI backend at /v1 (same origin).
   When opened as a bare file with no backend, it explains that clearly and
   still shows the demo report (client-side copy) so the design can be reviewed. */
const API = "/v1";
let currentScan = null;
let progressTimer = null;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ruleName = (id) => id.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

/* ---------------- progress ---------------- */
function showProgress() {
  const title = $("progress-title");
  title.textContent = "Scanning";
  delete title.dataset.kinetic;
  $("scan-progress").hidden = false;
  const steps = [...document.querySelectorAll("#progress-steps li")];
  steps.forEach((li) => li.className = "");
  let i = 0;
  steps[0].className = "active";
  clearInterval(progressTimer);
  progressTimer = setInterval(() => {
    if (i < steps.length - 1) { steps[i].className = "done"; i++; steps[i].className = "active"; }
  }, 2200);
}
function hideProgress(doneTitle) {
  clearInterval(progressTimer);
  document.querySelectorAll("#progress-steps li").forEach((li) => (li.className = "done"));
  $("progress-title").textContent = doneTitle || "Scan complete";
  setTimeout(() => ($("scan-progress").hidden = true), 900);
}

/* ---------------- scanning ---------------- */
async function runScan(url, maxPages) {
  $("scan-error").hidden = true;
  $("scan-btn").disabled = true;
  showProgress();
  try {
    const resp = await fetch(`${API}/scan`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, max_pages: maxPages }),
    });
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) throw new Error(data.error || `Scan failed (${resp.status}).`);
    hideProgress("Scan complete — report ready below");
    renderResults(data);
    loadHistory();
  } catch (e) {
    clearInterval(progressTimer);
    $("scan-progress").hidden = true;
    const err = $("scan-error");
    err.textContent = e.message.includes("Failed to fetch")
      ? "Could not reach the SiteSherlock server. If you opened this page as a file, start the backend first (see README) — or view the demo report below."
      : e.message;
    err.hidden = false;
  } finally {
    $("scan-btn").disabled = false;
  }
}

async function runDemo() {
  $("scan-error").hidden = true;
  try {
    const resp = await fetch(`${API}/demo`);
    if (!resp.ok) throw new Error();
    renderResults(await resp.json());
  } catch {
    renderResults(clientDemo());
  }
  document.getElementById("results").scrollIntoView({ behavior: "smooth" });
}

/* Client-side demo copy — used only when the backend is unreachable
   (e.g. opening the HTML file directly for a design review). */
function clientDemo() {
  return {
    root_url: "https://demo-shop.example", demo: true, pages_checked: 3,
    created_at: new Date().toISOString(),
    score: { overall: 61, categories: { "SEO & Metadata": 74, "Accessibility": 88, "Links": 88, "Performance Signals": 92, "Content Structure": 92, "Usability": 88, "Security Signals": 100 } },
    summary: { engine: "grounded-rules (offline demo)", text: "SiteSherlock checked 3 page(s) and found 12 issue(s): 3 high, 6 medium and 3 low severity. The biggest problem area is SEO & Metadata. Start with the broken link on the homepage — it is the highest-impact fix found. (Offline demo copy — start the backend for live scans.)",
      top_priorities: [], quick_wins: [] },
    pages: [
      { url: "https://demo-shop.example/", status: 200, elapsed_ms: 420, size_bytes: 48210, title: "Demo Shop — Home", word_count: 640 },
      { url: "https://demo-shop.example/products", status: 200, elapsed_ms: 3240, size_bytes: 91200, title: "Products", word_count: 210 },
      { url: "https://demo-shop.example/contact", status: 200, elapsed_ms: 380, size_bytes: 12100, title: "", word_count: 95 },
    ],
    findings: [
      { id: "F-001", rule_id: "LINK_BROKEN", page_url: "https://demo-shop.example/", category: "Links", severity: "high", effort: "Low", confidence: 0.98, evidence: "Link to https://demo-shop.example/offers-2023 returned HTTP 404.", explanation: "A link points to a page that does not load successfully.", recommendation: "Fix the link target, restore the missing page, or remove the link." },
      { id: "F-002", rule_id: "TITLE_MISSING", page_url: "https://demo-shop.example/contact", category: "SEO & Metadata", severity: "high", effort: "Low", confidence: 0.99, evidence: "No <title> text found.", explanation: "A page without a title shows a blank label in search results and tabs.", recommendation: "Add a unique, descriptive title of roughly 30-60 characters." },
      { id: "F-003", rule_id: "IMG_ALT_MISSING", page_url: "https://demo-shop.example/", category: "Accessibility", severity: "medium", effort: "Low", confidence: 0.97, evidence: "Image without alt attribute: /img/banner.jpg", explanation: "Screen readers cannot describe images without alt text.", recommendation: "Add short, meaningful alt text to content images." },
      { id: "F-004", rule_id: "SITEMAP_MISSING", page_url: "https://demo-shop.example/", category: "SEO & Metadata", severity: "medium", effort: "Low", confidence: 0.9, evidence: "No /sitemap.xml found and robots.txt does not declare one.", explanation: "A sitemap hands search engines a clean list of your pages so new and deep pages get discovered faster.", recommendation: "Generate a sitemap.xml, place it at the root, and reference it in robots.txt." },
      { id: "F-005", rule_id: "IMG_NO_LAZY", page_url: "https://demo-shop.example/", category: "Performance Signals", severity: "low", effort: "Low", confidence: 0.85, evidence: "6 below-the-top image(s) load eagerly without loading=\"lazy\".", explanation: "Lazy loading defers off-screen images so the visible part of the page renders faster.", recommendation: "Add loading=\"lazy\" to below-the-fold images (keep the main hero image eager)." },
    ],
  };
}

/* ---------------- rendering ---------------- */
function renderResults(scan) {
  currentScan = scan;
  $("results").hidden = false;
  $("results-title").textContent = scan.demo ? "Demo report — Demo Shop" : `Report for ${scan.root_url}`;
  $("results-meta").textContent =
    `${scan.pages_checked} page(s) checked · ${scan.findings.length} finding(s)` +
    (scan.created_at ? ` · ${new Date(scan.created_at).toLocaleString()}` : "") +
    (scan.demo ? " · Sample data — run a live scan for a real site" : "");

  const overall = scan.score.overall;
  $("score-num").textContent = overall;
  const ring = $("ring-fg");
  ring.style.strokeDashoffset = String(327 - (327 * overall) / 100);
  ring.style.stroke = overall >= 80 ? "var(--green)" : overall >= 55 ? "var(--orange)" : "var(--red)";
  $("score-label").textContent = overall >= 80 ? "Healthy — keep monitoring" : overall >= 55 ? "Needs attention" : "Priority fixes needed";

  $("summary-text").textContent = scan.summary?.text || "";
  $("summary-engine").textContent = scan.summary?.engine ? `Summary engine: ${scan.summary.engine} — every claim is grounded in the findings below.` : "";

  const prio = scan.summary?.top_priorities || [];
  $("priority-list").innerHTML = prio.length
    ? prio.map((p) => `<li><span class="tag sev-${p.severity}">${esc(p.severity)}</span> <b>${esc(ruleName(p.rule_id))}</b> — ${esc(p.recommendation)} <span class="muted">(${esc(p.id)} · effort: ${esc(p.effort)})</span></li>`).join("")
    : scan.findings.slice(0, 5).map((f) => `<li><span class="tag sev-${f.severity}">${esc(f.severity)}</span> <b>${esc(ruleName(f.rule_id))}</b> — ${esc(f.recommendation)}</li>`).join("") || "<li>No issues found — nice work.</li>";

  $("category-bars").innerHTML = Object.entries(scan.score.categories)
    .map(([cat, val]) => `<div class="cat-bar"><div class="row"><span>${esc(cat)}</span><span>${val}</span></div><div class="bar"><i style="width:${val}%"></i></div></div>`).join("");

  const sevCount = {};
  scan.findings.forEach((f) => (sevCount[f.severity] = (sevCount[f.severity] || 0) + 1));
  $("severity-pills").innerHTML = ["high", "medium", "low"].map((s) => `<span>${s}: ${sevCount[s] || 0}</span>`).join("") || "<span>None</span>";

  const cats = [...new Set(scan.findings.map((f) => f.category))].sort();
  $("filter-category").innerHTML = `<option value="">All categories</option>` + cats.map((c) => `<option>${esc(c)}</option>`).join("");
  $("filter-search").value = ""; $("filter-severity").value = ""; $("filter-category").value = "";
  renderFindings();

  $("pages-body").innerHTML = scan.pages.map((p) => `<tr>
    <td>${esc(p.url)}</td>
    <td class="${p.status === 200 ? "status-ok" : "status-bad"}">${p.status || "—"}</td>
    <td>${p.elapsed_ms} ms</td><td>${(p.size_bytes / 1024).toFixed(1)} KB</td>
    <td>${esc(p.title || "—")}</td><td>${p.word_count}</td></tr>`).join("");

  document.getElementById("results").scrollIntoView({ behavior: "smooth" });
}

function renderFindings() {
  if (!currentScan) return;
  const q = $("filter-search").value.toLowerCase();
  const cat = $("filter-category").value;
  const sev = $("filter-severity").value;
  const list = currentScan.findings.filter((f) =>
    (!cat || f.category === cat) && (!sev || f.severity === sev) &&
    (!q || `${f.rule_id} ${f.evidence} ${f.page_url} ${f.explanation}`.toLowerCase().includes(q)));
  $("filter-count").textContent = `${list.length} of ${currentScan.findings.length} findings`;
  $("no-findings").hidden = list.length > 0 || currentScan.findings.length === 0;
  $("findings-list").innerHTML = list.map((f) => `<article class="finding sev-${f.severity}">
    <header><span class="fid">${esc(f.id)}</span><span class="tag sev-${f.severity}">${esc(f.severity)}</span>
    <h3>${esc(ruleName(f.rule_id))}</h3><span class="tag" style="background:#eef1f7">${esc(f.category)}</span></header>
    <p class="page">${esc(f.page_url)}</p>
    <p>${esc(f.explanation)}</p>
    <p class="evidence"><b>Evidence:</b> ${esc(f.evidence)}</p>
    <p class="fix"><b>Fix:</b> ${esc(f.recommendation)}</p>
    <p class="meta-line">Effort: ${esc(f.effort)} · Confidence: ${Math.round((f.confidence || 0) * 100)}%</p>
  </article>`).join("");
}

/* ---------------- history ---------------- */
async function loadHistory() {
  const box = $("history-list");
  try {
    const resp = await fetch(`${API}/scans`);
    const data = await resp.json();
    if (!data.scans?.length) { box.innerHTML = `<p class="muted">No scans yet — your first audit will appear here.</p>`; return; }
    box.innerHTML = data.scans.map((s) => `<div class="history-item">
      <div><div class="url">${esc(s.root_url)}</div>
      <div class="meta">${new Date(s.created_at).toLocaleString()} · ${s.pages_checked} pages · ${s.findings_count} findings</div></div>
      <div style="display:flex;gap:10px;align-items:center">
        <span class="score-badge">${s.score}/100</span>
        <button type="button" data-open="${s.scan_id}">Open</button>
        <button type="button" data-del="${s.scan_id}">Delete</button>
      </div></div>`).join("");
    box.querySelectorAll("[data-open]").forEach((b) => b.addEventListener("click", async () => {
      const r = await fetch(`${API}/scans/${b.dataset.open}`);
      if (r.ok) renderResults(await r.json());
    }));
    box.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", async () => {
      await fetch(`${API}/scans/${b.dataset.del}`, { method: "DELETE" });
      loadHistory();
    }));
  } catch {
    box.innerHTML = `<p class="muted">History needs the backend running (see README). Demo reports still work above.</p>`;
  }
}

/* ---------------- export ---------------- */
function exportReport() {
  if (!currentScan) return;
  if (currentScan.scan_id) { window.open(`${API}/scans/${currentScan.scan_id}/report`, "_blank"); return; }
  const rows = currentScan.findings.map((f) => `<tr><td>${esc(f.id)}</td><td>${esc(f.severity)}</td><td>${esc(ruleName(f.rule_id))}</td><td>${esc(f.evidence)}</td><td>${esc(f.recommendation)}</td><td>${esc(f.page_url)}</td></tr>`).join("");
  const doc = `<!doctype html><html><head><meta charset="utf-8"><title>SiteSherlock Report</title><style>body{font-family:Arial;margin:30px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:7px;font-size:13px;text-align:left}</style></head><body><h1>SiteSherlock AI Report — ${esc(currentScan.root_url)}</h1><p>Score: ${currentScan.score.overall}/100 · Pages: ${currentScan.pages_checked}</p><p>${esc(currentScan.summary?.text || "")}</p><table><tr><th>ID</th><th>Severity</th><th>Finding</th><th>Evidence</th><th>Fix</th><th>Page</th></tr>${rows}</table></body></html>`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([doc], { type: "text/html" }));
  a.download = "sitesherlock-report.html";
  a.click();
  URL.revokeObjectURL(a.href);
}

/* ---------------- wiring ---------------- */
$("scan-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const url = $("url-input").value.trim();
  if (!url) { const err = $("scan-error"); err.textContent = "Enter a website URL first."; err.hidden = false; return; }
  runScan(url, parseInt($("pages-select").value, 10));
});
$("demo-btn").addEventListener("click", runDemo);
$("nav-scan-btn").addEventListener("click", () => { window.scrollTo({ top: 0, behavior: "smooth" }); $("url-input").focus(); });
$("rescan-btn").addEventListener("click", () => { if (currentScan && !currentScan.demo) runScan(currentScan.root_url, 10); else window.scrollTo({ top: 0, behavior: "smooth" }); });
$("export-btn").addEventListener("click", exportReport);
$("copy-summary-btn").addEventListener("click", async () => {
  if (!currentScan) return;
  const text = `SiteSherlock report for ${currentScan.root_url}\nScore: ${currentScan.score.overall}/100 · Pages checked: ${currentScan.pages_checked} · Findings: ${currentScan.findings.length}\n\n${currentScan.summary?.text || ""}`;
  try { await navigator.clipboard.writeText(text); $("copy-summary-btn").textContent = "Copied"; setTimeout(() => ($("copy-summary-btn").textContent = "Copy summary"), 1600); } catch {}
});
["filter-search", "filter-category", "filter-severity"].forEach((id) =>
  $(id).addEventListener("input", renderFindings));
loadHistory();

/* ============ v2 component engine ============
   Patterns recreated in vanilla JS:
   Skiper UI — text-roll nav, word-by-word scroll reveal, marquee
   Vengeance UI — spotlight cards, animated counters, flip text, kinetic loader
   Animaster — scroll reveals, cursor glow, magnetic buttons            */
(function initComponents() {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(pointer: fine)").matches;

  /* Text-roll nav (Skiper) */
  document.querySelectorAll("[data-roll]").forEach((a) => {
    const text = a.textContent.trim();
    a.setAttribute("aria-label", text);
    a.innerHTML = `<span class="roll" aria-hidden="true"><span>${esc(text)}</span><span class="r2">${esc(text)}</span></span>`;
  });

  /* Marquee (Skiper/Vengeance) */
  const items = ["BROKEN LINKS", "ROBOTS.TXT", "SITEMAP.XML", "TITLES & META", "OPEN GRAPH", "STRUCTURED DATA", "CUSTOM 404", "ALT TEXT", "ONE H1 PER PAGE", "WEBP & AVIF", "LAZY LOADING", "HTTPS & HEADERS"];
  const half = items.map((t) => `<span><i>·</i>${t}</span>`).join("");
  const mt = $("marquee-track");
  if (mt) mt.innerHTML = half + half;

  /* Flip word (Vengeance flip text) */
  const words = ["problems", "404 errors", "slow pages", "SEO gaps", "a11y issues"];
  let wi = 0;
  const flipEl = $("flip-word");
  if (flipEl && !reduced) {
    setInterval(() => {
      flipEl.classList.add("flip-out");
      setTimeout(() => {
        wi = (wi + 1) % words.length;
        flipEl.textContent = words[wi];
        flipEl.classList.remove("flip-out");
        flipEl.classList.add("flip-in-start");
        requestAnimationFrame(() => requestAnimationFrame(() => flipEl.classList.remove("flip-in-start")));
      }, 390);
    }, 2600);
  }

  /* Scroll reveals (Animaster) */
  const revealIO = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); revealIO.unobserve(e.target); } });
  }, { threshold: 0.14 });
  document.querySelectorAll(".reveal").forEach((el) => revealIO.observe(el));

  /* Animated counters (Vengeance) */
  const countIO = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      countIO.unobserve(e.target);
      const target = parseInt(e.target.dataset.count, 10);
      if (reduced) { e.target.textContent = target; return; }
      const t0 = performance.now();
      const tick = (t) => {
        const p = Math.min(1, (t - t0) / 1100);
        e.target.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }, { threshold: 0.6 });
  document.querySelectorAll("[data-count]").forEach((el) => countIO.observe(el));

  /* Word-by-word scroll reveal (Skiper TextBoxReveal) */
  const rt = $("reveal-text");
  if (rt) {
    const highlight = new Set(["evidence,", "fix", "first"]);
    rt.innerHTML = rt.textContent.trim().split(/\s+/)
      .map((w) => `<span class="w${highlight.has(w) ? " hl" : ""}">${esc(w)}</span>`).join(" ");
    const spans = rt.querySelectorAll(".w");
    const update = () => {
      const r = rt.getBoundingClientRect();
      const vh = window.innerHeight;
      const progress = Math.max(0, Math.min(1, (vh * 0.88 - r.top) / (r.height + vh * 0.25)));
      const n = Math.floor(progress * spans.length);
      spans.forEach((s, i) => s.classList.toggle("on", i < n));
    };
    if (reduced) spans.forEach((s) => s.classList.add("on"));
    else { window.addEventListener("scroll", update, { passive: true }); window.addEventListener("resize", update); update(); }
  }

  /* v3 Professional Edition: spotlight cards, magnetic buttons and cursor
     glow were removed on purpose — they are AI-template clichés. Motion is
     kept where it carries information: reveals, counters, flip word, loader. */

  /* Kinetic loader letters (Vengeance) — applied when progress shows */
  const title = $("progress-title");
  const kineticize = () => {
    if (title.dataset.kinetic || reduced) return;
    title.dataset.kinetic = "1";
    title.innerHTML = title.textContent.split("").map((ch, i) =>
      `<span style="animation-delay:${i * 70}ms">${esc(ch === " " ? " " : ch)}</span>`).join("");
  };
  new MutationObserver(() => { if (!$("scan-progress").hidden) kineticize(); })
    .observe($("scan-progress"), { attributes: true, attributeFilter: ["hidden"] });
})();
