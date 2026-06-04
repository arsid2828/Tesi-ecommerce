È stato creato lo script:

`prototype/scripts/export_demo_catalog.py`

Lo script serve a generare il catalogo demo `products_demo.json` partendo da file in diversi formati.

Supporta input:

- parquet;
- csv;
- json;
- jsonl.

Le funzioni principali dello script permettono di:

- leggere il dataset di input;
- trovare colonne anche quando hanno nomi diversi;
- normalizzare testi, liste e dizionari;
- estrarre il primo URL immagine disponibile;
- trasformare le righe del dataset nel formato prodotto demo;
- calcolare `popularity_score`;
- selezionare un catalogo piccolo e bilanciato tra categorie;
- esportare il risultato finale in `products_demo.json`.

La metrica di popolarità attuale viene calcolata normalizzando `rating_count` tra 0 e 1:

```
popularity_score = rating_count normalizzato
```

Per avviare il backend:

```
python -m uvicorn prototype.backend.app:app --port 8000
```

Per avviare il frontend:

```
python -m http.server 3000 -d prototype/frontend
```

Poi aprire nel browser:

```
http://localhost:3000
```