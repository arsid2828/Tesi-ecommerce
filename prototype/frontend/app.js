//URL base del backend FastAPI
const BASE_API_URL = "http://localhost:8000";

const state = {
  discovery: null,
};

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  if (page === "catalog") {
    initCatalogPage();
  }
  if (page === "product") {
    initProductPage();
  }
});

function initCatalogPage() {
  setupDiscoveryControls();
  runInitialQueryFromUrl();
}

function setupDiscoveryControls() {
  const form = document.getElementById("discoveryForm");
  const input = document.getElementById("searchInput");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runDiscoverySearch();
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      runDiscoverySearch();
    }
  });
  document.querySelectorAll(".example-chip").forEach((button) => {
    button.addEventListener("click", () => {
      input.value = button.dataset.query || "";
      runDiscoverySearch();
    });
  });
}

function runInitialQueryFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const query = params.get("q");
  if (!query) {
    return;
  }
  const input = document.getElementById("searchInput");
  input.value = query;
  runDiscoverySearch();
}

async function initProductPage() {
  const params = new URLSearchParams(window.location.search);
  const itemId = params.get("id");
  if (!itemId) {
    renderMessage("productDetail", "Prodotto non specificato.");
    return;
  }
  await loadProductDetail(itemId);
}

async function fetchJson(path) {
  const response = await fetch(`${BASE_API_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Errore API: ${response.status}`);
  }
  return response.json();
}

async function postJson(path, body) {
  const response = await fetch(`${BASE_API_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Errore API: ${response.status}`);
  }
  return response.json();
}

async function runDiscoverySearch() {
  const input = document.getElementById("searchInput");
  const query = input.value.trim();
  if (!query) {
    renderDiscoveryEmpty("Scrivi una query, anche semplice come mouse.");
    return;
  }

  setSearchLoading(true);
  renderDiscoveryLoading(query);
  try {
    const response = await postJson("/discover", {
      query,
      limit: 80,
      use_ai_support: true,
    });
    state.discovery = response;
    renderDiscovery(response);
  } catch (error) {
    console.error(error);
    renderDiscoveryEmpty("Ricerca discovery non disponibile.");
  } finally {
    setSearchLoading(false);
  }
}

function setSearchLoading(isLoading) {
  const button = document.getElementById("searchButton");
  if (!button) {
    return;
  }
  button.disabled = isLoading;
  button.textContent = isLoading ? "Analisi..." : "Analizza";
}

function renderDiscoveryLoading(query) {
  const summary = document.getElementById("discoverySummary");
  summary.className = "discovery-summary";
  summary.innerHTML = `
    <strong>Analisi in corso</strong>
    <p>Sto cercando ruoli e motivazioni locali per "${escapeHtml(query)}".</p>
  `;
  renderMessage("roleResults", "Caricamento gruppi prodotto...");
}

function renderDiscoveryEmpty(message) {
  const summary = document.getElementById("discoverySummary");
  summary.className = "discovery-summary hidden";
  summary.innerHTML = "";
  renderMessage("roleResults", message);
}

