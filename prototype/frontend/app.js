// URL base del backend FastAPI
const BASE_API_URL="http://localhost:8000";

// Stato minimale condiviso dalla pagina catalogo
const state = {
  categories: [],
};

// Scegliamo quale pagina inizializzare in base al data attribute
document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  // Home catalogo
  if (page === "catalog") {
    initCatalogPage();
  }
  // Pagina dettaglio prodotto
  if (page === "product") {
    initProductPage();
  }
});

// Inizializza catalogo, categorie e listener della ricerca
async function initCatalogPage() {
  await loadCategories();
  await Promise.all([loadInitialProducts(), loadPopularProducts()]);

  // Click sul bottone Cerca
  document.getElementById("searchButton").addEventListener("click", runSearch);
  // Invio nella barra di ricerca
  document.getElementById("searchInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      runSearch();
    }
  });
  // Cambio categoria
  document.getElementById("categorySelect").addEventListener("change", runSearch);
}

// Inizializza la pagina dettaglio leggendo item_id dalla query string
async function initProductPage() {
  const params = new URLSearchParams(window.location.search);
  const itemId = params.get("id");
  // Senza id non possiamo caricare il prodotto
  if (!itemId) {
    renderMessage("productDetail", "Prodotto non specificato.");
    return;
  }

  await Promise.all([loadProductDetail(itemId), loadRecommendations()]);
}

// Wrapper semplice per chiamate GET al backend
async function fetchJson(path) {
  const response = await fetch(`${BASE_API_URL}${path}`);
  // Gestiamo errori HTTP come eccezioni
  if (!response.ok) {
    throw new Error(`Errore API: ${response.status}`);
  }
  return response.json();
}

// Carica categorie e popola il filtro select
async function loadCategories() {
  try {
    state.categories = await fetchJson("/categories");
    const select = document.getElementById("categorySelect");
    // Creiamo una option per ogni categoria
    state.categories.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.category;
      option.textContent = `${item.category} (${item.count})`;
      select.appendChild(option);
    });
  } catch (error) {
    // Manteniamo il frontend utilizzabile anche senza categorie
    console.error(error);
  }
}

// Carica i primi prodotti del catalogo
async function loadInitialProducts() {
  try {
    const products = await fetchJson("/products?limit=30");
    renderProducts("resultsGrid", products);
    setResultsCount(products.length);
  } catch (error) {
    renderMessage("resultsGrid", "Backend non raggiungibile. Avvia FastAPI sulla porta 8000.");
  }
}

// Carica la sezione prodotti popolari
async function loadPopularProducts() {
  try {
    const products = await fetchJson("/popular?limit=12");
    renderProducts("popularGrid", products);
  } catch (error) {
    renderMessage("popularGrid", "Prodotti popolari non disponibili.");
  }
}

// Esegue ricerca testuale con eventuale filtro categoria
async function runSearch() {
  const query = document.getElementById("searchInput").value.trim();
  const category = document.getElementById("categorySelect").value;
  const params = new URLSearchParams({ q: query, limit: "30" });
  // Aggiungiamo categoria solo se selezionata
  if (category) {
    params.set("category", category);
  }

  try {
    const products = await fetchJson(`/search?${params.toString()}`);
    renderProducts("resultsGrid", products);
    setResultsCount(products.length);
  } catch (error) {
    renderMessage("resultsGrid", "Ricerca non disponibile.");
  }
}

// Carica e renderizza il dettaglio prodotto
async function loadProductDetail(itemId) {
  try {
    const product = await fetchJson(`/products/${encodeURIComponent(itemId)}`);
    renderProductDetail(product);
  } catch (error) {
    renderMessage("productDetail", "Prodotto non trovato.");
  }
}

// Carica raccomandazioni MostPopular
async function loadRecommendations() {
  try {
    const products = await fetchJson("/recommendations/popular?limit=8");
    renderProducts("recommendationsGrid", products);
  } catch (error) {
    renderMessage("recommendationsGrid", "Consigli non disponibili.");
  }
}

// Renderizza una lista di prodotti in una griglia
function renderProducts(containerId, products) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";

  // Stato vuoto
  if (!products.length) {
    renderMessage(containerId, "Nessun prodotto trovato.");
    return;
  }

  // Creiamo una card per ogni prodotto
  products.forEach((product) => {
    container.appendChild(createProductCard(product));
  });
}

// Crea una card prodotto riutilizzabile
function createProductCard(product) {
  const card = document.createElement("article");
  card.className = "product-card";

  const imageBox = createImageBox(product, "product-image");

  // Corpo card con metadati principali
  const body = document.createElement("div");
  body.className = "card-body";
  body.innerHTML = `
    <p class="category">${escapeHtml(product.category)}</p>
    <h3>${escapeHtml(product.title)}</h3>
    <div class="meta-row">
      <span>Rating ${formatRating(product.average_rating)}</span>
      <span>${Number(product.rating_count || 0).toLocaleString("it-IT")} recensioni</span>
    </div>
  `;

  // Bottone verso pagina dettaglio
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

// Renderizza la pagina dettaglio prodotto
function renderProductDetail(product) {
  const container = document.getElementById("productDetail");
  container.innerHTML = "";

  const imageBox = createImageBox(product, "detail-image");
  // Informazioni testuali e statistiche del prodotto
  const info = document.createElement("div");
  info.className = "detail-info";
  info.innerHTML = `
    <p class="category">${escapeHtml(product.category)}</p>
    <h2>${escapeHtml(product.title)}</h2>
    <p class="description">${escapeHtml(product.description || "Descrizione non disponibile.")}</p>
    <dl class="stats">
      <div><dt>Average rating</dt><dd>${formatRating(product.average_rating)}</dd></div>
      <div><dt>Rating count</dt><dd>${Number(product.rating_count || 0).toLocaleString("it-IT")}</dd></div>
      <div><dt>Popularity score</dt><dd>${Number(product.popularity_score || 0).toFixed(4)}</dd></div>
    </dl>
  `;

  container.appendChild(imageBox);
  container.appendChild(info);
}

// Crea box immagine con fallback
function createImageBox(product, className) {
  const wrapper = document.createElement("div");
  wrapper.className = className;

  // Nessun URL immagine
  if (!product.image_url) {
    wrapper.appendChild(createPlaceholder());
    return wrapper;
  }

  // Immagine prodotto remota
  const image = document.createElement("img");
  image.src = product.image_url;
  image.alt = product.title;
  image.loading = "lazy";
  // Fallback se il caricamento immagine fallisce
  image.addEventListener("error", () => {
    wrapper.innerHTML = "";
    wrapper.appendChild(createPlaceholder());
  });
  wrapper.appendChild(image);
  return wrapper;
}

// Placeholder grafico quando manca l'immagine
function createPlaceholder() {
  const placeholder = document.createElement("div");
  placeholder.className = "image-placeholder";
  placeholder.textContent = "Immagine non disponibile";
  return placeholder;
}

// Mostra messaggi vuoti o errori in una sezione
function renderMessage(containerId, message) {
  const container = document.getElementById(containerId);
  container.innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
}

// Aggiorna il contatore dei risultati
function setResultsCount(count) {
  document.getElementById("resultsCount").textContent = `${count} prodotti`;
}

// Formatta il rating medio
function formatRating(value) {
  const number = Number(value || 0);
  return number > 0 ? number.toFixed(1) : "N/D";
}

// Escapa testo prima di inserirlo in HTML
function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
