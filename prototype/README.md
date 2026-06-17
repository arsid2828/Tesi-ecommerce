# Product Discovery Prototype

## Obiettivo

Prototipo web minimale per una tesi triennale su product discovery AI-first in e-commerce.
La home usa una sola query testuale, raggruppa i prodotti per ruolo d'acquisto e spiega le scelte con evidenze locali da catalogo, recensioni e QA storiche.

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
      catalog_service.py
      discovery_service.py
      product_qa_service.py
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

Gemini e opzionale. Se la chiave manca, il backend usa solo fallback locali.

Creare un file `.env` nella root del progetto o in `prototype/`:

```bash
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

La chiave viene letta solo dal backend. Gemini puo rifinire testi, label e descrizioni dei gruppi gia calcolati, ma non sceglie prodotti e non inventa evidenze.

## Avviare il backend

```bash
uvicorn prototype.backend.app:app --reload --port 8000
```

Endpoint del sito:

- `GET /health`
- `GET /products/{item_id}`
- `POST /discover`

## Ricerca AI-first a ruoli

La home non espone filtri manuali. L'utente scrive una query anche semplice, per esempio `mouse`, oppure una richiesta piu lunga, per esempio `mouse gaming wireless`.

Il frontend chiama:

```http
POST /discover
```

Esempio payload:

```json
{
  "query": "mouse gaming wireless",
  "limit": 80,
  "use_ai_support": true
}
```

Il backend:

- recupera candidati dal catalogo locale con ricerca testuale e sinonimi controllati;
- costruisce gruppi per ruolo come migliore scelta, economici, compromesso, stessa marca, prodotti complementari e alternative popolari;
- motiva ogni prodotto con evidenze locali;
- indica se le evidenze arrivano da metadati, recensioni o QA storiche;
- usa Gemini solo come supporto opzionale per rifinire copy e label, senza permettere all'AI di scegliere prodotti o inventare dati.

Se Gemini non e disponibile, la risposta resta completamente locale.

## Evidenze locali

Le evidenze usate dalla discovery vengono recuperate localmente da:

- metadati e descrizione da `products_demo.json`;
- QA storiche da `qa.parquet`, se presente;
- recensioni testuali da `ratings.parquet`, se presente;
- futuri file opzionali `qa_demo.json`, `product_qa_demo.json`, `reviews_demo.json`, `product_reviews_demo.json`.

La pagina dettaglio prodotto contiene solo il dettaglio del prodotto. Q&A e consigliati non sono piu esposti nel sito.

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
curl -X POST http://localhost:8000/discover -H "Content-Type: application/json" -d "{\"query\":\"mouse\",\"limit\":80,\"use_ai_support\":false}"
```

Frontend:

- ricerca `mouse` e verifica gruppi per ruolo;
- ricerca `mouse gaming wireless` e verifica prodotti complementari separati;
- click su una card e apertura dettaglio prodotto senza sezione Q&A e senza consigliati;
- prova senza `GEMINI_API_KEY` per verificare i fallback locali.

## Limiti rimasti

- La ricerca locale resta semplice e basata su match testuali, sinonimi IT->EN e ruoli euristici.
- Alcuni ruoli dipendono dalla copertura del catalogo: se mancano prodotti reali, il sistema mostra solo alternative grounded.
- Le evidenze da recensioni e QA compaiono solo quando i parquet locali contengono dati rilevanti per quel prodotto.
- Nessun profilo utente, storico interazioni, database o personalizzazione online.
