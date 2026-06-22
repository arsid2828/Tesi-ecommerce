const BASE_API_URL = "http://localhost:8000";

const state = {
  profiles: [],
  currentProfileId: "cold-start",
  homeRequestId: 0,
  searchRequestId: 0,
};

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  if (page === "home") {
    initHomePage();
  }
  if (page === "product") {
    initProductPage();
  }
});

async function initHomePage() {
  setupProfileSwitcher();
  setupDiscoveryControls();
  const requestedProfile = new URLSearchParams(window.location.search).get("profile");
  state.currentProfileId = requestedProfile === "dataset-user" ? "dataset-user" : "cold-start";
  setActiveProfileButton(state.currentProfileId);

  try {
    state.profiles = await fetchJson("/home/profiles");
    updateProfileSwitcher(state.profiles);
  } catch (error) {
    console.error(error);
  }
  await loadHomeRecommendations(state.currentProfileId);
  runInitialSearchFromUrl();
}

function setupProfileSwitcher() {
  document.querySelectorAll(".profile-option").forEach((button) => {
    button.addEventListener("click", () => {
      const profileId = button.dataset.profileId;
      if (!profileId || profileId === state.currentProfileId) {
        return;
      }
      state.currentProfileId = profileId;
      setActiveProfileButton(profileId);
      loadHomeRecommendations(profileId);
    });
  });
}

function setupDiscoveryControls() {
  const form = document.getElementById("discoveryForm");
  const mode = document.getElementById("resultMode");
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runCatalogSearch();
  });
  mode.addEventListener("change", updateSearchModeControls);
  document.getElementById("clearSearchButton").addEventListener("click", clearSearchResults);
  updateSearchModeControls();
}

function updateSearchModeControls() {
  const isSorted = document.getElementById("resultMode").value === "sorted";
  document.getElementById("aiQueryField").classList.toggle("hidden", isSorted);
  document.getElementById("sortField").classList.toggle("hidden", !isSorted);
}

function runInitialSearchFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const query = params.get("q");
  if (!query) {
    return;
  }
  const mode = params.get("view") === "sorted" ? "sorted" : "clusters";
  const allowedSorts = new Set(["price_asc", "price_desc", "rating_desc", "reviews_desc"]);
  const sort = allowedSorts.has(params.get("sort")) ? params.get("sort") : "price_asc";
  document.getElementById("searchInput").value = query;
  document.getElementById("aiQueryInput").value = params.get("intent") || "";
  document.getElementById("resultMode").value = mode;
  document.getElementById("sortBy").value = sort;
  updateSearchModeControls();
  runCatalogSearch();
}

async function runCatalogSearch() {
  const query = document.getElementById("searchInput").value.trim();
  if (!query) {
    renderSearchMessage("Scrivi una query, anche semplice come mouse.");
    return;
  }

  const mode = document.getElementById("resultMode").value;
  const sortBy = document.getElementById("sortBy").value;
  const aiQuery = mode === "clusters" ? document.getElementById("aiQueryInput").value.trim() : "";
  const requestId = ++state.searchRequestId;
  setHomeContentVisible(false);
  setSearchLoading(true);
  renderSearchLoading(query, aiQuery, mode);
  try {
    if (mode === "clusters") {
      const response = await postJson("/discover", {
        query,
        ai_query: aiQuery,
        limit: 80,
        use_ai_support: true,
      });
      if (requestId !== state.searchRequestId) {
        return;
      }
      renderClusterSearch(response);
    } else {
      const products = await fetchJson(`/search?query=${encodeURIComponent(query)}&limit=80`);
      if (requestId !== state.searchRequestId) {
        return;
      }
      renderSortedSearch(query, products, sortBy);
    }
    updateSearchUrl(query, mode, sortBy, aiQuery);
    document.getElementById("searchResultsSection").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    console.error(error);
    renderSearchMessage("Ricerca non disponibile.");
  } finally {
    if (requestId === state.searchRequestId) {
      setSearchLoading(false);
    }
  }
}

