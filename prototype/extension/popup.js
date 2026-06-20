const BACKEND_URL = "http://localhost:8000";
const LOCAL_PRODUCT_URL = "http://localhost:3000/product.html";
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

async function initPopup() {
  const tab = await getActiveTab();
  popupState.activeTab = tab;
  const currentUrl = tab && tab.url ? tab.url : "";

  const loadButton = document.getElementById("loadProductButton");
  if (loadButton) {
    loadButton.addEventListener("click", loadCurrentProduct);
  }

  await updateProductPageState(tab, currentUrl);
  await Promise.all([checkBackendStatus(), loadRecommendations()]);
}

function getActiveTab() {
  return new Promise((resolve) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      resolve(tabs && tabs.length ? tabs[0] : null);
    });
  });
}

async function updateProductPageState(tab, currentUrl) {
  const detection = await detectActiveProduct(tab, currentUrl);
  const product = detection.product;
  const button = document.getElementById("loadProductButton");
  const idValue = document.getElementById("itemIdValue");

  popupState.itemId = null;
  popupState.amazonProduct = null;
  popupState.amazonCandidates = detection.amazonCandidates || [];
  if (button) {
    button.hidden = true;
    button.disabled = true;
    button.textContent = "Carica prodotto";
  }
  if (idValue) {
    idValue.hidden = true;
  }
  hideRecommendationDetail();

  if (!product) {
    setText("productPageStatus", "Non sei su una pagina prodotto riconosciuta.");
    setResultText("Apri una pagina prodotto locale o Amazon.");
    return;
  }

  if (product.kind === "amazon") {
    popupState.amazonProduct = product;
    setText("productPageStatus", "Prodotto Amazon rilevato.");
    renderAmazonProduct(product);
    return;
  }

  popupState.itemId = product.itemId;
  setText("productPageStatus", "Pagina prodotto locale rilevata.");
  await loadCurrentProduct();
}

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

async function fetchBackend(path) {
  const response = await fetch(`${BACKEND_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Errore API: ${response.status}`);
  }
  return response.json();
}

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
    result.textContent = "Prodotto non disponibile. Controlla che il backend sia acceso e che il catalogo locale esista.";
    result.className = "result-box error-text";
  }
}

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

  const itemId = document.createElement("p");
  itemId.className = "product-id-line";
  itemId.textContent = `item_id: ${product.item_id}`;

  info.appendChild(category);
  info.appendChild(title);
  info.appendChild(itemId);
  info.appendChild(rating);
  info.appendChild(reviews);
  layout.appendChild(imageBox);
  layout.appendChild(info);
  result.appendChild(layout);
}

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

async function loadRecommendations() {
  if (popupState.itemId) {
    await loadLocalRecommendations();
    return;
  }

  if (popupState.amazonProduct) {
    await loadAmazonRecommendations();
    return;
  }

  await loadPopularRecommendations();
}

async function loadLocalRecommendations() {
  const status = document.getElementById("recommendationsStatus");
  status.textContent = "Caricamento...";
  try {
    const response = await fetchBackend(
      `/recommendations/contextual/${encodeURIComponent(popupState.itemId)}?limit=4&use_ai_support=true`,
    );
    renderRecommendationGroups(response.groups || [], "local");
    status.textContent = response.used_ai_support ? "Locali + Gemini" : "Locali";
  } catch (error) {
    renderRecommendationGroups([], "local");
    status.textContent = "Non disponibili";
  }
}

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
    status.textContent = response.used_ai_support ? "Reali + Gemini" : "Reali";
  } catch (error) {
    renderRecommendationGroups(buildAmazonFallbackGroups(popupState.amazonCandidates, 4), "amazon");
    status.textContent = "Reali dalla pagina";
  }
}

async function loadPopularRecommendations() {
  const status = document.getElementById("recommendationsStatus");
  try {
    const products = await fetchBackend("/recommendations/popular?limit=5");
    renderRecommendationGroups([
      {
        role_id: "popular",
        label: "Popolari locali",
        description: "Fallback dal catalogo locale.",
        products,
      },
    ], "local");
    status.textContent = `${products.length} prodotti`;
  } catch (error) {
    renderRecommendationGroups([], "local");
    status.textContent = "Non disponibili";
  }
}

function renderRecommendationGroups(groups, kind) {
  const list = document.getElementById("recommendationsList");
  list.innerHTML = "";
  hideRecommendationDetail();
  const displayGroups = normalizeRecommendationGroups(groups, kind);

  if (!displayGroups.length) {
    const item = document.createElement("div");
    item.className = "empty-list-item";
    item.textContent = kind === "amazon"
      ? "Nessun prodotto Amazon reale leggibile nella pagina corrente."
      : "Raccomandazioni locali non disponibili.";
    list.appendChild(item);
    return;
  }

  displayGroups.forEach((group) => {
    const section = document.createElement("section");
    section.className = `recommendation-group recommendation-group-${group.role_id || "generic"}`;

    const heading = document.createElement("div");
    heading.className = "recommendation-group-heading";

    const title = document.createElement("h3");
    title.textContent = group.label || "Consigli";

    const count = document.createElement("span");
    count.textContent = `${(group.products || []).length}`;

    const description = document.createElement("p");
    description.textContent = group.description || "";

    heading.appendChild(title);
    heading.appendChild(count);
    section.appendChild(heading);
    if (description.textContent) {
      section.appendChild(description);
    }

    const products = document.createElement("div");
    products.className = "recommendation-products";
    (group.products || []).slice(0, 4).forEach((product) => {
      products.appendChild(createRecommendationButton(product, kind));
    });

    section.appendChild(products);
    list.appendChild(section);
  });
}

