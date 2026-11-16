// Popup Manifest V3 dell'estensione demo.
// Mostra prodotto corrente e consigli contestuali leggendo backend locale e content script.
const BACKEND_URL = "http://localhost:8000";
const LOCAL_ORIGIN = "http://localhost:3000";
const LOCAL_PRODUCT_URL = `${LOCAL_ORIGIN}/product.html`;
const DEFAULT_PRODUCT_IMAGE_URL = "placeholder-product.svg";

//Stato minimo del popup
//itemId vale per il prototipo locale,amazonProduct per Amazon reale
const popupState = {
  activeTab: null,
  itemId: null,
  amazonProduct: null,
  amazonCandidates: [],
};

document.addEventListener("DOMContentLoaded", initPopup);

// Punto di ingresso del popup.
// Legge la tab attiva, rileva il prodotto e carica stato backend + raccomandazioni.
async function initPopup() {
  const tab = await getActiveTab();
  popupState.activeTab = tab;
  const page = new URL(tab?.url || "about:blank");
  const productAndRecommendations = updateProductPageState(tab, page)
    .then(() => loadRecommendations(page.origin === LOCAL_ORIGIN));
  await Promise.all([checkBackendStatus(), productAndRecommendations]);
}

// Recupera la tab attiva nella finestra corrente.
// Wrappa chrome.tabs.query in Promise per usare async/await nel resto del popup.
function getActiveTab() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      resolve(tabs && tabs.length ? tabs[0] : null);
    });
  });
}

// Aggiorna lo stato UI in base al prodotto rilevato.
// Distingue pagina locale, pagina Amazon e pagina non riconosciuta.
async function updateProductPageState(tab, page) {
  const detection = await detectActiveProduct(tab, page.href);
  const product = detection.product;
  popupState.amazonCandidates = detection.amazonCandidates || [];

  if (!product) {
    const isLocal = page.origin === LOCAL_ORIGIN;
    const isAmazon = window.ThesisProductDetector.isAmazonHost(page.hostname);
    setText("productPageStatus", isLocal ? "Catalogo locale" : isAmazon ? "Amazon" : "Sito non supportato");
    setResultText(isLocal || isAmazon
      ? "Apri una scheda prodotto per vedere i consigli contestuali."
      : "Apri un prodotto del prototipo o di Amazon per usare l’estensione.");
    document.getElementById("recommendationsSection").classList.toggle("hidden", !isLocal);
    return;
  }

  if (product.kind === "amazon") {
    popupState.amazonProduct = product;
    setText("productPageStatus", "Pagina Amazon");
    renderAmazonProduct(product);
    return;
  }

  popupState.itemId = product.itemId;
  setText("productPageStatus", "Catalogo locale");
  await loadCurrentProduct();
}

// Combina rilevamento da URL e risposta del content script.
// Il DOM ha priorita quando fornisce titolo, immagine o candidati Amazon reali.
async function detectActiveProduct(tab, currentUrl) {
  const urlProduct = window.ThesisProductDetector.detectFromUrl(currentUrl);
  const pageData = await requestDetectedProduct(tab);
  const pageProduct = pageData.product;

  if (!pageProduct) {
    return {
      product: urlProduct,
      amazonCandidates: pageData.amazonCandidates || [],
    };
  }

  if (!urlProduct || urlProduct.kind === pageProduct.kind) {
    return {
      product: {
        ...urlProduct,
        ...pageProduct,
      },
      amazonCandidates: pageData.amazonCandidates || [],
    };
  }

  return {
    product: urlProduct,
    amazonCandidates: pageData.amazonCandidates || [],
  };
}

// Chiede al content script prodotto e candidati Amazon della pagina.
// Usa un timeout breve per non bloccare il popup se il content script non risponde.
function requestDetectedProduct(tab) {
  return new Promise((resolve) => {
    if (!tab || typeof tab.id === "undefined" || !chrome.tabs || !chrome.tabs.sendMessage) {
      resolve({ product: null, amazonCandidates: [] });
      return;
    }

    const timeoutId = setTimeout(() => resolve({ product: null, amazonCandidates: [] }), 700);
    chrome.tabs.sendMessage(tab.id, { type: "GET_DETECTED_PRODUCT" }, (response) => {
      clearTimeout(timeoutId);
      if (chrome.runtime.lastError || !response) {
        resolve({ product: null, amazonCandidates: [] });
        return;
      }
      resolve({
        product: response.product || null,
        amazonCandidates: Array.isArray(response.amazonCandidates) ? response.amazonCandidates : [],
      });
    });
  });
}