function setSearchLoading(isLoading) {
  const button = document.getElementById("searchButton");
  button.disabled = isLoading;
  button.textContent = isLoading ? "Analisi..." : "Analizza";
}

function renderSearchLoading(query, aiQuery, mode) {
  const section = document.getElementById("searchResultsSection");
  section.classList.remove("hidden");
  document.getElementById("clearSearchButton").classList.remove("hidden");
  document.getElementById("searchResultsKicker").textContent = "Ricerca in corso";
  document.getElementById("searchResultsTitle").textContent = `Risultati per “${query}”`;
  document.getElementById("searchResultsSummary").textContent = mode === "clusters" && aiQuery
    ? "Recupero evidenze locali, poi Gemini riorganizza la presentazione dei cluster."
    : "Sto preparando i prodotti...";
  document.getElementById("searchResultsCount").textContent = "";
  renderMessage("searchResultsContent", "Caricamento risultati...");
}

function renderClusterSearch(response) {
  const groups = response.groups || [];
  document.getElementById("searchResultsKicker").textContent = response.used_ai_support
    ? "Evidenze locali · riorganizzate da Gemini"
    : "Cluster con evidenze locali";
  document.getElementById("searchResultsTitle").textContent = `Risultati per “${response.query}”`;
  document.getElementById("searchResultsSummary").textContent = response.answer || "Prodotti raggruppati per ruolo.";
  document.getElementById("searchResultsCount").textContent = `${Number(response.total_candidates || 0)} candidati`;
  renderSearchRoleGroups(groups);
}

function renderSearchRoleGroups(groups) {
  const container = document.getElementById("searchResultsContent");
  container.className = "role-results search-role-results";
  container.innerHTML = "";
  if (!groups.length) {
    renderMessage("searchResultsContent", "Nessun cluster trovato.");
    return;
  }

  groups.forEach((group) => {
    const section = document.createElement("section");
    section.className = `role-section role-${group.role_id || "generic"}`;
    const heading = document.createElement("div");
    heading.className = "role-heading";
    heading.innerHTML = `
      <div>
        <p class="role-kicker">${escapeHtml(roleKicker(group.role_id))}</p>
        <h3>${escapeHtml(group.label)}</h3>
        <p>${escapeHtml(group.description || "")}</p>
      </div>
      <span class="role-size">${escapeHtml(formatProductCount(group.size))}</span>
    `;
    section.appendChild(heading);

    if (group.reason) {
      const reason = document.createElement("p");
      reason.className = "role-reason";
      reason.textContent = group.reason;
      section.appendChild(reason);
    }

    const keywords = document.createElement("div");
    keywords.className = "cluster-keywords";
    (group.keywords || []).slice(0, 6).forEach((keyword) => {
      const chip = document.createElement("span");
      chip.textContent = keyword;
      keywords.appendChild(chip);
    });
    if (keywords.children.length) {
      section.appendChild(keywords);
    }

    const grid = document.createElement("div");
    grid.className = "product-grid role-grid";
    (group.products || []).forEach((product) => {
      grid.appendChild(createProductCard(product, { showRoleReason: true, showEvidence: true }));
    });
    section.appendChild(grid);
    container.appendChild(section);
  });
}

function roleKicker(roleId) {
  const labels = {
    best_choice: "Priorità",
    budget: "Prezzo",
    balanced: "Compromesso",
    same_brand: "Marca",
    complementary: "Uso insieme",
    popular_alternatives: "Popolarità",
  };
  return labels[roleId] || "Cluster";
}

function formatProductCount(value) {
  const count = Number(value || 0);
  return `${count} ${count === 1 ? "prodotto" : "prodotti"}`;
}

function renderSortedSearch(query, products, sortBy) {
  const sorted = sortSearchProducts(products, sortBy);
  document.getElementById("searchResultsKicker").textContent = "Vista ordinata";
  document.getElementById("searchResultsTitle").textContent = `Risultati per “${query}”`;
  document.getElementById("searchResultsSummary").textContent = `Ordinamento: ${sortLabel(sortBy)}.`;
  document.getElementById("searchResultsCount").textContent = `${sorted.length} prodotti`;
  const container = document.getElementById("searchResultsContent");
  container.className = "product-grid ordered-search-grid";
  container.innerHTML = "";
  if (!sorted.length) {
    renderMessage("searchResultsContent", "Nessun prodotto trovato.");
    return;
  }
  sorted.forEach((product) => container.appendChild(createProductCard(product)));
}

