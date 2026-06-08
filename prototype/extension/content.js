const EXTENSION_BACKEND_URL = "http://localhost:8000";
const EXTENSION_BOX_ID = "thesisExtensionDemoBox";

initContentBox();
initMessageListener();

//Inserisce box demo su pagina prodotto locale o Amazon riconosciuta
//Evita duplicati controllando l'id del box prima di crearne uno nuovo
//Su Amazon non chiama il backend,per ora segnala solo riconoscimento
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
  status.textContent = product.kind === "amazon" ? "Prodotto Amazon riconosciuto" : await getBackendStatusText(); //backend serve solo per pagine locali
}

//Legge il prodotto dalla pagina usando detector condiviso
//Il content script puo accedere al DOM della pagina attiva
//Per questo integra titolo e immagine che il popup da solo non vede
function detectCurrentProduct() {
  return window.ThesisProductDetector.detectCurrentPage(window.location.href, document);
}

//Crea box informativo senza usare HTML dinamico non sicuro
//Usa solo createElement/textContent per evitare HTML non controllato
//Il contenuto cambia tra prodotto locale e prodotto Amazon
function createContentBox(product) {
  const box = document.createElement("aside");
  box.id = EXTENSION_BOX_ID;
  box.className = product.kind === "amazon" ? "thesis-extension-box amazon-detected" : "thesis-extension-box"; //classe extra per adattare layout Amazon

  const title = document.createElement("strong");
  title.textContent = "Tesi E-commerce Demo";

  const item = document.createElement("span");
  item.textContent = product.kind === "amazon" ? `ASIN rilevato: ${product.asin}` : `item_id rilevato: ${product.itemId}`; //id diverso nei due ambienti

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

//Sceglie un punto poco invasivo per inserire il box
//Su Amazon prova ad inserirlo vicino al titolo prodotto
//Se i selector non esistono,usa body/page-shell come fallback
function insertContentBox(box, product) {
  if (product.kind === "amazon") {
    const amazonTarget = document.querySelector("#titleSection") || document.querySelector("#centerCol"); //selector comuni nelle pagine prodotto Amazon
    if (amazonTarget && amazonTarget.parentElement) {
      amazonTarget.insertAdjacentElement("afterend", box);
      return;
    }
  }

  const target = document.querySelector(".page-shell") || document.body;
  target.prepend(box);
}

//Risponde al popup con il prodotto rilevato nella pagina
//Il popup manda GET_DETECTED_PRODUCT per ottenere dati DOM
//Ritorniamo false perche la risposta e sincrona
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
    return false; //nessuna risposta asincrona da mantenere aperta
  });
}

//Verifica collegamento con il backend locale
//Usata solo sul prototipo localhost
//Su Amazon il box non ha bisogno del backend
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