// Helper GET verso il backend locale.
// Centralizza errori HTTP per health check, dettagli e consigli.
async function fetchBackend(path) {
  const response = await fetch(`${BACKEND_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Errore API: ${response.status}`);
  }
  return response.json();
}

// Helper POST JSON verso il backend locale.
// Usato per organizzare candidati Amazon reali estratti dal DOM.
async function postBackend(path, body) {
  const response = await fetch(`${BACKEND_URL}${path}`, {
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

// Verifica se FastAPI e raggiungibile.
// Aggiorna il badge del popup senza interrompere eventuali fallback locali.
async function checkBackendStatus() {
  const status = document.getElementById("backendStatus");
  try {
    await fetchBackend("/health");
    status.textContent = "Backend online";
    status.className = "status-pill status-online";
  } catch (error) {
    status.textContent = "Backend offline";
    status.className = "status-pill status-offline";
  }
}

// Carica e mostra il prodotto corrente nel popup.
// Per Amazon usa i dati gia letti dalla pagina, per locale chiama /products/{item_id}.
async function loadCurrentProduct() {
  const result = document.getElementById("productResult");
  result.textContent = "Caricamento prodotto…";
  result.className = "result-box muted-text";

  try {
    const product = await fetchBackend(`/products/${encodeURIComponent(popupState.itemId)}`);
    renderProduct(product);
  } catch (error) {
    result.textContent = "Prodotto non disponibile. Controlla che il backend sia acceso e che il catalogo locale esista.";
    result.className = "result-box error-text";
  }
}

// Renderizza il prodotto del catalogo locale.
// Mostra immagine, categoria, titolo, item_id, rating e recensioni.
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
  title.title = title.textContent;

  const category = document.createElement("p");
  category.className = "category-line";
  category.textContent = product.category || "Categoria non disponibile";

  const stats = document.createElement("p");
  stats.className = "current-product-meta";
  stats.textContent = [
    formatPrice(product.price),
    `★ ${formatRating(product.average_rating)}`,
    `${Number(product.rating_count || 0).toLocaleString("it-IT")} recensioni`,
  ].filter(Boolean).join(" · ");

  const itemId = document.createElement("p");
  itemId.className = "product-id-line";
  itemId.textContent = `item_id: ${product.item_id}`;

  info.appendChild(category);
  info.appendChild(title);
  info.appendChild(itemId);
  info.appendChild(stats);
  layout.appendChild(imageBox);
  layout.appendChild(info);
  result.appendChild(layout);
}

// Renderizza il prodotto Amazon rilevato.
// Evidenzia ASIN e quanti candidati reali sono stati letti dalla pagina.
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
  source.textContent = "Dati della pagina";

  const title = document.createElement("h2");
  title.textContent = product.title || "Titolo non disponibile";
  title.title = title.textContent;

  const asin = document.createElement("p");
  asin.className = "product-id-line";
  asin.textContent = `ASIN: ${product.asin}`;

  const note = document.createElement("p");
  note.className = "muted-text";
  note.textContent = popupState.amazonCandidates.length
    ? `${popupState.amazonCandidates.length} candidati reali letti dalla pagina.`
    : "Nessun candidato reale leggibile nella pagina corrente.";

  info.appendChild(source);
  info.appendChild(title);
  info.appendChild(asin);
  info.appendChild(note);
  layout.appendChild(imageBox);
  layout.appendChild(info);
  result.appendChild(layout);
}

// Decide quale sorgente raccomandazioni caricare.
// Il catalogo locale puo mostrare i bestseller quando e aperta la home.
async function loadRecommendations(isLocalPage) {
  if (popupState.itemId) {
    await loadLocalRecommendations();
    return;
  }

  if (popupState.amazonProduct) {
    await loadAmazonRecommendations();
    return;
  }

  if (isLocalPage) {
    await loadPopularRecommendations();
  }
}

// Carica consigli contestuali per prodotto locale.
// Il backend sceglie prodotti solo dal catalogo demo e puo rifinire testi con Gemini.
async function loadLocalRecommendations() {
  const status = document.getElementById("recommendationsStatus");
  status.textContent = "Caricamento...";
  try {
    const response = await fetchBackend(
      `/recommendations/contextual/${encodeURIComponent(popupState.itemId)}?limit=4&use_ai_support=true`,
    );
    renderRecommendationGroups(response.groups || [], "local");
    status.textContent = response.used_ai_support ? "Catalogo + Gemini" : "Catalogo locale";
  } catch (error) {
    renderRecommendationGroups([], "local");
    status.textContent = "Non disponibili";
  }
}

// Organizza candidati Amazon gia letti dal content script.
// Se il backend non risponde usa un fallback locale senza inventare prodotti.
async function loadAmazonRecommendations() {
  const status = document.getElementById("recommendationsStatus");
  if (!popupState.amazonCandidates.length) {
    renderRecommendationGroups([], "amazon");
    status.textContent = "Nessun candidato";
    return;
  }

  status.textContent = "Organizzazione...";
  try {
    const response = await postBackend("/amazon/recommendations", {
      product: {
        asin: popupState.amazonProduct.asin,
        title: popupState.amazonProduct.title || "",
        image_url: popupState.amazonProduct.imageUrl || null,
        page_url: popupState.amazonProduct.pageUrl || null,
      },
      candidates: popupState.amazonCandidates,
      limit: 4,
      use_ai_support: true,
    });
    renderRecommendationGroups(response.groups || [], "amazon");
    status.textContent = response.used_ai_support ? "Amazon + Gemini" : "Dalla pagina Amazon";
  } catch (error) {
    renderRecommendationGroups(buildAmazonFallbackGroups(popupState.amazonCandidates, 4), "amazon");
    status.textContent = "Dalla pagina Amazon";
  }
}

// Presenta i bestseller come tali quando e aperto il catalogo locale.
async function loadPopularRecommendations() {
  const status = document.getElementById("recommendationsStatus");
  setText("recommendationsTitle", "Più popolari nel catalogo");
  try {
    const products = await fetchBackend("/recommendations/popular?limit=4");
    renderRecommendationGroups([
      {
        role_id: "popular",
        label: "Bestseller",
        products,
      },
    ], "local");
    status.textContent = "Catalogo locale";
  } catch (error) {
    renderRecommendationGroups([], "local");
    status.textContent = "Non disponibili";
  }
}

// Renderizza i gruppi di raccomandazioni nel popup.
// Normalizza simili e complementari in due blocchi compatti e cliccabili.
function renderRecommendationGroups(groups, kind) {
  const list = document.getElementById("recommendationsList");
  list.innerHTML = "";
  hideRecommendationDetail();
  const displayGroups = normalizeRecommendationGroups(groups);

  if (!displayGroups.length) {
    const item = document.createElement("div");
    item.className = "empty-list-item";
    item.textContent = kind === "amazon"
      ? "Nessun prodotto Amazon reale leggibile nella pagina corrente."
      : "Raccomandazioni locali non disponibili.";
    list.appendChild(item);
    return;
  }

  displayGroups.forEach((group, index) => {
    const section = document.createElement("details");
    section.className = `recommendation-group recommendation-group-${group.role_id || "generic"}`;
    section.open = index === 0;

    const heading = document.createElement("summary");
    heading.className = "recommendation-group-heading";

    const title = document.createElement("span");
    title.className = "recommendation-group-title";
    title.textContent = group.label || "Consigli";

    const count = document.createElement("span");
    count.className = "recommendation-group-count";
    count.textContent = group.products.length;

    heading.append(title, count);
    section.appendChild(heading);

    const products = document.createElement("div");
    products.className = "recommendation-products";
    group.products.slice(0, 2).forEach((product) => {
      products.appendChild(createRecommendationButton(product, kind));
    });

    section.appendChild(products);
    const extraProducts = group.products.slice(2);
    if (extraProducts.length) {
      const more = document.createElement("details");
      more.className = "more-recommendations";
      const summary = document.createElement("summary");
      summary.textContent = extraProducts.length === 1
        ? "Un altro suggerimento"
        : `Altri ${extraProducts.length} suggerimenti`;
      const extraRows = document.createElement("div");
      extraRows.className = "recommendation-products";
      extraProducts.forEach((product) => extraRows.appendChild(createRecommendationButton(product, kind)));
      more.append(summary, extraRows);
      section.appendChild(more);
    }
    list.appendChild(section);
  });
}

// Trasforma i gruppi backend nella vista compatta del popup.
// Separa simili/alternative da complementari in due blocchi distinti.
function normalizeRecommendationGroups(groups) {
  const safeGroups = Array.isArray(groups) ? groups : [];
  if (safeGroups[0]?.role_id === "popular") {
    return safeGroups.filter((group) => group.products.length);
  }
  const similarAlt = [];
  const complementary = [];
  const seenSim = new Set();
  const seenComp = new Set();

  safeGroups.forEach((group) => {
    const roleId = group.role_id || "";
    const products = Array.isArray(group.products) ? group.products : [];
    const isComplementary = roleId === "complementary" || roleId === "together";
    const target = isComplementary ? complementary : similarAlt;
    const seen = isComplementary ? seenComp : seenSim;
    products.forEach((product) => {
      const key = product.item_id || product.asin || product.product_url || product.title;
      if (!key || seen.has(key)) {
        return;
      }
      seen.add(key);
      target.push(product);
    });
  });

  const displayGroups = [];
  if (similarAlt.length) {
    displayGroups.push({
      role_id: "similar_alternatives",
      label: "Simili e alternative",
      products: similarAlt.slice(0, 4),
    });
  }
  if (complementary.length) {
    displayGroups.push({
      role_id: "complementary",
      label: "Utili insieme",
      products: complementary.slice(0, 4),
    });
  }
  return displayGroups;
}

// Crea il bottone di un singolo consiglio.
// Il click apre il dettaglio interno prima di navigare alla pagina prodotto.
function createRecommendationButton(product, kind) {
  const button = document.createElement("button");
  button.className = "recommendation-item";
  button.type = "button";
  button.addEventListener("click", () => {
    renderRecommendationDetail(product, kind, button);
  });
  button.setAttribute("aria-label", `Apri dettagli per ${product.title || "prodotto consigliato"}`);

  const imageBox = createProductImage(productImageAdapter(product, kind), "recommendation-image");
  const body = document.createElement("div");
  body.className = "recommendation-body";

  const title = document.createElement("span");
  const meta = document.createElement("small");
  const arrow = document.createElement("span");

  title.textContent = product.title || "Prodotto senza titolo";
  meta.textContent = recommendationMeta(product, kind);
  arrow.className = "recommendation-arrow";
  arrow.setAttribute("aria-hidden", "true");
  arrow.textContent = "›";

  body.append(title, meta);
  button.append(imageBox, body, arrow);
  return button;
}

// Mostra il dettaglio di un consiglio selezionato.
// Include immagine, metadati, motivazione e bottone di apertura pagina.
function renderRecommendationDetail(product, kind, trigger) {
  const detail = document.getElementById("recommendationDetail");
  if (!detail) {
    openRecommendationUrl(recommendationUrl(product, kind));
    return;
  }

  detail.innerHTML = "";
  detail.className = "recommendation-detail";
  document.getElementById("recommendationsList").classList.add("hidden");

  const header = document.createElement("div");
  header.className = "recommendation-detail-heading";

  const eyebrow = document.createElement("p");
  eyebrow.textContent = kind === "amazon" ? "Prodotto Amazon reale" : "Prodotto del catalogo locale";

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "recommendation-back";
  closeButton.textContent = "← Torna ai consigli";
  const showList = () => {
    hideRecommendationDetail();
    trigger.focus();
  };
  closeButton.addEventListener("click", showList);
  detail.onkeydown = (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      showList();
    }
  };

  header.append(closeButton, eyebrow);

  const layout = document.createElement("div");
  layout.className = "recommendation-detail-layout";
  layout.appendChild(createProductImage(productImageAdapter(product, kind), "recommendation-detail-image"));

  const body = document.createElement("div");
  body.className = "recommendation-detail-body";

  const title = document.createElement("h3");
  title.textContent = product.title || "Prodotto senza titolo";

  const meta = document.createElement("p");
  meta.className = "recommendation-detail-meta";
  meta.textContent = recommendationMeta(product, kind);

  const reason = document.createElement("p");
  reason.className = "recommendation-detail-reason";
  reason.textContent = product.role_reason || recommendationFallbackReason(product, kind);

  const openButton = document.createElement("button");
  openButton.type = "button";
  openButton.className = "primary-button open-product-button";
  openButton.textContent = kind === "amazon" ? "Apri su Amazon" : "Apri nel catalogo";
  openButton.addEventListener("click", () => {
    openRecommendationUrl(recommendationUrl(product, kind));
  });

  body.appendChild(title);
  body.appendChild(meta);
  body.appendChild(reason);
  body.appendChild(openButton);
  layout.appendChild(body);

  detail.appendChild(header);
  detail.appendChild(layout);
  detail.scrollIntoView({ block: "nearest" });
  closeButton.focus({ preventScroll: true });
}

