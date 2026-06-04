# Product Discovery Prototype

## Obiettivo

Primo prototipo minimale per una tesi su recommender system e product discovery in e-commerce. Serve a testare la struttura applicativa iniziale: catalogo Amazon-like, ricerca testuale, ordinamento per popolarita, pagina dettaglio e immagini prodotto con fallback.

Non include AI, clustering, database, estensione Chrome o chiamate a servizi esterni.

## Struttura

```text
prototype/
  data/
    products_demo.json
  backend/
    __init__.py
    app.py
    schemas.py
    services/
      __init__.py
      catalog_service.py
      search_service.py
      recommendation_service.py
  frontend/
    index.html
    product.html
    app.js
    style.css
  scripts/
    export_demo_catalog.py
  README.md
```

## Esportare il catalogo demo

Esempio con un file gia presente nei dati processati:

```bash
python prototype/scripts/export_demo_catalog.py --input data/processed/test_dataset2_intersection/items.parquet --output prototype/data/products_demo.json --limit 200
```

Lo script accetta input parquet, csv, json e jsonl. Normalizza colonne con nomi diversi, calcola `popularity_score` normalizzando `rating_count` tra 0 e 1, prova a estrarre il primo URL immagine disponibile e crea un catalogo piccolo e bilanciato tra categorie.

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
- `GET /recommendations/popular?limit=10`

## Avviare il frontend

```bash
python -m http.server 3000 -d prototype/frontend
```

Poi aprire:

```text
http://localhost:3000
```

## Limiti della prima versione

- Ricerca solo testuale con match semplice su titolo, categoria e descrizione.
- Raccomandazioni solo baseline MostPopular.
- Dati caricati da JSON locale a ogni avvio del backend.
- Nessun profilo utente, storico interazioni o personalizzazione.
- Nessun database e nessuna pipeline di training.

## Idee future

- Aggiungere filtri per prezzo, rating e disponibilita di immagine.
- Introdurre metriche offline per confrontare baseline e modelli.
- Integrare una pagina di confronto tra MostPopular, content-based e modelli collaborativi.
- Aggiungere logging delle query e valutazione della product discovery.
- Passare a un backend dati piu strutturato solo quando il prototipo cresce.

