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