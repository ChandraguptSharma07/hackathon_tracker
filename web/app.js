const DATA_URL = "data/hackathons.json";
const PAGE = 60;
const DAY = 86_400_000;

const SOURCE_NAMES = {
  devpost: "Devpost",
  mlh: "MLH",
  devfolio: "Devfolio",
  unstop: "Unstop",
  hackerearth: "HackerEarth",
  cerebralvalley: "Cerebral Valley",
  lablab: "lablab.ai",
};
const MODE_NAMES = { online: "Online", in_person: "In person", hybrid: "Hybrid" };

const $ = (sel) => document.querySelector(sel);
const form = $("#filters");
const regionName = new Intl.DisplayNames(["en"], { type: "region" });
const dateFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const dateYearFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" });
const money = (n, cur = "USD") =>
  new Intl.NumberFormat(undefined, { style: "currency", currency: cur, maximumFractionDigits: 0 }).format(n);

let all = [];
let trackingSince = 0;
let disabledSources = new Set();
let shown = PAGE;

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function country(code) {
  if (!code) return "";
  if (/^[A-Z]{2}$/.test(code)) {
    try { return regionName.of(code); } catch { return code; }
  }
  return code;
}

function prepare(h) {
  const d = (k) => (h[k] ? new Date(h[k]) : null);
  h.start = d("starts_at");
  h.end = d("ends_at");
  h.deadline = d("registration_deadline") || h.end;
  h.seen = d("first_seen");
  h.isNew = (days) => h.seen && h.seen > trackingSince && Date.now() - h.seen <= days * DAY;
  h.countryName = country(h.country);
  h.allSources = [h.source, ...(h.also_on || []).map((l) => l.source)];
  h.haystack = [h.title, h.organizer, h.location, h.city, h.countryName, h.description,
    ...(h.themes || []), ...(h.sponsors || [])].join(" ").toLowerCase();
  return h;
}

// ---- filters <-> URL ---------------------------------------------------------

function readState() {
  const p = new URLSearchParams(location.search);
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") el.checked = p.get(el.name) === "1";
    else if (p.has(el.name)) el.value = p.get(el.name);
  }
  disabledSources = new Set((p.get("off") || "").split(",").filter(Boolean));
}

function writeState() {
  const p = new URLSearchParams();
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") { if (el.checked) p.set(el.name, "1"); }
    else if (el.value && !(el.name === "sort" && el.value === "deadline")) p.set(el.name, el.value);
  }
  if (disabledSources.size) p.set("off", [...disabledSources].join(","));
  const qs = p.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

function filtered() {
  const f = Object.fromEntries(new FormData(form));
  const now = Date.now();
  const terms = (f.q || "").toLowerCase().split(/\s+/).filter(Boolean);
  const out = all.filter((h) => {
    if (h.allSources.every((s) => disabledSources.has(s))) return false;
    if (f.mode && h.mode !== f.mode) return false;
    if (f.sponsor && !(h.sponsors || []).includes(f.sponsor)) return false;
    if (f.country && h.countryName !== f.country) return false;
    if (f.within && !(h.deadline && h.deadline - now <= f.within * DAY && h.deadline >= now)) return false;
    if (f.prize && !h.prize_usd) return false;
    if (f.fresh && !h.isNew(7)) return false;
    return terms.every((t) => h.haystack.includes(t));
  });
  const far = 8.64e15;
  const sorters = {
    deadline: (a, b) => (a.deadline ?? far) - (b.deadline ?? far),
    start: (a, b) => (a.start ?? far) - (b.start ?? far),
    prize: (a, b) => (b.prize_usd || 0) - (a.prize_usd || 0),
    new: (a, b) => (b.seen ?? 0) - (a.seen ?? 0),
    popular: (a, b) => (b.participants || 0) - (a.participants || 0),
  };
  return out.sort(sorters[f.sort] || sorters.deadline);
}

// ---- rendering --------------------------------------------------------------

