//URL base del backend FastAPI
const BASE_API_URL = "http://localhost:8000";

//stato minimale condiviso dalla pagina catalogo
const state = {
  categories: [],
  currentProducts: [],
  priceFilterActive: false,
  aiSearch: null,
};

//scegliamo quale pagina inizializzare in base al data attribute
document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  //home catalogo
  if (page === "catalog") {
    initCatalogPage();
  }
  //pagina dettaglio prodotto
  if (page === "product") {
    initProductPage();
  }
});

//inizializza catalogo,categorie e listener della ricerca
async function initCatalogPage() {
  await loadCategories();
  await Promise.all([loadInitialProducts(), loadPopularProducts()]);

  //click sul bottone Cerca
  document.getElementById("searchButton").addEventListener("click", runSearch);
  //invio nella barra di ricerca
  document.getElementById("searchInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      runSearch();
    }
  });
  document.getElementById("aiQuestionInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      runSearch();
    }
  });
  //cambio categoria
  document.getElementById("categorySelect").addEventListener("change", runSearch);
  //cambio ordinamento
  document.getElementById("sortSelect").addEventListener("change", applyCatalogFilters);
  //slider prezzo minimo
  document.getElementById("minPriceInput").addEventListener("input", () => {
    syncPriceRange("min");
    applyCatalogFilters();
  });
  //slider prezzo massimo
  document.getElementById("maxPriceInput").addEventListener("input", () => {
    syncPriceRange("max");
    applyCatalogFilters();
  });
  //filtro rating minimo
  document.getElementById("minRatingSelect").addEventListener("change", applyCatalogFilters);
  //filtro recensioni minime
  document.getElementById("minReviewsInput").addEventListener("input", applyCatalogFilters);
  //reset filtri laterali
  document.getElementById("resetFiltersButton").addEventListener("click", resetFilters);
}

//inizializza la pagina dettaglio leggendo item_id dalla query string
async function initProductPage() {
  const params = new URLSearchParams(window.location.search);
  const itemId = params.get("id");
  //senza id non possiamo caricare il prodotto
  if (!itemId) {
    renderMessage("productDetail", "Prodotto non specificato.");
    return;
  }

  await Promise.all([loadProductDetail(itemId), loadRecommendations()]);
}

//wrapper semplice per chiamate GET al backend
async function fetchJson(path) {
  const response = await fetch(`${BASE_API_URL}${path}`);
  //gestiamo errori HTTP come eccezioni
  if (!response.ok) {
    throw new Error(`Errore API: ${response.status}`);
  }
  return response.json();
}

//wrapper per chiamate POST JSON al backend
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

//carica categorie e popola il filtro select
async function loadCategories() {
  try {
    state.categories = await fetchJson("/categories");
    const select = document.getElementById("categorySelect");
    //creiamo una option per ogni categoria
    state.categories.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.category;
      option.textContent = `${item.category} (${item.count})`;
      select.appendChild(option);
    });
  } catch (error) {
    //manteniamo il frontend utilizzabile anche senza categorie
    console.error(error);
  }
}

//carica i primi prodotti del catalogo
async function loadInitialProducts() {
  await runSearch();
}

//carica la sezione prodotti popolari
async function loadPopularProducts() {
  try {
    const products = await fetchJson("/popular?limit=12");
    renderProducts("popularGrid", products);
  } catch (error) {
    renderMessage("popularGrid", "Prodotti popolari non disponibili.");
  }
}

//esegue ricerca testuale con eventuale filtro categoria
async function runSearch() {
  const query = document.getElementById("searchInput").value.trim();
  const question = document.getElementById("aiQuestionInput").value.trim();
  const category = document.getElementById("categorySelect").value;
  const params = new URLSearchParams({ q: query, limit: "500" });
  //aggiungiamo categoria solo se selezionata
  if (category) {
    params.set("category", category);
  }

  try {
    state.aiSearch = null;
    const products = question
      ? await runAiSearch(query, question, category)
      : await fetchJson(`/search?${params.toString()}`);
    state.currentProducts = products;
    state.priceFilterActive = false;
    updatePriceControls(products);
    applyCatalogFilters();
  } catch (error) {
    renderMessage("resultsGrid", "Ricerca non disponibile.");
  }
}

//usa Gemini solo quando l'utente ha scritto una domanda/esigenza
async function runAiSearch(query, question, category) {
  try {
    const response = await postJson("/ai-search", {
      query,
      question,
      category: category || null,
      limit: 30,
    });
    state.aiSearch = {
      answer: response.answer,
      fallback: Boolean(response.fallback),
    };
    return response.results || [];
  } catch (error) {
    console.error(error);
    state.aiSearch = {
      answer: "Ricerca AI non disponibile, mostrati risultati locali.",
      fallback: true,
    };
    const params = new URLSearchParams({ q: query, limit: "500" });
    if (category) {
      params.set("category", category);
    }
    return fetchJson(`/search?${params.toString()}`);
  }
}

