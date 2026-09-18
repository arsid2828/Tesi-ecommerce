# Valutazione delle raccomandazioni contestuali — sezione 7.3

## Selezione congelata

`test_manifest.json` è stato salvato prima delle otto richieste di raccomandazione.
Per ciascuna delle otto categorie richieste è stato scelto il prodotto valido con
`popularity_score` massimo; in caso di parità prevale `item_id` crescente. Non è
stato necessario ricorrere a `rating_count`, sostituire categorie o prodotti.

La selezione usa il catalogo caricato da `CatalogService`, con identificativo
non vuoto e univoco, titolo e categoria non vuoti e prezzo finito positivo.
Non richiede una famiglia riconosciuta né la presenza di suggerimenti. Il manifest
riporta titoli completi, prezzi originali senza conversione di valuta, score,
numerosità delle categorie e hash SHA-256 del catalogo.

## Percorso reale

Il frontend `loadProductDetail` usa `GET /products/{item_id}` per il dettaglio.
`loadProductRecommendations` chiama
`GET /recommendations/contextual/{item_id}?limit=4&use_ai_support=false`.
Lo script esegue quest'ultima richiesta sulla vera app FastAPI tramite TestClient,
una volta per prodotto e in sequenza. Non abilita Gemini e non usa mock.

L'endpoint in `prototype/backend/app.py` chiama `contextual_recommendations` in
`prototype/backend/services/recommendation_service.py`:

- `_product_family` identifica la tipologia dal titolo e, dove previsto, dalla categoria.
- `_contextual_candidate_pool` sceglie candidati per famiglia, complementarità
  e termini comuni. Se il pool è piccolo, lo completa con prodotti della stessa
  categoria secondo le regole già implementate.
- `_score_local_candidates` calcola i punteggi del servizio reale.
- `_build_local_groups`, `_is_valid_recommendation` e `_take_unique` costruiscono
  “Simili e alternative” (fino a 8 prodotti con `limit=4`).
- `_complement_terms`, `_bundle_candidates` e i filtri esistenti costruiscono
  “Utili insieme” (fino a 4 prodotti).
- Il servizio aggiunge le evidenze locali. FastAPI valida e serializza la risposta
  con `ContextualRecommendationsResponse`.

Non è stata riscritta alcuna di queste logiche nello script di valutazione.
Il campo Famiglia è ottenuto chiamando la funzione reale `_product_family` sul
prodotto congelato. Una cella vuota significa che la funzione restituisce `None`.

## Definizioni e fallback

I conteggi derivano dalle liste `products` dei gruppi finali, identificati tramite
`role_id`: `similar_alternatives` e `complementary`. Un gruppo assente vale zero e
ha nome vuoto; un errore lascia vuoti i conteggi non calcolabili. Il totale è la
somma delle presenze nei gruppi, senza deduplicazioni aggiuntive della valutazione.
Le posizioni nel file di revisione partono da 1 e conservano l'ordine del backend.

La colonna Fallback riproduce il flag finale `fallback` del backend, che in questo
percorso vale `True` se non ci sono gruppi. Il completamento interno del pool di
candidati è una normale regola del retrieval e non viene segnalato da questo flag;
`Fallback=No` non implica che quel completamento non sia avvenuto.
Il servizio prevede inoltre un ripiego da TF-IDF alla sovrapposizione dei termini:
disponibilità delle dipendenze e warning sono riportati in `run_diagnostics.csv`.
In questa esecuzione TF-IDF era disponibile e non sono stati emessi warning.
Il ripiego del supporto Gemini non si applica perché il frontend lo disattiva.

## File

- `test_manifest.json`: otto prodotti congelati e metodo di selezione.
- `raw/R01.json` … `raw/R08.json`: byte delle risposte JSON finali, senza modifiche.
- `contextual_recommendations.csv`: otto righe di riepilogo.
- `contextual_recommendations_review.csv`: 65 righe, una per presenza di un prodotto
  raccomandato; nessun giudizio qualitativo.
- `run_diagnostics.csv`: stato HTTP, flag, warning, errori e durata.
- `verification.json`: controlli su manifest e file preesistenti.
- `evaluate_contextual_recommendations.py`: script di selezione ed esecuzione.

I CSV sono UTF-8 con BOM, separati da virgole e con quoting standard. Nessun
risultato della ricerca clusterizzata è stato modificato.

Per una futura valutazione separata, dalla root del repository:

```powershell
.\.venv\Scripts\python.exe prototype/evaluation/contextual_recommendations/evaluate_contextual_recommendations.py --output prototype/evaluation/contextual_recommendations_new
```

Lo script rifiuta cartelle con output già presenti: non sovrascrive questa selezione
né questi risultati. Una futura esecuzione selezionerebbe dal catalogo allora presente.