function sortSearchProducts(products, sortBy) {
  const sorted = [...products];
  const popularityTieBreak = (a, b) => Number(b.popularity_score || 0) - Number(a.popularity_score || 0);
  if (sortBy === "price_asc") {
    return sorted.sort((a, b) => (normalizePrice(a.price) ?? Number.POSITIVE_INFINITY) - (normalizePrice(b.price) ?? Number.POSITIVE_INFINITY) || popularityTieBreak(a, b));
  }
  if (sortBy === "price_desc") {
    return sorted.sort((a, b) => (normalizePrice(b.price) ?? Number.NEGATIVE_INFINITY) - (normalizePrice(a.price) ?? Number.NEGATIVE_INFINITY) || popularityTieBreak(a, b));
  }
  if (sortBy === "rating_desc") {
    return sorted.sort((a, b) => Number(b.average_rating || 0) - Number(a.average_rating || 0) || Number(b.rating_count || 0) - Number(a.rating_count || 0));
  }
  return sorted.sort((a, b) => Number(b.rating_count || 0) - Number(a.rating_count || 0) || Number(b.average_rating || 0) - Number(a.average_rating || 0));
}

function sortLabel(sortBy) {
  const labels = {
    price_asc: "prezzo crescente",
    price_desc: "prezzo decrescente",
    rating_desc: "rating più alto",
    reviews_desc: "numero di recensioni",
  };
  return labels[sortBy] || "numero di recensioni";
}

function renderSearchMessage(message) {
  const section = document.getElementById("searchResultsSection");
  section.classList.remove("hidden");
  document.getElementById("clearSearchButton").classList.remove("hidden");
  document.getElementById("searchResultsKicker").textContent = "Ricerca";
  document.getElementById("searchResultsTitle").textContent = "Cerca nel catalogo";
  document.getElementById("searchResultsSummary").textContent = message;
  document.getElementById("searchResultsCount").textContent = "";
  renderMessage("searchResultsContent", message);
}

function clearSearchResults() {
  state.searchRequestId += 1;
  setSearchLoading(false);
  setHomeContentVisible(true);
  document.getElementById("searchInput").value = "";
  document.getElementById("aiQueryInput").value = "";
  document.getElementById("searchResultsSection").classList.add("hidden");
  document.getElementById("clearSearchButton").classList.add("hidden");
  const url = new URL(window.location.href);
  url.searchParams.delete("q");
  url.searchParams.delete("view");
  url.searchParams.delete("sort");
  url.searchParams.delete("intent");
  window.history.replaceState({}, "", url);
}

function setHomeContentVisible(isVisible) {
  document.querySelectorAll(".home-hero, .home-products").forEach((section) => {
    section.classList.toggle("hidden", !isVisible);
  });
}

function updateSearchUrl(query, mode, sortBy, aiQuery) {
  const url = new URL(window.location.href);
  url.searchParams.set("q", query);
  url.searchParams.set("view", mode);
  if (mode === "sorted") {
    url.searchParams.set("sort", sortBy);
    url.searchParams.delete("intent");
  } else {
    url.searchParams.delete("sort");
    if (aiQuery) {
      url.searchParams.set("intent", aiQuery);
    } else {
      url.searchParams.delete("intent");
    }
  }
  window.history.replaceState({}, "", url);
}

function updateProfileSwitcher(profiles) {
  profiles.forEach((profile) => {
    const button = document.querySelector(`[data-profile-id="${profile.profile_id}"]`);
    if (!button) {
      return;
    }
    const title = button.querySelector("strong");
    const detail = button.querySelector("small");
    title.textContent = profile.label;
    detail.textContent = profile.profile_type === "cold_start"
      ? profile.short_label
      : `${Number(profile.history_count)} prodotti nello storico`;
  });
}