//applica filtri e ordinamento lato frontend
function applyCatalogFilters() {
  let products = [...state.currentProducts];
  const minRating = Number(document.getElementById("minRatingSelect").value || 0);
  const minReviews = Number(document.getElementById("minReviewsInput").value || 0);

  if (state.priceFilterActive) {
    const minPrice = Number(document.getElementById("minPriceInput").value || 0);
    const maxPrice = Number(document.getElementById("maxPriceInput").value || 0);
    products = products.filter((product) => {
      const price = normalizePrice(product.price);
      return price !== null && price >= minPrice && price <= maxPrice;
    });
  }

  if (minRating > 0) {
    products = products.filter((product) => Number(product.average_rating || 0) >= minRating);
  }

  if (minReviews > 0) {
    products = products.filter((product) => Number(product.rating_count || 0) >= minReviews);
  }

  const sortMode = document.getElementById("sortSelect").value;
  if (!hasAiOrder(products) || sortMode !== "popularity_desc") {
    products = sortProducts(products, sortMode);
  }
  renderAiSearchNotice();
  renderProducts("resultsGrid", products);
  setResultsCount(products.length, state.currentProducts.length);
}

//riconosce risultati gia ordinati da Gemini
function hasAiOrder(products) {
  return products.some((product) => product.ai_score !== null && product.ai_score !== undefined);
}

//ordina i prodotti secondo la scelta utente
function sortProducts(products, sortMode) {
  const ordered = [...products];
  if (sortMode === "price_asc") {
    return ordered.sort((a, b) => priceForSort(a.price, false) - priceForSort(b.price, false));
  }
  if (sortMode === "price_desc") {
    return ordered.sort((a, b) => priceForSort(b.price, true) - priceForSort(a.price, true));
  }
  if (sortMode === "rating_desc") {
    return ordered.sort((a, b) => Number(b.average_rating || 0) - Number(a.average_rating || 0));
  }
  if (sortMode === "reviews_desc") {
    return ordered.sort((a, b) => Number(b.rating_count || 0) - Number(a.rating_count || 0));
  }
  return ordered.sort((a, b) => Number(b.popularity_score || 0) - Number(a.popularity_score || 0));
}

//normalizza prezzi mancanti o non numerici
function normalizePrice(value) {
  const price = Number(value);
  return Number.isFinite(price) && price > 0 ? price : null;
}

//mantiene i prodotti senza prezzo in fondo all'ordinamento
function priceForSort(value, desc) {
  const price = normalizePrice(value);
  if (price === null) {
    return desc ? -1 : Number.MAX_SAFE_INTEGER;
  }
  return price;
}

//aggiorna slider prezzo in base ai prodotti caricati
function updatePriceControls(products) {
  const minPriceInput = document.getElementById("minPriceInput");
  const maxPriceInput = document.getElementById("maxPriceInput");
  const prices = products.map((product) => normalizePrice(product.price)).filter((price) => price !== null);

  if (!prices.length) {
    minPriceInput.disabled = true;
    maxPriceInput.disabled = true;
    minPriceInput.value = "0";
    maxPriceInput.value = "0";
    updatePriceLabel(null, null);
    return;
  }

  const minPrice = Math.floor(Math.min(...prices));
  const maxPrice = Math.ceil(Math.max(...prices));
  [minPriceInput, maxPriceInput].forEach((input) => {
    input.disabled = false;
    input.min = String(minPrice);
    input.max = String(maxPrice);
    input.step = "1";
  });
  minPriceInput.value = String(minPrice);
  maxPriceInput.value = String(maxPrice);
  updatePriceLabel(minPrice, maxPrice);
}

//sincronizza i due slider del prezzo
function syncPriceRange(changedInput) {
  const minPriceInput = document.getElementById("minPriceInput");
  const maxPriceInput = document.getElementById("maxPriceInput");
  let minPrice = Number(minPriceInput.value);
  let maxPrice = Number(maxPriceInput.value);

  if (minPrice > maxPrice && changedInput === "min") {
    maxPrice = minPrice;
    maxPriceInput.value = String(maxPrice);
  }
  if (maxPrice < minPrice && changedInput === "max") {
    minPrice = maxPrice;
    minPriceInput.value = String(minPrice);
  }

  state.priceFilterActive = true;
  updatePriceLabel(minPrice, maxPrice);
}

//aggiorna etichetta del range prezzo
function updatePriceLabel(minPrice, maxPrice) {
  const label = document.getElementById("priceRangeLabel");
  if (minPrice === null || maxPrice === null) {
    label.textContent = "N/D";
    return;
  }
  label.textContent = `${formatPrice(minPrice)} - ${formatPrice(maxPrice)}`;
}

