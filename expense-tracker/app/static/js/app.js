/* =========================================================
   Expense & GST Tracker — Single-Page App
   ========================================================= */

// ---- API client -------------------------------------------------
const api = {
  async req(method, url, body) {
    const opts = { method, headers: {} };
    if (body instanceof FormData) {
      opts.body = body;
    } else if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) return res.json();
    return res.text();
  },
  get:    (url)       => api.req("GET", url),
  post:   (url, body) => api.req("POST", url, body),
  patch:  (url, body) => api.req("PATCH", url, body),
  put:    (url, body) => api.req("PUT", url, body),
  delete: (url)       => api.req("DELETE", url),
};

// ---- Toast ------------------------------------------------------
function toast(msg, type = "info", duration = 3500) {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById("toast-container").appendChild(el);
  setTimeout(() => el.remove(), duration);
}

// ---- Formatting -------------------------------------------------
const fmt = {
  currency: (v, sym = "£") => `${v < 0 ? "-" : ""}${sym}${Math.abs(+v).toFixed(2)}`,
  date: (s) => s ? new Date(s + "T00:00:00").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }) : "—",
  pct: (v) => `${(+v * 100).toFixed(0)}%`,
};

function amountCell(v) {
  const n = +v;
  const cls = n < 0 ? "amount-neg" : "amount-pos";
  return `<span class="${cls}">${fmt.currency(n, currSym())}</span>`;
}

function statusBadge(s) {
  const map = { auto: "badge-auto", manual: "badge-manual", pending: "badge-pending", ignored: "badge-ignored" };
  return `<span class="badge ${map[s] || ""}">${s}</span>`;
}

function receiptLabel(count) {
  return count > 0 ? `📎 ${count}` : "📎 Attach";
}

function colorDot(color) {
  return `<span class="color-dot" style="background:${color || "#adb5bd"}"></span>`;
}

// ---- State ------------------------------------------------------
let state = { categories: [], settings: {}, pendingCount: 0, chart: null };

async function refreshMeta() {
  const [cats, settings, summary] = await Promise.all([
    api.get("/api/categories"),
    api.get("/api/settings"),
    api.get("/api/transactions/summary"),
  ]);
  state.categories = cats;
  state.settings = Object.fromEntries(settings.map(s => [s.key, s.value]));
  state.pendingCount = summary.pending_reconciliation || 0;

  const badge = document.getElementById("pending-badge");
  if (state.pendingCount > 0) {
    badge.textContent = state.pendingCount;
    badge.style.display = "inline-flex";
  } else {
    badge.style.display = "none";
  }
}

function currSym() {
  const map = { GBP: "£", EUR: "€", NZD: "NZ$", AUD: "A$", USD: "US$" };
  return map[state.settings.default_currency] || "$";
}

// ---- Router -----------------------------------------------------
const PAGES = {
  dashboard:    { title: "Dashboard",         render: renderDashboard },
  upload:       { title: "Upload Statement",  render: renderUpload },
  reconcile:    { title: "Reconcile",         render: renderReconcile },
  transactions: { title: "Transactions",      render: renderTransactions },
  categories:   { title: "Categories",        render: renderCategories },
  reports:      { title: "Reports",           render: renderReports },
  settings:     { title: "Settings",          render: renderSettings },
};