function setActiveProfileButton(profileId) {
  document.querySelectorAll(".profile-option").forEach((button) => {
    const isActive = button.dataset.profileId === profileId;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", String(isActive));
  });
}

async function loadHomeRecommendations(profileId) {
  const requestId = ++state.homeRequestId;
  setProfileLoading(true);
  renderMessage("primaryRecommendations", "Caricamento prodotti...");
  document.getElementById("secondaryRecommendations").innerHTML = "";
  try {
    const response = await fetchJson(`/home/recommendations/${encodeURIComponent(profileId)}?limit=24`);
    if (requestId !== state.homeRequestId) {
      return;
    }
    renderHome(response);
    const url = new URL(window.location.href);
    url.searchParams.set("profile", profileId);
    window.history.replaceState({}, "", url);
  } catch (error) {
    console.error(error);
    renderMessage("primaryRecommendations", "La home personalizzata non è disponibile.");
  } finally {
    if (requestId === state.homeRequestId) {
      setProfileLoading(false);
    }
  }
}

function setProfileLoading(isLoading) {
  document.querySelectorAll(".profile-option").forEach((button) => {
    button.disabled = isLoading;
  });
  document.body.classList.toggle("is-loading-profile", isLoading);
}

function renderHome(response) {
  const profile = response.profile;
  const products = response.products || [];
  const isColdStart = profile.profile_type === "cold_start";
  state.currentProfileId = profile.profile_id;
  setActiveProfileButton(profile.profile_id);

  document.getElementById("profileKicker").textContent = profile.short_label;
  document.getElementById("homeTitle").textContent = isColdStart
    ? "Una vetrina utile anche senza storico"
    : "Consigli costruiti su uno storico reale";
  document.getElementById("profileDescription").textContent = profile.description;
  renderProfileFacts(profile);
  renderAlgorithmCard(profile.algorithm);

  document.getElementById("primaryKicker").textContent = isColdStart ? "Popular · 100%" : "Miglior ibrido";
  document.getElementById("primaryTitle").textContent = isColdStart ? "I più popolari" : "Scelti per questo utente";
  document.getElementById("primaryDescription").textContent = isColdStart
    ? "La posizione dipende esclusivamente dalla popolarità osservata nel catalogo."
    : "Prodotti non ancora visti, ordinati dal modello vincitore sul validation set.";
  document.getElementById("secondaryKicker").textContent = isColdStart ? "Sempre Popular" : "Stesso modello ibrido";
  document.getElementById("secondaryTitle").textContent = isColdStart ? "Altri bestseller" : "Altri consigli per te";
  document.getElementById("secondaryDescription").textContent = isColdStart
    ? "Nessun segnale personale: continua la classifica Popular."
    : "La seconda selezione continua lo stesso ranking personalizzato, senza cambiare algoritmo.";
  document.getElementById("resultCount").textContent = `${products.length} prodotti`;

  renderProductGrid("primaryRecommendations", products.slice(0, 8));
  renderProductGrid("secondaryRecommendations", products.slice(8));
  document.getElementById("secondarySection").classList.toggle("hidden", products.length <= 8);
}

function renderProfileFacts(profile) {
  const container = document.getElementById("profileFacts");
  container.innerHTML = "";
  const facts = profile.profile_type === "cold_start"
    ? ["0 interazioni", "Nessuna preferenza nota"]
    : [
        `ID ${shortDatasetUserId(profile.dataset_user_id)}`,
        `${Number(profile.history_count)} prodotti nel training`,
        `${Number(profile.known_interactions)} interazioni note`,
        ...(profile.interests || []).slice(0, 3),
      ];
  facts.forEach((fact) => {
    const chip = document.createElement("span");
    chip.textContent = fact;
    container.appendChild(chip);
  });
}

function shortDatasetUserId(value) {
  const id = String(value || "dataset");
  if (id.length <= 13) {
    return id;
  }
  return `${id.slice(0, 7)}…${id.slice(-5)}`;
}