function normalizeRecommendationGroups(groups, kind) {
  const safeGroups = Array.isArray(groups) ? groups : [];
  const similarProducts = [];
  const complementaryProducts = [];
  const seenSimilar = new Set();
  const seenComplementary = new Set();

  safeGroups.forEach((group) => {
    const roleId = group.role_id || "";
    const products = Array.isArray(group.products) ? group.products : [];
    const isComplementary = roleId === "together" || roleId === "complementary";
    const target = isComplementary ? complementaryProducts : similarProducts;
    const seen = isComplementary ? seenComplementary : seenSimilar;
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
  if (similarProducts.length) {
    displayGroups.push({
      role_id: "best_similar",
      label: kind === "amazon" ? "Prodotti simili migliori" : "Migliori prodotti simili",
      description: kind === "amazon"
        ? "Alternative reali trovate nella pagina, scelte per somiglianza con il prodotto aperto."
        : "Scelte vicine per categoria, prezzo, qualita locale, popolarita e possibile affidabilita della marca.",
      products: similarProducts.slice(0, 4),
    });
  }
  if (complementaryProducts.length) {
    displayGroups.push({
      role_id: "complementary",
      label: "Complementari e utili assieme",
      description: kind === "amazon"
        ? "Accessori, servizi o prodotti reali letti nella pagina e collegati all'acquisto principale."
        : "Prodotti da usare insieme, accessori o alternative di supporto scelte dal catalogo locale.",
      products: complementaryProducts.slice(0, 4),
    });
  }
  return displayGroups;
}

function createRecommendationButton(product, kind) {
  const button = document.createElement("button");
  button.className = "recommendation-item";
  button.type = "button";
  button.addEventListener("click", () => {
    renderRecommendationDetail(product, kind);
  });
  button.setAttribute("aria-label", `Apri dettagli per ${product.title || "prodotto consigliato"}`);

  const imageBox = createProductImage(productImageAdapter(product, kind), "recommendation-image");
  const body = document.createElement("div");
  body.className = "recommendation-body";

  const title = document.createElement("span");
  const meta = document.createElement("small");
  const reason = document.createElement("small");
  const action = document.createElement("small");

  title.textContent = product.title || "Prodotto senza titolo";
  meta.textContent = recommendationMeta(product, kind);
  reason.className = "recommendation-reason";
  reason.textContent = shortReason(product.role_reason || recommendationFallbackReason(product, kind));
  action.className = "recommendation-action";
  action.textContent = "Apri dettagli";

  body.appendChild(title);
  body.appendChild(meta);
  if (reason.textContent) {
    body.appendChild(reason);
  }
  body.appendChild(action);
  button.appendChild(imageBox);
  button.appendChild(body);
  return button;
}

function renderRecommendationDetail(product, kind) {
  const detail = document.getElementById("recommendationDetail");
  if (!detail) {
    openRecommendationUrl(recommendationUrl(product, kind));
    return;
  }

  detail.innerHTML = "";
  detail.className = "recommendation-detail";

  const header = document.createElement("div");
  header.className = "recommendation-detail-heading";

  const eyebrow = document.createElement("p");
  eyebrow.textContent = kind === "amazon" ? "Prodotto Amazon reale" : "Prodotto del catalogo locale";

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "icon-button";
  closeButton.textContent = "x";
  closeButton.setAttribute("aria-label", "Chiudi dettaglio");
  closeButton.addEventListener("click", hideRecommendationDetail);

  header.appendChild(eyebrow);
  header.appendChild(closeButton);

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
  openButton.textContent = "Apri pagina prodotto";
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
}

function hideRecommendationDetail() {
  const detail = document.getElementById("recommendationDetail");
  if (!detail) {
    return;
  }
  detail.innerHTML = "";
  detail.className = "recommendation-detail hidden";
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

function recommendationUrl(product, kind) {
  if (kind === "amazon") {
    return product.product_url;
  }
  return product.page_url || `${LOCAL_PRODUCT_URL}?id=${encodeURIComponent(product.item_id)}`;
}

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

function buildAmazonFallbackGroups(candidates, limit) {
  const labels = {
    similar: "Prodotti simili su Amazon",
    alternatives: "Alternative reali",
    together: "Spesso acquistati insieme",
  };
  const roleMap = {
    similar: "similar",
    alternatives: "alternative",
    together: "together",
  };
  return Object.entries(labels)
    .map(([roleId, label]) => {
      const products = candidates
        .filter((candidate) => candidate.source_role === roleMap[roleId])
        .slice(0, limit)
        .map((candidate) => ({
          ...candidate,
          role_reason: candidate.role_reason || `Prodotto reale letto da ${candidate.source_label || "Amazon"}.`,
        }));
      return {
        role_id: roleId,
        label,
        products,
      };
    })
    .filter((group) => group.products.length);
}

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

function shortReason(value) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= 150) {
    return text;
  }
  return `${text.slice(0, 147).trim()}...`;
}

function recommendationFallbackReason(product, kind) {
  if (kind === "amazon") {
    return `Prodotto reale rilevato nella pagina Amazon, dalla sezione ${product.source_label || "suggerimenti"}.`;
  }
  return "Consiglio scelto dal catalogo locale usando segnali di somiglianza, prezzo, qualita e popolarita.";
}
