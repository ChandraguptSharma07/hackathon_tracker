// Personal tracking: which hackathons you're interested in, registered for, and so on.
//
// Everything lives in this browser's localStorage, so it needs no account and works on a
// static host. Each entry keeps a snapshot of the listing, because the feed drops events
// once they end and a "Done" or "Submitted" entry should outlive that.

const KEY = "hackathon-tracker.v1";

export const STATUSES = [
  { id: "interested", label: "Interested", icon: "★" },
  { id: "registered", label: "Registered", icon: "✓" },
  { id: "submitted", label: "Submitted", icon: "⇪" },
  { id: "done", label: "Done", icon: "◆" },
  { id: "not_going", label: "Not going", icon: "✕" },
];
export const STATUS = Object.fromEntries(STATUSES.map((s) => [s.id, s]));

export const RESULTS = [
  { id: "won", label: "Won" },
  { id: "placed", label: "Placed / special prize" },
  { id: "no_prize", label: "No prize" },
];

// Listing fields worth keeping once the feed no longer has the event.
const SNAPSHOT_FIELDS = [
  "id", "source", "title", "url", "kind", "organizer", "image_url", "starts_at", "ends_at",
  "registration_deadline", "registration_inferred", "mode", "location", "city", "country",
  "metro", "prize_amount", "prize_currency", "prize_usd", "themes", "sponsors", "also_on",
];

function storageOrNull() {
  try {
    const probe = `${KEY}.probe`;
    localStorage.setItem(probe, "1");
    localStorage.removeItem(probe);
    return localStorage;
  } catch {
    return null; // private mode, blocked site data, or a sandboxed preview
  }
}

function urlsOf(h) {
  return [h.url, ...(h.also_on || []).map((l) => l.url)].filter(Boolean);
}

function snapshot(h) {
  return Object.fromEntries(SNAPSHOT_FIELDS.filter((k) => h[k] != null).map((k) => [k, h[k]]));
}

function isEntry(e) {
  return e && typeof e === "object" && STATUS[e.status] && e.listing && e.listing.id;
}

export function createTracker() {
  const store = storageOrNull();
  let items = {};
  const listeners = new Set();

  function load() {
    items = {};
    if (!store) return;
    try {
      const data = JSON.parse(store.getItem(KEY) || "{}");
      for (const [id, e] of Object.entries(data.items || {})) if (isEntry(e)) items[id] = e;
    } catch {
      items = {}; // unreadable data: start clean rather than break the page
    }
  }

  function persist() {
    if (!store) return;
    try {
      store.setItem(KEY, JSON.stringify({ version: 1, items }));
    } catch {
      // quota exceeded or storage revoked: keep working in memory for this visit
    }
  }

  function save() {
    persist();
    listeners.forEach((fn) => fn());
  }

  // An event's id can change between feed runs (a merge picks a different primary
  // listing), so fall back to matching on any of its listing URLs.
  function find(h) {
    if (items[h.id]) return items[h.id];
    const urls = new Set(urlsOf(h));
    const hit = Object.values(items).find((e) => urlsOf(e.listing).some((u) => urls.has(u)));
    if (hit) {
      delete items[hit.listing.id];
      hit.listing = { ...hit.listing, ...snapshot(h) };
      items[h.id] = hit;
      persist();
    }
    return hit || null;
  }

  function update(h, patch) {
    const now = new Date().toISOString();
    const existing = find(h);
    if (patch.status === null) {
      if (existing) delete items[existing.listing.id];
      save();
      return null;
    }
    const entry = existing || { status: "interested", note: "", added_at: now };
    Object.assign(entry, patch, { listing: snapshot(h), updated_at: now });
    if (entry.status !== "done") delete entry.result;
    items[h.id] = entry;
    save();
    return entry;
  }

  // Merge an exported file into what's here; for the same event the newer edit wins.
  function importData(text) {
    const data = JSON.parse(text);
    let added = 0;
    for (const e of Object.values(data.items || {})) {
      if (!isEntry(e)) continue;
      const mine = items[e.listing.id];
      if (!mine || (e.updated_at || "") > (mine.updated_at || "")) {
        items[e.listing.id] = e;
        added += 1;
      }
    }
    save();
    return added;
  }

  load();
  if (store) {
    // Keep several open tabs in step.
    window.addEventListener("storage", (ev) => {
      if (ev.key === KEY) {
        load();
        listeners.forEach((fn) => fn());
      }
    });
  }

  return {
    persistent: Boolean(store),
    get: find,
    entries: () => Object.values(items),
    setStatus: (h, status) => update(h, { status }),
    setNote: (h, note) => update(h, { note }),
    setResult: (h, result) => update(h, { result }),
    remove: (h) => update(h, { status: null }),
    exportData: () => JSON.stringify({ version: 1, exported_at: new Date().toISOString(), items }, null, 2),
    importData,
    onChange: (fn) => listeners.add(fn),
  };
}
