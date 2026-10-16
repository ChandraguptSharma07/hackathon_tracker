import { createTracker, RESULTS, STATUS, STATUSES } from "./tracker.js";

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
  ethglobal: "ETHGlobal",
  dorahacks: "DoraHacks",
  luma: "lu.ma",
  hackclub: "Hack Club",
  taikai: "TAIKAI",
  kaggle: "Kaggle",
  zindi: "Zindi",
};
const MODE_NAMES = { online: "Online", in_person: "In person", hybrid: "Hybrid" };

const $ = (sel) => document.querySelector(sel);
const form = $("#filters");
const regionName = new Intl.DisplayNames(["en"], { type: "region" });
const dateFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const dateYearFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" });
const money = (n, cur = "USD") =>
  new Intl.NumberFormat(undefined, { style: "currency", currency: cur, maximumFractionDigits: 0 }).format(n);

const tracker = createTracker();

let all = [];
let view = "all";  // "all" listings or "mine" (tracked)
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
  h.deadline = d("registration_deadline") || h.end;  // last moment a newcomer can join
  // false = registration closed, true = open, null = no evidence. Re-checked against the
  // viewer's clock because the feed can be hours old.
  h.regOpen = () => {
    if (h.registration_open === false) return false;
    if (h.deadline) return h.deadline >= Date.now();
    return h.registration_open ?? null;
  };
  h.running = () => h.start && h.start <= Date.now() && (!h.end || h.end >= Date.now());
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
  view = p.get("view") === "mine" ? "mine" : "all";
}

function writeState() {
  const p = new URLSearchParams();
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") { if (el.checked) p.set(el.name, "1"); }
    else if (el.value && !(el.name === "sort" && el.value === "deadline")) p.set(el.name, el.value);
  }
  if (disabledSources.size) p.set("off", [...disabledSources].join(","));
  if (view === "mine") p.set("view", "mine");
  const qs = p.toString();
  history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
}