//riporta i filtri al valore iniziale
function resetFilters() {
  document.getElementById("searchInput").value = "";
  document.getElementById("aiQuestionInput").value = "";
  document.getElementById("categorySelect").value = "";
  document.getElementById("sortSelect").value = "popularity_desc";
  document.getElementById("minRatingSelect").value = "0";
  document.getElementById("minReviewsInput").value = "";
  runSearch();
}

//carica e renderizza il dettaglio prodotto
async function loadProductDetail(itemId) {
  try {
    const product = await fetchJson(`/products/${encodeURIComponent(itemId)}`);
    renderProductDetail(product);
  } catch (error) {
    renderMessage("productDetail", "Prodotto non trovato.");
  }
}

//carica raccomandazioni usando i prodotti popolari
async function loadRecommendations() {
  try {
    const products = await fetchJson("/popular?limit=8");
    renderProducts("recommendationsGrid", products);
  } catch (error) {
    renderMessage("recommendationsGrid", "Consigli non disponibili.");
  }
}

//renderizza una lista di prodotti in una griglia
function renderProducts(containerId, products) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  //stato vuoto
  if (!products.length) {
    renderMessage(containerId, "Nessun prodotto trovato.");
    return;
  }

  //creiamo una card per ogni prodotto
  products.forEach((product) => {
    container.appendChild(createProductCard(product));
  });
}

//mostra risposta AI o avviso fallback sopra la griglia risultati
function renderAiSearchNotice() {
  const notice = document.getElementById("aiSearchNotice");
  if (!notice) {
    return;
  }
  if (!state.aiSearch) {
    notice.classList.add("hidden");
    notice.innerHTML = "";
    return;
  }

  const title = state.aiSearch.fallback ? "Avviso" : "Risposta AI";
  notice.className = state.aiSearch.fallback
    ? "ai-search-notice fallback"
    : "ai-search-notice";
  notice.innerHTML = `
    <strong>${escapeHtml(title)}</strong>
    <p>${escapeHtml(state.aiSearch.answer || "")}</p>
  `;
}

//crea una card prodotto riutilizzabile
function createProductCard(product) {
  const card = document.createElement("article");
  card.className = "product-card";

  const imageBox = createImageBox(product, "product-image");

  //corpo card con metadati principali
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

  if (product.ai_reason) {
    const reason = document.createElement("p");
    reason.className = "ai-reason";
    reason.innerHTML = `<strong>Perche consigliato:</strong> ${escapeHtml(product.ai_reason)}`;
    body.appendChild(reason);
  }

  //bottone verso pagina dettaglio
  const button = document.createElement("button");
  button.className = "secondary-button";
  button.type = "button";
  button.textContent = "Dettagli";
  button.addEventListener("click", () => {
    window.location.href = `product.html?id=${encodeURIComponent(product.item_id)}`;
  });

  body.appendChild(button);
  card.appendChild(imageBox);
  card.appendChild(body);
  return card;
}

//renderizza la pagina dettaglio prodotto
function renderProductDetail(product) {
  const container = document.getElementById("productDetail");
  container.innerHTML = "";

  const imageBox = createImageBox(product, "detail-image");
  //informazioni testuali e statistiche del prodotto
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

//crea box immagine con fallback
function createImageBox(product, className) {
  const wrapper = document.createElement("div");
  wrapper.className = className;

  //nessun URL immagine
  if (!product.image_url) {
    wrapper.appendChild(createPlaceholder());
    return wrapper;
  }

  //immagine prodotto remota
  const image = document.createElement("img");
  image.src = product.image_url;
  image.alt = product.title;
  image.loading = "lazy";
  //fallback se il caricamento immagine fallisce
  image.addEventListener("error", () => {
    wrapper.innerHTML = "";
    wrapper.appendChild(createPlaceholder());
  });
  wrapper.appendChild(image);
  return wrapper;
}

//placeholder grafico quando manca l'immagine
function createPlaceholder() {
  const placeholder = document.createElement("div");
  placeholder.className = "image-placeholder";
  placeholder.textContent = "Immagine non disponibile";
  return placeholder;
}

//mostra messaggi vuoti o errori in una sezione
function renderMessage(containerId, message) {
  const container = document.getElementById(containerId);
  container.innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
}

//aggiorna il contatore dei risultati
function setResultsCount(count, total) {
  if (total && total !== count) {
    document.getElementById("resultsCount").textContent = `${count} di ${total} prodotti`;
    return;
  }
  document.getElementById("resultsCount").textContent = `${count} prodotti`;
}

//formatta il rating medio
function formatRating(value) {
  const number = Number(value || 0);
  return number > 0 ? number.toFixed(1) : "N/D";
}

//formatta il prezzo prodotto
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

//classe CSS diversa quando manca il prezzo
function priceClassName(value) {
  return normalizePrice(value) === null ? "price-row muted-price" : "price-row";
}

//escapa testo prima di inserirlo in HTML
function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
