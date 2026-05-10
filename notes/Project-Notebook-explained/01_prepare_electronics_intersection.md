Vogliamo costruire il dataset dei prodotti Amazon nel campo Electronics, intersecando:
- Amazon Reviews 2023 che contiene metadati + rating/recensioni
- Amazon question/answer storico McAuley.
Amazon Reviews 2023 viene preso da hugging face.
Su amazon qa cambiano asin in parent_asin per poter intersecare i due datasets.

Il notebook fa:
- carica i metadati dei prodotti electronics da amazon reviews 2023
- carica il dataset storico di **domande e risposte QA** sui prodotti Electronics;
- trova i prodotti presenti sia nei metadati sia nel QA, usando `parent_asin`;
- scansiona le recensioni/rating Amazon Reviews 2023 e mantiene solo i rating dei prodotti selezionati;
- salva i tre file principali: 
items.parquet   → prodotti con metadati
qa.parquet      → domande e risposte associate ai prodotti
ratings.parquet → rating/interazioni utente-prodotto

In pratica, il notebook trasforma dati grezzi e separati in un dataset integrato **metadata + QA + rating**, pronto per l’esplorazione e poi per i modelli di raccomandazione.
[[Ragionamenti su dati ottenuti da Notebook01]]
[[Dataset Electronics]]