function filtered() {
  const f = Object.fromEntries(new FormData(form));
  const now = Date.now();
  const terms = (f.q || "").toLowerCase().split(/\s+/).filter(Boolean);
  hiddenClosed = 0;
  const out = all.filter((h) => {
    if (h.allSources.every((s) => disabledSources.has(s))) return false;
    if (f.kind && (h.kind || "hackathon") !== f.kind) return false;
    if (f.mode === "onsite") {
      if (h.mode !== "in_person" && h.mode !== "hybrid") return false;
    } else if (f.mode && h.mode !== f.mode) return false;
    if (f.metro && h.metro !== f.metro) return false;
    if (f.sponsor && !(h.sponsors || []).includes(f.sponsor)) return false;
    if (f.country && h.countryName !== f.country) return false;
    if (f.within && !(h.deadline && h.deadline - now <= f.within * DAY && h.deadline >= now)) return false;
    if (f.prize && !h.prize_usd) return false;
    if (f.fresh && !h.isNew(7)) return false;
    if (!terms.every((t) => h.haystack.includes(t))) return false;
    const status = tracker.get(h)?.status;
    if (status === "not_going") return false;
    // Something you're tracking stays visible even after its registration closes.
    if (!f.closed && !status && h.regOpen() === false) { hiddenClosed += 1; return false; }
    return true;
  });
  const far = 8.64e15;
  const sorters = {
    // Closed ones (only shown on request) go last instead of first.
    deadline: (a, b) => (a.regOpen() === false) - (b.regOpen() === false)
      || (a.deadline ?? far) - (b.deadline ?? far),
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
  if (h.regOpen() === false) {
    const text = h.running() ? "Registration closed · running" : "Registration closed";
    return `<span class="deadline closed">${text}</span>`;
  }
  if (!h.deadline) return "";
  const ms = h.deadline - Date.now();
  const days = Math.floor(ms / DAY);
  const hours = Math.max(1, Math.floor(ms / 3_600_000));
  const left = days >= 1 ? `${days} day${days === 1 ? "" : "s"}` : `${hours}h`;
  const est = h.registration_inferred;
  const title = est
    ? `Estimated: this site gives no registration deadline, so this assumes you can join until ${h.deadline.toLocaleString()}`
    : `Registration closes ${h.deadline.toLocaleString()}`;
  return `<span class="deadline${days < 3 ? " soon" : ""}" title="${esc(title)}">${est ? "~" : ""}${left} left to join</span>`;
}

function prize(h) {
  if (!h.prize_amount) return "";
  const cur = h.prize_currency || "USD";
  let main;
  try { main = money(h.prize_amount, cur); } catch { main = `${h.prize_amount} ${cur}`; }
  const approx = cur !== "USD" && h.prize_usd ? ` <span class="listed">≈ ${money(h.prize_usd)}</span>` : "";
  return `<span class="prize">${esc(main)}</span>${approx}`;
}

function trackSelect(h, idx, entry) {
  const status = entry?.status || "";
  const options = [`<option value="">☆ Track</option>`,
    ...STATUSES.map((s) => `<option value="${s.id}"${s.id === status ? " selected" : ""}>${s.icon} ${s.label}</option>`)];
  if (status) options.push(`<option value="remove">Stop tracking</option>`);
  return `<select class="track status-${status || "none"}" data-track="${idx}" aria-label="Track ${esc(h.title)}">${options.join("")}</select>`;
}

// What to do next for something you're tracking, given its stage and dates.
function nextStep(h, entry) {
  const now = Date.now();
  const when = (d) => dateYearFmt.format(d);
  const inDays = (d) => {
    const days = Math.ceil((d - now) / DAY);
    return days <= 1 ? "within a day" : `in ${days} days`;
  };
  switch (entry.status) {
    case "interested":
      if (h.regOpen() === false) return "Registration has closed.";
      return h.deadline ? `Register by ${when(h.deadline)}${h.registration_inferred ? " (estimated)" : ""}.` : "";
    case "registered":
      if (h.start && h.start > now) return `Starts ${inDays(h.start)} (${when(h.start)}).`;
      if (h.end && h.end > now) return `Running: submit by ${when(h.end)}, ${inDays(h.end)}.`;
      return "Ended: mark it Submitted or Done.";
    case "submitted":
      return h.end && h.end > now ? `Submissions close ${when(h.end)}; results after that.` : "Record the result when it's out.";
    default:
      return "";
  }
}

function trackerPanel(h, idx, entry) {
  const result = entry.status === "done"
    ? `<select class="result" data-result="${idx}" aria-label="Result">
        <option value="">Result…</option>
        ${RESULTS.map((r) => `<option value="${r.id}"${r.id === entry.result ? " selected" : ""}>${r.label}</option>`).join("")}
      </select>`
    : "";
  const step = nextStep(h, entry);
  return `<div class="tracker-panel">
      ${step ? `<p class="next">${esc(step)}</p>` : ""}
      ${result}
      <textarea data-note="${idx}" rows="2" placeholder="Notes: team, idea, repo, links…" aria-label="Notes for ${esc(h.title)}">${esc(entry.note || "")}</textarea>
    </div>`;
}

function card(h, idx, mine = false) {
  const entry = tracker.get(h);
  const where = h.mode === "online" ? "Online"
    : [h.location || [h.city, h.countryName].filter(Boolean).join(", "), h.mode === "hybrid" ? "(hybrid)" : ""]
      .filter(Boolean).join(" ");
  const seenUrls = new Set();
  const listings = [{ source: h.source, url: h.url }, ...(h.also_on || [])]
    .filter((l) => !seenUrls.has(l.url) && seenUrls.add(l.url))  // one link per page
    .map((l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(SOURCE_NAMES[l.source] || l.source)}</a>`)
    .join(" · ");
  const img = h.image_url
    ? `<img class="thumb" src="${esc(h.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer">`
    : `<div class="thumb" aria-hidden="true"></div>`;
  return `<li class="card${entry ? ` tracked status-${entry.status}` : ""}">
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
        ${h.gone ? `<span class="tag">No longer listed</span>` : ""}
        ${h.isNew(3) ? `<span class="tag new">New</span>` : ""}
        ${h.running() && h.regOpen() !== false ? `<span class="tag live">Running · open to join</span>` : ""}
        ${h.registration_note ? `<span class="tag note">${esc(h.registration_note)}</span>` : ""}
        ${h.kind === "competition" ? `<span class="tag kind">ML competition</span>` : ""}
        ${(h.sponsors || []).map((s) => `<button type="button" class="tag sponsor" data-sponsor="${esc(s)}">${esc(s)}</button>`).join("")}
        ${(h.themes || []).slice(0, 4).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}
      </div>
      ${mine && entry ? trackerPanel(h, idx, entry) : ""}
    </div>
    <div class="side">
      ${trackSelect(h, idx, entry)}
      ${prize(h)}
      ${!entry || entry.status === "interested" ? deadlineBadge(h) : ""}
      <span class="listed">${listings}</span>
      ${h.start || h.end ? `<button type="button" class="ics" data-idx="${idx}">Add to calendar</button>` : ""}
    </div>
  </li>`;
}

let current = [];
let hiddenClosed = 0;  // matches of the other filters left out only for closed registration

function render() {
  writeState();
  const mine = view === "mine";
  form.hidden = mine;
  $("#all-view").hidden = mine;
  $("#mine-view").hidden = !mine;
  $(".quick").hidden = mine;
  document.querySelectorAll("[data-view]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.view === view)));
  updateMineCount();
  // Only one view's cards may exist at a time: both index into `current`.
  if (mine) {
    $("#list").innerHTML = "";
    return renderMine();
  }
  $("#mine-groups").innerHTML = "";
  current = filtered();
  const hidden = hiddenClosed ? ` · ${hiddenClosed} with closed registration hidden` : "";
  $("#count").textContent = `${current.length} of ${all.length} listings${hidden}`;
  $("#list").innerHTML = current.slice(0, shown).map((h, i) => card(h, i)).join("");
  $("#more").hidden = current.length <= shown;
}

function updateMineCount() {
  const active = tracker.entries().filter((e) => e.status !== "not_going").length;
  $("#mine-count").textContent = active ? String(active) : "";
}

// Tracked entries joined with today's feed; ones the feed dropped come from their snapshot.
function trackedListings() {
  const byId = new Map(all.map((h) => [h.id, h]));
  const byUrl = new Map(all.flatMap((h) => [h.url, ...(h.also_on || []).map((l) => l.url)].map((u) => [u, h])));
  return tracker.entries().map((entry) => {
    const s = entry.listing;
    const live = byId.get(s.id) || [s.url, ...(s.also_on || []).map((l) => l.url)].map((u) => byUrl.get(u)).find(Boolean);
    return { entry, h: live || Object.assign(prepare(structuredClone(s)), { gone: true }) };
  });
}

function renderMine() {
  const rows = trackedListings();
  const far = 8.64e15;
  // Soonest thing that matters for the stage first.
  const key = ({ h, entry }) => {
    if (entry.status === "interested") return h.deadline ?? far;
    if (entry.status === "registered") return (h.start > Date.now() ? h.start : h.end) ?? far;
    if (entry.status === "done") return -(h.end ?? 0);
    return h.end ?? far;
  };
  current = [];
  const groups = STATUSES.map((s) => {
    const items = rows.filter((r) => r.entry.status === s.id).sort((a, b) => key(a) - key(b));
    if (!items.length) return "";
    const cards = items.map(({ h }) => { current.push(h); return card(h, current.length - 1, true); }).join("");
    const body = `<ol class="list">${cards}</ol>`;
    const heading = `${s.icon} ${s.label} <span class="pill">${items.length}</span>`;
    return s.id === "not_going"
      ? `<details class="group"><summary><h2>${heading}</h2></summary>${body}</details>`
      : `<section class="group"><h2>${heading}</h2>${body}</section>`;
  }).join("");
  const active = rows.filter((r) => r.entry.status !== "not_going").length;
  $("#mine-summary").textContent = rows.length
    ? `${active} tracked${tracker.persistent ? ", saved in this browser" : ""}.`
    : "";
  $("#mine-groups").innerHTML = groups || `<p class="empty">Nothing tracked yet. Use the
    <strong>☆ Track</strong> menu on any listing to save it here as Interested, Registered,
    Submitted or Done.</p>`;
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

const icsText = (s) => String(s || "").replace(/[\\;,]/g, (c) => `\\${c}`).replace(/\n/g, "\\n");

function icsEvent(uid, summary, start, end, h) {
  return [
    "BEGIN:VEVENT", `UID:${uid}@hackathon-tracker`, `DTSTAMP:${icsDate(new Date())}`,
    `DTSTART:${icsDate(start)}`, `DTEND:${icsDate(end)}`,
    `SUMMARY:${icsText(summary)}`, `URL:${h.url}`,
    `DESCRIPTION:${icsText([h.organizer, h.deadline ? `Join by: ${h.deadline.toUTCString()}${h.registration_inferred ? " (estimated)" : ""}` : "", h.url].filter(Boolean).join("\n"))}`,
    h.mode !== "online" && h.location ? `LOCATION:${icsText(h.location)}` : "",
    "END:VEVENT",
  ].filter(Boolean);
}

function eventLines(h) {
  const start = h.start || h.end;
  if (!start) return [];
  const end = h.end && h.end > start ? h.end : new Date(start.getTime() + 3_600_000);
  return icsEvent(h.id, h.title, start, end, h);
}

function download(filename, text, type) {
  const a = Object.assign(document.createElement("a"), {
    href: URL.createObjectURL(new Blob([text], { type })),
    download: filename,
  });
  a.click();
  URL.revokeObjectURL(a.href);
}

function downloadIcs(events, name) {
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//hackathon-tracker//EN", ...events, "END:VCALENDAR"];
  download(`${name.replace(/[^\w-]+/g, "_").slice(0, 60)}.ics`, lines.join("\r\n"), "text/calendar");
}

// Event dates for everything you're tracking, plus a "Register by" reminder for the
// ones you're only interested in so far.
function trackedCalendar() {
  const events = [];
  for (const { h, entry } of trackedListings()) {
    if (!["interested", "registered", "submitted"].includes(entry.status)) continue;
    events.push(...eventLines(h));
    if (entry.status === "interested" && h.deadline && h.deadline > Date.now()) {
      const reminder = new Date(h.deadline.getTime() - 3_600_000);
      events.push(...icsEvent(`${h.id}-register`, `Register: ${h.title}`, reminder, h.deadline, h));
    }
  }
  return events;
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
  if (ics) {
    const h = current[Number(ics.dataset.idx)];
    downloadIcs(eventLines(h), h.title);
  }
});

// ---- tracking ---------------------------------------------------------------

let quietSave = false;  // note typing saves without re-rendering (keeps focus and caret)

tracker.onChange(() => {
  if (quietSave) { quietSave = false; updateMineCount(); return; }
  render();
});

document.querySelectorAll("[data-view]").forEach((b) => b.addEventListener("click", () => {
  view = b.dataset.view;
  shown = PAGE;
  render();
  window.scrollTo({ top: 0 });
}));

document.addEventListener("change", (e) => {
  const track = e.target.closest("[data-track]");
  if (track) {
    const h = current[Number(track.dataset.track)];
    if (track.value === "" || track.value === "remove") tracker.remove(h);
    else tracker.setStatus(h, track.value);
    return;
  }
  const note = e.target.closest("[data-note]");
  if (note) {  // fires on blur: save right away instead of waiting for the debounce
    const h = current[Number(note.dataset.note)];
    clearTimeout(noteTimers.get(h.id));
    quietSave = true;
    tracker.setNote(h, note.value);
    return;
  }
  const result = e.target.closest("[data-result]");
  if (result) tracker.setResult(current[Number(result.dataset.result)], result.value || undefined);
});

const noteTimers = new Map();
document.addEventListener("input", (e) => {
  const note = e.target.closest("[data-note]");
  if (!note) return;
  const h = current[Number(note.dataset.note)];
  clearTimeout(noteTimers.get(h.id));
  noteTimers.set(h.id, setTimeout(() => { quietSave = true; tracker.setNote(h, note.value); }, 400));
});

$("#mine-export").addEventListener("click", () => {
  const day = new Date().toISOString().slice(0, 10);
  download(`hackathon-tracker-${day}.json`, tracker.exportData(), "application/json");
});

$("#mine-import").addEventListener("change", async (e) => {
  const file = e.target.files[0];
  e.target.value = "";
  if (!file) return;
  try {
    const n = tracker.importData(await file.text());
    alert(n ? `Imported ${n} tracked hackathon${n === 1 ? "" : "s"}.` : "Nothing new in that file.");
  } catch {
    alert("That file isn't a Hackathon Tracker export.");
  }
});

$("#mine-calendar").addEventListener("click", () => {
  const events = trackedCalendar();
  if (!events.length) return alert("No upcoming dates among the hackathons you're tracking.");
  downloadIcs(events, "tracked-hackathons");
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
  fillSelect("metro", counts(all.map((h) => h.metro)));
  fillSelect("country", counts(all.map((h) => h.countryName)));
  readState();
  $("#storage-warning").hidden = tracker.persistent;
  sourceChips(feed.sources);
  health(feed);
  const updated = new Date(feed.generated_at);
  $("#summary").textContent =
    `${all.filter((h) => h.regOpen() !== false).length} hackathons and competitions open to join, from ${Object.keys(feed.sources).length} sites · updated ${updated.toLocaleString()}`;
  render();
}

main();
