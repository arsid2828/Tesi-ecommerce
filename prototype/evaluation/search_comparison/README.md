# Confronto descrittivo della ricerca — sezione 7.4

Sono state eseguite soltanto quattro richieste alla vera app FastAPI tramite
TestClient: `GET /search?query=...&limit=80`, come nel frontend. Le query fisse
sono T01 `mouse`, T02 `phone`, T03 `drill`, T04 `board game`.
Nessuna chiamata a `/discover` o a Gemini è stata eseguita.

## Pipeline tradizionale

`prototype/backend/app.py:search` chiama
`prototype/backend/services/search_service.py:search_products` sul catalogo reale.
La query viene privata degli spazi esterni e convertita in minuscolo. Il matching
cerca una sottostringa in titolo, categoria e descrizione concatenati in minuscolo.
Se non esiste alcun match della query intera, cerca tutti i token separati da spazi
di lunghezza maggiore di uno. Se anche questo passaggio non trova risultati, usa
`expand_query_terms` e accetta un match di almeno un termine espanso.

L'espansione condivisa usa token alfanumerici di almeno tre caratteri, rimuove
le stopword previste, include la query originale e i sinonimi già configurati,
deduplica e limita i termini a 18. Non è stata cambiata alcuna regola.
Una query vuota mantiene il catalogo; una query non vuota senza match può restituire
una lista vuota. Non viene aggiunta una selezione di prodotti popolari ai risultati.

L'ordinamento del backend è `popularity_score` decrescente, stabile in caso di
parità. L'endpoint limita il parametro a 1–200; il frontend chiede 80 e così fa
questa valutazione. Non sono stati applicati ordinamenti successivi del frontend
o della valutazione. Le posizioni partono da 1 nella lista JSON ricevuta.

## Fonti clusterizzate e conteggi

I riferimenti sono gli originali `../cluster_search/raw/G01.json`, `G03.json`,
`G05.json`, `G10.json`, letti senza copiarli, riscriverli o rieseguirli.
Percorsi e hash SHA-256 sono in `test_manifest.json`. Il controllo finale verifica
anche l'integrità dei file del prototipo e delle valutazioni precedenti.

Il numero di prodotti mostrati è la somma delle presenze nelle liste `products`
dei gruppi finali. La presenza nella ricerca tradizionale viene verificata con
`item_id`; in questi quattro output gli identificativi clusterizzati sono univoci.
La percentuale è:

`prodotti clusterizzati presenti nella lista tradizionale / prodotti clusterizzati mostrati * 100`

Il denominatore è quindi il totale clusterizzato, non il totale tradizionale.
Il confronto riguarda la lista effettivamente restituita con limite 80: assenza
da quella lista non dimostra assenza dal catalogo. Il CSV conserva la precisione
del calcolo; eventuali percentuali mostrate a due decimali sono arrotondamenti.
Una posizione vuota con presenza `No` indica assenza dalla lista tradizionale.
In caso di errore, le misure non calcolabili restano vuote e l'errore è registrato.

## Output

- `search_comparison.csv`: quattro riepiloghi, con nomi cluster separati da `; `.
- `search_comparison_products.csv`: 75 presenze clusterizzate, gruppo, presenza
  nella lista tradizionale e posizione originale quando presente.
- `traditional_search_products.csv`: 274 prodotti restituiti, con titolo,
  categoria, prezzo, rating, numero di valutazioni e posizione originale.
- `raw/traditional_T01.json` … `raw/traditional_T04.json`: risposte complete,
  conservate nei byte restituiti dal backend, senza aggiunta di campi.
- `test_manifest.json`: richieste e riferimenti ai JSON clusterizzati originali.
- `run_diagnostics.csv`: stati HTTP ed eventuali errori.
- `verification.json`: conteggi e controlli di integrità.
- `evaluate_search_comparison.py`: script della valutazione.

I CSV usano UTF-8 con BOM e separatore virgola. Nessun giudizio qualitativo è stato
assegnato. Nessun file preesistente è stato modificato.

Per una futura esecuzione separata, dalla root:

```powershell
.\.venv\Scripts\python.exe prototype/evaluation/search_comparison/evaluate_search_comparison.py --output prototype/evaluation/search_comparison_new
```

Lo script rifiuta la sovrascrittura degli output e legge sempre i quattro riferimenti
clusterizzati esistenti; esegue esclusivamente le richieste tradizionali.