function range(start, end) {
  if (!start && !end) return "";
  if (!start) return `Ends ${dateYearFmt.format(end)}`;
  if (!end || start.toDateString() === end.toDateString()) return dateYearFmt.format(start);
  const sameYear = start.getFullYear() === end.getFullYear();
  return `${(sameYear ? dateFmt : dateYearFmt).format(start)} – ${dateYearFmt.format(end)}`;
}

function deadlineBadge(h) {
  if (!h.deadline) return "";
  const ms = h.deadline - Date.now();
  if (ms < 0) {
    return h.end && h.end > Date.now() ? `<span class="deadline">Happening now</span>` : "";
  }
  const days = Math.floor(ms / DAY);
  const hours = Math.floor(ms / 3_600_000);
  const text = days >= 1 ? `${days} day${days === 1 ? "" : "s"} left` : `${hours}h left`;
  return `<span class="deadline${days < 3 ? " soon" : ""}" title="Deadline ${h.deadline.toLocaleString()}">${text}</span>`;
}

function prize(h) {
  if (!h.prize_amount) return "";
  const cur = h.prize_currency || "USD";
  let main;
  try { main = money(h.prize_amount, cur); } catch { main = `${h.prize_amount} ${cur}`; }
  const approx = cur !== "USD" && h.prize_usd ? ` <span class="listed">≈ ${money(h.prize_usd)}</span>` : "";
  return `<span class="prize">${esc(main)}</span>${approx}`;
}

function card(h, idx) {
  const where = h.mode === "online" ? "Online"
    : [h.location || [h.city, h.countryName].filter(Boolean).join(", "), h.mode === "hybrid" ? "(hybrid)" : ""]
      .filter(Boolean).join(" ");
  const listings = [{ source: h.source, url: h.url }, ...(h.also_on || [])]
    .map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(SOURCE_NAMES[l.source] || l.source)}</a>`)
    .join(" · ");
  const img = h.image_url
    ? `<img class="thumb" src="${esc(h.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
    : `<div class="thumb" aria-hidden="true"></div>`;
  return `<li class="card">
    ${img}
    <div>
      <h2><a href="${esc(h.url)}" target="_blank" rel="noopener">${esc(h.title)}</a></h2>
      ${h.organizer ? `<p class="org">${esc(h.organizer)}</p>` : ""}
      <p class="meta">
        ${range(h.start, h.end) ? `<span>${range(h.start, h.end)}</span>` : ""}
        ${where ? `<span>${esc(where)}</span>` : ""}
        ${h.participants ? `<span>${h.participants.toLocaleString()} registered</span>` : ""}
      </p>
      <div class="tags">
        ${h.isNew(3) ? `<span class="tag new">New</span>` : ""}
        ${(h.sponsors || []).map((s) => `<button type="button" class="tag sponsor" data-sponsor="${esc(s)}">${esc(s)}</button>`).join("")}
        ${(h.themes || []).slice(0, 4).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}
      </div>
    </div>
    <div class="side">
      ${prize(h)}
      ${deadlineBadge(h)}
      <span class="listed">${listings}</span>
      ${h.start || h.end ? `<button type="button" class="ics" data-idx="${idx}">Add to calendar</button>` : ""}
    </div>
  </li>`;
}

let current = [];

function render() {
  writeState();
  current = filtered();
  $("#count").textContent = `${current.length} of ${all.length} hackathons`;
  $("#list").innerHTML = current.slice(0, shown).map(card).join("");
  $("#more").hidden = current.length <= shown;
}

function fillSelect(name, values) {
  const sel = form.elements[name];
  for (const [value, n] of values) {
    sel.add(new Option(`${value} (${n})`, value));
  }
}

function counts(list) {
  const m = new Map();
  for (const v of list) if (v) m.set(v, (m.get(v) || 0) + 1);
  return [...m].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
}

