#!/usr/bin/env python3
"""Generate index.html from the most recent Bambu Tracker JSON and CSV exports in data/."""

import csv
import glob
import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUT_FILE = os.path.join(os.path.dirname(__file__), "index.html")


def latest_file(pattern):
    files = sorted(glob.glob(os.path.join(DATA_DIR, pattern)))
    if not files:
        print(f"Error: no files matching {pattern} found in {DATA_DIR}", file=sys.stderr)
        sys.exit(1)
    return files[-1]


def build_filaments(json_path, csv_path):
    with open(json_path) as f:
        data = json.load(f)

    csv_data = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            csv_data[row["Colour Code"]] = row

    # Build a map from hyphenated slugs (e.g. "pla-matte") to clean names (e.g. "PLA Matte")
    # Only use properly-cased CSV values (not already-slug values) as canonical names
    type_slug_map = {}
    for row in csv_data.values():
        clean = row.get("Product Type", "").strip()
        if clean and clean != clean.lower():
            slug = clean.lower().replace(" ", "-")
            type_slug_map[slug] = clean

    filaments = []
    for code, inv in data["inventory"].items():
        if inv["status"] == "none" and inv["spools"] == 0 and inv["refills"] == 0 and inv.get("partial", 0) == 0:
            continue

        cat = data.get("archive", {}).get(code) or data.get("custom", {}).get(code)
        csv_row = csv_data.get(code)

        name = (csv_row or {}).get("Colour Name") or (cat or {}).get("colourName") or f"Unknown ({code})"
        hex1 = (cat or {}).get("hexColor") or (cat or {}).get("hex") or "#888888"
        hex2 = (cat or {}).get("hexColor2")
        image = (csv_row or {}).get("Image URL") or (cat or {}).get("image") or ""
        product_type = (csv_row or {}).get("Product Type") or ""
        if not product_type and cat and cat.get("typeList"):
            product_type = cat["typeList"][0].get("productType", "")
        if product_type and product_type in type_slug_map:
            product_type = type_slug_map[product_type]

        supplier = (csv_row or {}).get("Supplier") or (cat or {}).get("supplier") or "Bambu Lab"

        url = (csv_row or {}).get("Product URL") or ""
        if not url and cat:
            for t in cat.get("typeList", []):
                url = (t.get("withSpool") or {}).get("url") or (t.get("refill") or {}).get("url") or ""
                if url:
                    break
            if not url:
                url = cat.get("url", "")

        price = None
        if cat and cat.get("typeList"):
            t = cat["typeList"][0]
            for ptype in ["withSpool", "refill"]:
                p = (t.get(ptype) or {}).get("price")
                if p and p != "N/A":
                    price = p
                    break

        filaments.append({
            "code": code,
            "name": name,
            "hex1": hex1,
            "hex2": hex2,
            "image": image,
            "productType": product_type,
            "supplier": supplier,
            "spools": inv["spools"],
            "refills": inv["refills"],
            "partial": inv.get("partial", 0),
            "totalWeight": sum(s.get("weight", 0) for s in inv.get("openSpools", [])),
            "price": price,
            "url": url,
            "notes": inv.get("notes", ""),
            "status": inv["status"],
        })

    return filaments


HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Filament Inventory</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0f1117; --surface: #1a1d27; --surface2: #252833;
    --border: #2e3245; --text: #e4e6ef; --text2: #9499b3;
    --accent: #6c7ee1; --accent-hover: #8290f0;
    --green: #4ade80; --yellow: #fbbf24; --red: #f87171;
  }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }
  .container { max-width: 1400px; margin: 0 auto; padding: 24px; }

  header { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; margin-bottom: 24px; }
  header h1 { font-size: 24px; font-weight: 700; flex-shrink: 0; }
  .header-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin-left: auto; }
  .search-box { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 8px 14px; color: var(--text); font-size: 14px; width: 280px; outline: none; transition: border-color .15s; }
  .search-box:focus { border-color: var(--accent); }
  .search-box::placeholder { color: var(--text2); }
  .view-toggle { display: flex; background: var(--surface); border-radius: 8px; overflow: hidden; border: 1px solid var(--border); }
  .view-btn { background: none; border: none; color: var(--text2); padding: 8px 16px; cursor: pointer; font-size: 14px; transition: all .15s; }
  .view-btn.active { background: var(--accent); color: #fff; }
  .view-btn:hover:not(.active) { color: var(--text); background: var(--surface2); }
  .stats { font-size: 13px; color: var(--text2); }

  .card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
  .card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
    overflow: hidden; transition: border-color .15s, transform .15s;
  }
  .card:hover { border-color: var(--accent); transform: translateY(-2px); }
  .card-top { display: flex; align-items: center; gap: 14px; padding: 16px 16px 12px; }
  .color-swatch {
    width: 48px; height: 48px; border-radius: 10px; flex-shrink: 0;
    border: 2px solid var(--border); position: relative; overflow: hidden;
  }
  .color-swatch.dual .half-left, .color-swatch.dual .half-right {
    position: absolute; top: 0; bottom: 0; width: 50%;
  }
  .color-swatch.dual .half-left { left: 0; }
  .color-swatch.dual .half-right { right: 0; }
  .card-title { font-weight: 600; font-size: 15px; line-height: 1.3; }
  .card-subtitle { font-size: 12px; color: var(--text2); margin-top: 2px; }
  .card-body { padding: 0 16px 16px; }
  .card-stats { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
  .stat-chip {
    font-size: 12px; padding: 3px 10px; border-radius: 20px;
    background: var(--surface2); color: var(--text2); white-space: nowrap;
  }
  .stat-chip.has-stock { background: rgba(74,222,128,.12); color: var(--green); }
  .stat-chip.low-stock { background: rgba(251,191,36,.12); color: var(--yellow); }
  .stat-chip.empty { background: rgba(248,113,113,.08); color: var(--red); }
  .card-buy-link { text-decoration: none; color: var(--accent); background: rgba(108,126,225,.12); }
  .card-img { width: 100%; height: 140px; object-fit: contain; background: #fff; border-radius: 8px; margin-bottom: 10px; }
  .card-type-tag { display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 10px; border-radius: 20px; background: rgba(108,126,225,.18); color: var(--accent); letter-spacing: .3px; text-transform: uppercase; }
  .weight-bar-container { background: var(--surface2); border-radius: 4px; height: 6px; margin-top: 8px; overflow: hidden; }
  .weight-bar { height: 100%; border-radius: 4px; transition: width .3s; }

  .table-wrap { overflow-x: auto; border-radius: 12px; border: 1px solid var(--border); }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th {
    background: var(--surface2); text-align: left; padding: 10px 14px; font-weight: 600;
    font-size: 12px; text-transform: uppercase; letter-spacing: .5px; color: var(--text2);
    cursor: pointer; user-select: none; white-space: nowrap; position: sticky; top: 0; z-index: 1;
  }
  th:hover { color: var(--text); }
  th .sort-arrow { margin-left: 4px; font-size: 10px; opacity: 0; transition: opacity .15s; }
  th.sorted .sort-arrow { opacity: 1; }
  td { padding: 10px 14px; border-top: 1px solid var(--border); vertical-align: middle; }
  tr { background: var(--surface); transition: background .1s; }
  tr:hover { background: var(--surface2); }
  .table-swatch { width: 28px; height: 28px; border-radius: 6px; border: 1px solid var(--border); display: inline-block; vertical-align: middle; position: relative; overflow: hidden; }
  .table-swatch.dual .half-left, .table-swatch.dual .half-right { position: absolute; top: 0; bottom: 0; width: 50%; }
  .table-swatch.dual .half-left { left: 0; }
  .table-swatch.dual .half-right { right: 0; }
  .table-type { font-size: 12px; color: var(--accent); }
  .table-stock { font-weight: 500; }
  .table-stock.in-stock { color: var(--green); }
  .table-stock.partial-stock { color: var(--yellow); }
  .table-stock.no-stock { color: var(--red); }
  td a { color: var(--accent); text-decoration: none; }
  td a:hover { text-decoration: underline; }

  .sort-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; flex-wrap: wrap; }
  .sort-bar label { font-size: 13px; color: var(--text2); white-space: nowrap; }
  .sort-bar select {
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 6px 12px; color: var(--text); font-size: 13px; outline: none; cursor: pointer;
    appearance: none; -webkit-appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg width='10' height='6' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%239499b3'/%3E%3C/svg%3E");
    background-repeat: no-repeat; background-position: right 10px center; padding-right: 28px;
  }
  .sort-bar select:focus { border-color: var(--accent); }
  .sort-dir-btn {
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    padding: 6px 10px; color: var(--text2); font-size: 13px; cursor: pointer;
    transition: all .15s; line-height: 1;
  }
  .sort-dir-btn:hover { color: var(--text); border-color: var(--accent); }

  .type-filters { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
  .type-filter-btn {
    font-size: 12px; font-weight: 600; padding: 5px 14px; border-radius: 20px;
    border: 1px solid var(--border); background: var(--surface); color: var(--text2);
    cursor: pointer; transition: all .15s; text-transform: uppercase; letter-spacing: .3px;
    white-space: nowrap;
  }
  .type-filter-btn:hover { border-color: var(--accent); color: var(--text); }
  .type-filter-btn.active { background: rgba(108,126,225,.18); color: var(--accent); border-color: var(--accent); }

  .hidden { display: none !important; }
  .no-results { text-align: center; padding: 60px 20px; color: var(--text2); font-size: 16px; }

  @media (max-width: 600px) {
    .container { padding: 12px; }
    header { flex-direction: column; align-items: stretch; }
    .header-controls { flex-direction: column; }
    .search-box { width: 100%; }
    .card-grid { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Filament Inventory</h1>
    <div class="header-controls">
      <input type="text" class="search-box" id="search" placeholder="Search filaments..." autocomplete="off">
      <div class="view-toggle">
        <button class="view-btn active" data-view="cards">Cards</button>
        <button class="view-btn" data-view="table">Table</button>
      </div>
    </div>
  </header>
  <div class="stats" id="stats"></div>
  <div class="type-filters" id="type-filters"></div>
  <div id="card-sort-bar" class="sort-bar" style="margin-top:16px">
    <label for="card-sort-select">Sort by</label>
    <select id="card-sort-select">
      <option value="name">Name</option>
      <option value="code">Code</option>
      <option value="productType">Type</option>
      <option value="supplier">Supplier</option>
      <option value="spools">Spools</option>
      <option value="refills">Refills</option>
      <option value="partial">Partial (g)</option>
      <option value="totalWeight">Open Weight (g)</option>
      <option value="price">Price</option>
    </select>
    <button class="sort-dir-btn" id="card-sort-dir" title="Toggle sort direction">&#9650;</button>
  </div>
  <div id="card-view" class="card-grid"></div>
  <div id="table-view" class="hidden" style="margin-top:16px">
    <div class="table-wrap">
      <table>
        <thead id="table-head"></thead>
        <tbody id="table-body"></tbody>
      </table>
    </div>
  </div>
  <div id="no-results" class="no-results hidden">No filaments match your search.</div>
</div>
<script>
const filaments = %%FILAMENTS_JSON%%;

filaments.sort((a, b) => a.name.localeCompare(b.name));

const types = [...new Set(filaments.map(f => f.productType).filter(Boolean))].sort();
let selectedType = '';

(function buildTypeFilters() {
  const container = document.getElementById('type-filters');
  const allBtn = document.createElement('button');
  allBtn.className = 'type-filter-btn active';
  allBtn.textContent = 'All';
  allBtn.dataset.type = '';
  container.appendChild(allBtn);
  types.forEach(t => {
    const btn = document.createElement('button');
    btn.className = 'type-filter-btn';
    btn.textContent = t;
    btn.dataset.type = t;
    container.appendChild(btn);
  });
  container.addEventListener('click', e => {
    const btn = e.target.closest('.type-filter-btn');
    if (!btn) return;
    const val = btn.dataset.type;
    selectedType = (val === selectedType) ? '' : val;
    container.querySelectorAll('.type-filter-btn').forEach(b => b.classList.toggle('active', b.dataset.type === selectedType));
    applyFilter();
  });
})();

function esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

function swatchHTML(hex1, hex2, cls) {
  if (hex2) return `<div class="${cls} dual"><div class="half-left" style="background:${hex1}"></div><div class="half-right" style="background:${hex2}"></div></div>`;
  return `<div class="${cls}" style="background:${hex1}"></div>`;
}

function stockClass(f) {
  if (f.spools + f.refills > 0) return 'has-stock';
  if (f.partial > 0) return 'low-stock';
  return 'empty';
}

function stockLabel(f) {
  const parts = [];
  if (f.spools > 0) parts.push(`${f.spools} spool${f.spools > 1 ? 's' : ''}`);
  if (f.refills > 0) parts.push(`${f.refills} refill${f.refills > 1 ? 's' : ''}`);
  if (f.partial > 0) parts.push(`${f.partial}g partial`);
  return parts.length ? parts.join(' + ') : 'Empty';
}

function weightPct(f) {
  if (f.totalWeight <= 0) return 0;
  const full = Math.max(f.spools + f.refills, 1) * 1000;
  return Math.min(100, Math.round((f.totalWeight / full) * 100));
}

function weightBarColor(pct) {
  if (pct > 50) return 'var(--green)';
  if (pct > 20) return 'var(--yellow)';
  return 'var(--red)';
}

function renderCards(list) {
  const grid = document.getElementById('card-view');
  if (!list.length) { grid.innerHTML = ''; return; }
  grid.innerHTML = list.map(f => {
    const sc = stockClass(f);
    const pct = weightPct(f);
    const imgTag = f.image ? `<img class="card-img" src="${esc(f.image)}" alt="${esc(f.name)}" loading="lazy" onerror="this.style.display='none'">` : '';
    const typeTag = f.productType ? `<span class="card-type-tag">${esc(f.productType)}</span>` : '';
    const priceHtml = f.price ? `<span class="stat-chip">$${f.price}</span>` : '';
    const buyHtml = f.url ? `<a href="${esc(f.url)}" target="_blank" rel="noopener" class="stat-chip card-buy-link">Info/Buy</a>` : '';
    return `<div class="card">
      <div class="card-top">
        ${swatchHTML(f.hex1, f.hex2, 'color-swatch')}
        <div>
          <div class="card-title">${esc(f.name)}</div>
          <div class="card-subtitle">${esc(f.code)} &middot; ${esc(f.supplier)}</div>
          ${typeTag ? `<div style="margin-top:6px">${typeTag}</div>` : ''}
        </div>
      </div>
      <div class="card-body">
        ${imgTag}
        <div class="card-stats">
          <span class="stat-chip ${sc}">${stockLabel(f)}</span>
          ${priceHtml}
          ${buyHtml}
        </div>
        <div class="weight-bar-container">
          <div class="weight-bar" style="width:${pct}%;background:${weightBarColor(pct)}"></div>
        </div>
      </div>
    </div>`;
  }).join('');
}

const columns = [
  { key: 'color', label: 'Color', sort: null },
  { key: 'name', label: 'Name', sort: (a, b) => a.name.localeCompare(b.name) },
  { key: 'code', label: 'Code', sort: (a, b) => a.code.localeCompare(b.code) },
  { key: 'productType', label: 'Type', sort: (a, b) => a.productType.localeCompare(b.productType) },
  { key: 'supplier', label: 'Supplier', sort: (a, b) => a.supplier.localeCompare(b.supplier) },
  { key: 'spools', label: 'Spools', sort: (a, b) => b.spools - a.spools },
  { key: 'refills', label: 'Refills', sort: (a, b) => b.refills - a.refills },
  { key: 'partial', label: 'Partial (g)', sort: (a, b) => b.partial - a.partial },
  { key: 'totalWeight', label: 'Open Weight (g)', sort: (a, b) => b.totalWeight - a.totalWeight },
  { key: 'price', label: 'Price', sort: (a, b) => (b.price||0) - (a.price||0) },
  { key: 'link', label: 'Info/Buy', sort: null },
];

let sortCol = 'name';
let sortDir = 1;

function renderTableHead() {
  document.getElementById('table-head').innerHTML = '<tr>' + columns.map(c => {
    const sorted = sortCol === c.key;
    const arrow = sorted ? (sortDir === 1 ? '&#9650;' : '&#9660;') : '&#9650;';
    const cls = sorted ? ' class="sorted"' : '';
    const click = c.sort ? ` data-sort="${c.key}"` : '';
    return `<th${cls}${click}>${c.label}${c.sort ? `<span class="sort-arrow">${arrow}</span>` : ''}</th>`;
  }).join('') + '</tr>';
}

function renderTableBody(list) {
  const tbody = document.getElementById('table-body');
  if (!list.length) { tbody.innerHTML = ''; return; }
  tbody.innerHTML = list.map(f => {
    const sc = (f.spools + f.refills) > 0 ? 'in-stock' : f.partial > 0 ? 'partial-stock' : 'no-stock';
    const link = f.url ? `<a href="${esc(f.url)}" target="_blank" rel="noopener">Info/Buy</a>` : '';
    return `<tr>
      <td>${swatchHTML(f.hex1, f.hex2, 'table-swatch')}</td>
      <td><strong>${esc(f.name)}</strong></td>
      <td>${esc(f.code)}</td>
      <td class="table-type">${esc(f.productType)}</td>
      <td>${esc(f.supplier)}</td>
      <td class="table-stock ${sc}">${f.spools}</td>
      <td class="table-stock ${sc}">${f.refills}</td>
      <td>${f.partial || '\u2014'}</td>
      <td>${f.totalWeight || '\u2014'}</td>
      <td>${f.price ? '$' + f.price : '\u2014'}</td>
      <td>${link}</td>
    </tr>`;
  }).join('');
}

let currentView = 'cards';
let filtered = [...filaments];

function applyFilter() {
  const q = document.getElementById('search').value.toLowerCase().trim();
  filtered = filaments.filter(f => {
    if (selectedType && f.productType !== selectedType) return false;
    if (!q) return true;
    return f.name.toLowerCase().includes(q)
      || f.code.toLowerCase().includes(q)
      || f.productType.toLowerCase().includes(q)
      || f.supplier.toLowerCase().includes(q)
      || (f.notes && f.notes.toLowerCase().includes(q));
  });
  applySort();
}

function applySort() {
  const col = columns.find(c => c.key === sortCol);
  if (col && col.sort) filtered.sort((a, b) => sortDir * col.sort(a, b));
  render();
}

function render() {
  const noRes = document.getElementById('no-results');
  const cardV = document.getElementById('card-view');
  const tableV = document.getElementById('table-view');

  const sortBar = document.getElementById('card-sort-bar');
  if (!filtered.length) {
    noRes.classList.remove('hidden');
    cardV.classList.add('hidden');
    tableV.classList.add('hidden');
    sortBar.classList.add('hidden');
  } else {
    noRes.classList.add('hidden');
    if (currentView === 'cards') {
      cardV.classList.remove('hidden');
      tableV.classList.add('hidden');
      sortBar.classList.remove('hidden');
      renderCards(filtered);
    } else {
      cardV.classList.add('hidden');
      tableV.classList.remove('hidden');
      sortBar.classList.add('hidden');
      renderTableHead();
      renderTableBody(filtered);
    }
  }
  document.getElementById('stats').textContent = `Showing ${filtered.length} of ${filaments.length} filaments`;
}

document.getElementById('search').addEventListener('input', applyFilter);

document.querySelectorAll('.view-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentView = btn.dataset.view;
    render();
  });
});

document.getElementById('table-head').addEventListener('click', e => {
  const th = e.target.closest('th[data-sort]');
  if (!th) return;
  const key = th.dataset.sort;
  if (sortCol === key) sortDir *= -1;
  else { sortCol = key; sortDir = 1; }
  syncSortControls();
  applySort();
});

const cardSortSelect = document.getElementById('card-sort-select');
const cardSortDirBtn = document.getElementById('card-sort-dir');

cardSortSelect.addEventListener('change', () => {
  sortCol = cardSortSelect.value;
  sortDir = 1;
  syncSortControls();
  applySort();
});

cardSortDirBtn.addEventListener('click', () => {
  sortDir *= -1;
  syncSortControls();
  applySort();
});

function syncSortControls() {
  cardSortSelect.value = sortCol;
  cardSortDirBtn.innerHTML = sortDir === 1 ? '&#9650;' : '&#9660;';
}

render();
</script>
</body>
</html>'''


def main():
    json_path = latest_file("*.json")
    csv_path = latest_file("*.csv")
    print(f"Using JSON: {os.path.basename(json_path)}")
    print(f"Using CSV:  {os.path.basename(csv_path)}")

    filaments = build_filaments(json_path, csv_path)
    print(f"Built {len(filaments)} filaments")

    filaments_json = json.dumps(filaments, separators=(",", ":"))
    html = HTML_TEMPLATE.replace("%%FILAMENTS_JSON%%", filaments_json)

    with open(OUT_FILE, "w") as f:
        f.write(html)
    print(f"Wrote {OUT_FILE}")


if __name__ == "__main__":
    main()
