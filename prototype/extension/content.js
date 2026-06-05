const EXTENSION_BACKEND_URL = "http://localhost:8000";
const EXTENSION_BOX_ID = "thesisExtensionDemoBox";

initContentBox();

//inserisce box demo solo sulla pagina prodotto locale
async function initContentBox() {
  if (document.getElementById(EXTENSION_BOX_ID)) {
    return;
  }

  const itemId = getCurrentItemId();
  if (!itemId) {
    return;
  }

  const box = createContentBox(itemId);
  const target = document.querySelector(".page-shell") || document.body;
  target.prepend(box);

  const status = box.querySelector(".thesis-extension-status");
  status.textContent = await getBackendStatusText();
}

//legge item_id dalla query string della pagina prodotto
function getCurrentItemId() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id");
}

//crea box informativo senza usare HTML dinamico non sicuro
function createContentBox(itemId) {
  const box = document.createElement("aside");
  box.id = EXTENSION_BOX_ID;
  box.className = "thesis-extension-box";

  const title = document.createElement("strong");
  title.textContent = "Tesi E-commerce Demo";

  const item = document.createElement("span");
  item.textContent = `item_id rilevato: ${itemId}`;

  const status = document.createElement("span");
  status.className = "thesis-extension-status";
  status.textContent = "Controllo backend...";

  const note = document.createElement("span");
  note.textContent = "Demo locale per prototipo di tesi";

  box.appendChild(title);
  box.appendChild(item);
  box.appendChild(status);
  box.appendChild(note);

  return box;
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
