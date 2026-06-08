//URL base del backend FastAPI
const BASE_API_URL = "http://localhost:8000";

//Stato minimale condiviso dalla pagina catalogo
//Tiene separati prodotti correnti,ricerca AI e cluster per non perdere i dati originali
//I filtri frontend lavorano su currentProducts senza richiamare sempre il backend
const state = {
  categories: [],
  currentProducts: [],
  priceFilterActive: false,
  aiSearch: null,
  clusteredSearch: null,
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

//Inizializza catalogo,categorie e listener della ricerca
//Carica dati iniziali in parallelo dove possibile
//Poi collega tutti i controlli della UI alle funzioni di filtro/ricerca
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
  //attiva/disattiva clustering dei risultati lato backend
  document.getElementById("clusterSearchCheckbox").addEventListener("change", runSearch);
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
    disableProductQa();
    return;
  }

  setupProductQa(itemId);
  await Promise.all([loadProductDetail(itemId), loadRecommendations()]);
}

//Wrapper semplice per chiamate GET al backend
//Centralizza gestione errori HTTP
//Chi chiama puo usare try/catch senza duplicare controlli response.ok
async function fetchJson(path) {
  const response = await fetch(`${BASE_API_URL}${path}`);
  //gestiamo errori HTTP come eccezioni
  if (!response.ok) {
    throw new Error(`Errore API: ${response.status}`);
  }
  return response.json();
}

//Wrapper per chiamate POST JSON al backend
//Converte il body in JSON e imposta Content-Type
//Viene usato per AI search,clustering e QA prodotto
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

//Esegue ricerca testuale con eventuale filtro categoria
//Se il clustering e attivo chiama endpoint cluster,altrimenti ricerca locale o AI
//Dopo ogni ricerca resetta filtri prezzo per allinearli ai nuovi risultati
async function runSearch() {
  const query = document.getElementById("searchInput").value.trim();
  const question = document.getElementById("aiQuestionInput").value.trim();
  const category = document.getElementById("categorySelect").value;
  const clusteringEnabled = document.getElementById("clusterSearchCheckbox").checked;
  const params = new URLSearchParams({ q: query, limit: "500" }); //costruisce query string sicura
  //aggiungiamo categoria solo se selezionata
  if (category) {
    params.set("category", category);
  }

  try {
    state.aiSearch = null; //cancella avviso AI precedente
    state.clusteredSearch = null; //cancella cluster precedente
    let products = [];
    if (clusteringEnabled) {
      state.clusteredSearch = await runClusteredSearch(query, category);
      products = flattenClusterProducts(state.clusteredSearch); //serve per riusare filtri prezzo/rating
    } else {
      products = question
        ? await runAiSearch(query, question, category)
        : await fetchJson(`/search?${params.toString()}`);
    }
    state.currentProducts = products;
    state.priceFilterActive = false;
    updatePriceControls(products); //ricalcola min/max slider sui nuovi risultati
    applyCatalogFilters();
  } catch (error) {
    renderMessage("resultsGrid", "Ricerca non disponibile.");
  }
}

//Usa Gemini solo quando l'utente ha scritto una domanda/esigenza
//Il backend prova AI ma puo rispondere fallback locale
//Se anche la POST fallisce,torniamo alla ricerca GET semplice
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
      fallback: Boolean(response.fallback), //normalizza valore per classi CSS/avviso
    };
    return response.results || [];
  } catch (error) {
    console.error(error);
    state.aiSearch = {
      answer: "Ricerca AI non disponibile, mostrati risultati locali.",
      fallback: true,
    };
    const params = new URLSearchParams({ q: query, limit: "500" }); //fallback locale con stessi filtri base
    if (category) {
      params.set("category", category);
    }
    return fetchJson(`/search?${params.toString()}`);
  }
}

//richiede al backend cluster calcolati sui risultati della ricerca locale
async function runClusteredSearch(query, category) {
  return postJson("/search/clustered", {
    query,
    category: category || null,
    limit: 500,
    use_ai_labels: true,
  });
}

//Appiattiamo solo per riusare filtri prezzo/rating gia presenti nel frontend
//I cluster originali restano in state.clusteredSearch
//Quando renderizziamo,ricostruiamo i cluster filtrando solo prodotti visibili
function flattenClusterProducts(clusteredSearch) {
  const clusters = clusteredSearch.clusters || [];
  return clusters.flatMap((cluster) => cluster.products || []);
}

