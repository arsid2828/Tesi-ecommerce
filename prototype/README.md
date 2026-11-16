# Avvio del prototipo

## Preparare il catalogo

Dalla radice del repository, in un ambiente Python (la demo è stata verificata con Python 3.13):

```bash
python -m pip install -r requirements.txt jupyterlab
python -m jupyterlab prototype/notebooks/01_prepare_prototype_amazon_like_intersection.ipynb
```

Esegui le celle del notebook in ordine. La prima esecuzione scarica ed elabora i dati e può richiedere tempo. Il notebook genera `prototype/data/products_demo.json` e i parquet con recensioni e domande e risposte in `prototype/data/processed/prototype_amazon_like_intersection/`.

Il JSON serve per popolare la demo. Quando sono presenti, i parquet aggiungono evidenze alle schede dei risultati raggruppati. Le classifiche per i due profili della home sono già esportate in `backend/assets/home_profiles.json`. Per rigenerarle occorre eseguire i cinque notebook di [`test_dataset2`](../notebooks/test_dataset2/) e poi lanciare `python prototype/scripts/export_home_profiles.py` dalla radice.

## Avviare la demo

Dalla radice, avvia il backend e il frontend in due terminali con lo stesso ambiente Python:

```bash
python -m uvicorn prototype.backend.app:app --port 8000
```

```bash
python -m http.server 3000 -d prototype/frontend
```

Apri [localhost:3000](http://localhost:3000). Puoi cambiare profilo in home, cercare `mouse wireless` in lista o a gruppi e aprire una scheda prodotto. La [documentazione delle API](http://localhost:8000/docs) è generata da FastAPI. Per il popup, segui le [istruzioni dell’estensione Chrome](extension/README.md).

## Usare Gemini

La ricerca a gruppi funziona anche con regole locali. Per attivare Gemini, crea `prototype/.env` con la tua chiave prima di avviare il backend:

```dotenv
GEMINI_API_KEY=la_tua_chiave
GEMINI_MODEL=gemini-2.5-flash
```

La chiave è letta dal backend. Per la ricerca a gruppi Gemini lavora sui candidati recuperati dal catalogo. Se la risposta non produce gruppi validi, il backend usa il raggruppamento locale.