function hideRecommendationDetail() {
  const detail = document.getElementById("recommendationDetail");
  if (!detail) {
    return;
  }
  detail.innerHTML = "";
  detail.className = "recommendation-detail hidden";
  detail.onkeydown = null;
  document.getElementById("recommendationsList").classList.remove("hidden");
}

function productImageAdapter(product, kind) {
  if (kind === "amazon") {
    return {
      title: product.title,
      image_url: product.image_url,
    };
  }
  return product;
}

function recommendationMeta(product, kind) {
  if (kind === "amazon") {
    return [product.price, product.source_label].filter(Boolean).join(" - ") || "Amazon reale";
  }
  return [
    product.category || "Categoria N/D",
    formatPrice(product.price),
    `rating ${formatRating(product.average_rating)}`,
  ].filter(Boolean).join(" - ");
}

// Determina la URL finale del consiglio.
// Amazon usa product_url reale, locale usa page_url o costruisce product.html?id=...
function recommendationUrl(product, kind) {
  if (kind === "amazon") {
    return product.product_url;
  }
  const destination = new URL(product.page_url || `${LOCAL_PRODUCT_URL}?id=${encodeURIComponent(product.item_id)}`);
  const current = new URL(popupState.activeTab?.url || LOCAL_ORIGIN);
  if (current.origin === LOCAL_ORIGIN && destination.origin === LOCAL_ORIGIN) {
    ["profile", "q", "view", "sort", "intent"].forEach((key) => {
      if (current.searchParams.has(key)) {
        destination.searchParams.set(key, current.searchParams.get(key));
      }
    });
  }
  return destination.href;
}

