# Raccomandazioni e ricerca di prodotti per l’e-commerce

Progetto di tesi su come aiutare chi acquista online a trovare un prodotto, confrontare le alternative e scoprire accessori pertinenti. Il risultato è un prototipo web con un catalogo locale e un’estensione Chrome.

## Prototipo

- **Raccomandazioni in home.** Si può passare da un nuovo utente, a cui vengono mostrati i prodotti più popolari, a un profilo del dataset con uno storico di valutazioni. Il secondo profilo usa un modello ibrido che combina SVD, contenuto dei prodotti e popolarità.
- **Ricerca nel catalogo.** I risultati si possono vedere in una lista ordinabile o in gruppi tematici. Nella vista a gruppi si può indicare un criterio, per esempio separare i mouse da gaming da quelli da viaggio. Gemini è facoltativo. Il prototipo può raggruppare i risultati anche con regole locali.
- **Scheda prodotto ed estensione.** La scheda mostra prodotti simili e accessori da abbinare. L’estensione porta questi suggerimenti nel popup e, sulle pagine Amazon supportate, usa i prodotti correlati già presenti nella pagina.

Il backend è in FastAPI e l’interfaccia è in HTML, CSS e JavaScript. Per provare la demo, genera il catalogo dal notebook del prototipo e avvia i due server locali seguendo le [istruzioni di avvio](prototype/README.md).

## Notebook

In [`notebooks/`](notebooks/) trovi gli esperimenti sulla categoria Electronics. [`notebooks/test_dataset2/`](notebooks/test_dataset2/) ripete il percorso su un dataset che copre più categorie. Le due serie vanno eseguite nell’ordine da 01 a 05. I primi tre notebook costruiscono, esplorano e dividono il dataset in train, validation e test. Gli ultimi due confrontano popolarità, ItemKNN e SVD con modelli basati su TF-IDF e combinazioni ibride.

Il [notebook del prototipo](prototype/notebooks/01_prepare_prototype_amazon_like_intersection.ipynb) prepara il catalogo della demo e i file con recensioni e domande e risposte. I dataset e i file generati restano locali. I risultati delle prove sulla ricerca e sui consigli contestuali sono in [`prototype/evaluation/`](prototype/evaluation/).

I dati provengono da due raccolte del McAuley Lab, [Amazon Reviews 2023](https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023) e [Amazon Question/Answer Data](https://cseweb.ucsd.edu/~jmcauley/datasets/amazon/qa/).
