const EXTENSION_BACKEND_URL = "http://localhost:8000";
const EXTENSION_LOCAL_PRODUCT_URL = "http://localhost:3000/product.html";
const EXTENSION_BOX_ID = "thesisExtensionDemoBox";

//Rimuove anche un eventuale pannello lasciato da una versione precedente dell'estensione.
document.getElementById(EXTENSION_BOX_ID)?.remove();

//Il content script resta invisibile: rileva il prodotto per il popup senza aggiungere box alla pagina.
initMessageListener();

//Inserisce box demo su pagina prodotto locale o Amazon riconosciuta
//Il box ora mostra anche consigli contestuali cliccabili
async function initContentBox() {
  if (document.getElementById(EXTENSION_BOX_ID)) {
    return;
  }

  const product = detectCurrentProduct();
  if (!product) {
    return;
  }

  const box = createContentBox(product);
  insertContentBox(box, product);

  const status = box.querySelector(".thesis-extension-status");
  if (product.kind === "amazon") {
    status.textContent = "Prodotto Amazon riconosciuto";
    await loadAmazonContentRecommendations(box, product);
    return;
  }

  const backendStatus = await getBackendStatusText();
  status.textContent = backendStatus;
  if (backendStatus === "Backend online") {
    await loadLocalContentRecommendations(box, product);
  }
}

//Legge il prodotto dalla pagina usando detector condiviso
function detectCurrentProduct() {
  return window.ThesisProductDetector.detectCurrentPage(window.location.href, document);
}

//Crea box informativo senza usare HTML dinamico non sicuro
function createContentBox(product) {
  const box = document.createElement("aside");
  box.id = EXTENSION_BOX_ID;
  box.className = product.kind === "amazon" ? "thesis-extension-box amazon-detected" : "thesis-extension-box";

  const title = document.createElement("strong");
  title.textContent = "Tesi E-commerce Demo";

  const item = document.createElement("span");
  item.textContent = product.kind === "amazon" ? `ASIN rilevato: ${product.asin}` : `item_id rilevato: ${product.itemId}`;

  const productTitle = document.createElement("span");
  productTitle.className = "thesis-extension-product-title";
  productTitle.textContent = product.kind === "amazon" && product.title ? product.title : "";

  const status = document.createElement("span");
  status.className = "thesis-extension-status";
  status.textContent = "Controllo backend...";

  const note = document.createElement("span");
  note.textContent = product.kind === "amazon"
    ? "Suggerimenti reali se la pagina espone prodotti correlati"
    : "Consigli solo dal dataset locale del sito";

  box.appendChild(title);
  box.appendChild(item);
  if (productTitle.textContent) {
    box.appendChild(productTitle);
  }
  box.appendChild(status);
  box.appendChild(note);
  box.appendChild(createRecommendationShell());

  return box;
}

function createRecommendationShell() {
  const shell = document.createElement("div");
  shell.className = "thesis-extension-recommendations";

  const heading = document.createElement("div");
  heading.className = "thesis-extension-rec-heading";

  const title = document.createElement("strong");
  title.textContent = "Consigli contestuali";

  const status = document.createElement("span");
  status.className = "thesis-extension-rec-status";
  status.textContent = "Caricamento...";

  heading.appendChild(title);
  heading.appendChild(status);
  shell.appendChild(heading);
  return shell;
}

async function loadLocalContentRecommendations(box, product) {
  const shell = box.querySelector(".thesis-extension-recommendations");
  const status = box.querySelector(".thesis-extension-rec-status");
  try {
    const response = await fetchBackendJson(
      `/recommendations/contextual/${encodeURIComponent(product.itemId)}?limit=3&use_ai_support=true`,
    );
    renderContentRecommendationGroups(shell, response.groups || [], "local");
    status.textContent = response.used_ai_support ? "Organizzati con Gemini" : "Locale";
  } catch (error) {
    renderContentRecommendationGroups(shell, [], "local");
    status.textContent = "Non disponibili";
  }
}