function renderDiscovery(response) {
  renderDiscoverySummary(response);
  renderRoleGroups(response.groups || []);
  const results = document.getElementById("roleResults");
  if (results) {
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function renderDiscoverySummary(response) {
  const summary = document.getElementById("discoverySummary");
  const sourceSummary = response.source_summary || {};
  const sourceChips = Object.entries(sourceSummary)
    .map(([label, count]) => `<span>${escapeHtml(label)} ${Number(count || 0)}</span>`)
    .join("");
  summary.className = "discovery-summary";
  summary.innerHTML = `
    <div>
      <strong>${response.used_ai_support ? "Discovery assistita" : "Discovery locale"}</strong>
      <p>${escapeHtml(response.answer || "")}</p>
    </div>
    <div class="source-summary">${sourceChips}</div>
  `;
}

function renderRoleGroups(groups) {
  const container = document.getElementById("roleResults");
  container.className = "role-results";
  container.innerHTML = "";

  if (!groups.length) {
    renderMessage("roleResults", "Nessun gruppo prodotto trovato.");
    return;
  }

  groups.forEach((group) => {
    const section = document.createElement("section");
    section.className = `role-section role-${escapeHtml(group.role_id || "generic")}`;

    const heading = document.createElement("div");
    heading.className = "role-heading";
    heading.innerHTML = `
      <div>
        <p class="role-kicker">${escapeHtml(roleKicker(group.role_id))}</p>
        <h2>${escapeHtml(group.label)}</h2>
        <p>${escapeHtml(group.description || "")}</p>
      </div>
      <span class="role-size">${formatProductCount(group.size)}</span>
    `;

    const keywords = document.createElement("div");
    keywords.className = "cluster-keywords";
    (group.keywords || []).slice(0, 6).forEach((keyword) => {
      const chip = document.createElement("span");
      chip.textContent = keyword;
      keywords.appendChild(chip);
    });

    const grid = document.createElement("div");
    grid.className = "product-grid role-grid";
    (group.products || []).forEach((product) => {
      grid.appendChild(createProductCard(product, { showEvidence: true }));
    });

    section.appendChild(heading);
    if (group.reason) {
      const reason = document.createElement("p");
      reason.className = "role-reason";
      reason.textContent = group.reason;
      section.appendChild(reason);
    }
    if (keywords.children.length) {
      section.appendChild(keywords);
    }
    section.appendChild(grid);
    container.appendChild(section);
  });
}

function roleKicker(roleId) {
  const labels = {
    best_choice: "Priorita",
    budget: "Prezzo",
    balanced: "Compromesso",
    same_brand: "Marca",
    complementary: "Uso insieme",
    popular_alternatives: "Popolarita",
  };
  return labels[roleId] || "Ruolo";
}

function formatProductCount(value) {
  const count = Number(value || 0);
  return `${count} ${count === 1 ? "prodotto" : "prodotti"}`;
}

async function loadProductDetail(itemId) {
  try {
    const product = await fetchJson(`/products/${encodeURIComponent(itemId)}`);
    renderProductDetail(product);
  } catch (error) {
    renderMessage("productDetail", "Prodotto non trovato.");
  }
}

function createProductCard(product, options = {}) {
  const card = document.createElement("article");
  card.className = "product-card";

  const imageBox = createImageBox(product, "product-image");
  const body = document.createElement("div");
  body.className = "card-body";
  body.innerHTML = `
    <p class="category">${escapeHtml(product.category)}</p>
    <h3>${escapeHtml(product.title)}</h3>
    <p class="${priceClassName(product.price)}">${escapeHtml(formatPrice(product.price))}</p>
    <div class="meta-row">
      <span>Rating ${formatRating(product.average_rating)}</span>
      <span>${Number(product.rating_count || 0).toLocaleString("it-IT")} recensioni</span>
    </div>
  `;

  if (product.role_reason) {
    const reason = document.createElement("p");
    reason.className = "ai-reason";
    reason.innerHTML = `<strong>Perche qui:</strong> ${escapeHtml(product.role_reason)}`;
    body.appendChild(reason);
  }

  if (options.showEvidence) {
    body.appendChild(createEvidenceBlock(product));
  }

  const button = document.createElement("button");
  button.className = "secondary-button";
  button.type = "button";
  button.textContent = "Dettagli";
  button.addEventListener("click", () => {
    window.location.href = `product.html?id=${encodeURIComponent(product.item_id)}&v=mission-cleanup-1`;
  });

  body.appendChild(button);
  card.appendChild(imageBox);
  card.appendChild(body);
  return card;
}

function createEvidenceBlock(product) {
  const wrapper = document.createElement("div");
  wrapper.className = "evidence-preview";

  const sources = document.createElement("div");
  sources.className = "source-chips";
  (product.evidence_sources || ["metadati"]).forEach((source) => {
    const chip = document.createElement("span");
    chip.textContent = source;
    sources.appendChild(chip);
  });

  const list = document.createElement("div");
  list.className = "evidence-snippets";
  (product.evidence || []).slice(0, 2).forEach((item) => {
    const snippet = document.createElement("p");
    snippet.innerHTML = `<strong>${escapeHtml(item.source_label || item.source)}:</strong> ${escapeHtml(item.text || "")}`;
    list.appendChild(snippet);
  });

  wrapper.appendChild(sources);
  wrapper.appendChild(list);
  return wrapper;
}

function renderProductDetail(product) {
  const container = document.getElementById("productDetail");
  container.innerHTML = "";

  const imageBox = createImageBox(product, "detail-image");
  const info = document.createElement("div");
  info.className = "detail-info";
  info.innerHTML = `
    <p class="category">${escapeHtml(product.category)}</p>
    <h2>${escapeHtml(product.title)}</h2>
    <p class="description">${escapeHtml(product.description || "Descrizione non disponibile.")}</p>
    <dl class="stats">
      <div><dt>Prezzo</dt><dd>${escapeHtml(formatPrice(product.price))}</dd></div>
      <div><dt>Average rating</dt><dd>${formatRating(product.average_rating)}</dd></div>
      <div><dt>Rating count</dt><dd>${Number(product.rating_count || 0).toLocaleString("it-IT")}</dd></div>
      <div><dt>Popularity score</dt><dd>${Number(product.popularity_score || 0).toFixed(4)}</dd></div>
    </dl>
  `;

  container.appendChild(imageBox);
  container.appendChild(info);
}

function createImageBox(product, className) {
  const wrapper = document.createElement("div");
  wrapper.className = className;

  if (!product.image_url) {
    wrapper.appendChild(createPlaceholder());
    return wrapper;
  }

  const image = document.createElement("img");
  image.src = product.image_url;
  image.alt = product.title;
  image.loading = "lazy";
  image.addEventListener("error", () => {
    wrapper.innerHTML = "";
    wrapper.appendChild(createPlaceholder());
  });
  wrapper.appendChild(image);
  return wrapper;
}

function createPlaceholder() {
  const placeholder = document.createElement("div");
  placeholder.className = "image-placeholder";
  placeholder.textContent = "Immagine non disponibile";
  return placeholder;
}

function renderMessage(containerId, message) {
  const container = document.getElementById(containerId);
  container.innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
}

function normalizePrice(value) {
  const price = Number(value);
  return Number.isFinite(price) && price > 0 ? price : null;
}

function formatRating(value) {
  const number = Number(value || 0);
  return number > 0 ? number.toFixed(1) : "N/D";
}

function formatPrice(value) {
  const price = normalizePrice(value);
  if (price === null) {
    return "Prezzo non disponibile";
  }
  return price.toLocaleString("it-IT", {
    style: "currency",
    currency: "USD",
  });
}

function priceClassName(value) {
  return normalizePrice(value) === null ? "price-row muted-price" : "price-row";
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
