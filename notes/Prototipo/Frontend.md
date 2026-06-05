La cartella `frontend/` contiene il sito statico del prototipo.

È scritto con:

- HTML;
- CSS;
- JavaScript vanilla.

Non usa React, Vue o altri framework. Questa scelta mantiene il prototipo semplice e adatto a una tesi triennale.

---

## `frontend/index.html`

Questo file rappresenta la pagina principale del catalogo.

Contiene l’intestazione del sito e un layout diviso in due parti:

1. pannello laterale dei filtri;
2. area dei risultati.

Nel pannello filtri sono presenti:

- campo di ricerca testuale;
- selettore categoria;
- ordinamento;
- filtro prezzo minimo/massimo;
- filtro rating minimo;
- filtro numero minimo di recensioni;
- bottone “Applica”;
- bottone “Reset”.

L’area risultati contiene due sezioni:

```
Risultati
```

e

```
Prodotti popolari
```

La pagina non contiene direttamente i prodotti nel codice HTML. I prodotti vengono caricati dinamicamente da `app.js`, che chiama il backend FastAPI.

Il body contiene:

```
<body data-page="catalog">
```

Questo attributo serve a `app.js` per capire che deve inizializzare la pagina catalogo.

---

## `frontend/product.html`

Questo file rappresenta la pagina dettaglio prodotto.

Contiene:

- link per tornare al catalogo;
- titolo “Dettaglio prodotto”;
- sezione `productDetail`, riempita dinamicamente via JavaScript;
- sezione “Consigliati”, basata sulla baseline MostPopular;
- griglia `recommendationsGrid`.

La pagina legge l’id del prodotto dalla URL, nel formato:

```
product.html?id=...
```

Anche questa pagina non contiene dati statici del prodotto. I dati vengono caricati dal backend tramite `app.js`.

Il body contiene:

```
<body data-page="product">
```

Questo permette a `app.js` di inizializzare la logica della pagina dettaglio.

---

## `frontend/app.js`

Questo è il file JavaScript principale del frontend.

Contiene tutta la logica client-side del prototipo.

La costante principale è:

```
BASE_API_URL="http://localhost:8000"
```

Quindi il frontend comunica con il backend FastAPI locale.

### Stato interno

Il file mantiene uno stato minimo:

```
state = {
  categories: [],
  currentProducts: [],
  priceFilterActive: false
}
```

Serve a ricordare le categorie caricate, i prodotti correnti e se il filtro prezzo è attivo.

### Inizializzazione pagine

Quando il DOM è caricato, il codice controlla:

```
document.body.dataset.page
```

Se la pagina è `catalog`, chiama:

```
initCatalogPage()
```

Se la pagina è `product`, chiama:

```
initProductPage()
```

### Catalogo

La funzione `initCatalogPage()`:

- carica le categorie;
- carica i prodotti iniziali;
- carica i prodotti popolari;
- collega gli event listener ai filtri;
- abilita ricerca, ordinamento, reset e filtri laterali.

### Ricerca

La funzione `runSearch()` legge:

- testo inserito dall’utente;
- categoria selezionata.

Poi chiama il backend:

```
/search?q=...&limit=500&category=...
```

I risultati vengono salvati in `state.currentProducts`.

Dopo la ricerca, i filtri lato frontend vengono applicati con:

```
applyCatalogFilters()
```

### Filtri lato frontend

La funzione `applyCatalogFilters()` applica:

- filtro prezzo;
- filtro rating minimo;
- filtro numero minimo di recensioni;
- ordinamento.

Gli ordinamenti disponibili sono:

- popolarità;
- prezzo crescente;
- prezzo decrescente;
- rating migliore;
- più recensioni.

Questo significa che la ricerca principale è backend-side, mentre alcuni filtri sono gestiti direttamente nel browser.

### Pagina dettaglio

La funzione `initProductPage()` legge `item_id` dalla query string.

Poi carica:

- dettaglio prodotto tramite `/products/{item_id}`;
- raccomandazioni tramite `/popular?limit=8`.

### Rendering prodotti

Il file contiene funzioni per costruire dinamicamente le card prodotto:

- `renderProducts()`;
- `createProductCard()`;
- `renderProductDetail()`;
- `createImageBox()`.

Le card mostrano:

- immagine o fallback;
- categoria;
- titolo;
- prezzo;
- rating medio;
- numero recensioni;
- bottone “Dettagli”.

### Gestione immagini

Se un prodotto non ha immagine, oppure se il caricamento fallisce, viene mostrato un placeholder:

```
Immagine non disponibile
```

### Sicurezza base

Il file contiene anche una funzione `escapeHtml()`, usata per evitare di inserire testo non pulito direttamente nell’HTML.

Questo è utile perché titoli e descrizioni arrivano da dataset esterni.

---

## `frontend/style.css`

Questo file gestisce tutta la grafica del sito.

Definisce variabili CSS globali per:

- colori;
- sfondo;
- superfici;
- testo;
- bordi;
- accento;
- ombre.

Gestisce il layout principale del catalogo con:

- header;
- contenitore centrale;
- pannello filtri laterale;
- area risultati;
- griglie prodotto;
- card prodotto.

Le card prodotto hanno:

- immagine centrata;
- categoria;
- titolo;
- prezzo;
- metadati rating/recensioni;
- bottone dettaglio.

Il file gestisce anche la pagina dettaglio con:

- layout a due colonne;
- immagine grande;
- descrizione;
- statistiche prodotto;
- griglia dei consigli.

Sono presenti regole responsive per schermi piccoli. Su mobile il layout passa da griglia a colonna singola.

Lo stile è minimale ma già abbastanza ordinato per una demo: non punta a imitare Amazon, ma a mostrare in modo chiaro prodotti, filtri e risultati.