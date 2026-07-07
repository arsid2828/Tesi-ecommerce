# Product Discovery Prototype

## Obiettivo

Prototipo web minimale per una tesi triennale sui recommender system e sulla product discovery in e-commerce.
La home permette di confrontare due profili: un cold start servito soltanto dalla baseline Popular e un utente reale del dataset con 118 prodotti nello storico, servito dal miglior modello ibrido validato.

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
    export_home_profiles.py
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
- `GET /home/profiles`
- `GET /home/recommendations/{profile_id}`
- `GET /search`
- `GET /products/{item_id}`
- `GET /popular`
- `GET /recommendations/popular`
- `GET /recommendations/contextual/{item_id}`
- `POST /amazon/recommendations`
- `POST /discover`

## Home con due profili

La home espone due viste selezionabili:

- `cold-start`: nessuna interazione disponibile; ranking prodotto esclusivamente da `Popular`;
- `dataset-user`: utente `AEHOFUNZP6VT74RUDDCJ2VVIT56A`, scelto automaticamente per lo storico di training piu lungo (`118` prodotti, `120` interazioni note); ranking prodotto da `HybridGrid_SVD4_010_Content_025_Pop_065`.

Il miglior ibrido e quello con il miglior `NDCG@10` sul validation set di `test_dataset2 / AmazonLike_v1` (`0.311657`). I pesi sono `10% SVD`, `25% Content TF-IDF` e `65% Popular`.

Le raccomandazioni del profilo storico sono esportate in modo riproducibile dagli artefatti dei notebook, senza caricare in memoria la matrice completa dei profili utente durante la demo:

```bash
python prototype/scripts/export_home_profiles.py
```

La barra di ricerca resta sticky durante lo scroll ed e disponibile con entrambi i profili. Nella vista a cluster un secondo campo opzionale raccoglie la richiesta in linguaggio naturale per Gemini: il backend recupera e motiva prima prodotti e cluster con evidenze locali, poi Gemini puo riordinare i gruppi e riscriverne la presentazione senza cambiare i prodotti. La query puo anche essere mostrata come lista ordinata per prezzo, rating o numero di recensioni tramite `GET /search`.

## Ricerca AI-first a ruoli (API)

L'endpoint di discovery a query resta disponibile per esperimenti e integrazioni, anche se non e piu la vista iniziale del frontend.

Un client puo chiamare:

```http
POST /discover
```

Esempio payload:

```json
{
  "query": "mouse",
  "ai_query": "wireless, da gaming e comodo per uso prolungato",
  "limit": 80,
  "use_ai_support": true
}
```

Il backend:

- recupera candidati dal catalogo locale con ricerca testuale e sinonimi controllati;
- costruisce gruppi per ruolo come migliore scelta, economici, compromesso, stessa marca, prodotti complementari e alternative popolari;
- motiva ogni prodotto con evidenze locali;
- indica se le evidenze arrivano da metadati, recensioni o QA storiche;
- usa Gemini solo dopo il recupero locale per riordinare i gruppi e rifinire il copy, senza permettere all'AI di scegliere prodotti o inventare dati.

Se Gemini non e disponibile, la risposta resta completamente locale.

## Estensione e consigli contestuali

L'estensione usa:

- `GET /recommendations/contextual/{item_id}` sulle pagine prodotto locali;
- `POST /amazon/recommendations` sulle pagine Amazon reali, passando solo candidati gia' letti dal DOM della pagina.

Per il sito locale i prodotti consigliati sono sempre scelti dal dataset `products_demo.json`: simili, alternative e prodotti da acquistare assieme. Gemini puo solo rifinire testi e label dei gruppi gia' calcolati.

Per Amazon reale il backend non cerca autonomamente sul web e non inventa prodotti. Organizza candidati reali estratti dalla pagina corrente; una ricerca Amazon esterna richiederebbe una API o un motore di ricerca collegato esplicitamente al backend.

## Evidenze locali

Le evidenze usate dalla discovery vengono recuperate localmente da:

- metadati e descrizione da `products_demo.json`;
- QA storiche da `qa.parquet`, se presente;
- recensioni testuali da `ratings.parquet`, se presente;
- futuri file opzionali `qa_demo.json`, `product_qa_demo.json`, `reviews_demo.json`, `product_reviews_demo.json`.

La pagina dettaglio mostra anche prodotti simili, alternative e complementari in card cliccabili. Il content script dell'estensione non inietta piu pannelli dimostrativi nelle pagine; il popup continua a rilevare il prodotto corrente e a mostrare i propri consigli.

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
curl http://localhost:8000/home/profiles
curl http://localhost:8000/home/recommendations/dataset-user
curl "http://localhost:8000/search?query=mouse&limit=20"
curl -X POST http://localhost:8000/discover -H "Content-Type: application/json" -d "{\"query\":\"mouse\",\"limit\":80,\"use_ai_support\":false}"
```

Frontend:

- seleziona `Nuovo utente` e verifica `Popular 100%` e la classifica dei bestseller;
- seleziona `Utente dal dataset` e verifica pesi dell'ibrido, storico e ranking differente;
- click su una card e apertura dettaglio prodotto, poi ritorno allo stesso profilo della home;
- prova senza `GEMINI_API_KEY` per verificare i fallback locali.

## Limiti rimasti

- La ricerca locale resta semplice e basata su match testuali, sinonimi IT->EN e ruoli euristici.
- Alcuni ruoli dipendono dalla copertura del catalogo: se mancano prodotti reali, il sistema mostra solo alternative grounded.
- Le evidenze da recensioni e QA compaiono solo quando i parquet locali contengono dati rilevanti per quel prodotto.
- I profili della home sono due casi dimostrativi fissi; non esistono ancora login, database o aggiornamento online dello storico.