async function loadAmazonContentRecommendations(box, product) {
  const shell = box.querySelector(".thesis-extension-recommendations");
  const status = box.querySelector(".thesis-extension-rec-status");
  const candidates = extractAmazonRecommendationCandidates(product);

  if (!candidates.length) {
    renderContentRecommendationGroups(shell, [], "amazon");
    status.textContent = "Nessun candidato reale visibile";
    return;
  }

  try {
    const response = await postBackendJson("/amazon/recommendations", {
      product: toAmazonRequestProduct(product),
      candidates,
      limit: 3,
      use_ai_support: true,
    });
    renderContentRecommendationGroups(shell, response.groups || [], "amazon");
    status.textContent = response.used_ai_support ? "Reali + Gemini" : "Reali";
  } catch (error) {
    renderContentRecommendationGroups(shell, buildAmazonFallbackGroups(candidates, 3), "amazon");
    status.textContent = "Reali dalla pagina";
  }
}

function renderContentRecommendationGroups(shell, groups, kind) {
  shell.querySelectorAll(".thesis-extension-rec-group, .thesis-extension-empty").forEach((node) => node.remove());

  if (!groups.length) {
    const empty = document.createElement("p");
    empty.className = "thesis-extension-empty";
    empty.textContent = kind === "amazon"
      ? "Amazon non ha esposto card prodotto leggibili in questa pagina."
      : "Nessun consiglio locale disponibile per questo prodotto.";
    shell.appendChild(empty);
    return;
  }

  groups.slice(0, 3).forEach((group) => {
    const section = document.createElement("section");
    section.className = "thesis-extension-rec-group";

    const title = document.createElement("p");
    title.className = "thesis-extension-rec-title";
    title.textContent = group.label || "Consigli";

    const list = document.createElement("div");
    list.className = "thesis-extension-rec-list";

    (group.products || []).slice(0, 3).forEach((item) => {
      list.appendChild(createContentRecommendationLink(item, kind));
    });

    section.appendChild(title);
    section.appendChild(list);
    shell.appendChild(section);
  });
}

function createContentRecommendationLink(item, kind) {
  const link = document.createElement("a");
  link.className = "thesis-extension-rec-link";
  link.href = kind === "amazon" ? item.product_url : productLocalUrl(item);
  if (kind === "amazon") {
    link.rel = "noopener noreferrer";
  }

  const title = document.createElement("span");
  title.className = "thesis-extension-rec-item-title";
  title.textContent = item.title || "Prodotto senza titolo";

  const meta = document.createElement("small");
  meta.textContent = kind === "amazon"
    ? [item.price, item.source_label].filter(Boolean).join(" - ") || "Amazon reale"
    : [item.category, formatPrice(item.price)].filter(Boolean).join(" - ");

  link.appendChild(title);
  link.appendChild(meta);
  return link;
}

function productLocalUrl(product) {
  return product.page_url || `${EXTENSION_LOCAL_PRODUCT_URL}?id=${encodeURIComponent(product.item_id)}`;
}

function toAmazonRequestProduct(product) {
  return {
    asin: product.asin,
    title: product.title || "",
    image_url: product.imageUrl || null,
    page_url: product.pageUrl || window.location.href,
  };
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
  return ["similar", "alternatives", "together"]
    .map((role) => {
      const products = candidates.filter((candidate) => candidate.source_role === roleMap[role]).slice(0, limit);
      return {
        role_id: role,
        label: labels[role],
        products,
      };
    })
    .filter((group) => group.products.length);
}

