## cella 3:
In questa sezione sono stati costruiti i testi descrittivi dei prodotti combinando titolo, categoria, brand/store, caratteristiche, descrizione, categorie e dettagli tecnici. Il dataset contiene 131.398 utenti e 12.306 prodotti, tutti con un testo disponibile: infatti il numero di prodotti con testo vuoto è pari a 0. La lunghezza media dei testi è di circa 352 token, con mediana 288; questo indica che i metadati sono abbastanza informativi per costruire un modello content-based. Sono però presenti alcuni testi molto lunghi, fino a 5.974 token, quindi nelle fasi successive l’uso di limiti sui campi e della rappresentazione TF-IDF aiuta a ridurre il rumore.

cella 4:
I testi dei prodotti sono stati trasformati in una matrice TF-IDF con **12.306 prodotti** e **20.000 feature testuali**. La matrice contiene **2.244.999 valori non nulli** e ha densità pari a circa **0,91%**, confermando una rappresentazione molto sparsa ma adatta al confronto tra prodotti. Il controllo dei termini principali serve a verificare che il modello stia catturando parole rappresentative dei prodotti e non solo rumore.

cella 5:
La matrice di training contiene **287.752 interazioni** tra **131.398 utenti** e **12.306 prodotti**, con densità molto bassa, circa **0,018%**, tipica dei sistemi di raccomandazione. I prodotti candidati presenti nel train sono **12.299**, quindi quasi tutto il catalogo ha almeno un’interazione utile. I profili content-based sono stati costruiti per tutti gli utenti e hanno forma **131.398 × 20.000**, con **47.609.835 valori non nulli**.

cella 6:
Sono state definite funzioni comuni per valutare tutti i modelli con la stessa procedura. Per ogni esempio, il prodotto positivo viene confrontato con un insieme di negativi campionati e viene calcolata la sua posizione nel ranking. Le metriche usate sono **HitRate, Recall, NDCG e MRR** a diversi valori di K, in continuità con il Notebook 04.

cella 7:
Il modello **ContentTFIDF** assegna punteggi confrontando il profilo testuale dell’utente con i vettori TF-IDF dei prodotti candidati. Su validation ottiene **NDCG@10 = 0,164** e **HitRate@10 = 0,274**, quindi riesce a catturare una parte del segnale, ma rimane sotto la baseline di popolarità del Notebook 04. Questo indica che i soli metadati testuali non sono sufficienti come modello principale, ma possono essere utili in combinazione con altri segnali.

cella 8:
Sono stati recuperati i risultati e gli artefatti del Notebook 04, inclusi i punteggi di popolarità e il modello SVD migliore disponibile. La baseline **MostPopular** aveva ottenuto su validation **NDCG@10 = 0,284**, mentre i punteggi di popolarità sono disponibili per **12.299 prodotti**, con popolarità massima pari a **1.118 interazioni**. È disponibile anche il modello **SVD_4**, con **4 componenti** e varianza spiegata pari a circa **0,0139**.

cella 9:
Sono stati valutati modelli ibridi che combinano ContentTFIDF, SVD e popolarità dopo normalizzazione min-max degli score. Il modello content-based con sola popolarità, **Hybrid_Content70_Pop30**, migliora rispetto al ContentTFIDF puro ma resta sotto MostPopular, con **NDCG@10 = 0,241**. I modelli che includono SVD superano invece la baseline: il migliore è **Hybrid_SVD50_Content25_Pop25**, con **NDCG@10 = 0,303**, seguito da **Hybrid_SVD40_Content40_Pop20**, con **NDCG@10 = 0,302**. Questo suggerisce che il segnale collaborativo resta centrale, ma contenuto e popolarità possono migliorare il ranking quando combinati in modo controllato.