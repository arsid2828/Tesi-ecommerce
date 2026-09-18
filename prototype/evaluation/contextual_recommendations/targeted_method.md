# Test aggiuntivo F01–F04

Il censimento legge i nomi delle famiglie e `family_mapping` dal codice tramite AST.
La classificazione dei prodotti usa esclusivamente `_product_family`; il censimento
dei complementari possibili usa `_title_matches_complement` sui termini effettivi
del mapping. Conta prodotti unici del catalogo valido, senza ranking, senza chiamare
le raccomandazioni e senza interpretare la compatibilità reale. Il conteggio è
potenziale e non applica tutti i successivi filtri del ranking (per esempio immagine,
esclusione del prodotto sorgente e deduplicazione fra gruppi).

I prodotti validi hanno item_id non vuoto e univoco, titolo e categoria non vuoti e
prezzo finito positivo. Tutti i prodotti del catalogo caricato soddisfano i requisiti
usati nel censimento. Una famiglia riconosciuta senza voce in `family_mapping`
riceve una lista vuota: il mapping testuale generico successivo non viene eseguito
quando esiste una famiglia riconosciuta. Il CSV distingue mapping assente e lista
esplicitamente vuota.

Sono state scelte printer, phone, camera e vacuum: le prime quattro famiglie
ammissibili per numero di prodotti validi decrescente (parità alfabetica), senza
deroghe manuali. Per ognuna è stato congelato nel manifest il prodotto con massima
popularity_score; in caso di parità prevale item_id crescente. Non sono stati
necessari criteri sostitutivi. Non sono state corrette classificazioni prodotte
dal codice: il collare GoTags, per esempio, è riconosciuto come phone.

`targeted_family_manifest.json` precede ogni richiesta. Le quattro richieste sono
GET `/recommendations/contextual/{item_id}?limit=4&use_ai_support=false` alla vera
app FastAPI tramite TestClient, sequenziali e senza mock. Nessuna chiamata Gemini.
Gli output raw conservano i byte delle risposte finali del backend.

## Controllo meccanico delle tipologie

Le voci del mapping sono termini/tipologie come `ink`, `memory card`, `case` e
`replacement bag`, non una tassonomia di nomi restituiti da `_product_family`.
Confrontare letteralmente soltanto i nomi delle famiglie introdurrebbe una regola
diversa da quella del prototipo. Non sono state aggiunte equivalenze o associazioni.

Per ogni prodotto in “Utili insieme”:

- `Famiglia_raccomandato` conserva il risultato di `_product_family`, vuoto se None.
- `Complementarita_prevista=Sì` indica almeno una corrispondenza con una tipologia
  prevista, verificata dal matcher reale `_title_matches_complement`.
- Se non c'è corrispondenza ma la famiglia è riconosciuta, il valore è No.
- Se non c'è corrispondenza né famiglia riconosciuta, è Non determinabile.

`targeted_mapping_checks.csv` conserva i termini corrispondenti. Una famiglia vuota
può quindi avere Sì se il sistema riconosce una tipologia complementare tramite il
matcher. Il controllo è lo stesso già richiesto dal filtro dei complementari:
la conformità non è una prova indipendente di qualità o compatibilità reale.
Per “Simili e alternative” il campo è vuoto.

La colonna Fallback riproduce il flag finale del backend. Non descrive il normale
completamento del pool dei candidati dalla stessa categoria. I warning del servizio
e gli errori sono conservati separatamente; non ne sono stati ricevuti.

## File aggiunti

- evaluate_targeted_families.py
- targeted_family_inventory.csv
- targeted_family_manifest.json
- targeted_raw/F01.json, F02.json, F03.json, F04.json
- contextual_recommendations_targeted.csv
- contextual_recommendations_targeted_review.csv
- targeted_mapping_checks.csv
- targeted_diagnostics.csv
- targeted_verification.json
- targeted_method.md

Lo script rifiuta una nuova esecuzione se il manifest esiste. I test R01–R08,
cluster_search, search_comparison, catalogo e codice preesistenti sono stati
verificati tramite SHA-256 prima/dopo e sono invariati. I CSV sono UTF-8 con BOM,
separati da virgole; le posizioni nei gruppi partono da 1.
