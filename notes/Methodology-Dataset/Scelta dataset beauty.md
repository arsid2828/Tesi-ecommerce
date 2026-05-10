Per la tesi è stato scelto di usare dataset Amazon della famiglia McAuley, con l’obiettivo di costruire un prototipo e-commerce in cui **sistema di raccomandazione** e **sistema QA** lavorino sullo **stesso catalogo di prodotti**. Per questo motivo i dataset devono essere collegabili tramite un identificativo comune del prodotto.

Inizialmente era stata considerata l’idea di usare dataset Amazon più vecchi, perché più direttamente compatibili con il dataset QA storico tramite `asin`. Tuttavia, la scelta è stata aggiornata: per il modulo di raccomandazione e per i metadati prodotto verrà usato **Amazon Reviews 2023**, più recente e più ricco. Per il modulo QA verrà invece usato l’**Amazon Question/Answer Data storico**, perché non esiste una versione ufficiale “Amazon QA 2023”.

## La scelta finale è quindi:

Recommendation e metadati:
Amazon Reviews 2023
Categoria: Beauty_and_Personal_Care
Config:
- raw_meta_Beauty_and_Personal_Care
- raw_review_Beauty_and_Personal_Care

Question Answering:
Amazon Question/Answer Data storico
Categoria:
- QA_Beauty.json.gz

I dataset vengono collegati confrontando:

QA_Beauty.asin
con
Amazon Reviews 2023 parent_asin


È stata testata l’intersezione tra il QA storico Beauty e due categorie di Amazon Reviews 2023. All_Beauty è risultato poco adatto, perché ha solo 46 prodotti in comune con il QA. Beauty_and_Personal_Care, invece, è molto più compatibile: ha 2.620 prodotti in comune, pari a circa il 44,7% dei prodotti del QA Beauty.

Dopo aver verificato anche la presenza di recensioni/rating nel dataset 2023, il catalogo finale ottenuto contiene:

2.619 prodotti
615.015 recensioni/rating
543.992 utenti

Il catalogo del prototipo sarà quindi costruito usando solo i prodotti presenti in tutti e tre i blocchi:

prodotti con metadati 2023
∩ prodotti con recensioni/rating 2023
∩ prodotti con domande/risposte QA storico

Questa scelta è metodologicamente solida perché permette al recommender di suggerire prodotti usando rating, recensioni e interazioni utente-prodotto, mentre il QA potrà rispondere usando domande/risposte, recensioni e metadati relativi agli stessi prodotti.
Un limite da tenere presente è la possibile sparsità lato utente: ci sono molti utenti rispetto al numero di recensioni, quindi alcuni modelli collaborativi complessi potrebbero essere meno adatti. Tuttavia il dataset è più che sufficiente per baseline, modelli popularity-based, item-item, content-based e una prima estensione QA.


La scelta dei dataset è motivata dalla survey _Information Discovery in E-commerce_ di Ren et al. (2025), che inquadra recommendation e question answering come componenti centrali dell’information discovery in ambito e-commerce. Per i dati, invece, vengono usate come fonti primarie le pagine ufficiali McAuley Lab/UCSD: Amazon Reviews 2023 per recensioni, rating e metadati prodotto, e Amazon question/answer data per domande e risposte sui prodotti. I due dataset vengono collegati tramite identificativo prodotto, usando `parent_asin` in Amazon Reviews 2023 e `asin` nel dataset QA storico.