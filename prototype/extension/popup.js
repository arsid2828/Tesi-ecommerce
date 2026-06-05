const BACKEND_URL = "http://localhost:8000";
const PRODUCT_PAGE_ORIGIN = "http://localhost:3000";

const popupState = {
  itemId: null,
};

document.addEventListener("DOMContentLoaded", initPopup);

//inizializza popup,tab attiva e dati demo
async function initPopup() {
  const tab = await getActiveTab();
  const currentUrl = tab && tab.url ? tab.url : "";

  setText("currentUrl", currentUrl || "URL non disponibile");
  updateProductPageState(currentUrl);

  document.getElementById("loadProductButton").addEventListener("click", loadCurrentProduct);

  await Promise.all([checkBackendStatus(), loadRecommendations()]);
}

//legge la tab attiva usando API Chrome
function getActiveTab() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      resolve(tabs && tabs.length ? tabs[0] : null);
    });
  });
}

//controlla se la URL appartiene alla pagina dettaglio locale
function updateProductPageState(currentUrl) {
  const itemId = getItemIdFromProductUrl(currentUrl);
  popupState.itemId = itemId;

  if (!itemId) {
    setText("productPageStatus", "Non sei su una pagina prodotto locale.");
    setText("itemIdValue", "item_id non rilevato");
    document.getElementById("loadProductButton").disabled = true;
    return;
  }

  setText("productPageStatus", "Pagina prodotto locale rilevata.");
  setText("itemIdValue", itemId);
  document.getElementById("loadProductButton").disabled = false;
}

//estrae item_id solo dalla pagina product.html locale
function getItemIdFromProductUrl(currentUrl) {
  try {
    const url = new URL(currentUrl);
    if (url.origin !== PRODUCT_PAGE_ORIGIN || !url.pathname.endsWith("/product.html")) {
      return null;
    }
    const params = new URLSearchParams(url.search);
    return params.get("id");
  } catch (error) {
    return null;
  }
}

//wrapper GET per il backend locale
async function fetchBackend(path) {
  const response = await fetch(`${BACKEND_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Errore API: ${response.status}`);
  }
  return response.json();
}

//mostra lo stato del backend nel popup
async function checkBackendStatus() {
  const status = document.getElementById("backendStatus");
  try {
    await fetchBackend("/health");
    status.textContent = "Backend online";
    status.className = "status-pill status-online";
  } catch (error) {
    status.textContent = "Backend non raggiungibile";
    status.className = "status-pill status-offline";
  }
}

//carica dettaglio prodotto quando disponibile un item_id
async function loadCurrentProduct() {
  const result = document.getElementById("productResult");
  if (!popupState.itemId) {
    result.textContent = "Apri una pagina prodotto locale prima di caricare il prodotto.";
    result.className = "result-box error-text";
    return;
  }

  result.textContent = "Caricamento prodotto...";
  result.className = "result-box muted-text";

  try {
    const product = await fetchBackend(`/products/${encodeURIComponent(popupState.itemId)}`);
    renderProduct(product);
  } catch (error) {
    result.textContent = "Prodotto non disponibile. Controlla che il backend sia acceso.";
    result.className = "result-box error-text";
  }
}

//renderizza dettaglio prodotto usando solo nodi DOM
function renderProduct(product) {
  const result = document.getElementById("productResult");
  result.innerHTML = "";
  result.className = "result-box";

  const layout = document.createElement("div");
  layout.className = "popup-product-layout";

  const imageBox = createProductImage(product, "popup-product-image");
  const info = document.createElement("div");
  info.className = "popup-product-info";

  const title = document.createElement("h2");
  title.textContent = product.title || "Titolo non disponibile";

  const category = document.createElement("p");
  category.className = "category-line";
  category.textContent = product.category || "Categoria non disponibile";

  const rating = document.createElement("p");
  rating.textContent = `Rating medio: ${formatRating(product.average_rating)}`;

  const reviews = document.createElement("p");
  reviews.textContent = `Recensioni: ${Number(product.rating_count || 0).toLocaleString("it-IT")}`;

  info.appendChild(category);
  info.appendChild(title);
  info.appendChild(rating);
  info.appendChild(reviews);
  layout.appendChild(imageBox);
  layout.appendChild(info);
  result.appendChild(layout);
}

//carica raccomandazioni baseline con fallback su /popular
async function loadRecommendations() {
  const status = document.getElementById("recommendationsStatus");
  try {
    const products = await fetchRecommendations();
    renderRecommendations(products);
    status.textContent = `${products.length} prodotti`;
  } catch (error) {
    renderRecommendations([]);
    status.textContent = "Non disponibili";
  }
}

//usa endpoint semantico,se non esiste usa /popular
async function fetchRecommendations() {
  try {
    return await fetchBackend("/recommendations/popular?limit=5");
  } catch (error) {
    return fetchBackend("/popular?limit=5");
  }
}

//renderizza lista raccomandazioni senza HTML non sicuro
function renderRecommendations(products) {
  const list = document.getElementById("recommendationsList");
  list.innerHTML = "";

  if (!products.length) {
    const item = document.createElement("li");
    item.className = "empty-list-item";
    item.textContent = "Raccomandazioni non disponibili.";
    list.appendChild(item);
    return;
  }

  products.forEach((product) => {
    const item = document.createElement("li");
    item.className = "recommendation-item";

    const imageBox = createProductImage(product, "recommendation-image");
    const body = document.createElement("div");
    body.className = "recommendation-body";

    const title = document.createElement("span");
    const meta = document.createElement("small");

    title.textContent = product.title || "Prodotto senza titolo";
    meta.textContent = `${product.category || "Categoria N/D"} - rating ${formatRating(product.average_rating)}`;

    body.appendChild(title);
    body.appendChild(meta);
    item.appendChild(imageBox);
    item.appendChild(body);
    list.appendChild(item);
  });
}

//crea immagine prodotto con fallback
function createProductImage(product, className) {
  const wrapper = document.createElement("div");
  wrapper.className = className;

  if (!product.image_url) {
    wrapper.appendChild(createImagePlaceholder());
    return wrapper;
  }

  const image = document.createElement("img");
  image.src = product.image_url;
  image.alt = product.title || "Immagine prodotto";
  image.loading = "lazy";
  image.addEventListener("error", () => {
    wrapper.innerHTML = "";
    wrapper.appendChild(createImagePlaceholder());
  });

  wrapper.appendChild(image);
  return wrapper;
}

//placeholder quando manca l'immagine
function createImagePlaceholder() {
  const placeholder = document.createElement("div");
  placeholder.className = "image-placeholder";
  placeholder.textContent = "Immagine non disponibile";
  return placeholder;
}

//formatta rating medio
function formatRating(value) {
  const number = Number(value || 0);
  return number > 0 ? number.toFixed(1) : "N/D";
}

//assegna testo a un elemento
function setText(elementId, value) {
  document.getElementById(elementId).textContent = value;
}
