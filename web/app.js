const state = {
  data: null,
  rows: [],
  sortKey: "live_yield_diff",
  sortDir: "desc",
  filters: {
    category: "통합",
    level: "",
    sector: "",
    search: "",
  },
};

const columns = {
  name_ko: "text",
  ticker: "text",
  asset_category: "text",
  level: "text",
  sector: "text",
  price: "number",
  live_yield: "number",
  avg_yield_5y: "number",
  live_yield_diff_5y: "number",
  avg_yield_10y: "number",
  live_yield_diff: "number",
  increase_years: "number",
  growth_5y: "number",
  payout_ratio: "number",
  pay_months: "text",
};

const els = {
  lastUpdated: document.querySelector("#lastUpdated"),
  statusCount: document.querySelector("#statusCount"),
  categoryFilter: document.querySelector("#categoryFilter"),
  levelFilter: document.querySelector("#levelFilter"),
  sectorFilter: document.querySelector("#sectorFilter"),
  searchInput: document.querySelector("#searchInput"),
  resetButton: document.querySelector("#resetButton"),
  visibleCount: document.querySelector("#visibleCount"),
  positiveCount: document.querySelector("#positiveCount"),
  failedCount: document.querySelector("#failedCount"),
  tableBody: document.querySelector("#tableBody"),
  emptyState: document.querySelector("#emptyState"),
  detailDialog: document.querySelector("#detailDialog"),
  detailContent: document.querySelector("#detailContent"),
  closeDialog: document.querySelector("#closeDialog"),
};

function formatCurrency(value) {
  return Number.isFinite(value)
    ? value.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 })
    : "-";
}

function formatPercent(value, digits = 2) {
  return Number.isFinite(value) ? `${(value * 100).toFixed(digits)}%` : "-";
}

function formatNumber(value, digits = 0) {
  return Number.isFinite(value) ? value.toLocaleString("ko-KR", { maximumFractionDigits: digits }) : "-";
}

function formatKst(iso) {
  if (!iso) return "-";
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

function uniqueValues(rows, key) {
  return [...new Set(rows.map((row) => row[key]).filter(Boolean))].sort((a, b) => `${a}`.localeCompare(`${b}`, "ko"));
}

function fillSelect(select, values) {
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  });
}

function updateQuery() {
  const params = new URLSearchParams();
  if (state.filters.category !== "통합") params.set("category", state.filters.category);
  if (state.filters.level) params.set("level", state.filters.level);
  if (state.filters.sector) params.set("sector", state.filters.sector);
  if (state.filters.search) params.set("q", state.filters.search);
  if (state.sortKey !== "live_yield_diff") params.set("sort", state.sortKey);
  if (state.sortDir !== "desc") params.set("dir", state.sortDir);
  const query = params.toString();
  history.replaceState(null, "", query ? `?${query}` : location.pathname);
}

function hydrateFromQuery() {
  const params = new URLSearchParams(location.search);
  state.filters.category = params.get("category") || "통합";
  state.filters.level = params.get("level") || "";
  state.filters.sector = params.get("sector") || "";
  state.filters.search = params.get("q") || "";
  state.sortKey = params.get("sort") || state.sortKey;
  state.sortDir = params.get("dir") === "asc" ? "asc" : "desc";
}

function compareRows(a, b) {
  const key = state.sortKey;
  const type = columns[key] || "text";
  const dir = state.sortDir === "asc" ? 1 : -1;
  const av = a[key];
  const bv = b[key];

  if (type === "number") {
    const an = Number.isFinite(av) ? av : -Infinity;
    const bn = Number.isFinite(bv) ? bv : -Infinity;
    return (an - bn) * dir;
  }

  return `${av ?? ""}`.localeCompare(`${bv ?? ""}`, "ko") * dir;
}

function getVisibleRows() {
  const search = state.filters.search.trim().toLowerCase();
  return state.rows
    .filter((row) => state.filters.category === "통합" || (row.asset_category || "주식") === state.filters.category)
    .filter((row) => !state.filters.level || row.level === state.filters.level)
    .filter((row) => !state.filters.sector || row.sector === state.filters.sector)
    .filter((row) => {
      if (!search) return true;
      return `${row.name_ko} ${row.ticker}`.toLowerCase().includes(search);
    })
    .sort(compareRows);
}

function renderSortButtons() {
  document.querySelectorAll("th button[data-sort]").forEach((button) => {
    const active = button.dataset.sort === state.sortKey;
    button.classList.toggle("active", active);
    button.classList.toggle("asc", active && state.sortDir === "asc");
    button.classList.toggle("desc", active && state.sortDir === "desc");
  });
}

function makeCell(content, className = "") {
  const td = document.createElement("td");
  if (className) td.className = className;
  if (content instanceof Node) {
    td.append(content);
  } else {
    td.textContent = content;
  }
  return td;
}

function makePill(text, extraClass = "") {
  const span = document.createElement("span");
  span.className = `pill ${extraClass}`.trim();
  span.textContent = text || "-";
  return span;
}