//Estrae candidati Amazon gia presenti nel DOM della pagina corrente
//Non cerca sul web e non inventa prodotti: prende solo link /dp o /gp/product visibili
function extractAmazonRecommendationCandidates(product = detectCurrentProduct()) {
  if (!product || product.kind !== "amazon") {
    return [];
  }

  const anchors = Array.from(document.querySelectorAll("a[href*='/dp/'], a[href*='/gp/product/']"));
  const currentAsin = window.ThesisProductDetector.normalizeAsin(product.asin);
  const seen = new Set();
  const candidates = [];

  for (const anchor of anchors) {
    const href = absoluteUrl(anchor.getAttribute("href"));
    const asin = href ? readAmazonAsinFromHref(href) : null;
    if (!href || !asin || asin === currentAsin || seen.has(asin)) {
      continue;
    }
    const productUrl = canonicalAmazonProductUrl(href, asin);

    const container = findAmazonCandidateContainer(anchor);
    const title = readAmazonCandidateTitle(anchor, container);
    if (!isUsefulAmazonTitle(title)) {
      continue;
    }

    seen.add(asin);
    const sourceLabel = readAmazonSectionLabel(container);
    candidates.push({
      asin,
      title,
      product_url: productUrl,
      image_url: readAmazonCandidateImage(anchor, container),
      price: readAmazonCandidatePrice(container),
      rating: readAmazonCandidateRating(container),
      source_label: sourceLabel,
      source_role: inferAmazonSourceRole(sourceLabel, title, product.title || ""),
    });

    if (candidates.length >= 24) {
      break;
    }
  }

  return candidates;
}

function findAmazonCandidateContainer(anchor) {
  return anchor.closest(".a-carousel-card, [data-asin], li, tr, .p13n-sc-uncoverable-faceout")
    || anchor.parentElement
    || anchor;
}

function readAmazonCandidateTitle(anchor, container) {
  const values = [
    anchor.getAttribute("title"),
    anchor.getAttribute("aria-label"),
    cleanText(anchor.textContent),
    readFirstText(anchor, ["img[alt]"], "alt"),
    readFirstText(container, ["img[alt]"], "alt"),
    readFirstText(container, [".a-truncate-full", ".a-size-base-plus", ".a-size-medium", ".a-size-base", ".p13n-sc-truncate"]),
  ];

  return values
    .map(cleanText)
    .filter(isUsefulAmazonTitle)
    .sort((left, right) => right.length - left.length)[0] || "";
}

function readAmazonCandidateImage(anchor, container) {
  return readFirstText(anchor, ["img"], "src")
    || readFirstText(container, ["img"], "src")
    || readFirstText(container, ["img"], "data-src")
    || null;
}

function readAmazonCandidatePrice(container) {
  const price = readFirstText(container, [
    ".a-price .a-offscreen",
    ".p13n-sc-price",
    ".a-color-price",
  ]);
  if (price) {
    return price;
  }

  const text = cleanText(container && container.textContent);
  const match = text.match(/(?:\u20ac|\$|\u00a3)\s?\d+(?:[.,]\d{2})?/u);
  return match ? match[0] : null;
}

function readAmazonCandidateRating(container) {
  const rating = readFirstText(container, [
    "[aria-label*='stelle']",
    "[aria-label*='stars']",
    ".a-icon-alt",
  ], "aria-label");
  return rating || readFirstText(container, [".a-icon-alt"]);
}

function readAmazonSectionLabel(element) {
  let current = element;
  for (let depth = 0; current && depth < 7; depth += 1) {
    const label = cleanText(current.getAttribute && (current.getAttribute("aria-label") || current.getAttribute("data-a-carousel-options")));
    if (label && label.length < 120) {
      return label;
    }
    const heading = current.querySelector && current.querySelector("h2, h3, .a-carousel-heading");
    const headingText = cleanText(heading && heading.textContent);
    if (headingText && headingText.length < 120) {
      return headingText;
    }
    current = current.parentElement;
  }
  return "Sezione Amazon visibile";
}

function inferAmazonSourceRole(label, title, sourceTitle) {
  const text = `${label || ""} ${title || ""}`.toLowerCase();
  if (/(insieme|acquistati|bought|together|bundle|frequently|accessor|protezione|protection|garanzia|warranty|danni accidentali)/i.test(text)) {
    return "together";
  }
  if (/(simil|similar|compare|confront|related|confronta)/i.test(text)) {
    return "similar";
  }
  if (tokenOverlap(title, sourceTitle) >= 0.08) {
    return "similar";
  }
  return "alternative";
}

function readFirstText(root, selectors, attributeName) {
  if (!root || !root.querySelector) {
    return "";
  }
  for (const selector of selectors) {
    const element = root.querySelector(selector);
    if (!element) {
      continue;
    }
    const value = attributeName ? element.getAttribute(attributeName) : element.textContent;
    const text = cleanText(value);
    if (text) {
      return text;
    }
  }
  return "";
}

