La logica applicativa è stata separata dagli endpoint FastAPI e organizzata nella cartella:

`prototype/backend/services/`

Sono stati creati tre service principali.

### `catalog_service.py`

Gestisce il catalogo prodotti.

Le funzioni principali permettono di:

- caricare i prodotti da `prototype/data/products_demo.json`;
- ordinare i prodotti tramite `popularity_score`;
- restituire prodotti paginati;
- filtrare i prodotti per categoria;
- cercare un prodotto tramite `item_id`;
- calcolare il riepilogo delle categorie;
- restituire i prodotti più popolari;
- pulire valori non validi, come `NaN`.

### `search_service.py`

Gestisce la ricerca testuale.

La ricerca controlla se la query compare nei principali campi testuali del prodotto:

- titolo;
- categoria;
- descrizione.

Supporta anche il filtro per categoria e restituisce i risultati ordinati per popolarità.

### `recommendation_service.py`

Contiene una prima baseline di raccomandazione.

Per ora la raccomandazione è semplice e usa l’approccio `MostPopular`: i prodotti vengono ordinati per `popularity_score` e vengono restituiti i primi `limit`.

Questa parte non contiene ancora AI o modelli di raccomandazione avanzati, ma prepara una struttura utile per evoluzioni future.