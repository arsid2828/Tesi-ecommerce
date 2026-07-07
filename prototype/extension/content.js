// Content script invisibile dell'estensione.
// Rileva prodotto corrente e candidati Amazon reali, poi li espone al popup via messaggi Chrome.

initMessageListener();

// Legge il prodotto corrente con il detector condiviso tra popup e content script.
// Mantiene una sola fonte di verita per pagine locali e pagine prodotto Amazon.
function detectCurrentProduct() {
  return window.ThesisProductDetector.detectCurrentPage(window.location.href, document);
}

// Estrae candidati Amazon gia presenti nel DOM della pagina corrente.
// Non cerca sul web e non inventa prodotti: prende solo link /dp o /gp/product visibili.
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
      product_url: canonicalAmazonProductUrl(href, asin),
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

// Risale dal link Amazon al contenitore visuale piu vicino.
// Serve per leggere titolo, prezzo, rating e sezione senza dipendere da un solo markup.
function findAmazonCandidateContainer(anchor) {
  return anchor.closest(".a-carousel-card, [data-asin], li, tr, .p13n-sc-uncoverable-faceout")
    || anchor.parentElement
    || anchor;
}

// Sceglie il titolo candidato piu informativo tra attributi, testo e immagini.
// Filtra stringhe generiche per evitare bottoni, sponsor o testi non prodotto.
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

// Legge l'immagine del candidato da link o contenitore Amazon.
// Restituisce null se la card non espone un URL immagine utilizzabile.
function readAmazonCandidateImage(anchor, container) {
  return readFirstText(anchor, ["img"], "src")
    || readFirstText(container, ["img"], "src")
    || readFirstText(container, ["img"], "data-src")
    || null;
}

// Estrae prezzo visibile dalla card Amazon.
// Usa selector noti e fallback regex per simboli valuta nel testo del contenitore.
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

// Estrae rating leggibile dalla card Amazon quando presente.
// Cerca prima attributi aria-label, poi testo alternativo dell'icona rating.
function readAmazonCandidateRating(container) {
  const rating = readFirstText(container, [
    "[aria-label*='stelle']",
    "[aria-label*='stars']",
    ".a-icon-alt",
  ], "aria-label");
  return rating || readFirstText(container, [".a-icon-alt"]);
}

// Cerca il nome della sezione Amazon che contiene il candidato.
// Risale pochi livelli nel DOM per associare ogni prodotto alla fonte visibile.
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

// Classifica il candidato come simile, alternativo o complementare.
// Combina label della sezione, titolo del candidato e overlap con il prodotto sorgente.
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

// Legge il primo testo o attributo disponibile da una lista di selector.
// Centralizza i fallback DOM per non ripetere controlli null in ogni extractor.
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

// Valida che una stringa sembri un titolo prodotto reale.
// Scarta call-to-action, testi sponsor e label troppo corte o troppo lunghe.
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

// Calcola una somiglianza semplice tra due testi tramite token condivisi.
// E un fallback leggero adatto al content script, senza librerie esterne.
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

// Trasforma testo libero in token confrontabili.
// Mantiene parole alfanumeriche di almeno tre caratteri per ridurre rumore.
function tokenize(value) {
  return cleanText(value)
    .toLowerCase()
    .match(/[a-z0-9][a-z0-9-]{2,}/g) || [];
}

// Converte URL relativi o redirect locali in URL assoluti.
// Se il valore non e parsabile restituisce stringa vuota invece di lanciare errore.
function absoluteUrl(value) {
  try {
    return new URL(value, window.location.href).toString();
  } catch (error) {
    return "";
  }
}

// Estrae ASIN da link prodotto Amazon diretti o redirect.
// Riusa il detector condiviso e controlla anche parametri di redirect comuni.
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

// Normalizza un link Amazon alla pagina prodotto canonica /dp/<ASIN>.
// Mantiene l'href originale come fallback se URL non e parsabile.
function canonicalAmazonProductUrl(href, asin) {
  try {
    const url = new URL(href);
    return `${url.origin}/dp/${encodeURIComponent(asin)}`;
  } catch (error) {
    return href;
  }
}

// Pulisce testo proveniente dal DOM.
// Collassa whitespace multipli e protegge i caller da valori null o undefined.
function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

// Risponde al popup con prodotto e candidati Amazon reali rilevati nella pagina.
// Questo e l'unico comportamento attivo del content script: nessuna UI viene iniettata.
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