//Applica filtri e ordinamento lato frontend
//Lavora sempre su una copia per non alterare state.currentProducts
//Se c'e ordine AI e sort e popularity_desc,conserviamo l'ordine suggerito
function applyCatalogFilters() {
  let products = [...state.currentProducts];
  const minRating = Number(document.getElementById("minRatingSelect").value || 0);
  const minReviews = Number(document.getElementById("minReviewsInput").value || 0);

  if (state.priceFilterActive) {
    const minPrice = Number(document.getElementById("minPriceInput").value || 0);
    const maxPrice = Number(document.getElementById("maxPriceInput").value || 0);
    products = products.filter((product) => {
      const price = normalizePrice(product.price); //normalizza prima di confrontare range
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
  if (!hasAiOrder(products) || sortMode !== "popularity_desc") { //non sovrascrive ranking AI di default
    products = sortProducts(products, sortMode);
  }
  renderAiSearchNotice();
  if (state.clusteredSearch) {
    const clusters = filterAndSortClusters(state.clusteredSearch.clusters || [], products, sortMode);
    renderClusters("resultsGrid", clusters);
  } else {
    renderProducts("resultsGrid", products);
  }
  setResultsCount(products.length, state.currentProducts.length);
}

//Applica filtri e ordinamento ai prodotti interni a ogni cluster
//Usa visibleIds per mantenere solo i prodotti sopravvissuti ai filtri
//Elimina cluster diventati vuoti dopo filtri prezzo/rating
function filterAndSortClusters(clusters, visibleProducts, sortMode) {
  const visibleIds = new Set(visibleProducts.map((product) => product.item_id)); //lookup veloce per id visibili
  return clusters
    .map((cluster) => {
      const products = (cluster.products || []).filter((product) => visibleIds.has(product.item_id));
      return {
        ...cluster,
        products: sortProducts(products, sortMode),
      };
    })
    .filter((cluster) => cluster.products.length > 0);
}

//riconosce risultati gia ordinati da Gemini
function hasAiOrder(products) {
  return products.some((product) => product.ai_score !== null && product.ai_score !== undefined);
}

//Ordina i prodotti secondo la scelta utente
//Crea una copia per non mutare l'array ricevuto
//I prezzi mancanti sono gestiti da priceForSort
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

//Aggiorna slider prezzo in base ai prodotti caricati
//Usa solo prezzi validi,cosi prodotti senza prezzo non falsano il range
//Se non ci sono prezzi,disabilita i controlli
function updatePriceControls(products) {
  const minPriceInput = document.getElementById("minPriceInput");
  const maxPriceInput = document.getElementById("maxPriceInput");
  const prices = products.map((product) => normalizePrice(product.price)).filter((price) => price !== null); //scarta null prima di min/max

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
  [minPriceInput, maxPriceInput].forEach((input) => { //sincronizza attributi comuni dei due slider
    input.disabled = false;
    input.min = String(minPrice);
    input.max = String(maxPrice);
    input.step = "1";
  });
  minPriceInput.value = String(minPrice);
  maxPriceInput.value = String(maxPrice);
  updatePriceLabel(minPrice, maxPrice);
}

//Sincronizza i due slider del prezzo
//Impedisce che il minimo superi il massimo o viceversa
//Attiva il filtro prezzo solo dopo interazione utente
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
  document.getElementById("clusterSearchCheckbox").checked = false;
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
    disableProductQa();
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

//collega la form QA al prodotto corrente
function setupProductQa(itemId) {
  const form = document.getElementById("qaForm");
  if (!form) {
    return;
  }
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    askProductQuestion(itemId);
  });
}

function disableProductQa() {
  const section = document.querySelector(".qa-section");
  if (section) {
    section.classList.add("hidden");
  }
}

//Invia una domanda grounded al backend
//Il backend recupera evidenze solo per il prodotto corrente
//finally spegne sempre lo stato loading,anche in caso di errore
async function askProductQuestion(itemId) {
  const input = document.getElementById("qaQuestionInput");
  const question = input.value.trim();
  if (!question) {
    renderQaError("Scrivi una domanda sul prodotto.");
    return;
  }

  setQaLoading(true);
  try {
    const response = await postJson(`/products/${encodeURIComponent(itemId)}/qa`, {
      question,
      use_ai: true,
    });
    renderProductQaResponse(response);
  } catch (error) {
    console.error(error);
    renderQaError("Risposta QA non disponibile.");
  } finally {
    setQaLoading(false);
  }
}

function setQaLoading(isLoading) {
  const button = document.getElementById("qaSubmitButton");
  if (!button) {
    return;
  }
  button.disabled = isLoading;
  button.textContent = isLoading ? "Caricamento..." : "Chiedi";
}

//Mostra risposta ed evidenze usate dal backend
//La confidence controlla il colore del box risposta
//Tutti i testi dinamici passano da escapeHtml prima di entrare nell'HTML
function renderProductQaResponse(response) {
  const answerBox = document.getElementById("qaAnswer");
  const evidenceBox = document.getElementById("qaEvidence");
  const confidence = ["low", "medium", "high"].includes(response.confidence) //valida classe CSS attesa
    ? response.confidence
    : "low";
  answerBox.className = `qa-answer confidence-${confidence}`;
  answerBox.innerHTML = `
    <strong>Risposta</strong>
    <p>${escapeHtml(response.answer || "")}</p>
  `;

  const evidence = response.evidence || [];
  evidenceBox.className = "qa-evidence";
  if (!evidence.length) {
    evidenceBox.innerHTML = "<p>Nessuna evidenza specifica recuperata.</p>";
    return;
  }

  evidenceBox.innerHTML = `
    <h3>Evidenze usate</h3>
    <div class="evidence-list">
      ${evidence.map((item) => ` //template sicuro perche i campi testuali sono escapati
        <article class="evidence-item">
          <div class="evidence-meta">
            <span>${escapeHtml(item.source)}</span>
            <span>score ${Number(item.score || 0).toFixed(2)}</span>
          </div>
          <p>${escapeHtml(item.text)}</p>
        </article>
      `).join("")}
    </div>
  `;
}

function renderQaError(message) {
  const answerBox = document.getElementById("qaAnswer");
  const evidenceBox = document.getElementById("qaEvidence");
  answerBox.className = "qa-answer confidence-low";
  answerBox.innerHTML = `<strong>Avviso</strong><p>${escapeHtml(message)}</p>`;
  evidenceBox.className = "qa-evidence hidden";
  evidenceBox.innerHTML = "";
}

//renderizza una lista di prodotti in una griglia
function renderProducts(containerId, products) {
  const container = document.getElementById(containerId);
  if (containerId === "resultsGrid") {
    container.className = "product-grid";
  }
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

//Renderizza sezioni cluster con card prodotto cliccabili
//Ogni cluster ha heading,keyword e una griglia di card
//Le label possono arrivare da AI,quindi vengono sempre escapate
function renderClusters(containerId, clusters) {
  const container = document.getElementById(containerId);
  container.className = "cluster-results";
  container.innerHTML = "";

  if (!clusters.length) {
    renderMessage(containerId, "Nessun prodotto trovato.");
    return;
  }

  clusters.forEach((cluster) => {
    const section = document.createElement("section");
    section.className = "cluster-section";

    const heading = document.createElement("div");
    heading.className = "cluster-heading";
    heading.innerHTML = `
      <div>
        <h3>${escapeHtml(cluster.label)}</h3>
        <p>${escapeHtml(cluster.description || "")}</p>
      </div>
      <span class="cluster-size">${cluster.products.length} prodotti</span>
    `;

    const keywords = document.createElement("div");
    keywords.className = "cluster-keywords";
    (cluster.keywords || []).slice(0, 6).forEach((keyword) => { //limita chip per non appesantire UI
      const chip = document.createElement("span");
      chip.textContent = keyword;
      keywords.appendChild(chip);
    });

    const grid = document.createElement("div");
    grid.className = "product-grid cluster-grid";
    cluster.products.forEach((product) => {
      grid.appendChild(createProductCard(product));
    });

    section.appendChild(heading);
    if (keywords.children.length) {
      section.appendChild(keywords);
    }
    section.appendChild(grid);
    container.appendChild(section);
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

//Crea una card prodotto riutilizzabile
//Usa DOM API per struttura principale e escapeHtml per testo dinamico
//Il click naviga alla pagina dettaglio passando item_id in query string
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

//Escapa testo prima di inserirlo in HTML
//Serve per evitare che titoli/descrizioni del dataset vengano interpretati come markup
//Va usato ogni volta che una stringa dinamica entra in innerHTML
function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
