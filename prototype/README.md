# Product Discovery Prototype

## Obiettivo

Prototipo web minimale per una tesi triennale su recommender system e product discovery in e-commerce. Include catalogo Amazon-like, ricerca testuale locale, ricerca assistita da Gemini con fallback locale, clustering demo dei risultati di ricerca e QA grounded nella pagina dettaglio prodotto.

Il progetto resta volutamente semplice: dati JSON/parquet locali, backend FastAPI, frontend statico HTML/CSS/JavaScript, nessun database e nessuna chiave API nel frontend.

## Struttura

```text
prototype/
  data/
    products_demo.json
    processed/prototype_amazon_like_intersection/
      qa.parquet
      ratings.parquet
  backend/
    app.py
    schemas.py
    services/
      ai_search_service.py
      catalog_service.py
      clustering_service.py
      product_qa_service.py
      recommendation_service.py
      search_service.py
  frontend/
    index.html
    product.html
    app.js
    style.css
  scripts/
    export_demo_catalog.py
```

## Configurazione AI opzionale

Gemini e opzionale. Se la chiave manca, il backend usa fallback locali.

Creare un file `.env` nella root del progetto o in `prototype/`:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

La chiave viene letta solo dal backend.

## Avviare il backend

```bash
uvicorn prototype.backend.app:app --reload --port 8000
```

Endpoint principali:

- `GET /health`
- `GET /products?limit=30&offset=0&category=...`
- `GET /products/{item_id}`
- `GET /categories`
- `GET /popular?limit=20`
- `GET /search?q=...&category=...&limit=30`
- `POST /ai-search`
- `POST /search/clustered`
- `POST /products/{item_id}/qa`

## Clustering dei risultati

Nel catalogo e disponibile la checkbox `Raggruppa risultati in cluster`.

Quando e attiva, il frontend chiama:

```http
POST /search/clustered
```

Esempio payload:

```json
{
  "query": "telefoni",
  "category": null,
  "limit": 40,
  "use_ai_labels": true
}
```

Il backend:

- esegue prima la ricerca locale sui prodotti;
- clusterizza solo quei risultati con TF-IDF e MiniBatchKMeans;
- sceglie 1, 2, 3 o massimo 5 cluster in base al numero di risultati;
- usa Gemini solo per label/descrizione dei cluster, se disponibile;
- mantiene sempre i prodotti originali dei risultati, senza far scegliere item all'AI.

Se Gemini o scikit-learn non sono disponibili, la risposta resta locale e serializzabile.

## QA nella pagina prodotto

In `product.html?id=...` e presente la sezione `Domande sul prodotto`.

Il frontend chiama:

```http
POST /products/{item_id}/qa
```

Esempio payload:

```json
{
  "question": "La batteria dura tanto?",
  "use_ai": true
}
```

Il backend costruisce documenti testuali solo per quel prodotto:

- metadati e descrizione da `products_demo.json`;
- QA storiche da `qa.parquet`, se presente;
- recensioni testuali da `ratings.parquet`, se presente;
- futuri file opzionali `qa_demo.json`, `product_qa_demo.json`, `reviews_demo.json`, `product_reviews_demo.json`.

La domanda viene confrontata con i chunk tramite TF-IDF. Gemini, se disponibile, riceve solo domanda ed evidenze recuperate. Se le evidenze non bastano, la risposta dichiara esplicitamente che non ci sono abbastanza informazioni.

## Avviare il frontend

```bash
python -m http.server 3000 -d prototype/frontend
```

Poi aprire:

```text
http://localhost:3000
```

## Test manuali rapidi

Backend:

```bash
curl http://localhost:8000/health
curl "http://localhost:8000/search?q=phone&limit=5"
curl -X POST http://localhost:8000/search/clustered -H "Content-Type: application/json" -d "{\"query\":\"telefoni\",\"limit\":40,\"use_ai_labels\":false}"
curl -X POST http://localhost:8000/products/B0002GTTRC/qa -H "Content-Type: application/json" -d "{\"question\":\"Come si installa il filtro?\",\"use_ai\":false}"
```

Frontend:

- ricerca normale con checkbox clustering disattivata;
- ricerca `telefoni` con checkbox clustering attivata;
- click su una card clusterizzata e apertura dettaglio prodotto;
- domanda nella sezione QA del prodotto;
- prova senza `GEMINI_API_KEY` per verificare i fallback locali.

## Limiti rimasti

- La ricerca locale resta semplice e basata su match testuali con pochi sinonimi IT->EN.
- Il clustering e dimostrativo, non semantico profondo.
- Il QA e retrieval-based: risponde solo se trova evidenze nei dati locali.
- Nessun profilo utente, storico interazioni, database o personalizzazione online.