async function navigate(hash) {
  const page = (hash || "").replace(/^#?\//, "") || "dashboard";
  const def = PAGES[page] || PAGES.dashboard;

  document.getElementById("page-title").textContent = def.title;
  document.getElementById("topbar-actions").innerHTML = "";

  // Update nav links
  document.querySelectorAll("#nav a").forEach(a => {
    a.classList.toggle("active", a.dataset.page === page);
  });

  if (state.chart) { state.chart.destroy(); state.chart = null; }

  const content = document.getElementById("content");
  content.innerHTML = '<div class="empty-state"><div class="icon">⏳</div><p>Loading…</p></div>';

  try {
    await def.render();
  } catch (e) {
    content.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><p>Error: ${e.message}</p></div>`;
    console.error(e);
  }
}

// ---- Dashboard --------------------------------------------------
async function renderDashboard() {
  const [summary, report] = await Promise.all([
    api.get("/api/transactions/summary"),
    api.get("/api/reports/summary?preset=this_month"),
  ]);

  const sym = currSym();
  const content = document.getElementById("content");
  content.innerHTML = `
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="label">Total Expenses (this month)</div>
        <div class="value expense">${fmt.currency(summary.total_expenses, sym)}</div>
      </div>
      <div class="kpi-card">
        <div class="label">GST Claimable (all time)</div>
        <div class="value gst">${fmt.currency(summary.total_gst_claimable, sym)}</div>
      </div>
      <div class="kpi-card">
        <div class="label">Pending Reconciliation</div>
        <div class="value pending">${summary.pending_reconciliation}</div>
      </div>
      <div class="kpi-card">
        <div class="label">Total Transactions</div>
        <div class="value">${summary.total_transactions}</div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header">&#x1F4CA; Spend by Category (this month)</div>
        <div class="card-body">
          <div class="chart-wrap"><canvas id="cat-chart"></canvas></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header">&#x1F4CB; Category Breakdown</div>
        <div class="card-body" style="padding:0">
          <div class="table-wrap">
            <table>
              <thead><tr><th>Category</th><th>Amount</th><th>GST</th></tr></thead>
              <tbody id="cat-table-body"></tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `;

  // Category doughnut chart
  const cats = report.by_category.filter(c => !c.is_income).slice(0, 10);
  const ctx = document.getElementById("cat-chart").getContext("2d");
  state.chart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: cats.map(c => c.category),
      datasets: [{
        data: cats.map(c => c.total),
        backgroundColor: cats.map(c => c.color || "#adb5bd"),
        borderWidth: 2,
        borderColor: "#fff",
      }],
    },
    options: {
      plugins: { legend: { position: "bottom", labels: { boxWidth: 12, font: { size: 11 } } } },
      cutout: "60%",
    },
  });

  const tbody = document.getElementById("cat-table-body");
  if (cats.length === 0) {
    tbody.innerHTML = '<tr><td colspan="3" class="text-muted" style="text-align:center;padding:20px">No data yet</td></tr>';
  } else {
    tbody.innerHTML = cats.map(c => `
      <tr>
        <td>${colorDot(c.color)} ${c.category}</td>
        <td>${fmt.currency(c.total, sym)}</td>
        <td class="gst">${c.gst_claimable > 0 ? fmt.currency(c.gst_claimable, sym) : "—"}</td>
      </tr>
    `).join("");
  }
}

// ---- Upload -----------------------------------------------------
function renderUpload() {
  const content = document.getElementById("content");
  content.innerHTML = `
    <div style="max-width:600px;margin:0 auto">
      <div class="card">
        <div class="card-header">&#x1F4C4; Upload Bank Statement CSV</div>
        <div class="card-body">
          <div id="drop-zone">
            <div class="upload-icon">&#x1F4C1;</div>
            <p><strong>Drop your CSV file here</strong> or click to browse</p>
            <p class="hint">Supports ANZ NZ, ASB, BNZ, Kiwibank, Westpac NZ &amp; generic CSV exports</p>
            <input type="file" id="file-input" accept=".csv" style="display:none">
          </div>
          <div id="upload-result" style="margin-top:16px"></div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">&#x1F4CB; Previous Uploads</div>
        <div class="card-body" style="padding:0">
          <div class="table-wrap">
            <table>
              <thead><tr><th>File</th><th>Format</th><th>Imported</th><th>Dupes</th><th>Date</th><th></th></tr></thead>
              <tbody id="uploads-table"></tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `;

  loadUploadsTable();

  const zone = document.getElementById("drop-zone");
  const input = document.getElementById("file-input");

  zone.addEventListener("click", () => input.click());
  input.addEventListener("change", () => { if (input.files[0]) doUpload(input.files[0]); });
  zone.addEventListener("dragover", e => { e.preventDefault(); zone.classList.add("drag-over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
  zone.addEventListener("drop", e => {
    e.preventDefault();
    zone.classList.remove("drag-over");
    if (e.dataTransfer.files[0]) doUpload(e.dataTransfer.files[0]);
  });
}

async function doUpload(file) {
  const result = document.getElementById("upload-result");
  result.innerHTML = '<p class="text-muted">Uploading…</p>';
  const fd = new FormData();
  fd.append("file", file);
  try {
    const data = await api.post("/api/uploads", fd);
    result.innerHTML = `
      <div style="background:#d1fae5;border:1px solid #6ee7b7;border-radius:8px;padding:14px 18px">
        <strong>✅ Upload successful</strong><br>
        <span class="text-sm">Format detected: <strong>${data.bank_format}</strong> &nbsp;|&nbsp;
        Imported: <strong>${data.imported_count}</strong> &nbsp;|&nbsp;
        Duplicates skipped: <strong>${data.duplicate_count}</strong></span>
        ${data.imported_count > 0 ? '<br><a href="#/reconcile" style="font-size:.85rem;color:#1d4ed8">→ Reconcile pending transactions</a>' : ""}
      </div>
    `;
    loadUploadsTable();
    refreshMeta();
    toast(`Imported ${data.imported_count} transactions`, "success");
  } catch (e) {
    result.innerHTML = `<div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:8px;padding:14px 18px">❌ ${e.message}</div>`;
    toast(e.message, "error");
  }
}

async function loadUploadsTable() {
  const tbody = document.getElementById("uploads-table");
  if (!tbody) return;
  const uploads = await api.get("/api/uploads");
  if (uploads.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No uploads yet</td></tr>';
    return;
  }
  tbody.innerHTML = uploads.map(u => `
    <tr>
      <td>${u.original_filename}</td>
      <td><code>${u.bank_format}</code></td>
      <td>${u.imported_count}</td>
      <td>${u.duplicate_count}</td>
      <td class="text-muted text-sm">${fmt.date(u.uploaded_at.substring(0,10))}</td>
      <td>
        <button class="btn btn-sm btn-danger" onclick="deleteUpload(${u.id})">Delete</button>
      </td>
    </tr>
  `).join("");
}

window.deleteUpload = async function(id) {
  if (!confirm("Delete this upload and all its transactions?")) return;
  try {
    await api.delete(`/api/uploads/${id}`);
    toast("Upload deleted", "success");
    loadUploadsTable();
    refreshMeta();
  } catch (e) { toast(e.message, "error"); }
};

// ---- Reconcile --------------------------------------------------
let reconcilePage = 1;
let reconcileTotal = 0;

async function renderReconcile() {
  const content = document.getElementById("content");
  content.innerHTML = `
    <div class="card">
      <div class="card-header">
        ✅ Pending Reconciliation
        <span id="recon-count" class="badge badge-pending" style="margin-left:6px"></span>
        <div class="ml-auto flex gap-2">
          <button class="btn btn-sm btn-secondary" id="btn-rerun">&#x1F504; Re-run Auto-categorise</button>
        </div>
      </div>
      <div class="card-body" style="padding:0">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Date</th><th>Description</th><th>Amount</th>
                <th>Category</th><th>GST?</th><th>Notes</th><th>Receipt</th><th></th>
              </tr>
            </thead>
            <tbody id="recon-tbody"></tbody>
          </table>
        </div>
        <div class="pagination" style="padding:12px 16px">
          <button class="btn btn-sm btn-secondary" id="btn-prev-p">‹ Prev</button>
          <span id="recon-pager" class="text-sm text-muted"></span>
          <button class="btn btn-sm btn-secondary" id="btn-next-p">Next ›</button>
        </div>
      </div>
    </div>
  `;

  document.getElementById("btn-rerun").addEventListener("click", async () => {
    try {
      const r = await api.post("/api/transactions/bulk-categorize");
      toast(`Auto-categorised ${r.updated} transactions`, "success");
      reconcilePage = 1;
      loadReconcileData();
      refreshMeta();
    } catch (e) { toast(e.message, "error"); }
  });

  document.getElementById("btn-prev-p").addEventListener("click", () => {
    if (reconcilePage > 1) { reconcilePage--; loadReconcileData(); }
  });
  document.getElementById("btn-next-p").addEventListener("click", () => {
    if (reconcilePage * 25 < reconcileTotal) { reconcilePage++; loadReconcileData(); }
  });

  loadReconcileData();
}

async function loadReconcileData() {
  const data = await api.get(`/api/transactions/pending?page=${reconcilePage}&page_size=25`);
  reconcileTotal = data.total;

  const badge = document.getElementById("recon-count");
  if (badge) badge.textContent = data.total;

  const pager = document.getElementById("recon-pager");
  if (pager) {
    const from = (reconcilePage - 1) * 25 + 1;
    const to = Math.min(reconcilePage * 25, data.total);
    pager.textContent = data.total === 0 ? "No pending items" : `${from}–${to} of ${data.total}`;
  }

  const tbody = document.getElementById("recon-tbody");
  if (!tbody) return;

  if (data.items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="8" class="empty-state"><div class="icon">🎉</div>All transactions reconciled!</td></tr>';
    return;
  }

  const catOptions = state.categories
    .map(c => `<option value="${c.id}">${c.name}</option>`)
    .join("");

  tbody.innerHTML = data.items.map(tx => `
    <tr id="row-${tx.id}">
      <td class="text-sm">${fmt.date(tx.date)}</td>
      <td>
        <div style="max-width:260px">
          <div>${tx.description}</div>
          ${tx.merchant ? `<div class="text-muted text-sm">${tx.merchant}</div>` : ""}
        </div>
      </td>
      <td>${amountCell(tx.amount)}</td>
      <td>
        <select class="form-control" id="cat-${tx.id}" style="min-width:160px">
          <option value="">— Choose —</option>
          ${catOptions}
        </select>
      </td>
      <td>
        <label style="display:flex;align-items:center;gap:6px;font-size:.85rem;cursor:pointer">
          <input type="checkbox" id="gst-${tx.id}" ${tx.gst_claimable ? "checked" : ""}> Claimable
        </label>
      </td>
      <td>
        <input type="text" class="form-control" id="notes-${tx.id}" placeholder="Notes…" value="${tx.notes || ""}" style="min-width:120px">
      </td>
      <td>
        <button class="btn btn-sm btn-secondary" data-receipt-btn="${tx.id}" onclick="openReceipts(${tx.id})">${receiptLabel(tx.receipt_count)}</button>
      </td>
      <td>
        <div class="flex gap-2">
          <button class="btn btn-sm btn-success" onclick="saveRecon(${tx.id})">Save</button>
          <button class="btn btn-sm btn-secondary" onclick="ignoreRecon(${tx.id})">Ignore</button>
        </div>
      </td>
    </tr>
  `).join("");
}

window.saveRecon = async function(id) {
  const catEl = document.getElementById(`cat-${id}`);
  const gstEl = document.getElementById(`gst-${id}`);
  const notesEl = document.getElementById(`notes-${id}`);

  const catId = catEl.value ? parseInt(catEl.value) : null;
  if (!catId) { toast("Please select a category", "error"); return; }

  try {
    await api.patch(`/api/transactions/${id}`, {
      category_id: catId,
      gst_claimable: gstEl.checked,
      notes: notesEl.value || null,
    });
    document.getElementById(`row-${id}`)?.remove();
    toast("Saved", "success");
    reconcileTotal--;
    refreshMeta();
    const badge = document.getElementById("recon-count");
    if (badge) badge.textContent = reconcileTotal;
    if (document.querySelectorAll("#recon-tbody tr").length === 0) {
      loadReconcileData();
    }
  } catch (e) { toast(e.message, "error"); }
};

window.ignoreRecon = async function(id) {
  try {
    await api.patch(`/api/transactions/${id}`, { reconciliation_status: "ignored" });
    document.getElementById(`row-${id}`)?.remove();
    reconcileTotal--;
    refreshMeta();
  } catch (e) { toast(e.message, "error"); }
};

// ---- Transactions -----------------------------------------------
let txPage = 1;
let txTotal = 0;
let txFilters = {};

async function renderTransactions() {
  const content = document.getElementById("content");
  const catOptions = state.categories.map(c => `<option value="${c.id}">${c.name}</option>`).join("");

  content.innerHTML = `
    <div class="card">
      <div class="card-header">
        &#x1F4B3; All Transactions
        <div class="ml-auto">
          <button class="btn btn-sm btn-secondary" id="btn-export-tx">&#x1F4E5; Export CSV</button>
        </div>
      </div>
      <div class="card-body">
        <div class="filter-row">
          <div class="form-group">
            <label class="form-label">From</label>
            <input type="date" class="form-control" id="tx-from" style="width:150px">
          </div>
          <div class="form-group">
            <label class="form-label">To</label>
            <input type="date" class="form-control" id="tx-to" style="width:150px">
          </div>
          <div class="form-group">
            <label class="form-label">Category</label>
            <select class="form-control" id="tx-cat" style="width:180px">
              <option value="">All categories</option>
              ${catOptions}
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Status</label>
            <select class="form-control" id="tx-status" style="width:130px">
              <option value="">All</option>
              <option value="auto">Auto</option>
              <option value="manual">Manual</option>
              <option value="pending">Pending</option>
              <option value="ignored">Ignored</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">Search</label>
            <input type="text" class="form-control" id="tx-search" placeholder="Description…" style="width:180px">
          </div>
          <button class="btn btn-primary" id="btn-filter">Filter</button>
        </div>
      </div>
      <div style="padding:0">
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>Date</th><th>Description</th><th>Amount</th><th>Category</th><th>GST</th><th>Status</th><th>Notes</th><th>Receipt</th><th></th></tr>
            </thead>
            <tbody id="tx-tbody"></tbody>
          </table>
        </div>
        <div class="pagination" style="padding:12px 16px">
          <span id="tx-pager" class="text-sm text-muted ml-auto"></span>
          <button class="btn btn-sm btn-secondary" id="tx-prev">‹</button>
          <button class="btn btn-sm btn-secondary" id="tx-next">›</button>
        </div>
      </div>
    </div>
  `;

  document.getElementById("btn-filter").addEventListener("click", () => {
    txFilters = {
      from_date: document.getElementById("tx-from").value || undefined,
      to_date:   document.getElementById("tx-to").value || undefined,
      category_id: document.getElementById("tx-cat").value || undefined,
      status:    document.getElementById("tx-status").value || undefined,
      search:    document.getElementById("tx-search").value || undefined,
    };
    txPage = 1;
    loadTxData();
  });

  document.getElementById("tx-prev").addEventListener("click", () => {
    if (txPage > 1) { txPage--; loadTxData(); }
  });
  document.getElementById("tx-next").addEventListener("click", () => {
    if (txPage * 50 < txTotal) { txPage++; loadTxData(); }
  });

  document.getElementById("btn-export-tx").addEventListener("click", () => {
    const p = new URLSearchParams();
    if (txFilters.from_date) p.set("from_date", txFilters.from_date);
    if (txFilters.to_date) p.set("to_date", txFilters.to_date);
    if (!txFilters.from_date && !txFilters.to_date) p.set("preset", "6m");
    window.location.href = `/api/reports/export?${p}`;
  });

  loadTxData();
}

async function loadTxData() {
  const params = new URLSearchParams({ page: txPage, page_size: 50 });
  if (txFilters.from_date) params.set("from_date", txFilters.from_date);
  if (txFilters.to_date)   params.set("to_date",   txFilters.to_date);
  if (txFilters.category_id) params.set("category_id", txFilters.category_id);
  if (txFilters.status)    params.set("status",    txFilters.status);
  if (txFilters.search)    params.set("search",    txFilters.search);

  const data = await api.get(`/api/transactions?${params}`);
  txTotal = data.total;

  const pager = document.getElementById("tx-pager");
  if (pager) {
    const from = (txPage - 1) * 50 + 1;
    const to = Math.min(txPage * 50, data.total);
    pager.textContent = data.total === 0 ? "No results" : `${from}–${to} of ${data.total}`;
  }

  const tbody = document.getElementById("tx-tbody");
  if (!tbody) return;

  if (data.items.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="empty-state">No transactions found</td></tr>';
    return;
  }

  const sym = currSym();
  tbody.innerHTML = data.items.map(tx => `
    <tr>
      <td class="text-sm">${fmt.date(tx.date)}</td>
      <td>
        <div>${tx.description}</div>
        ${tx.merchant ? `<div class="text-muted text-sm">${tx.merchant}</div>` : ""}
      </td>
      <td>${amountCell(tx.amount)}</td>
      <td>
        ${tx.category_name
          ? `${colorDot(state.categories.find(c=>c.id===tx.category_id)?.color)} ${tx.category_name}`
          : '<span class="text-muted">—</span>'}
      </td>
      <td class="text-sm">${tx.gst_claimable ? fmt.currency(tx.gst_amount, sym) : "—"}</td>
      <td>${statusBadge(tx.reconciliation_status)}</td>
      <td class="text-muted text-sm">${tx.notes || ""}</td>
      <td>
        <button class="btn btn-sm btn-secondary" data-receipt-btn="${tx.id}" onclick="openReceipts(${tx.id})">${receiptLabel(tx.receipt_count)}</button>
      </td>
      <td>
        <button class="btn btn-sm btn-secondary" onclick="editTransaction(${tx.id})">Edit</button>
      </td>
    </tr>
  `).join("");
}

window.editTransaction = async function(id) {
  const tx = await api.get(`/api/transactions/${id}`);
  const catOptions = state.categories
    .map(c => `<option value="${c.id}" ${c.id === tx.category_id ? "selected" : ""}>${c.name}</option>`)
    .join("");

  createModal("Edit Transaction", `
    <div class="text-sm text-muted" style="margin-bottom:12px">
      ${fmt.date(tx.date)} &middot; ${tx.description}${tx.merchant ? " &middot; " + tx.merchant : ""} &middot; ${amountCell(tx.amount)}
    </div>
    <div class="form-group">
      <label class="form-label">Category</label>
      <select class="form-control" id="e-cat">
        <option value="">— None —</option>
        ${catOptions}
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">Reconciliation status</label>
      <select class="form-control" id="e-status">
        <option value="pending" ${tx.reconciliation_status === "pending" ? "selected" : ""}>Pending (send back to Reconcile)</option>
        <option value="manual" ${tx.reconciliation_status === "manual" ? "selected" : ""}>Manual</option>
        <option value="auto" ${tx.reconciliation_status === "auto" ? "selected" : ""}>Auto</option>
        <option value="ignored" ${tx.reconciliation_status === "ignored" ? "selected" : ""}>Ignored</option>
      </select>
    </div>
    <div class="form-group">
      <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
        <input type="checkbox" id="e-gst" ${tx.gst_claimable ? "checked" : ""}> GST claimable
      </label>
    </div>
    <div class="form-group">
      <label class="form-label">Notes</label>
      <input class="form-control" id="e-notes" value="${(tx.notes || "").replace(/"/g, "&quot;")}">
    </div>
  `, async () => {
    const catVal = document.getElementById("e-cat").value;
    const newCatId = catVal ? parseInt(catVal) : null;
    const body = {
      gst_claimable: document.getElementById("e-gst").checked,
      reconciliation_status: document.getElementById("e-status").value,
      notes: document.getElementById("e-notes").value || null,
    };
    if (newCatId !== null && newCatId !== tx.category_id) {
      body.category_id = newCatId;
    }
    try {
      await api.patch(`/api/transactions/${id}`, body);
      toast("Transaction updated", "success");
      closeModal();
      loadTxData();
      refreshMeta();
    } catch (e) { toast(e.message, "error"); }
  });
};

// ---- Categories -------------------------------------------------
async function renderCategories() {
  await refreshMeta();
  const content = document.getElementById("content");

  const actionsEl = document.getElementById("topbar-actions");
  actionsEl.innerHTML = `<button class="btn btn-primary btn-sm" id="btn-add-cat">+ Add Category</button>`;
  document.getElementById("btn-add-cat").addEventListener("click", () => showCategoryModal(null));

  content.innerHTML = `
    <div class="card">
      <div class="card-body" style="padding:0">
        <div class="table-wrap">
          <table>
            <thead><tr><th>Category</th><th>GST Claimable</th><th>Type</th><th>Rules</th><th>Transactions</th><th></th></tr></thead>
            <tbody id="cat-tbody"></tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  renderCatTable();
}

async function renderCatTable() {
  const cats = await api.get("/api/categories");
  state.categories = cats;
  const tbody = document.getElementById("cat-tbody");
  if (!tbody) return;

  tbody.innerHTML = cats.map(c => `
    <tr>
      <td>${colorDot(c.color)} <strong>${c.name}</strong>${c.description ? `<br><span class="text-muted text-sm">${c.description}</span>` : ""}</td>
      <td>${c.gst_claimable ? "✅ Yes" : "❌ No"}</td>
      <td>${c.is_income ? "Income" : "Expense"}</td>
      <td>
        <button class="btn btn-sm btn-secondary" onclick="showRulesModal(${c.id}, '${c.name.replace(/'/g,"\\'")}')">
          ${c.rules.length} rules
        </button>
      </td>
      <td>${c.transaction_count}</td>
      <td>
        <div class="flex gap-2">
          <button class="btn btn-sm btn-secondary" onclick="showCategoryModal(${c.id})">Edit</button>
          <button class="btn btn-sm btn-danger" onclick="deleteCategory(${c.id}, ${c.transaction_count})">Delete</button>
        </div>
      </td>
    </tr>
  `).join("");
}

window.showCategoryModal = function(catId) {
  const cat = catId ? state.categories.find(c => c.id === catId) : null;
  const title = cat ? "Edit Category" : "New Category";
  const modal = createModal(title, `
    <div class="form-group">
      <label class="form-label">Name *</label>
      <input class="form-control" id="m-name" value="${cat?.name || ""}">
    </div>
    <div class="form-group">
      <label class="form-label">Description</label>
      <input class="form-control" id="m-desc" value="${cat?.description || ""}">
    </div>
    <div class="grid-2">
      <div class="form-group">
        <label class="form-label">Color</label>
        <input type="color" class="form-control" id="m-color" value="${cat?.color || "#6c757d"}" style="height:38px;cursor:pointer">
      </div>
      <div class="form-group">
        <label class="form-label">Type</label>
        <select class="form-control" id="m-type">
          <option value="expense" ${!cat?.is_income ? "selected" : ""}>Expense</option>
          <option value="income"  ${cat?.is_income  ? "selected" : ""}>Income</option>
        </select>
      </div>
    </div>
    <div class="form-group">
      <label style="display:flex;align-items:center;gap:8px;cursor:pointer">
        <input type="checkbox" id="m-gst" ${cat?.gst_claimable !== false ? "checked" : ""}> GST claimable on this category
      </label>
    </div>
  `, async () => {
    const body = {
      name: document.getElementById("m-name").value.trim(),
      description: document.getElementById("m-desc").value.trim() || null,
      color: document.getElementById("m-color").value,
      is_income: document.getElementById("m-type").value === "income",
      gst_claimable: document.getElementById("m-gst").checked,
    };
    if (!body.name) { toast("Name is required", "error"); return; }
    try {
      if (cat) {
        await api.put(`/api/categories/${cat.id}`, body);
        toast("Category updated", "success");
      } else {
        await api.post("/api/categories", body);
        toast("Category created", "success");
      }
      closeModal();
      renderCatTable();
    } catch (e) { toast(e.message, "error"); }
  });
};

window.deleteCategory = async function(id, count) {
  if (count > 0) {
    toast(`Cannot delete: ${count} transactions use this category`, "error");
    return;
  }
  if (!confirm("Delete this category?")) return;
  try {
    await api.delete(`/api/categories/${id}`);
    toast("Deleted", "success");
    renderCatTable();
  } catch (e) { toast(e.message, "error"); }
};

window.showRulesModal = async function(catId, catName) {
  const rules = await api.get(`/api/categories/${catId}/rules`);
  const rulesHtml = rules.length === 0
    ? '<p class="text-muted">No rules yet.</p>'
    : `<table style="width:100%;font-size:.82rem">
        <thead><tr><th>Keyword</th><th>Type</th><th>Source</th><th>Conf</th><th></th></tr></thead>
        <tbody>
          ${rules.map(r => `
            <tr>
              <td><code>${r.keyword}</code></td>
              <td>${r.match_type}</td>
              <td>${r.source}</td>
              <td>${(r.confidence * 100).toFixed(0)}%</td>
              <td>
                ${r.source !== "manual" && r.source !== "seed" ? `<button class="btn btn-sm btn-secondary" onclick="promoteRule(${r.id})">Promote</button>` : ""}
                <button class="btn btn-sm btn-danger" onclick="deleteRule(${r.id}, ${catId}, '${catName.replace(/'/g,"\\'")}')">✕</button>
              </td>
            </tr>
          `).join("")}
        </tbody>
      </table>`;

  createModal(`Rules: ${catName}`, `
    ${rulesHtml}
    <hr>
    <strong style="font-size:.85rem">Add Rule</strong>
    <div style="display:flex;gap:8px;margin-top:8px">
      <input class="form-control" id="r-kw" placeholder="keyword…">
      <select class="form-control" id="r-type" style="width:130px">
        <option value="contains">contains</option>
        <option value="startswith">starts with</option>
        <option value="regex">regex</option>
      </select>
      <button class="btn btn-primary" onclick="addRule(${catId}, '${catName.replace(/'/g,"\\'")}')">Add</button>
    </div>
  `, null, "Close");
};

window.addRule = async function(catId, catName) {
  const kw = document.getElementById("r-kw").value.trim();
  if (!kw) { toast("Enter a keyword", "error"); return; }
  try {
    await api.post(`/api/categories/${catId}/rules`, {
      keyword: kw,
      match_type: document.getElementById("r-type").value,
    });
    toast("Rule added", "success");
    closeModal();
    showRulesModal(catId, catName);
  } catch (e) { toast(e.message, "error"); }
};

window.deleteRule = async function(ruleId, catId, catName) {
  try {
    await api.delete(`/api/categories/rules/${ruleId}`);
    toast("Rule deleted", "success");
    closeModal();
    showRulesModal(catId, catName);
  } catch (e) { toast(e.message, "error"); }
};

window.promoteRule = async function(ruleId) {
  try {
    await api.post(`/api/categories/rules/${ruleId}/promote`);
    toast("Rule promoted to manual", "success");
  } catch (e) { toast(e.message, "error"); }
};

// ---- Reports ----------------------------------------------------
async function renderReports() {
  const content = document.getElementById("content");
  content.innerHTML = `
    <div class="card" style="margin-bottom:16px">
      <div class="card-body">
        <div class="filter-row">
          <div class="form-group">
            <label class="form-label">Preset</label>
            <select class="form-control" id="rpt-preset" style="width:160px">
              <option value="this_month">This Month</option>
              <option value="last_month">Last Month</option>
              <option value="2m">Last 2 Months</option>
              <option value="6m" selected>Last 6 Months</option>
              <option value="ytd">Year to Date</option>
              <option value="custom">Custom Range</option>
            </select>
          </div>
          <div id="custom-range" style="display:none;gap:8px" class="flex">
            <div class="form-group">
              <label class="form-label">From</label>
              <input type="date" class="form-control" id="rpt-from" style="width:150px">
            </div>
            <div class="form-group">
              <label class="form-label">To</label>
              <input type="date" class="form-control" id="rpt-to" style="width:150px">
            </div>
          </div>
          <button class="btn btn-primary" id="btn-gen-report">Generate Report</button>
          <button class="btn btn-secondary" id="btn-export-csv">&#x1F4E5; Export CSV</button>
        </div>
      </div>
    </div>
    <div id="report-output"></div>
  `;

  document.getElementById("rpt-preset").addEventListener("change", function() {
    document.getElementById("custom-range").style.display =
      this.value === "custom" ? "flex" : "none";
  });

  document.getElementById("btn-gen-report").addEventListener("click", loadReport);
  document.getElementById("btn-export-csv").addEventListener("click", exportReport);

  loadReport();
}

async function getReportParams() {
  const preset = document.getElementById("rpt-preset").value;
  const params = new URLSearchParams();
  if (preset === "custom") {
    const from = document.getElementById("rpt-from").value;
    const to = document.getElementById("rpt-to").value;
    if (!from || !to) { toast("Enter custom date range", "error"); return null; }
    params.set("preset", "custom");
    params.set("from_date", from);
    params.set("to_date", to);
  } else {
    params.set("preset", preset);
  }
  return params;
}

async function loadReport() {
  const params = await getReportParams();
  if (!params) return;

  const out = document.getElementById("report-output");
  out.innerHTML = '<p class="text-muted">Generating…</p>';

  const data = await api.get(`/api/reports/summary?${params}`);
  const sym = currSym();

  out.innerHTML = `
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="label">Total Expenses</div>
        <div class="value expense">${fmt.currency(data.total_expenses, sym)}</div>
      </div>
      <div class="kpi-card">
        <div class="label">Total Income</div>
        <div class="value income">${fmt.currency(data.total_income, sym)}</div>
      </div>
      <div class="kpi-card">
        <div class="label">GST Paid (on expenses)</div>
        <div class="value">${fmt.currency(data.total_gst_paid, sym)}</div>
      </div>
      <div class="kpi-card">
        <div class="label">GST Claimable</div>
        <div class="value gst">${fmt.currency(data.total_gst_claimable, sym)}</div>
      </div>
      <div class="kpi-card">
        <div class="label">Transactions</div>
        <div class="value">${data.transaction_count}</div>
      </div>
      <div class="kpi-card">
        <div class="label">Pending Reconciliation</div>
        <div class="value pending">${data.pending_count}</div>
      </div>
    </div>

    <div class="grid-2">
      <div class="card">
        <div class="card-header">Monthly Breakdown</div>
        <div class="card-body">
          <div class="chart-wrap"><canvas id="monthly-chart"></canvas></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header">GST Summary</div>
        <div class="card-body">
          <table>
            <tbody>
              <tr><td>Total GST paid on purchases</td><td><strong>${fmt.currency(data.total_gst_paid, sym)}</strong></td></tr>
              <tr><td>GST claimable (business)</td><td><strong style="color:#2563eb">${fmt.currency(data.total_gst_claimable, sym)}</strong></td></tr>
              <tr><td>Non-claimable GST</td><td><strong>${fmt.currency(data.total_gst_paid - data.total_gst_claimable, sym)}</strong></td></tr>
              <tr><td>Period</td><td>${data.from_date} → ${data.to_date}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">By Category</div>
      <div class="card-body" style="padding:0">
        <div class="table-wrap">
          <table>
            <thead><tr><th>Category</th><th>Transactions</th><th>Total</th><th>GST Claimable</th><th>Type</th></tr></thead>
            <tbody>
              ${data.by_category.map(c => `
                <tr>
                  <td>${colorDot(state.categories.find(x=>x.name===c.category)?.color)} ${c.category}</td>
                  <td>${c.count}</td>
                  <td>${fmt.currency(c.total, sym)}</td>
                  <td>${c.gst_claimable > 0 ? fmt.currency(c.gst_claimable, sym) : "—"}</td>
                  <td>${c.is_income ? "Income" : "Expense"}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-header">Monthly Breakdown</div>
      <div class="card-body" style="padding:0">
        <div class="table-wrap">
          <table>
            <thead><tr><th>Month</th><th>Expenses</th><th>Income</th><th>GST Claimable</th><th>Transactions</th></tr></thead>
            <tbody>
              ${data.monthly_breakdown.map(m => `
                <tr>
                  <td>${m.month}</td>
                  <td>${fmt.currency(m.expenses, sym)}</td>
                  <td>${fmt.currency(m.income, sym)}</td>
                  <td>${fmt.currency(m.gst_claimable, sym)}</td>
                  <td>${m.transaction_count}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;

  // Monthly bar chart
  const months = data.monthly_breakdown;
  if (months.length > 0 && state.chart) { state.chart.destroy(); state.chart = null; }
  if (months.length > 0) {
    const ctx = document.getElementById("monthly-chart").getContext("2d");
    state.chart = new Chart(ctx, {
      type: "bar",
      data: {
        labels: months.map(m => m.month),
        datasets: [
          {
            label: "Expenses",
            data: months.map(m => m.expenses),
            backgroundColor: "#ef44441a",
            borderColor: "#ef4444",
            borderWidth: 2,
          },
          {
            label: "Income",
            data: months.map(m => m.income),
            backgroundColor: "#22c55e1a",
            borderColor: "#22c55e",
            borderWidth: 2,
          },
          {
            label: "GST Claimable",
            data: months.map(m => m.gst_claimable),
            backgroundColor: "#3b82f61a",
            borderColor: "#3b82f6",
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }
}

async function exportReport() {
  const params = await getReportParams();
  if (!params) return;
  window.location.href = `/api/reports/export?${params}`;
}

// ---- Settings ---------------------------------------------------
async function renderSettings() {
  const settings = await api.get("/api/settings");
  const map = Object.fromEntries(settings.map(s => [s.key, s.value]));

  const content = document.getElementById("content");
  content.innerHTML = `
    <div style="max-width:560px">
      <div class="card">
        <div class="card-header">⚙️ Application Settings</div>
        <div class="card-body">
          <div class="form-group">
            <label class="form-label">Company / Trading Name</label>
            <input class="form-control" id="s-company" value="${map.company_name || ""}">
          </div>
          <div class="grid-2">
            <div class="form-group">
              <label class="form-label">VAT / GST Rate (%)</label>
              <input type="number" class="form-control" id="s-gst" value="${((+map.gst_rate || 0.20) * 100).toFixed(0)}" min="0" max="100" step="1">
              <small class="text-muted">NZ standard GST = 15%</small>
            </div>
            <div class="form-group">
              <label class="form-label">Default Currency</label>
              <select class="form-control" id="s-curr">
                <option value="NZD" ${map.default_currency === "NZD" ? "selected" : ""}>NZD (NZ$)</option>
                <option value="AUD" ${map.default_currency === "AUD" ? "selected" : ""}>AUD (A$)</option>
                <option value="GBP" ${map.default_currency === "GBP" ? "selected" : ""}>GBP (£)</option>
                <option value="EUR" ${map.default_currency === "EUR" ? "selected" : ""}>EUR (€)</option>
                <option value="USD" ${map.default_currency === "USD" ? "selected" : ""}>USD (US$)</option>
              </select>
            </div>
          </div>
          <button class="btn btn-primary" id="btn-save-settings">Save Settings</button>
        </div>
      </div>

      <div class="card">
        <div class="card-header">&#x1F527; Bulk Actions</div>
        <div class="card-body">
          <p class="text-muted" style="font-size:.875rem;margin-top:0">Re-run the auto-categoriser against all pending transactions using the current rules.</p>
          <button class="btn btn-secondary" id="btn-recat">&#x1F504; Re-run Auto-categorise</button>
        </div>
      </div>

      <div class="card">
        <div class="card-header">&#x1F4DA; API Documentation</div>
        <div class="card-body">
          <p class="text-muted" style="font-size:.875rem;margin-top:0">Interactive API docs are available at:</p>
          <a href="/api/docs" target="_blank" class="btn btn-secondary btn-sm">Open Swagger UI</a>
        </div>
      </div>
    </div>
  `;

  document.getElementById("btn-save-settings").addEventListener("click", async () => {
    try {
      const gstPct = parseFloat(document.getElementById("s-gst").value) / 100;
      await Promise.all([
        api.put("/api/settings/gst_rate",         { value: gstPct.toString() }),
        api.put("/api/settings/default_currency",  { value: document.getElementById("s-curr").value }),
        api.put("/api/settings/company_name",      { value: document.getElementById("s-company").value }),
      ]);
      toast("Settings saved", "success");
      refreshMeta();
    } catch (e) { toast(e.message, "error"); }
  });

  document.getElementById("btn-recat").addEventListener("click", async () => {
    try {
      const r = await api.post("/api/transactions/bulk-categorize");
      toast(`Updated ${r.updated} transactions`, "success");
      refreshMeta();
    } catch (e) { toast(e.message, "error"); }
  });
}

// ---- Receipts -----------------------------------------------------
window.openReceipts = async function(txId) {
  const body = `
    <div id="receipt-list" class="text-sm" style="margin-bottom:14px">Loading…</div>
    <div class="flex gap-2" style="align-items:center">
      <input type="file" id="receipt-file-input" accept=".jpg,.jpeg,.png,.webp,.gif,.heic,.pdf" style="flex:1">
      <button class="btn btn-sm btn-primary" id="receipt-upload-btn">Upload</button>
    </div>
  `;
  createModal("📎 Receipts", body, null, "Close");
  document.getElementById("receipt-upload-btn").addEventListener("click", () => uploadReceipt(txId));
  await loadReceiptList(txId);
};

async function loadReceiptList(txId) {
  const listEl = document.getElementById("receipt-list");
  if (!listEl) return;
  try {
    const receipts = await api.get(`/api/transactions/${txId}/receipts`);
    listEl.innerHTML = receipts.length === 0
      ? '<span class="text-muted">No receipts attached yet.</span>'
      : receipts.map(r => `
          <div class="flex gap-2" style="align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid #eee">
            <a href="/api/receipts/${r.id}/file" target="_blank">${r.original_filename}</a>
            <button class="btn btn-sm btn-secondary" onclick="deleteReceipt(${txId}, ${r.id})">✕</button>
          </div>
        `).join("");
    updateReceiptBadge(txId, receipts.length);
  } catch (e) { toast(e.message, "error"); }
}

async function uploadReceipt(txId) {
  const input = document.getElementById("receipt-file-input");
  if (!input.files[0]) { toast("Choose a file first", "error"); return; }
  const fd = new FormData();
  fd.append("file", input.files[0]);
  try {
    await api.post(`/api/transactions/${txId}/receipts`, fd);
    input.value = "";
    toast("Receipt uploaded", "success");
    await loadReceiptList(txId);
  } catch (e) { toast(e.message, "error"); }
}

window.deleteReceipt = async function(txId, receiptId) {
  try {
    await api.delete(`/api/receipts/${receiptId}`);
    await loadReceiptList(txId);
  } catch (e) { toast(e.message, "error"); }
};

function updateReceiptBadge(txId, count) {
  const btn = document.querySelector(`[data-receipt-btn="${txId}"]`);
  if (btn) btn.textContent = receiptLabel(count);
}

// ---- Modal helpers ----------------------------------------------
function createModal(title, bodyHtml, onSave, cancelLabel = "Cancel") {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.id = "active-modal";
  backdrop.innerHTML = `
    <div class="modal">
      <div class="modal-header">
        <span>${title}</span>
        <button class="close-btn" onclick="closeModal()">✕</button>
      </div>
      <div class="modal-body">${bodyHtml}</div>
      <div class="modal-footer">
        <button class="btn btn-secondary" onclick="closeModal()">${cancelLabel}</button>
        ${onSave ? '<button class="btn btn-primary" id="modal-save-btn">Save</button>' : ""}
      </div>
    </div>
  `;
  document.body.appendChild(backdrop);
  backdrop.addEventListener("click", e => { if (e.target === backdrop) closeModal(); });
  if (onSave) {
    document.getElementById("modal-save-btn").addEventListener("click", onSave);
  }
  return backdrop;
}

window.closeModal = function() {
  document.getElementById("active-modal")?.remove();
};

// ---- Init -------------------------------------------------------
async function init() {
  try {
    await refreshMeta();
  } catch (e) {
    console.warn("Meta refresh failed:", e);
  }
  const page = (location.hash || "#/dashboard").replace(/^#\//, "") || "dashboard";
  navigate(page);
}

window.addEventListener("hashchange", () => {
  const page = location.hash.replace(/^#\//, "") || "dashboard";
  navigate(page);
});

window.addEventListener("DOMContentLoaded", init);
