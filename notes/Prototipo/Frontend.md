Il frontend è stato implementato in modo statico, senza React, nella cartella:

`prototype/frontend/`

Sono state create due pagine principali.

### `index.html`

È la home del prototipo.

Contiene:

- titolo del sito;
- barra di ricerca;
- filtro categoria;
- bottone di ricerca;
- sezione risultati;
- sezione prodotti popolari.

Quando viene aperta la pagina su:

`http://localhost:3000`

il frontend chiama il backend FastAPI e mostra i prodotti disponibili.

### `product.html`

È la pagina di dettaglio prodotto.

Legge l’id del prodotto dalla query string:

`product.html?id=...`

e mostra:

- immagine grande;
- titolo;
- categoria;
- descrizione;
- rating medio;
- numero di recensioni;
- popularity score;
- prodotti consigliati tramite baseline `MostPopular`.

### `app.js`

Il file `app.js` contiene la logica principale del frontend.

Le funzioni più importanti sono:

- `initCatalogPage()`, per inizializzare la home;
- `initProductPage()`, per inizializzare la pagina dettaglio;
- `fetchJson(path)`, per effettuare chiamate al backend;
- `loadCategories()`, per caricare le categorie;
- `loadInitialProducts()`, per caricare i prodotti iniziali;
- `loadPopularProducts()`, per mostrare i prodotti popolari;
- `runSearch()`, per eseguire la ricerca;
- `createProductCard(product)`, per creare le card prodotto;
- `renderProductDetail(product)`, per mostrare il dettaglio prodotto;
- `createImageBox(product, className)`, per gestire immagini e fallback.

### `style.css`

Il file `style.css` gestisce la parte grafica del prototipo.

Sono stati curati:

- layout responsive;
- griglia prodotti;
- card prodotto;
- pagina dettaglio;
- gestione delle immagini;
- fallback quando un’immagine non è disponibile;
- correzione delle sovrapposizioni tra immagini e testi.

Durante il lavoro sono state anche rimosse scritte provvisorie, come “Tesi Informatica”, e sono stati aggiunti commenti prima delle funzioni e dei blocchi principali.