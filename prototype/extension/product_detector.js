//Racchiudiamo il detector in una IIFE per non sporcare lo scope globale
//Esponiamo solo ThesisProductDetector,usato da popup e content script
//La logica resta condivisa cosi ASIN/titolo vengono rilevati nello stesso modo
(function initProductDetector(globalScope) {
  const LOCAL_PRODUCT_ORIGIN = "http://localhost:3000";
  const ASIN_PATTERN = /^[A-Z0-9]{10}$/i; //ASIN Amazon:10 caratteri alfanumerici
  const AMAZON_HOST_PATTERN = /(^|\.)amazon\./i; //matcha domini e sottodomini Amazon

  //Normalizza testo letto da URL o DOM
  //Riduce spazi multipli e gestisce valori nulli
  //Serve prima di confrontare ASIN,titoli e attributi
  function cleanText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  //Converte un valore in ASIN valido o null
  //Utile per non fidarsi di URL o attributi DOM non controllati
  //La uppercase rende uniforme il valore mostrato nel popup
  function normalizeAsin(value) {
    const candidate = cleanText(value).toUpperCase();
    return ASIN_PATTERN.test(candidate) ? candidate : null; //scarta valori non compatibili con ASIN
  }

  function isAmazonHost(hostname) {
    return AMAZON_HOST_PATTERN.test(String(hostname || ""));
  }

  //Riconosce pagine prodotto locali del prototipo
  //Controlla origin e path prima di leggere id
  //Questo evita falsi positivi su URL simili
  function getLocalItemIdFromUrl(currentUrl) {
    try {
      const url = new URL(currentUrl);
      if (url.origin !== LOCAL_PRODUCT_ORIGIN || !url.pathname.endsWith("/product.html")) {
        return null;
      }
      return cleanText(url.searchParams.get("id"));
    } catch (error) {
      return null;
    }
  }

  //Estrae ASIN da URL Amazon reali
  //Gestisce formati come /dp/<ASIN>,/gp/product/<ASIN> e query pd_rd_i
  //Se l'URL non basta,il content script usera anche il DOM
  function getAmazonAsinFromUrl(currentUrl) {
    try {
      const url = new URL(currentUrl);
      if (!isAmazonHost(url.hostname)) {
        return null;
      }

      const queryKeys = ["asin", "ASIN", "pd_rd_i"]; //parametri comuni nelle URL Amazon
      for (const key of queryKeys) {
        const asin = normalizeAsin(url.searchParams.get(key));
        if (asin) {
          return asin;
        }
      }

      const segments = url.pathname.split("/").map(cleanText).filter(Boolean); //segmenti puliti del path
      const markerNames = new Set(["dp", "product", "asin", "d"]); //marker che spesso precedono ASIN
      for (let index = 0; index < segments.length - 1; index += 1) {
        if (markerNames.has(segments[index].toLowerCase())) {
          const asin = normalizeAsin(segments[index + 1]); //ASIN subito dopo il marker
          if (asin) {
            return asin;
          }
        }
      }

      for (const segment of segments) {
        const asin = normalizeAsin(segment);
        if (asin) {
          return asin;
        }
      }
    } catch (error) {
      return null;
    }

    return null;
  }

  //Legge il primo testo disponibile tra piu selector
  //Amazon cambia markup tra paesi o layout
  //Provare selector in ordine rende il detector piu robusto
  function readText(documentRef, selectors) {
    for (const selector of selectors) {
      const element = documentRef.querySelector(selector);
      const value = cleanText(element && element.textContent);
      if (value) {
        return value;
      }
    }
    return "";
  }

  //Legge il primo attributo disponibile tra piu selector
  //Usato per immagini e meta tag
  //Restituisce stringa vuota se nessun selector funziona
  function readAttribute(documentRef, selectors, attributeName) {
    for (const selector of selectors) {
      const element = documentRef.querySelector(selector);
      const value = cleanText(element && element.getAttribute(attributeName));
      if (value) {
        return value;
      }
    }
    return "";
  }

  //Cerca ASIN direttamente nel DOM Amazon
  //Prima controlla input nascosti,poi attributi data-asin
  //Questo copre pagine in cui l'URL non contiene un ASIN pulito
  function getAmazonAsinFromDocument(documentRef) {
    const valueSelectors = [
      "#ASIN",
      "input[name='ASIN']",
      "input[name='asin']",
      "input#asin",
    ];

    for (const selector of valueSelectors) {
      const element = documentRef.querySelector(selector);
      const asin = normalizeAsin(element && element.value); //input nascosti spesso contengono ASIN
      if (asin) {
        return asin;
      }
    }

    const dataSelectors = [
      "#averageCustomerReviews",
      "#centerCol",
      "#ppd",
      "[data-asin]",
    ];

    for (const selector of dataSelectors) {
      const element = documentRef.querySelector(selector);
      const asin = normalizeAsin(element && element.getAttribute("data-asin")); //fallback su attributi Amazon
      if (asin) {
        return asin;
      }
    }

    return null;
  }

  //Estrae titolo prodotto da selector Amazon o meta tag
  //Il titolo DOM e preferito perche piu vicino a quello visibile
  //Il replace finale rimuove suffissi tipo : Amazon.it
  function getAmazonTitleFromDocument(documentRef) {
    const title = readText(documentRef, [
      "#productTitle",
      "#title",
      "h1.a-size-large",
      "h1 span",
    ]);

    if (title) {
      return title;
    }

    const metaTitle = readAttribute(documentRef, [
      "meta[property='og:title']",
      "meta[name='title']",
    ], "content");

    if (metaTitle) {
      return metaTitle.replace(/\s*:\s*Amazon\..*$/i, ""); //pulisce suffisso marketplace
    }

    return cleanText(documentRef.title).replace(/\s*:\s*Amazon\..*$/i, "");
  }

  //Estrae immagine prodotto principale
  //Prima prova immagini visibili,poi og:image
  //Serve solo per mostrare anteprima nel popup
  function getAmazonImageFromDocument(documentRef) {
    return readAttribute(documentRef, [
      "#landingImage",
      "#imgTagWrapperId img",
      "#main-image",
      "meta[property='og:image']",
    ], "src") || readAttribute(documentRef, [
      "meta[property='og:image']",
    ], "content");
  }

  //Detector solo da URL
  //Usato dal popup anche quando il content script non risponde
  //Ritorna local,amazon oppure null
  function detectFromUrl(currentUrl) {
    const localItemId = getLocalItemIdFromUrl(currentUrl);
    if (localItemId) {
      return {
        kind: "local",
        itemId: localItemId,
        pageUrl: currentUrl,
      };
    }

    const amazonAsin = getAmazonAsinFromUrl(currentUrl);
    if (amazonAsin) {
      return {
        kind: "amazon",
        asin: amazonAsin,
        pageUrl: currentUrl,
      };
    }

    return null;
  }

  //Detector completo per la pagina corrente
  //Combina URL e DOM per ottenere ASIN,titolo e immagine
  //Su pagine non Amazon mantiene eventuale risultato locale o null
  function detectCurrentPage(currentUrl, documentRef) {
    const urlProduct = detectFromUrl(currentUrl);
    if (urlProduct && urlProduct.kind === "local") {
      return urlProduct;
    }

    try {
      const url = new URL(currentUrl);
      if (!isAmazonHost(url.hostname)) {
        return urlProduct;
      }
    } catch (error) {
      return urlProduct;
    }

    const asin = (urlProduct && urlProduct.asin) || getAmazonAsinFromDocument(documentRef); //URL prima,DOM come fallback
    if (!asin) {
      return null;
    }

    return {
      kind: "amazon",
      asin,
      title: getAmazonTitleFromDocument(documentRef),
      imageUrl: getAmazonImageFromDocument(documentRef),
      pageUrl: currentUrl,
    };
  }

  globalScope.ThesisProductDetector = {
    cleanText,
    detectCurrentPage,
    detectFromUrl,
    getAmazonAsinFromUrl,
    isAmazonHost,
    normalizeAsin,
  };
})(window);
