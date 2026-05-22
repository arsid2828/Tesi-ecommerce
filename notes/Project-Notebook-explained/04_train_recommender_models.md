La metrica NDCG@K valuta la qualità del ranking prodotto dal sistema, assegnando un peso maggiore agli elementi rilevanti posizionati nelle prime posizioni. Nel caso della valutazione con un solo item positivo per utente, il valore è pari a 0 se l’item positivo non compare nella top-K, mentre diminuisce logaritmicamente all’aumentare della sua posizione nel ranking.

Truncated SVD è una tecnica di riduzione dimensionale che approssima la matrice utenti-prodotti usando un numero limitato di fattori latenti. Nel recommender permette di rappresentare utenti e prodotti con vettori più piccoli, catturando pattern collaborativi nelle interazioni. È utile perché lavora bene con matrici sparse e consente di stimare prodotti potenzialmente rilevanti per un utente, anche se resta una baseline meno specifica rispetto a modelli progettati appositamente per feedback implicito.

## cella 3:
In questo blocco viene costruita la matrice sparsa utente-prodotto a partire dal training set. La scelta fatta è usare valori binari, cioè `1` se l’utente ha interagito con il prodotto, invece del valore del rating, perché in questa fase stiamo valutando la capacità del modello di raccomandare prodotti rilevanti, non di predire il voto esatto.

Dopo l’esecuzione otteniamo:

```
Utenti: 131.398Prodotti: 12.306Interazioni di training: 287.752Densità: 0,0178%
```

Il dato più importante è la densità molto bassa: solo circa lo **0,018%** delle possibili coppie utente-prodotto è osservato nel training set. Questo conferma che il problema è molto sparso, come tipico dei sistemi di raccomandazione e-commerce. Inoltre, tutti i **131.398 utenti** hanno uno storico nel train, mentre i prodotti candidati effettivamente presenti nel training set sono **12.299** su **12.306**.

## cella 4:
Questo blocco definisce le funzioni usate per valutare i modelli. Per ogni utente si confronta un prodotto positivo, cioè realmente presente nello split di validation/test, con una lista di prodotti negativi campionati. Il modello assegna un punteggio a tutti i candidati e si misura in quale posizione viene collocato il prodotto positivo.

La valutazione usa metriche top-k: `HitRate`, `Recall`, `NDCG` e `MRR`. In questo caso `HitRate` e `Recall` coincidono, perché per ogni esempio c’è un solo prodotto positivo da recuperare. La scelta di includere `NDCG` e `MRR` è importante perché non basta sapere se il prodotto corretto entra nella top-k: è utile anche misurare quanto in alto viene posizionato nella classifica.

## cella 5:
In questo blocco viene costruita la baseline **MostPopular**, che assegna a ogni prodotto un punteggio pari al numero di volte in cui compare nel training set. È una baseline non personalizzata: non usa lo storico specifico dell’utente, ma raccomanda semplicemente i prodotti più frequenti.

I risultati su validation sono:

```
HitRate@5  = 0,341973
HitRate@10 = 0,464293
HitRate@20 = 0,609853
NDCG@10 = 0,284317
MRR@10  = 0,229132
```

Questo significa che nel **46,4%** dei casi il prodotto positivo entra nei primi 10 risultati, e nel **61,0%** dei casi entra nei primi 20. È una baseline abbastanza forte, segno che nel dataset la popolarità dei prodotti ha un peso rilevante. Tuttavia rimane un modello non personalizzato: i modelli successivi, come ItemKNN o SVD, dovranno superare questa baseline per dimostrare di aggiungere reale valore rispetto alla sola popolarità.

## cella 6:
In questa sezione è stato testato un modello **ItemKNN**, basato sulla similarità tra prodotti calcolata a partire dalla matrice prodotto-utente. Invece di usare un solo numero di vicini, sono state provate più configurazioni: `5`, `10`, `20`, `30`, `50` e `100` vicini. La matrice massima dei vicini ha dimensione `(12306,101)`, cioè per ciascuno dei 12.306 prodotti vengono calcolati fino a 101 vicini, includendo inizialmente anche il prodotto stesso.

