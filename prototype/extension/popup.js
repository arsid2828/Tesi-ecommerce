const BACKEND_URL = "http://localhost:8000";

const popupState = {
  itemId: null,
  amazonProduct: null,
};

document.addEventListener("DOMContentLoaded", initPopup);

//inizializza popup,tab attiva e dati demo
async function initPopup() {
  const tab = await getActiveTab();
  const currentUrl = tab && tab.url ? tab.url : "";

  setText("currentUrl", currentUrl || "URL non disponibile");
  document.getElementById("loadProductButton").addEventListener("click", loadCurrentProduct);

  await updateProductPageState(tab, currentUrl);
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

//controlla se la tab contiene una pagina prodotto locale o Amazon
async function updateProductPageState(tab, currentUrl) {
  const product = await detectActiveProduct(tab, currentUrl);
  const button = document.getElementById("loadProductButton");
  popupState.itemId = null;
  popupState.amazonProduct = null;
  button.textContent = "Carica prodotto";

  if (!product) {
    setText("productPageStatus", "Non sei su una pagina prodotto riconosciuta.");
    setText("itemIdValue", "item_id/ASIN non rilevato");
    button.disabled = true;
    setResultText("Apri una pagina prodotto locale o Amazon.");
    return;
  }

  if (product.kind === "amazon") {
    popupState.amazonProduct = product;
    setText("productPageStatus", "Prodotto Amazon rilevato.");
    setText("itemIdValue", `ASIN: ${product.asin}`);
    button.textContent = "Solo riconoscimento";
    button.disabled = true;
    renderAmazonProduct(product);
    return;
  }

  popupState.itemId = product.itemId;
  setText("productPageStatus", "Pagina prodotto locale rilevata.");
  setText("itemIdValue", product.itemId);
  button.disabled = false;
  setResultText("Nessun prodotto caricato.");
}

//usa il detector URL e, quando possibile, integra i dati letti dal content script
async function detectActiveProduct(tab, currentUrl) {
  const urlProduct = window.ThesisProductDetector.detectFromUrl(currentUrl);
  const pageProduct = await requestDetectedProduct(tab);

  if (!pageProduct) {
    return urlProduct;
  }

  if (!urlProduct || urlProduct.kind === pageProduct.kind) {
    return {
      ...urlProduct,
      ...pageProduct,
    };
  }

  return urlProduct;
}

//richiede al content script i dati gia letti dalla pagina attiva
function requestDetectedProduct(tab) {
  return new Promise((resolve) => {
    if (!tab || typeof tab.id === "undefined" || !chrome.tabs || !chrome.tabs.sendMessage) {
      resolve(null);
      return;
    }

    const timeoutId = setTimeout(() => resolve(null), 500);
    chrome.tabs.sendMessage(tab.id, { type: "GET_DETECTED_PRODUCT" }, (response) => {
      clearTimeout(timeoutId);
      if (chrome.runtime.lastError || !response || !response.product) {
        resolve(null);
        return;
      }
      resolve(response.product);
    });
  });
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
  if (popupState.amazonProduct) {
    renderAmazonProduct(popupState.amazonProduct);
    return;
  }

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

//mostra il prodotto Amazon riconosciuto senza chiamare il backend
function renderAmazonProduct(product) {
  const result = document.getElementById("productResult");
  result.innerHTML = "";
  result.className = "result-box";

  const layout = document.createElement("div");
  layout.className = "popup-product-layout";

  const imageBox = createProductImage({
    image_url: product.imageUrl,
    title: product.title || product.asin,
  }, "popup-product-image");

  const info = document.createElement("div");
  info.className = "popup-product-info";

  const source = document.createElement("p");
  source.className = "category-line";
  source.textContent = "Amazon reale";

  const title = document.createElement("h2");
  title.textContent = product.title || "Titolo non disponibile";

  const asin = document.createElement("p");
  asin.textContent = `ASIN: ${product.asin}`;

  const note = document.createElement("p");
  note.className = "muted-text";
  note.textContent = "Riconoscimento prodotto attivo.";

  info.appendChild(source);
  info.appendChild(title);
  info.appendChild(asin);
  info.appendChild(note);
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

//assegna il testo al box risultato
function setResultText(value) {
  const result = document.getElementById("productResult");
  result.textContent = value;
  result.className = "result-box muted-text";
}