function isUsefulAmazonTitle(value) {
  const text = cleanText(value);
  if (text.length < 12 || text.length > 220) {
    return false;
  }
  if (!/[a-zA-Z]/.test(text)) {
    return false;
  }
  if (/click to learn more|sponsored product|carta amazon business|amazon business amex|business american express|passa a amazon business/i.test(text)) {
    return false;
  }
  return !/^(vedi|see|details|shop|visit|clicca|immagine|image)$/i.test(text);
}

function tokenOverlap(left, right) {
  const leftTokens = new Set(tokenize(left));
  const rightTokens = new Set(tokenize(right));
  if (!leftTokens.size || !rightTokens.size) {
    return 0;
  }
  let intersection = 0;
  leftTokens.forEach((token) => {
    if (rightTokens.has(token)) {
      intersection += 1;
    }
  });
  const union = new Set([...leftTokens, ...rightTokens]).size;
  return intersection / Math.max(1, union);
}

function tokenize(value) {
  return cleanText(value)
    .toLowerCase()
    .match(/[a-z0-9][a-z0-9-]{2,}/g) || [];
}

function absoluteUrl(value) {
  try {
    return new URL(value, window.location.href).toString();
  } catch (error) {
    return "";
  }
}

function readAmazonAsinFromHref(href) {
  const direct = window.ThesisProductDetector.getAmazonAsinFromUrl(href);
  if (direct) {
    return direct;
  }

  try {
    const url = new URL(href);
    const redirectKeys = ["url", "redirect", "redirectUrl"];
    for (const key of redirectKeys) {
      const value = url.searchParams.get(key);
      if (!value) {
        continue;
      }
      const redirectedUrl = new URL(value, window.location.origin).toString();
      const asin = window.ThesisProductDetector.getAmazonAsinFromUrl(redirectedUrl);
      if (asin) {
        return asin;
      }
    }
  } catch (error) {
    return null;
  }

  return null;
}

function canonicalAmazonProductUrl(href, asin) {
  try {
    const url = new URL(href);
    return `${url.origin}/dp/${encodeURIComponent(asin)}`;
  } catch (error) {
    return href;
  }
}

async function fetchBackendJson(path) {
  const response = await fetch(`${EXTENSION_BACKEND_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Errore API: ${response.status}`);
  }
  return response.json();
}

async function postBackendJson(path, body) {
  const response = await fetch(`${EXTENSION_BACKEND_URL}${path}`, {
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

function formatPrice(value) {
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0) {
    return "";
  }
  return number.toLocaleString("it-IT", {
    style: "currency",
    currency: "USD",
  });
}

function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

//Sceglie un punto poco invasivo per inserire il box
function insertContentBox(box, product) {
  if (product.kind === "amazon") {
    const amazonTarget = document.querySelector("#titleSection") || document.querySelector("#centerCol");
    if (amazonTarget && amazonTarget.parentElement) {
      amazonTarget.insertAdjacentElement("afterend", box);
      return;
    }
  }

  const target = document.querySelector(".page-shell") || document.body;
  target.prepend(box);
}

//Risponde al popup con prodotto e candidati Amazon reali rilevati nella pagina
function initMessageListener() {
  if (typeof chrome === "undefined" || !chrome.runtime || !chrome.runtime.onMessage) {
    return;
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (!message || message.type !== "GET_DETECTED_PRODUCT") {
      return false;
    }

    const product = detectCurrentProduct();
    sendResponse({
      product,
      amazonCandidates: product && product.kind === "amazon" ? extractAmazonRecommendationCandidates(product) : [],
    });
    return false;
  });
}

//Verifica collegamento con il backend locale
async function getBackendStatusText() {
  try {
    const response = await fetch(`${EXTENSION_BACKEND_URL}/health`);
    if (!response.ok) {
      throw new Error(`Errore API: ${response.status}`);
    }
    return "Backend online";
  } catch (error) {
    return "Backend non raggiungibile";
  }
}