function renderTable() {
  const rows = getVisibleRows();
  els.tableBody.replaceChildren();
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.className = row.status === "failed" ? "failed" : "";
    tr.tabIndex = 0;
    tr.addEventListener("click", () => openDetail(row));
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter") openDetail(row);
    });

    const diff = document.createElement("span");
    diff.className = `diff ${row.live_yield_diff > 0 ? "positive" : "negative"}`;
    diff.textContent = formatPercent(row.live_yield_diff);
    const diff5y = document.createElement("span");
    diff5y.className = `diff ${row.live_yield_diff_5y > 0 ? "positive" : "negative"}`;
    diff5y.textContent = formatPercent(row.live_yield_diff_5y);

    tr.append(
      makeCell(row.name_ko || "-"),
      makeCell(row.ticker || "-", "ticker"),
      makeCell(makePill(row.asset_category || "주식")),
      makeCell(makePill(row.level)),
      makeCell(row.sector || "-"),
      makeCell(formatCurrency(row.price), "numeric"),
      makeCell(formatPercent(row.live_yield), "numeric"),
      makeCell(formatPercent(row.avg_yield_5y), "numeric"),
      makeCell(diff5y, "numeric emphasis"),
      makeCell(formatPercent(row.avg_yield_10y), "numeric"),
      makeCell(diff, "numeric emphasis"),
      makeCell(formatNumber(row.increase_years), "numeric"),
      makeCell(formatPercent(row.growth_5y), "numeric"),
      makeCell(formatPercent(row.payout_ratio), "numeric"),
      makeCell(row.pay_months || "-")
    );
    els.tableBody.append(tr);
  });

  els.visibleCount.textContent = rows.length.toLocaleString("ko-KR");
  els.positiveCount.textContent = rows.filter((row) => row.live_yield_diff > 0).length.toLocaleString("ko-KR");
  els.failedCount.textContent = rows.filter((row) => row.status === "failed").length.toLocaleString("ko-KR");
  els.emptyState.hidden = rows.length !== 0;
  renderSortButtons();
}

function openDetail(row) {
  els.detailContent.innerHTML = `
    <h2 class="detail-title">${row.name_ko || row.ticker} <span class="ticker">${row.ticker}</span></h2>
    <div class="detail-grid">
      <div><span>상태</span>${row.status}</div>
      <div><span>카테고리</span>${row.asset_category || "주식"}</div>
      <div><span>현재가</span>${formatCurrency(row.price)}</div>
      <div><span>현재 배당률</span>${formatPercent(row.live_yield)}</div>
      <div><span>5년 평균 배당률</span>${formatPercent(row.avg_yield_5y)}</div>
      <div><span>5년 평균 대비 차이</span>${formatPercent(row.live_yield_diff_5y)}</div>
      <div><span>10년 평균 배당률</span>${formatPercent(row.avg_yield_10y)}</div>
      <div><span>평균 대비 차이</span>${formatPercent(row.live_yield_diff)}</div>
      <div><span>연 배당금</span>${formatCurrency(row.live_dividend)}</div>
      <div><span>지급월</span>${row.pay_months || "-"}</div>
      <div><span>조회 시각</span>${formatKst(row.fetched_at)} KST</div>
    </div>
  `;
  els.detailDialog.showModal();
}

function bindEvents() {
  els.categoryFilter.addEventListener("change", () => {
    state.filters.category = els.categoryFilter.value;
    updateQuery();
    renderTable();
  });
  els.levelFilter.addEventListener("change", () => {
    state.filters.level = els.levelFilter.value;
    updateQuery();
    renderTable();
  });
  els.sectorFilter.addEventListener("change", () => {
    state.filters.sector = els.sectorFilter.value;
    updateQuery();
    renderTable();
  });
  els.searchInput.addEventListener("input", () => {
    state.filters.search = els.searchInput.value;
    updateQuery();
    renderTable();
  });
  els.resetButton.addEventListener("click", () => {
    state.filters = { category: "통합", level: "", sector: "", search: "" };
    state.sortKey = "live_yield_diff";
    state.sortDir = "desc";
    els.categoryFilter.value = "통합";
    els.levelFilter.value = "";
    els.sectorFilter.value = "";
    els.searchInput.value = "";
    updateQuery();
    renderTable();
  });
  els.closeDialog.addEventListener("click", () => els.detailDialog.close());
  document.querySelectorAll("th button[data-sort]").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.sort;
      if (state.sortKey === key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        state.sortDir = columns[key] === "number" ? "desc" : "asc";
      }
      updateQuery();
      renderTable();
    });
  });
}

async function init() {
  try {
    hydrateFromQuery();
    const response = await fetch("../data/dividends.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`데이터를 불러오지 못했습니다. (${response.status})`);
    state.data = await response.json();
    state.rows = state.data.companies || [];
    fillSelect(els.levelFilter, uniqueValues(state.rows, "level"));
    fillSelect(els.sectorFilter, uniqueValues(state.rows, "sector"));
    els.categoryFilter.value = state.filters.category;
    els.levelFilter.value = state.filters.level;
    els.sectorFilter.value = state.filters.sector;
    els.searchInput.value = state.filters.search;
    els.lastUpdated.textContent = `마지막 갱신: ${formatKst(state.data.generated_at)} KST`;
    els.statusCount.textContent = `OK ${state.data.ok_count} / Failed ${state.data.failed_count}`;
    bindEvents();
    renderTable();
  } catch (error) {
    els.tableBody.replaceChildren();
    els.emptyState.hidden = false;
    els.emptyState.textContent = error.message;
  }
}

init();