function renderAlgorithmCard(algorithm) {
  const card = document.getElementById("algorithmCard");
  const weights = Object.entries(algorithm.weights || {})
    .filter(([, value]) => Number(value) > 0)
    .map(([name, value]) => `<span>${escapeHtml(weightLabel(name))} <strong>${Math.round(Number(value) * 100)}%</strong></span>`)
    .join("");
  const metric = algorithm.validation_metric_value === null || algorithm.validation_metric_value === undefined
    ? ""
    : `<p class="model-metric">${escapeHtml(algorithm.validation_metric_name)} <strong>${Number(algorithm.validation_metric_value).toFixed(4)}</strong></p>`;
  card.innerHTML = `
    <p class="algorithm-label">Modello attivo</p>
    <h3>${escapeHtml(algorithm.name)}</h3>
    <p>${escapeHtml(algorithm.description)}</p>
    <div class="model-weights">${weights}</div>
    ${metric}
  `;
}

function weightLabel(name) {
  const labels = {
    svd: "SVD",
    content: "Contenuto",
    popularity: "Popular",
  };
  return labels[name] || name;
}

function renderProductGrid(containerId, products) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  if (!products.length) {
    renderMessage(containerId, "Nessun prodotto disponibile.");
    return;
  }
  products.forEach((product) => {
    container.appendChild(createProductCard(product, { showRecommendation: true }));
  });
}

async function initProductPage() {
  const params = new URLSearchParams(window.location.search);
  const itemId = params.get("id");
  const profileId = params.get("profile");
  const safeProfileId = profileId === "dataset-user" ? "dataset-user" : "cold-start";
  state.currentProfileId = safeProfileId;
  if (profileId === "cold-start" || profileId === "dataset-user") {
    const backLink = document.getElementById("homeBackLink");
    const homeParams = new URLSearchParams({ profile: safeProfileId, v: "profiles-gemini-3" });
    ["q", "view", "sort", "intent"].forEach((key) => {
      if (params.get(key)) {
        homeParams.set(key, params.get(key));
      }
    });
    backLink.href = `index.html?${homeParams.toString()}`;
  }
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
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Errore API: ${response.status}`);
  }
  return response.json();
}

async function loadProductDetail(itemId) {
  try {
    const product = await fetchJson(`/products/${encodeURIComponent(itemId)}`);
    renderProductDetail(product);
  } catch (error) {
    console.error(error);
    renderMessage("productDetail", "Prodotto non trovato.");
  }
}

function createProductCard(product, options = {}) {
  const card = document.createElement("article");
  card.className = "product-card";

  const imageBox = createImageBox(product, "product-image");
  if (options.showRecommendation && product.rank) {
    const rank = document.createElement("span");
    rank.className = "rank-badge";
    rank.textContent = `#${Number(product.rank)}`;
    imageBox.appendChild(rank);
  }

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

  if (options.showRecommendation && product.recommendation_reason) {
    const reason = document.createElement("p");
    reason.className = "recommendation-reason";
    reason.innerHTML = `<strong>Perché compare:</strong> ${escapeHtml(product.recommendation_reason)}`;
    body.appendChild(reason);
  }

  if (options.showRoleReason && product.role_reason) {
    const reason = document.createElement("p");
    reason.className = "ai-reason";
    reason.innerHTML = `<strong>Perché qui:</strong> ${escapeHtml(product.role_reason)}`;
    body.appendChild(reason);
  }

  if (options.showEvidence) {
    body.appendChild(createEvidenceBlock(product));
  }

  const button = document.createElement("button");
  button.className = "secondary-button";
  button.type = "button";
  button.textContent = "Vedi prodotto";
  button.addEventListener("click", () => {
    const detailParams = new URLSearchParams({
      id: product.item_id,
      profile: state.currentProfileId,
      v: "profiles-gemini-3",
    });
    const homeParams = new URLSearchParams(window.location.search);
    ["q", "view", "sort", "intent"].forEach((key) => {
      if (homeParams.get(key)) {
        detailParams.set(key, homeParams.get(key));
      }
    });
    window.location.href = `product.html?${detailParams.toString()}`;
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
    wrapper.querySelector("img")?.remove();
    wrapper.prepend(createPlaceholder());
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
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