I risultati su validation mostrano che aumentare il numero di vicini migliora progressivamente ItemKNN: il modello migliore tra questi è **ItemKNN_100**, con `HitRate@10=0,1523`, `NDCG@10=0,0957` e `MRR@10=0,0785`. Tuttavia, anche la configurazione migliore rimane molto distante dalla baseline MostPopular, che su validation ottiene `HitRate@10=0,4643` e `NDCG@10=0,2843`. Questo suggerisce che la similarità item-item calcolata sulle sole interazioni è debole rispetto al segnale di popolarità.

## cella 7:
In questa sezione è stato testato un modello di **matrix factorization** tramite `TruncatedSVD`, con diversi numeri di fattori latenti. Sono state provate configurazioni da `2` a `32` componenti, così da verificare se una rappresentazione più compatta o più espressiva fosse più adatta al dataset.

Il miglior risultato tra gli SVD è ottenuto da **SVD_4**, con `HitRate@10=0,4444`, `NDCG@10=0,2752` e `MRR@10=0,2233` su validation. È interessante notare che aumentando il numero di fattori le metriche peggiorano: ad esempio `SVD_32` ha una varianza spiegata più alta, pari a circa `0,0647`, ma scende a `NDCG@10=0,2404`. Questo indica che spiegare più varianza della matrice non implica necessariamente migliori raccomandazioni top-k.

## cella 8:
In questa sezione vengono raccolte tutte le metriche calcolate su validation e viene scelto il modello migliore secondo la metrica principale impostata nel notebook, cioè **NDCG@10**. La scelta viene fatta solo sulla validation, lasciando il test set per la valutazione finale.

Il miglior modello su validation risulta essere **MostPopular**, con `NDCG@10=0,2843`. Il miglior modello personalizzato è invece **SVD_4**, con `NDCG@10=0,2752`, quindi molto vicino ma ancora inferiore alla baseline. Questo risultato conferma che la popolarità dei prodotti è un segnale molto forte nel dataset, mentre i modelli personalizzati testati non riescono ancora a superarla.

## cella 9:
In questa sezione i modelli vengono valutati sul test set, usando la stessa procedura di ranking già applicata alla validation. Il test set contiene `131.352` esempi, quindi ha una dimensione molto simile alla validation.

Anche sul test set il modello migliore resta **MostPopular**, con `HitRate@10=0,4810`, `NDCG@10=0,3002` e `MRR@10=0,2446`. Il miglior modello personalizzato resta **SVD_4**, che ottiene `HitRate@10=0,4669`, `NDCG@10=0,2950` e `MRR@10=0,2421`. La distanza tra MostPopular e SVD_4 è quindi ridotta, ma la baseline resta leggermente superiore. ItemKNN_100 è il migliore tra gli ItemKNN, ma rimane molto più basso, con `NDCG@10=0,0729` sul test.

## cella 10:
In questa sezione vengono salvati i risultati principali prodotti dal notebook, così da poterli riutilizzare nei notebook successivi e nella fase di analisi finale. Vengono esportate le metriche complessive, la tabella di confronto con MostPopular, i punteggi di popolarità dei prodotti e, se richiesto dalla configurazione, anche i rank dettagliati e gli artefatti dei modelli.

Il summary finale riassume l’esperimento: il dataset usato è `Electronics`, la metrica principale è `NDCG@10`, il miglior modello su validation è `MostPopular` con punteggio `0,2843`, mentre il miglior SVD è `SVD_4`. Il notebook lavora su `287.752` interazioni di training, `131.376` esempi di validation, `131.352` esempi di test, `131.398` utenti e `12.306` prodotti. Questi file salvati saranno utili per il Notebook 05 e per il confronto finale dei modelli.