La cartella `backend/` contiene il backend FastAPI del prototipo. Il suo compito è caricare il catalogo demo da file JSON e renderlo disponibile al frontend tramite API HTTP.

Il backend non addestra modelli, non usa database e non interroga i notebook. Legge semplicemente i dati già esportati e li serve al frontend.

---

## `backend/app.py`

Questo è il file principale del backend.

Crea l’app FastAPI con il titolo:

```
E-commerce Product Discovery Prototype
```

Abilita CORS, così il frontend locale servito su `localhost:3000` può comunicare con il backend su `localhost:8000`.

Il file definisce il percorso del catalogo demo:

```
prototype/data/products_demo.json
```

Poi crea un oggetto `CatalogService`, che carica i prodotti all’avvio del backend.

Gli endpoint implementati sono:

```
GET /health
```

Serve per controllare se il backend è online.

```
GET /products
```

Restituisce una lista di prodotti, con supporto a `limit`, `offset` e filtro per categoria.

```
GET /products/{item_id}
```

Restituisce il dettaglio di un singolo prodotto. Se il prodotto non esiste, restituisce errore 404.

```
GET /categories
```

Restituisce le categorie disponibili e il numero di prodotti per categoria.

```
GET /popular
```

Restituisce i prodotti più popolari secondo `popularity_score`.

```
GET /search
```

Esegue una ricerca testuale semplice su titolo, categoria e descrizione.

Questo file rappresenta il punto di collegamento tra frontend e dati del prototipo.

---

## `backend/schemas.py`

Questo file definisce gli schemi Pydantic usati dal backend.

Contiene tre classi principali.

### `Product`

Rappresenta un prodotto del catalogo.

I campi principali sono:

- `item_id`;
- `title`;
- `category`;
- `description`;
- `price`;
- `average_rating`;
- `rating_count`;
- `popularity_score`;
- `image_url`.

Questo schema serve a standardizzare il formato dei prodotti restituiti dalle API.

### `CategorySummary`

Rappresenta una categoria con il numero di prodotti associati.

Contiene:

- `category`;
- `count`.

### `HealthResponse`

Rappresenta la risposta dell’endpoint `/health`.

Contiene solo:

```
status
```

Attualmente viene restituito `status="ok"`.

---

## `backend/services/`

Questa cartella contiene la logica applicativa del backend, separata dagli endpoint FastAPI.

La scelta è corretta perché evita di mettere tutta la logica dentro `app.py`. In questo modo il backend resta più ordinato e più facile da estendere.

---

## `backend/services/__init__.py`

È un file quasi vuoto che serve a Python per trattare la cartella `services/` come un modulo importabile.

Non contiene logica applicativa, ma è utile per permettere import come:

```
from prototype.backend.services.catalog_service import CatalogService
```

---

## `backend/services/catalog_service.py`

Questo file gestisce il catalogo prodotti.

La classe principale è:

```
CatalogService
```

Quando viene creata, riceve il percorso del file `products_demo.json`, carica i prodotti e costruisce un dizionario interno per recuperarli rapidamente tramite `item_id`.

Le funzioni principali sono:

### `_load_products()`

Carica il file JSON del catalogo demo.

Se il file non esiste, restituisce una lista vuota. Questo evita che il backend crashi subito quando manca la cartella `data/`.

Durante il caricamento:

- pulisce i valori `NaN`;
- converte ogni riga in un oggetto `Product`;
- tiene solo i prodotti con prezzo disponibile;
- ordina i prodotti per `popularity_score` decrescente.

Questa scelta è importante: nel sito vengono mostrati solo prodotti con `price` valido e maggiore di zero.

### `_clean_row()` e `_clean_value()`

Servono a pulire i valori letti dal JSON.

In particolare, se trova un valore `NaN`, lo converte in `None`, così Pydantic e JSON non danno problemi.

### `_has_price()`

Filtra i prodotti senza prezzo.

Attualmente un prodotto viene mantenuto solo se:

```
price is not None
price > 0
```

Questa scelta rende il catalogo più realistico, ma può ridurre il numero di prodotti mostrati se molti prodotti non hanno prezzo.

### `list_products()`

Restituisce i prodotti con paginazione e filtro opzionale per categoria.

Supporta:

- `limit`;
- `offset`;
- `category`.

### `get_product()`

Cerca un prodotto tramite `item_id`.

Usa un dizionario interno, quindi la ricerca è veloce.

### `categories()`

Conta quanti prodotti ci sono per ogni categoria e restituisce una lista ordinata alfabeticamente.

### `popular()`

Restituisce i primi prodotti del catalogo, già ordinati per popolarità.

### `all_products()`

Restituisce una copia della lista prodotti, usata ad esempio dal servizio di ricerca.

---

## `backend/services/search_service.py`

Questo file gestisce la ricerca testuale.

La funzione principale è:

```
search_products()
```

Riceve:

- lista prodotti;
- query testuale;
- categoria opzionale;
- limite di risultati.

La ricerca funziona così:

1. se è selezionata una categoria, filtra prima i prodotti di quella categoria;
2. normalizza la query in minuscolo;
3. controlla se la query compare in titolo, categoria o descrizione;
4. ordina i risultati per `popularity_score`;
5. restituisce solo i primi `limit` risultati.

È una ricerca semplice basata su substring matching.

Non usa ancora:

- TF-IDF;
- BM25;
- embedding;
- modelli NLP;
- ricerca semantica.

Questa scelta va bene per una prima demo, perché permette di avere una funzione di ricerca comprensibile e facile da spiegare.

---

## `backend/services/recommendation_service.py`

Questo file contiene una prima funzione di raccomandazione baseline:

```
most_popular()
```

La funzione ordina i prodotti per `popularity_score` decrescente e restituisce i primi `limit`.

Al momento è una baseline molto semplice: non usa utenti, storico, sessioni o modelli collaborativi.

Nota importante: nel backend attuale questa funzione non è ancora collegata a un endpoint dedicato tipo:

```
/recommendations/popular
```

Il backend espone invece:

```
/popular
```

Quindi `recommendation_service.py` è utile come base futura, ma attualmente la raccomandazione viene servita soprattutto tramite l’endpoint `/popular`.

---

## `backend/__pycache__/` e `backend/services/__pycache__/`

Queste cartelle contengono file generati automaticamente da Python, ad esempio file `.pyc`.

Non sono parte del codice scritto manualmente.

Servono a Python per velocizzare l’esecuzione, ma non vanno spiegate nella tesi come componenti del prototipo.

Idealmente possono essere escluse da Git con `.gitignore`.