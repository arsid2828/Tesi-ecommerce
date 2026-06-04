Il backend è stato implementato con FastAPI nella cartella:

`prototype/backend/`

Il file principale è:

`prototype/backend/app.py`

Sono stati creati gli endpoint principali per servire il catalogo prodotti:

- `GET /health`  
    Restituisce lo stato del backend.
- `GET /products`  
    Restituisce i prodotti ordinati per popolarità, con supporto a `limit`, `offset` e filtro per categoria.
- `GET /products/{item_id}`  
    Restituisce il dettaglio di un singolo prodotto.
- `GET /categories`  
    Restituisce le categorie disponibili con il relativo numero di prodotti.
- `GET /popular`  
    Restituisce i prodotti più popolari.
- `GET /search`  
    Esegue una ricerca testuale su titolo, categoria e descrizione.
- `GET /recommendations/popular`  
    Restituisce raccomandazioni baseline basate sui prodotti più popolari.

Nel file:

`prototype/backend/schemas.py`

sono stati definiti gli schemi Pydantic usati dal backend:

- `Product`, per rappresentare un prodotto;
- `CategorySummary`, per rappresentare una categoria con conteggio;
- `HealthResponse`, per la risposta dell’endpoint di health check.

È stato inoltre corretto un problema legato ai valori `NaN`, in particolare su `image_url`, trasformandoli in `null`/`None` per evitare errori di validazione Pydantic.

---