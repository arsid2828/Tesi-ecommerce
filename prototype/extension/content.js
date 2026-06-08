const EXTENSION_BACKEND_URL = "http://localhost:8000";
const EXTENSION_BOX_ID = "thesisExtensionDemoBox";

initContentBox();
initMessageListener();

//inserisce box demo su pagina prodotto locale o Amazon riconosciuta
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
  status.textContent = product.kind === "amazon" ? "Prodotto Amazon riconosciuto" : await getBackendStatusText();
}

//legge il prodotto dalla pagina usando detector condiviso
function detectCurrentProduct() {
  return window.ThesisProductDetector.detectCurrentPage(window.location.href, document);
}

//crea box informativo senza usare HTML dinamico non sicuro
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
  note.textContent = product.kind === "amazon" ? "Riconoscimento pagina Amazon reale" : "Demo locale per prototipo di tesi";

  box.appendChild(title);
  box.appendChild(item);
  if (productTitle.textContent) {
    box.appendChild(productTitle);
  }
  box.appendChild(status);
  box.appendChild(note);

  return box;
}

//sceglie un punto poco invasivo per inserire il box
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

//risponde al popup con il prodotto rilevato nella pagina
function initMessageListener() {
  if (typeof chrome === "undefined" || !chrome.runtime || !chrome.runtime.onMessage) {
    return;
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (!message || message.type !== "GET_DETECTED_PRODUCT") {
      return false;
    }

    sendResponse({
      product: detectCurrentProduct(),
    });
    return false;
  });
}

//verifica collegamento con il backend locale
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