function sourceChips(feedSources) {
  const box = $("#sources");
  box.innerHTML = Object.keys(feedSources).map((s) =>
    `<button type="button" class="chip" data-source="${s}" aria-pressed="${!disabledSources.has(s)}">${esc(SOURCE_NAMES[s] || s)}</button>`,
  ).join("");
}

function health(feed) {
  $("#health").innerHTML = Object.entries(feed.sources).map(([name, h]) => {
    const status = h.ok ? "ok" : h.stale ? "stale (using last good data)" : "failed";
    return `<li class="${h.ok ? "" : "bad"}">${esc(SOURCE_NAMES[name] || name)}: ${h.count} listings, ${status}${h.error ? ` — ${esc(h.error)}` : ""}</li>`;
  }).join("");
}

// ---- calendar export ------------------------------------------------------------

function icsDate(d) {
  return d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
}

function downloadIcs(h) {
  const start = h.start || h.end;
  const end = h.end && h.end > start ? h.end : new Date(start.getTime() + 3_600_000);
  const text = (s) => String(s || "").replace(/[\\;,]/g, (c) => `\\${c}`).replace(/\n/g, "\\n");
  const lines = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//hackathon-tracker//EN", "BEGIN:VEVENT",
    `UID:${h.id}@hackathon-tracker`, `DTSTAMP:${icsDate(new Date())}`,
    `DTSTART:${icsDate(start)}`, `DTEND:${icsDate(end)}`,
    `SUMMARY:${text(h.title)}`, `URL:${h.url}`,
    `DESCRIPTION:${text([h.organizer, h.deadline ? `Deadline: ${h.deadline.toUTCString()}` : "", h.url].filter(Boolean).join("\n"))}`,
    h.mode !== "online" && h.location ? `LOCATION:${text(h.location)}` : "",
    "END:VEVENT", "END:VCALENDAR",
  ].filter(Boolean);
  const blob = new Blob([lines.join("\r\n")], { type: "text/calendar" });
  const a = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(blob),
    download: `${h.title.replace(/[^\w-]+/g, "_").slice(0, 60)}.ics`,
  });
  a.click();
  URL.revokeObjectURL(a.href);
}

// ---- wiring -----------------------------------------------------------------

form.addEventListener("input", () => { shown = PAGE; render(); });
$("#more").addEventListener("click", () => { shown += PAGE; render(); });
$("#clear").addEventListener("click", () => {
  form.reset();
  disabledSources.clear();
  document.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", "true"));
  shown = PAGE;
  render();
});
$("#sources").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  const s = chip.dataset.source;
  disabledSources.has(s) ? disabledSources.delete(s) : disabledSources.add(s);
  chip.setAttribute("aria-pressed", String(!disabledSources.has(s)));
  shown = PAGE;
  render();
});
$("#list").addEventListener("click", (e) => {
  const sponsor = e.target.closest("[data-sponsor]");
  if (sponsor) {
    form.elements.sponsor.value = sponsor.dataset.sponsor;
    shown = PAGE;
    render();
    return;
  }
  const ics = e.target.closest(".ics");
  if (ics) downloadIcs(current[Number(ics.dataset.idx)]);
});

async function main() {
  let feed;
  try {
    const r = await fetch(DATA_URL, { cache: "no-cache" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    feed = await r.json();
  } catch (err) {
    $("#summary").textContent = `Could not load data (${err.message}).`;
    return;
  }
  trackingSince = new Date(feed.tracking_since || 0);
  all = feed.hackathons.map(prepare);
  fillSelect("sponsor", counts(all.flatMap((h) => h.sponsors || [])));
  fillSelect("country", counts(all.map((h) => h.countryName)));
  readState();
  sourceChips(feed.sources);
  health(feed);
  const updated = new Date(feed.generated_at);
  $("#summary").textContent =
    `${all.length} open and upcoming hackathons from ${Object.keys(feed.sources).length} sites · updated ${updated.toLocaleString()}`;
  render();
}

main();