// Apre la URL del consiglio nella tab corrente quando possibile.
// In fallback apre una nuova finestra e mantiene noopener/noreferrer.
function openRecommendationUrl(url) {
  if (!url) {
    return;
  }
  if (chrome.tabs && popupState.activeTab && typeof popupState.activeTab.id !== "undefined") {
    chrome.tabs.update(popupState.activeTab.id, { url });
    window.close();
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
}

// Crea gruppi Amazon quando il backend non e disponibile.
// Usa solo candidati reali gia presenti nel DOM, due soli gruppi: simili/alternative e complementari.
function buildAmazonFallbackGroups(candidates, limit) {
  const simAltRoles = new Set(["similar", "alternative"]);
  const simAlt = candidates
    .filter((candidate) => simAltRoles.has(candidate.source_role))
    .slice(0, limit * 2)
    .map((candidate) => ({
      ...candidate,
      role_reason: candidate.role_reason || `Prodotto reale letto da ${candidate.source_label || "Amazon"}.`,
    }));
  const comp = candidates
    .filter((candidate) => candidate.source_role === "together")
    .slice(0, limit)
    .map((candidate) => ({
      ...candidate,
      role_reason: candidate.role_reason || `Prodotto reale letto da ${candidate.source_label || "Amazon"}.`,
    }));
  const groups = [];
  if (simAlt.length) {
    groups.push({
      role_id: "similar_alternatives",
      label: "Simili e alternative reali",
      products: simAlt,
    });
  }
  if (comp.length) {
    groups.push({
      role_id: "complementary",
      label: "Utili insieme",
      products: comp,
    });
  }
  return groups;
}

// Crea immagine prodotto per popup e consigli.
// Usa placeholder locale se l'immagine manca o genera errore.
function createProductImage(product, className) {
  const wrapper = document.createElement("div");
  wrapper.className = className;

  const image = document.createElement("img");
  image.src = product.image_url || DEFAULT_PRODUCT_IMAGE_URL;
  image.alt = product.title || "Immagine prodotto";
  image.loading = "lazy";
  image.addEventListener("error", () => {
    if (image.src.endsWith(DEFAULT_PRODUCT_IMAGE_URL)) {
      return;
    }
    image.src = DEFAULT_PRODUCT_IMAGE_URL;
    image.className = "default-product-image";
  });
  if (!product.image_url) {
    image.className = "default-product-image";
  }

  wrapper.appendChild(image);
  return wrapper;
}

function formatRating(value) {
  const number = Number(value || 0);
  return number > 0 ? number.toFixed(1) : "N/D";
}

function formatPrice(value) {
  const price = Number(value);
  if (!Number.isFinite(price) || price <= 0) {
    return "";
  }
  return price.toLocaleString("it-IT", {
    style: "currency",
    currency: "USD",
  });
}

function setText(elementId, value) {
  const element = document.getElementById(elementId);
  if (element) {
    element.textContent = value;
  }
}

function setResultText(value) {
  const result = document.getElementById("productResult");
  result.textContent = value;
  result.className = "result-box muted-text";
}

function recommendationFallbackReason(product, kind) {
  if (kind === "amazon") {
    return `Prodotto reale rilevato nella pagina Amazon, dalla sezione ${product.source_label || "suggerimenti"}.`;
  }
  return "Consiglio scelto dal catalogo locale usando segnali di somiglianza, prezzo, qualita e popolarita.";
}
