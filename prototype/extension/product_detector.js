(function initProductDetector(globalScope) {
  const LOCAL_PRODUCT_ORIGIN = "http://localhost:3000";
  const ASIN_PATTERN = /^[A-Z0-9]{10}$/i;
  const AMAZON_HOST_PATTERN = /(^|\.)amazon\./i;

  function cleanText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function normalizeAsin(value) {
    const candidate = cleanText(value).toUpperCase();
    return ASIN_PATTERN.test(candidate) ? candidate : null;
  }

  function isAmazonHost(hostname) {
    return AMAZON_HOST_PATTERN.test(String(hostname || ""));
  }

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

  function getAmazonAsinFromUrl(currentUrl) {
    try {
      const url = new URL(currentUrl);
      if (!isAmazonHost(url.hostname)) {
        return null;
      }

      const queryKeys = ["asin", "ASIN", "pd_rd_i"];
      for (const key of queryKeys) {
        const asin = normalizeAsin(url.searchParams.get(key));
        if (asin) {
          return asin;
        }
      }

      const segments = url.pathname.split("/").map(cleanText).filter(Boolean);
      const markerNames = new Set(["dp", "product", "asin", "d"]);
      for (let index = 0; index < segments.length - 1; index += 1) {
        if (markerNames.has(segments[index].toLowerCase())) {
          const asin = normalizeAsin(segments[index + 1]);
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

  function getAmazonAsinFromDocument(documentRef) {
    const valueSelectors = [
      "#ASIN",
      "input[name='ASIN']",
      "input[name='asin']",
      "input#asin",
    ];

    for (const selector of valueSelectors) {
      const element = documentRef.querySelector(selector);
      const asin = normalizeAsin(element && element.value);
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
      const asin = normalizeAsin(element && element.getAttribute("data-asin"));
      if (asin) {
        return asin;
      }
    }

    return null;
  }

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
      return metaTitle.replace(/\s*:\s*Amazon\..*$/i, "");
    }

    return cleanText(documentRef.title).replace(/\s*:\s*Amazon\..*$/i, "");
  }

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

    const asin = (urlProduct && urlProduct.asin) || getAmazonAsinFromDocument(documentRef);
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
