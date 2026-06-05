La cartella `extension/` contiene una piccola estensione Chrome Manifest V3 collegata al prototipo locale.

L’estensione non fa scraping di Amazon o siti reali. Funziona solo sulle pagine locali del prototipo, in particolare:

```
http://localhost:3000/product.html?id=...
```

Serve a dimostrare un possibile collegamento tra pagina prodotto, backend e raccomandazioni.

---

## `extension/README.md`

Questo file spiega lo scopo dell’estensione Chrome.

Dice che l’estensione:

- mostra lo stato del backend;
- mostra la URL della tab corrente;
- rileva l’`item_id` se ci si trova su una pagina prodotto locale;
- carica il prodotto dal backend;
- carica raccomandazioni popolari;
- inserisce un box informativo nella pagina prodotto locale.

Contiene anche le istruzioni per installarla in Chrome:

1. aprire `chrome://extensions`;
2. attivare Developer mode;
3. cliccare “Load unpacked”;
4. selezionare `prototype/extension/`;
5. aprire una pagina prodotto locale;
6. usare il popup dell’estensione.

Il README chiarisce anche i limiti: è solo una demo locale, non salva cronologia, non raccoglie dati personali e non usa siti reali.

---

## `extension/manifest.json`

Questo file configura l’estensione Chrome.

Usa:

```
"manifest_version": 3
```

Definisce:

- nome estensione;
- versione;
- descrizione;
- permessi;
- host locali autorizzati;
- popup;
- content script.

I permessi principali sono:

```
activeTab
tabs
```

Gli host autorizzati sono:

```
http://localhost:8000/*
http://localhost:3000/*
```

Questo permette all’estensione di comunicare con backend e frontend locali.

Il content script viene eseguito solo sulle pagine:

```
http://localhost:3000/product.html*
```

e carica:

- `content.js`;
- `style.css`.

---

## `extension/popup.html`

Questo file definisce l’interfaccia del popup dell’estensione.

Il popup contiene:

- header “Tesi E-commerce Demo”;
- stato del backend;
- URL della tab corrente;
- stato della pagina prodotto;
- valore `item_id` rilevato;
- bottone “Carica prodotto”;
- box risultato prodotto;
- sezione raccomandazioni popolari.

Il file carica:

```
<link rel="stylesheet" href="style.css">
<script src="popup.js" defer></script>
```

Quindi la grafica è gestita da `style.css` e la logica da `popup.js`.

---

## `extension/popup.js`

Questo file contiene la logica del popup dell’estensione.

Quando il popup viene aperto, la funzione `initPopup()`:

1. legge la tab attiva;
2. mostra la URL corrente;
3. controlla se la pagina è una pagina prodotto locale;
4. abilita o disabilita il bottone “Carica prodotto”;
5. controlla se il backend è online;
6. carica le raccomandazioni popolari.

### Rilevamento pagina prodotto

La funzione `getItemIdFromProductUrl()` controlla che la URL appartenga a:

```
http://localhost:3000/product.html
```

e legge il parametro:

```
id
```

Se l’id esiste, viene considerato come `item_id`.

### Controllo backend

La funzione `checkBackendStatus()` chiama:

```
/health
```

Se il backend risponde, mostra “Backend online”. Se non risponde, mostra “Backend non raggiungibile”.

### Caricamento prodotto

Quando l’utente clicca “Carica prodotto”, la funzione `loadCurrentProduct()` chiama:

```
/products/{item_id}
```

e mostra:

- immagine;
- categoria;
- titolo;
- rating medio;
- numero recensioni.

### Raccomandazioni

La funzione `fetchRecommendations()` prova prima a chiamare:

```
/recommendations/popular?limit=5
```

Se questo endpoint non esiste o fallisce, usa il fallback:

```
/popular?limit=5
```

Questo è importante perché nel backend attuale l’endpoint `/recommendations/popular` non è ancora definito. Il fallback su `/popular` permette comunque al popup di funzionare.

### Rendering sicuro

Il popup costruisce molti elementi tramite `document.createElement()` invece di inserire grandi blocchi HTML dinamici. È una buona scelta perché riduce il rischio di problemi con testo proveniente dal dataset.

---

## `extension/content.js`

Questo file viene iniettato automaticamente nella pagina prodotto locale.

Il suo compito è aggiungere un piccolo box informativo sopra la pagina prodotto.

Il box mostra:

- titolo “Tesi E-commerce Demo”;
- `item_id` rilevato dalla URL;
- stato del backend;
- nota “Demo locale per prototipo di tesi”.

La funzione principale è:

```
initContentBox()
```

Prima controlla se il box è già presente, così evita duplicati.

Poi legge l’`item_id` dalla query string della pagina:

```
product.html?id=...
```

Se l’id esiste, crea un box HTML e lo inserisce all’inizio della pagina.

Infine chiama `/health` per mostrare se il backend è online.

Questo file non legge dati sensibili e non fa scraping: si limita a lavorare sulla pagina locale del prototipo.

---

## `extension/style.css`

Questo file contiene lo stile grafico dell’estensione.

Gestisce due parti:

1. il popup Chrome;
2. il box iniettato nella pagina prodotto.

Per il popup definisce:

- dimensione della finestra;
- header;
- sezioni;
- stato backend;
- bottone principale;
- box risultato;
- immagini prodotto;
- lista raccomandazioni;
- placeholder immagine.

Per il box iniettato nella pagina prodotto definisce:

- bordo laterale colorato;
- sfondo bianco;
- ombra;
- spaziatura;
- testo dello stato backend.

Lo stile è separato da quello del frontend, anche se usa colori simili. Questo rende l’estensione coerente visivamente con il resto del prototipo.