# Parte 1 - Lavoro svolto finora sul recommender e-commerce

> Documento preparatorio per incontro con il relatore.  
> Fonti interne usate: Notebook 01-05 e notes del progetto.  
> Nota: i numeri riportati sono quelli presenti negli output dei notebook o nelle notes. Dove un’informazione non è ricavabile con certezza, è indicata come “da verificare” o “non determinabile dai file”.

---

## 1. Introduzione generale

Il progetto di tesi riguarda la costruzione di un prototipo di sistema di raccomandazione per e-commerce basato su dataset pubblici Amazon. L’idea generale è partire da dati reali su prodotti, metadati, rating/recensioni e domande/risposte, per costruire un sistema capace di suggerire prodotti personalizzati agli utenti.

Questa prima parte del lavoro non riguarda ancora il sito o l’interfaccia finale, ma la costruzione della pipeline sperimentale del recommender:

- scelta e preparazione del dataset;
    
- analisi della qualità e della sparsità dei dati;
    
- costruzione degli split train/validation/test;
    
- implementazione di baseline e modelli collaborativi;
    
- costruzione di un modello content-based;
    
- valutazione di un modello ibrido;
    
- analisi dei risultati e dei limiti.
    

Il lavoro fatto finora è quindi la base sperimentale su cui potrà poi essere costruito un prototipo web dimostrativo.

---

## 2. Obiettivo della parte 1

L’obiettivo della parte 1 è costruire una pipeline completa e spiegabile:

```text
dataset → esplorazione → filtraggio → split → modelli → valutazione → modello ibrido
```

In pratica, questa fase serve a rispondere a domande come:

- i dati Amazon scelti sono adatti a un recommender e-commerce?
    
- quanti prodotti, utenti e rating rimangono dopo i filtri?
    
- il dataset è troppo sparso?
    
- quali modelli semplici funzionano come baseline?
    
- i modelli collaborativi riescono a battere la popolarità?
    
- i metadati dei prodotti aiutano?
    
- un modello ibrido migliora i risultati?
    
- quali limiti metodologici devo dichiarare?
    

La cosa importante è che il lavoro non prova a costruire “il miglior recommender possibile”, ma una pipeline coerente, verificabile e adatta a una tesi triennale.

---

## 3. Dataset e scelta della categoria

### Dataset considerati

Dalle notes risulta che sono stati considerati dataset pubblici Amazon della famiglia McAuley, in particolare:

- **Amazon Reviews 2023**, per:
    
    - metadati prodotto;
        
    - rating;
        
    - recensioni;
        
    - timestamp;
        
    - utenti;
        
    - categorie;
        
    - descrizioni e dettagli prodotto.
        
- **Amazon Question/Answer Data storico**, per:
    
    - domande degli utenti sui prodotti;
        
    - risposte associate ai prodotti.
        

L’idea metodologica è collegare i dataset tramite identificativo prodotto:

```text
QA storico: asin
Amazon Reviews 2023: parent_asin
```

In questo modo il catalogo finale contiene solo prodotti che hanno dati utili sia per il recommender sia, potenzialmente, per un futuro modulo QA.

### Categorie considerate

Nelle notes sono state considerate diverse categorie:

|Categoria|Prodotti finali con QA + metadata + rating|Osservazione|
|---|---|---|
|Beauty / Beauty and Personal Care|2.619|Utilizzabile, ma meno interessante per un prototipo simil-Amazon|
|Cell Phones and Accessories|4.705|Buona categoria, più piccola e controllabile|
|Video Games|607|Molto densa, ma catalogo troppo piccolo|
|Electronics|22.974|Categoria più ampia e più adatta al prototipo|

La scelta finale è stata **Electronics**.

### Perché Electronics

Electronics è stata scelta perché:

- ha un catalogo finale molto più grande rispetto alle alternative;
    
- è una categoria varia, con prodotti tecnologici diversi;
    
- è adatta a un prototipo e-commerce credibile;
    
- contiene metadati testuali utili per un modello content-based;
    
- contiene rating sufficienti lato prodotto;
    
- mantiene anche dati QA per una possibile estensione futura.
    

Dalle notes:

```text
Electronics:
22.974 prodotti finali con QA + metadata + rating
QA coverage: 58,35%
rating medi per prodotto: circa 150
```

Dal Notebook 01 il dataset finale contiene:

|File finale|Righe|
|---|---|
|`items.parquet`|22.974|
|`qa.parquet`|180.976|
|`ratings.parquet`|3.484.401|

### Ruolo di metadati, rating/recensioni e QA

Nel progetto attuale i dati hanno ruoli diversi:

|Tipo di dato|Ruolo attuale|
|---|---|
|Metadati prodotto|Usati per descrivere prodotti e costruire il modello content-based TF-IDF|
|Rating|Usati come interazioni utente-prodotto per il recommender|
|Recensioni testuali|Presenti nel dataset di origine, ma non usate direttamente nella pipeline attuale|
|QA|Allineato al catalogo, ma non ancora usato nel recommender|

Nota critica: nel Notebook 01 `SAVE_TEXT_OFREVIEW=False`, quindi il file `ratings.parquet` salva i rating ma non il testo completo delle recensioni. Se in futuro si volessero usare le recensioni testuali, bisognerà ricostruire o estendere l’estrazione.

### Perché il QA resta una possibile estensione

Il QA per ora non è il focus principale perché:

- avrebbe bisogno di una pipeline separata;
    
- richiede una valutazione diversa rispetto al recommender;
    
- rischia di allargare troppo la tesi;
    
- il recommender non è ancora integrato in un prototipo web;
    
- per una triennale è più realistico completare bene prima la parte recommendation.
    

Il QA rimane però sensato come estensione futura, perché i prodotti finali hanno anche domande/risposte associate.

### Vantaggi e limiti della scelta

|Aspetto|Vantaggio|Limite|
|---|---|---|
|Electronics|Catalogo ampio e vario|Dataset pesante|
|Intersezione QA + metadata + rating|Catalogo coerente|Si perdono prodotti non presenti in tutti i blocchi|
|Amazon Reviews 2023|Dataset recente e ricco|Collegamento col QA storico da trattare con cautela|
|QA storico|Utile per estensione futura|Non è della stessa versione temporale del dataset 2023|
|Rating reali|Permettono collaborative filtering|Molti utenti hanno pochissime interazioni|

Dato da verificare: nelle notes compare il riferimento al fatto che per Electronics siano stati scansionati oltre 43 milioni di rating grezzi. Nel Notebook 01 eseguito però il filtraggio viene saltato perché `ratings.parquet` esiste già; quindi quel numero va verificato prima di citarlo in tesi.

---

## 4. Notebook 01 - Preparazione dell’intersezione dei dati

### Obiettivo del notebook

Il Notebook 01 costruisce il primo dataset pulito per Electronics, unendo tre fonti:

```text
Amazon QA storico Electronics
∩ Amazon Reviews 2023 metadata Electronics
∩ Amazon Reviews 2023 rating/reviews Electronics
```

L’obiettivo è ottenere un catalogo unico di prodotti che abbiano:

- metadati;
    
- rating;
    
- domande/risposte QA.
    

### Input usati

|Input|Fonte|Uso|
|---|---|---|
|`qa_Electronics.json.gz`|Amazon QA storico|Domande e risposte|
|`raw_meta_Electronics`|Amazon Reviews 2023|Metadati prodotto|
|`raw_review_Electronics`|Amazon Reviews 2023|Rating/recensioni|

### Cosa viene costruito

Il notebook costruisce tre file principali:

|File|Contenuto|
|---|---|
|`items.parquet`|Prodotti Electronics con metadati|
|`qa.parquet`|Domande/risposte dei prodotti rimasti|
|`ratings.parquet`|Rating dei prodotti rimasti|

Alla fine viene anche creato:

```text
summary.json
```

con il riepilogo delle righe finali.

### Filtraggio dei prodotti

Il primo filtro importante è l’intersezione tra prodotti con QA e prodotti con metadati 2023.

Dati principali dal Notebook 01:

|Passaggio|Numero|
|---|---|
|Righe QA iniziali|314.263|
|Prodotti unici nel QA|39.371|
|Prodotti nei metadata 2023 Electronics|1.610.012|
|Prodotti comuni QA + metadata|22.975|
|Prodotti finali con metadata + QA + rating|22.974|

È stato quindi escluso un solo prodotto che aveva metadati e QA ma non aveva rating.

### Filtraggio QA

Dopo l’intersezione con i prodotti finali, il QA viene ridotto a:

```text
180.976 righe QA
22.974 prodotti con QA
```

Quindi tutti i prodotti finali hanno almeno una riga QA.

### Filtraggio rating

Il notebook produce un file `ratings.parquet` con:

```text
3.484.401 rating
```

Nota critica: il notebook eseguito non mostra il numero di righe grezze effettivamente scansionate perché trova già il file `ratings.parquet` e salta il filtraggio. Quindi il numero di righe grezze lette è non determinabile dal solo output del Notebook 01 eseguito.

### Output finali

Dal `summary.json` del Notebook 01:

|Output|Righe|
|---|---|
|`items`|22.974|
|`qa`|180.976|
|`ratings`|3.484.401|

### Perché questa fase è importante

Questa fase è importante perché evita di lavorare su dataset scollegati. Il prototipo finale deve poter mostrare prodotti che abbiano dati coerenti:

- il recommender usa rating/interazioni;
    
- il content-based usa metadati;
    
- il possibile QA usa domande/risposte.
    

Senza questa intersezione, si rischierebbe di avere prodotti raccomandabili ma senza QA, oppure prodotti con QA ma senza rating.

### Problemi e controlli fatti

Controlli importanti:

- verifica dei prodotti comuni tra QA e metadata;
    
- controllo dei prodotti con almeno un rating;
    
- esclusione del prodotto senza rating;
    
- salvataggio dei file in formato Parquet;
    
- salvataggio di un riepilogo finale.
    

Limite da ricordare:

- il collegamento tra QA storico e Amazon Reviews 2023 avviene tramite `asin`/`parent_asin`; è una scelta pratica, ma va spiegata come assunzione metodologica.
    

---

## 5. Notebook 02 - Esplorazione del dataset Electronics

### Obiettivo del notebook

Il Notebook 02 analizza il dataset costruito nel Notebook 01 per capire:

- qualità dei dati;
    
- distribuzione dei rating;
    
- numero di interazioni per utente;
    
- numero di interazioni per prodotto;
    
- sparsità della matrice utente-prodotto;
    
- soglie di filtraggio più adatte per i modelli.
    

Non addestra ancora modelli: serve a decidere come filtrare i dati prima degli esperimenti.

### Dati caricati

|Dataset|Shape|
|---|---|
|`items_df`|22.974 × 12|
|`qa_df`|180.976 × 8|
|`ratings_df`|3.484.401 × 6|

Statistiche generali:

|Grandezza|Valore|
|---|---|
|Prodotti totali|22.974|
|Rating totali|3.484.401|
|Utenti unici|2.434.619|
|Prodotti con rating|22.974|
|Righe QA|180.976|
|Prodotti con QA|22.974|

Tutti i prodotti presenti nei rating e nel QA sono presenti anche in `items`.

### Controlli qualità

Il notebook controlla:

- valori nulli nelle colonne principali;
    
- rating validi;
    
- presenza del timestamp;
    
- duplicati `user_id` + `parent_asin`;
    
- copertura dei prodotti nei vari file.
    

Risultati principali:

|Controllo|Risultato|
|---|---|
|Rating invalidi|0|
|Prodotti dei rating non presenti in items|0|
|Prodotti QA non presenti in items|0|
|`items.parent_asin` univoco|True|
|Righe coinvolte in coppie duplicate `user_id,parent_asin`|68.896|
|Coppie duplicate distinte|31.666|

Il notebook rimuove i duplicati mantenendo una sola interazione per coppia utente-prodotto, usando il timestamp per conservare l’interazione più recente.

Dopo la pulizia:

|Stato|Righe|
|---|---|
|Rating iniziali|3.484.401|
|Interazioni dopo pulizia|3.447.171|
|Righe rimosse|37.230|

### Distribuzione dei rating

Distribuzione dei rating originali:

|Rating|Numero|Percentuale|
|---|---|---|
|1|399.404|11,46%|
|2|195.919|5,62%|
|3|264.586|7,59%|
|4|573.679|16,46%|
|5|2.050.813|58,86%|

Osservazione critica: i rating sono molto sbilanciati verso 5 stelle. Questo rende sensato trattare come feedback positivo solo i rating alti, ad esempio `rating >= 4`, scelta poi fatta nel Notebook 03.

### Analisi temporale

Il timestamp viene interpretato in millisecondi.

Intervallo temporale:

```text
min: 1999-07-23
max: 2023-09-11
```

Il grosso delle interazioni è concentrato soprattutto tra 2012 e 2015. Questo va ricordato perché il dataset non rappresenta necessariamente il comportamento attuale degli utenti.

### Analisi degli utenti

Statistiche interazioni per utente dopo pulizia:

|Metrica|Valore|
|---|---|
|Utenti|2.434.619|
|Media interazioni per utente|1,416|
|Mediana|1|
|75° percentile|1|
|90° percentile|2|
|95° percentile|3|
|99° percentile|6|
|Massimo|98|

Questo mostra una forte sparsità lato utente: moltissimi utenti hanno una sola interazione.

Soglie utenti:

|Soglia utenti|Utenti rimasti|Interazioni rimaste|
|---|---|---|
|almeno 1 interazione|2.434.619|3.447.171|
|almeno 2 interazioni|535.461|1.548.013|
|almeno 3 interazioni|206.190|889.471|
|almeno 5 interazioni|55.824|393.849|
|almeno 10 interazioni|7.399|100.497|

Conclusione: per fare train/validation/test serve almeno una soglia a 3 interazioni per utente, altrimenti non si può assegnare una interazione a train, una a validation e una a test.

### Analisi dei prodotti

Statistiche interazioni per prodotto:

|Metrica|Valore|
|---|---|
|Prodotti|22.974|
|Media interazioni per prodotto|150,05|
|Mediana|52|
|25° percentile|20|
|75° percentile|137|
|90° percentile|317|
|95° percentile|536|
|99° percentile|1.540,7|
|Massimo|19.205|

Lato prodotto la situazione è migliore rispetto agli utenti: molti prodotti hanno un numero ragionevole di rating.

Soglie prodotti:

|Soglia prodotti|Prodotti rimasti|Interazioni rimaste|
|---|---|---|
|almeno 5 rating|21.853|3.444.256|
|almeno 8 rating|20.862|3.438.371|
|almeno 10 rating|20.211|3.432.824|
|almeno 20 rating|17.261|3.390.535|
|almeno 50 rating|11.768|3.211.164|

Il filtro prodotto serve a rimuovere item con pochissimo segnale collaborativo.

### QA

Statistiche QA:

|Grandezza|Valore|
|---|---|
|Prodotti totali|22.974|
|Prodotti con QA|22.974|
|Righe QA|180.976|
|Media QA per prodotto|7,88|
|Mediana QA per prodotto|9|
|Massimo QA per prodotto|40|

Il QA è quindi ben coperto nel catalogo finale, ma non ancora usato nei modelli.

### Sparsità della matrice utente-prodotto

Prima del filtro finale:

|Grandezza|Valore|
|---|---|
|Utenti|2.434.619|
|Prodotti|22.974|
|Interazioni|3.447.171|
|Densità|0,006163%|
|Sparsità|99,993837%|

La matrice è estremamente sparsa, cosa normale nei recommender e-commerce, ma problematica per i modelli collaborativi.

### Confronto soglie di filtraggio

Sono state provate diverse combinazioni di soglie su utenti e prodotti.

La configurazione scelta è:

```text
user3_item8
```

cioè:

```text
utenti con almeno 3 interazioni
prodotti con almeno 8 interazioni
```

Risultato della configurazione scelta:

|Grandezza|Valore|
|---|---|
|Utenti|196.509|
|Prodotti|15.069|
|Interazioni|844.060|
|Percentuale utenti mantenuti|8,07%|
|Percentuale prodotti mantenuti|65,59%|
|Percentuale interazioni mantenute|24,49%|
|Densità|0,028504%|
|Sparsità|99,971496%|
|Media interazioni per utente|4,30|
|Media interazioni per prodotto|56,01|

Motivazione:

- almeno 3 interazioni per utente permettono lo split train/validation/test;
    
- almeno 8 interazioni per prodotto riducono item troppo deboli;
    
- il filtro non distrugge completamente il catalogo;
    
- la densità migliora, anche se rimane bassa.
    

### Cosa si è capito sui dati

Il Notebook 02 mostra che:

- il dataset è coerente e utilizzabile;
    
- la copertura QA è completa sul catalogo finale;
    
- i rating sono sbilanciati verso valori alti;
    
- il problema principale è la sparsità lato utente;
    
- serve filtrare prima di addestrare modelli;
    
- la soglia `user3_item8` è un compromesso ragionevole.
    

---

## 6. Notebook 03 - Preparazione degli split train/validation/test

### Obiettivo del notebook

Il Notebook 03 trasforma il dataset candidato del Notebook 02 in un dataset pronto per la valutazione dei modelli.

Fa quattro cose principali:

1. seleziona solo feedback positivi;
    
2. rifiltra utenti e prodotti;
    
3. costruisce mapping numerici per utenti e item;
    
4. crea train, validation, test e negative samples.
    

### Perché servono train, validation e test

Nel recommender serve separare i dati per evitare di valutare il modello su interazioni già viste.

|Split|Uso|
|---|---|
|Train|Addestrare/calcolare i modelli|
|Validation|Scegliere modello e parametri|
|Test|Valutazione finale del modello scelto|

Regola metodologica importante: il test set non deve essere usato per scegliere pesi, modelli o soglie.

### Selezione del feedback positivo

Dal dataset `user3_item8`:

```text
844.060 interazioni candidate
```

Il notebook considera positive le interazioni con:

```text
rating >= 4
```

Risultato:

|Grandezza|Valore|
|---|---|
|Interazioni candidate|844.060|
|Interazioni positive prima del rifiltro|671.903|
|Percentuale positive|79,60%|
|Interazioni rimosse|172.157|

Questa scelta trasforma il problema da rating prediction a top-N recommendation basata su feedback positivo.

### Rifiltro dopo il rating positivo

Dopo aver tenuto solo rating `>= 4`, alcune soglie non sono più garantite. Il notebook rifiltra quindi utenti e prodotti mantenendo:

```text
utenti con almeno 3 interazioni positive
prodotti con almeno 8 interazioni positive
```

Dataset finale:

|Grandezza|Valore|
|---|---|
|Interazioni finali|550.548|
|Utenti finali|131.398|
|Prodotti finali|12.306|
|Densità finale|0,034048%|

Metadati e QA vengono riallineati ai prodotti rimasti:

|File|Righe|
|---|---|
|Prodotti finali con metadati|12.306|
|Righe QA finali|106.914|
|Prodotti finali con QA|12.306|

### Mapping user/item

Il notebook crea ID numerici:

|Mapping|Numero|
|---|---|
|Utenti mappati|131.398|
|Prodotti mappati|12.306|

Questi mapping sono necessari perché modelli come matrici sparse, ItemKNN e SVD lavorano meglio con indici interi continui, non con stringhe come `user_id` o `parent_asin`.

### Come viene fatto lo split

Lo split è temporale per utente:

- l’ultima interazione positiva dell’utente va nel test;
    
- la penultima va nella validation;
    
- tutte le precedenti vanno nel train.
    

Risultato:

|Split|Righe|
|---|---|
|Train|287.752|
|Validation|131.398|
|Test|131.398|

Ogni utente ha quindi una interazione in validation e una in test.

### Data leakage

Il data leakage si evita perché:

- il modello viene addestrato solo sul train;
    
- validation e test rappresentano interazioni future rispetto al train;
    
- i parametri vengono scelti su validation;
    
- il test resta per la valutazione finale.
    

Nota critica: il negative sampling esclude anche item già visti dall’utente, ma bisogna sempre spiegare che si tratta di valutazione offline approssimata, non di ranking su tutto il catalogo.

### Cold-start negli split

Alcuni item in validation/test non compaiono nel train. Sono pochi:

|Grandezza|Validation|Test|
|---|---|---|
|Cold item|7|7|
|Righe valutabili|131.376|131.352|

Queste righe non valutabili vengono escluse dalla valutazione collaborativa.

### Negative sampling

Per valutare il top-K recommendation, il notebook crea per ogni esempio:

```text
1 prodotto positivo reale
100 prodotti negativi campionati
```

Quindi il modello deve ordinare 101 candidati e mettere il positivo più in alto possibile.

I negativi servono perché valutare ogni utente contro tutti i 12.299 item candidati sarebbe più costoso. Questa è una scelta comune, ma introduce un limite metodologico.

Parametri:

|Parametro|Valore|
|---|---|
|Negativi per esempio|100|
|Candidati item dal train|12.299|
|Validation samples|131.376|
|Test samples|131.352|

### Baseline popularity del Notebook 03

Il Notebook 03 calcola una prima baseline basata sulla popolarità degli item nel train.

Risultati MostPopular:

|Split|K|HitRate / Recall|
|---|---|---|
|Validation|5|0,341973|
|Validation|10|0,464293|
|Validation|20|0,609853|
|Test|5|0,361639|
|Test|10|0,480998|
|Test|20|0,624878|

Nel Notebook 03 vengono calcolati HitRate e Recall; nel Notebook 04 vengono aggiunti anche NDCG e MRR.

### Output salvati

Il Notebook 03 salva:

- `train.parquet`
    
- `validation.parquet`
    
- `test.parquet`
    
- `validation_eval.parquet`
    
- `test_eval.parquet`
    
- `items.parquet`
    
- `qa.parquet`
    
- `user_mapping.parquet`
    
- `item_mapping.parquet`
    
- `negative_samples_validation.parquet`
    
- `negative_samples_test.parquet`
    
- `popularity_baseline_metrics.csv`
    
- `popularity_baseline_ranks.parquet`
    
- `split_summary.json`
    
- `positive_filter_history.csv`
    

---

## 7. Notebook 04 - Modelli collaborativi e valutazione

### Obiettivo del notebook

Il Notebook 04 addestra e valuta i primi modelli di raccomandazione collaborativi usando gli split del Notebook 03.

L’obiettivo è confrontare:

- una baseline semplice;
    
- ItemKNN;
    
- TruncatedSVD;
    
- metriche top-K comuni.
    

### Dati caricati

|Dataset|Righe|
|---|---|
|Train|287.752|
|Validation eval|131.376|
|Test eval|131.352|
|Utenti|131.398|
|Prodotti|12.306|

La matrice train utente-prodotto ha:

|Grandezza|Valore|
|---|---|
|Utenti|131.398|
|Item|12.306|
|Interazioni train|287.752|
|Densità|0,017796%|

È una matrice molto sparsa.

### Modelli implementati o valutati

Nel Notebook 04 vengono valutati:

|Modello|Tipo|
|---|---|
|MostPopular|Baseline non personalizzata|
|ItemKNN|Collaborative filtering item-item|
|TruncatedSVD|Modello a fattori latenti|

### Baseline MostPopular

La baseline assegna a ogni item un punteggio pari al numero di volte in cui compare nel training set.

Caratteristiche:

- non usa il profilo dell’utente;
    
- consiglia gli item più frequenti;
    
- è semplice ma spesso forte nei dataset e-commerce;
    
- serve come riferimento minimo.
    

### ItemKNN

ItemKNN costruisce una similarità tra prodotti usando le co-interazioni nel train.

Nel notebook:

- si costruisce una matrice item-utente;
    
- si usa `NearestNeighbors` con metrica cosine;
    
- si provano diversi numeri di vicini: 5, 10, 50, 100;
    
- per un utente, il punteggio di un candidato dipende dalla similarità con gli item che l’utente ha nel train.
    

Risultato importante: ItemKNN è molto sotto MostPopular e SVD. Anche `ItemKNN_100`, il migliore tra gli ItemKNN, rimane debole.

### TruncatedSVD

TruncatedSVD scompone la matrice utente-prodotto in fattori latenti a dimensione ridotta.

Nel notebook vengono provati:

```text
2, 4, 6, 8, 10, 12, 16, 24, 32 fattori
```

Il punteggio utente-item viene calcolato tramite prodotto scalare tra:

- embedding utente;
    
- embedding item.
    

Il miglior SVD su validation è:

```text
SVD_4
```

con varianza spiegata:

```text
0,013917
```

Nota: la varianza spiegata è bassa, ma non va interpretata da sola come metrica di qualità del recommender. La metrica principale resta NDCG@10.

### Differenza tra baseline, ItemKNN e SVD

|Modello|Cosa usa|Personalizzato?|Idea|
|---|---|---|---|
|MostPopular|Frequenza globale item|No|Consiglia ciò che è popolare|
|ItemKNN|Similarità tra item|Sì|Consiglia item simili a quelli visti dall’utente|
|SVD|Fattori latenti utente/item|Sì|Proietta utenti e item in uno spazio comune|

### Come vengono calcolati i punteggi

|Modello|Score|
|---|---|
|MostPopular|Conteggio item nel train|
|ItemKNN|Somma delle similarità tra candidato e item già visti dall’utente|
|SVD|Prodotto scalare tra embedding utente e embedding item|

### Come vengono valutati i modelli

Per ogni esempio:

1. si prende il prodotto positivo reale;
    
2. si aggiungono 100 negativi;
    
3. il modello assegna uno score a tutti i candidati;
    
4. si calcola la posizione del positivo;
    
5. si aggregano le metriche a K = 5, 10, 20.
    

### Metriche usate

Il Notebook 04 usa:

- HitRate@K;
    
- Recall@K;
    
- NDCG@K;
    
- MRR@K.
    

La metrica principale scelta è:

```text
NDCG@10
```

### Miglior modello su validation nel Notebook 04

Su validation il miglior modello è:

```text
MostPopular
```

con:

```text
NDCG@10 = 0,284317
```

Risultati principali validation@10:

|Modello|HitRate@10|NDCG@10|MRR@10|
|---|---|---|---|
|MostPopular|0,464293|0,284317|0,229132|
|SVD_4|0,444381|0,275201|0,223258|
|ItemKNN_100|0,152258|0,095706|0,078517|

### Risultati su test

Risultati principali test@10:

|Modello|HitRate@10|NDCG@10|MRR@10|
|---|---|---|---|
|MostPopular|0,480998|0,300195|0,244596|
|SVD_4|0,466898|0,295019|0,242076|
|ItemKNN_100|0,125579|0,072880|0,056909|

### Interpretazione critica

Il risultato più importante del Notebook 04 è che la baseline MostPopular batte i modelli collaborativi testati.

Questo non significa che il progetto sia fallito. Significa che:

- nel dataset c’è un forte effetto di popolarità;
    
- molti utenti hanno poche interazioni;
    
- la matrice è molto sparsa;
    
- modelli semplici collaborativi faticano a personalizzare;
    
- è metodologicamente corretto confrontare sempre con baseline semplici.
    

SVD_4 rimane comunque utile come componente collaborativa per il modello ibrido del Notebook 05.

### Artefatti salvati

Il Notebook 04 salva:

- metriche;
    
- confronto con baseline;
    
- rank dettagliati;
    
- popularity scores;
    
- vicini ItemKNN;
    
- embedding SVD migliori;
    
- summary JSON;
    
- demo recommendations.
    

Nota critica: le demo recommendations generate con MostPopular risultano sostanzialmente uguali per utenti diversi, perché il modello migliore del Notebook 04 è non personalizzato. Questo è un buon motivo per provare un modello ibrido.

---

## 8. Notebook 05 - Content-based e modello ibrido

### Obiettivo del notebook

Il Notebook 05 introduce informazioni contenutistiche dei prodotti e costruisce un modello ibrido che combina:

- contenuto testuale dei prodotti;
    
- SVD_4 dal Notebook 04;
    
- popolarità degli item.
    

L’obiettivo è verificare se i metadati dei prodotti possono migliorare il ranking rispetto alla sola popolarità o ai soli modelli collaborativi.

### Metadati testuali usati

Per ogni prodotto viene costruito un testo combinando campi come:

- titolo;
    
- categoria;
    
- store/brand;
    
- features;
    
- description;
    
- categories;
    
- details.
    

Il testo viene pulito rimuovendo HTML, simboli e spazi inutili, e convertito in minuscolo.

Risultati:

|Grandezza|Valore|
|---|---|
|Prodotti|12.306|
|Prodotti con testo vuoto|0|
|Token medi per prodotto|352,24|
|Mediana token|288|
|Massimo token|5.974|

Questo indica che i metadati sono abbastanza ricchi per provare un modello content-based.

### Come funziona TF-IDF

TF-IDF trasforma il testo dei prodotti in vettori numerici.

L’idea è:

- parole frequenti in un prodotto hanno peso alto;
    
- parole troppo comuni in tutti i prodotti hanno peso più basso;
    
- parole distintive aiutano a rappresentare meglio il contenuto del prodotto.
    

Parametri principali usati:

|Parametro|Valore|
|---|---|
|`max_features`|20.000|
|`min_df`|2|
|`max_df`|0,85|
|`ngram_range`|1-2|
|`stop_words`|English|

Matrice TF-IDF:

|Grandezza|Valore|
|---|---|
|Prodotti|12.306|
|Feature TF-IDF|20.000|
|Valori non nulli|2.244.999|
|Densità|0,912156%|

### Profili content-based degli utenti

Il profilo content-based di un utente viene costruito sommando i vettori TF-IDF dei prodotti con cui ha interagito nel train.

In pratica:

```text
profilo utente = somma dei testi/vettori dei prodotti apprezzati nel train
```

Statistiche:

|Grandezza|Valore|
|---|---|
|Forma matrice profili utente|131.398 × 20.000|
|Valori non nulli|47.609.835|
|Utenti con profilo non vuoto|131.398|

### Come viene calcolata la similarità

Il modello `ContentTFIDF` assegna uno score confrontando:

- profilo testuale dell’utente;
    
- vettore TF-IDF del prodotto candidato.
    

Poiché i vettori sono normalizzati, il prodotto scalare corrisponde alla similarità coseno.

### Risultati ContentTFIDF

Validation:

|K|HitRate|NDCG|MRR|
|---|---|---|---|
|5|0,191458|0,137711|0,120060|
|10|0,274023|0,164241|0,130911|
|20|0,399441|0,195723|0,139433|

Test:

|K|HitRate|NDCG|MRR|
|---|---|---|---|
|5|0,149164|0,104445|0,089809|
|10|0,223590|0,128317|0,099546|
|20|0,346763|0,159208|0,107894|

Interpretazione: il content-based puro cattura un segnale, ma è molto sotto MostPopular. Da solo non basta come modello principale.

### Recupero SVD e popolarità

Dal Notebook 04 vengono caricati:

|Componente|Dettaglio|
|---|---|
|Popularity scores|Disponibili per 12.299 item|
|Max popularity|1.118|
|Mean popularity|23,396|
|SVD disponibile|True|
|Modello SVD|SVD_4|
|Componenti SVD|4|
|Explained variance ratio|0,013917|

### Modello ibrido

Il modello ibrido combina tre componenti:

```text
score_finale =
  peso_content * score_content
+ peso_svd * score_svd
+ peso_popularity * score_popularity
```

Prima di combinarli, gli score vengono normalizzati con min-max normalization all’interno della lista candidati.

Questa normalizzazione serve perché content, SVD e popularity producono punteggi su scale diverse.

### Perché ha senso un modello ibrido

Il modello ibrido ha senso perché:

- la popolarità è forte ma non personalizzata;
    
- SVD aggiunge segnale collaborativo personalizzato;
    
- TF-IDF aggiunge informazioni sui contenuti dei prodotti;
    
- combinare segnali diversi può compensare i limiti dei singoli modelli.
    

### Modelli ibridi iniziali

Sono stati provati modelli manuali, ad esempio:

|Modello|Idea|
|---|---|
|`Hybrid_Content70_Pop30`|Molto content + un po’ popolarità|
|`Hybrid_SVD70_Content30`|Molto SVD + contenuto|
|`Hybrid_SVD50_Content25_Pop25`|Combinazione bilanciata|
|`Hybrid_SVD40_Content40_Pop20`|Più peso a contenuto e SVD|

Risultati test@10:

|Modello|HitRate@10|NDCG@10|MRR@10|
|---|---|---|---|
|Hybrid_Content70_Pop30|0,399431|0,212671|0,155803|
|Hybrid_SVD70_Content30|0,468078|0,297265|0,244757|
|Hybrid_SVD50_Content25_Pop25|0,488443|0,306868|0,250986|
|Hybrid_SVD40_Content40_Pop20|0,466715|0,298823|0,247309|

Il modello manuale migliore tra questi è `Hybrid_SVD50_Content25_Pop25`, che supera MostPopular su NDCG@10 test.

### Grid search dei pesi

Nel Notebook 05 viene poi aggiunta una grid search dei pesi:

```text
step = 0,05
combinazioni valutate = 231
componenti = SVD_4, ContentTFIDF, Popularity
```

La griglia prova tutte le combinazioni di pesi che sommano a 1.

### Migliore combinazione su validation

Il miglior modello complessivo su validation è:

```text
HybridGrid_SVD4_010_Content_035_Pop_055
```

cioè:

|Componente|Peso|
|---|---|
|SVD_4|0,10|
|ContentTFIDF|0,35|
|Popularity|0,55|

Validation@10:

|Modello|HitRate@10|NDCG@10|MRR@10|
|---|---|---|---|
|MostPopular|0,464293|0,284317|0,229132|
|HybridGrid best validation|0,500480|0,308938|0,249900|

Miglioramento su validation rispetto a MostPopular:

```text
NDCG@10: +0,024621 circa
```

### Test del modello scelto su validation

Per correttezza metodologica, il modello da considerare principale è quello scelto su validation:

```text
HybridGrid_SVD4_010_Content_035_Pop_055
```

Risultati test:

|K|HitRate|NDCG|MRR|
|---|---|---|---|
|5|0,367950|0,269498|0,237027|
|10|0,485329|0,307328|0,252566|
|20|0,626112|0,342828|0,262259|

Confronto con MostPopular test@10:

|Modello|HitRate@10|NDCG@10|MRR@10|
|---|---|---|---|
|MostPopular|0,480998|0,300195|0,244596|
|Hybrid scelto su validation|0,485329|0,307328|0,252566|

Miglioramento test@10:

|Metrica|Delta|
|---|---|
|HitRate@10|+0,004331|
|NDCG@10|+0,007133|
|MRR@10|+0,007970|

Nota critica: alcune configurazioni vicine ottengono risultati leggermente migliori sul test, ad esempio `HybridGrid_SVD4_015_Content_030_Pop_055` ha NDCG@10 test pari a 0,309659. Però non va scelta a posteriori sul test: il modello corretto da presentare come scelto è quello migliore su validation.

### Limiti del modello ibrido

Il modello ibrido migliora, ma con limiti:

- il miglioramento su test è reale ma non enorme;
    
- la componente popularity resta molto forte;
    
- il content-based puro è debole;
    
- la normalizzazione min-max viene fatta sui candidati del singolo esempio, quindi dipende dal negative sampling;
    
- la valutazione non è su tutto il catalogo, ma su 1 positivo + 100 negativi;
    
- il modello non è ancora integrato in un prototipo con utenti reali.
    

---

## 9. Spiegazione compatta delle metriche

### HitRate@K

HitRate@K misura se il prodotto positivo compare tra i primi K risultati.

Esempio:

```text
se il prodotto corretto è in top 10 → hit = 1
se non è in top 10 → hit = 0
```

Poi si fa la media su tutti gli esempi.

Nel progetto è una metrica utile perché vogliamo sapere se il recommender riesce a mettere il prodotto rilevante nella lista mostrata all’utente.

### Recall@K

Recall@K misura quanti prodotti rilevanti sono stati recuperati tra i primi K.

Nel nostro caso, ogni esempio ha un solo prodotto positivo. Per questo:

```text
Recall@K = HitRate@K
```

Se in futuro avessimo più prodotti rilevanti per utente, Recall e HitRate potrebbero divergere.

### NDCG@K

NDCG@K tiene conto non solo del fatto che il prodotto positivo sia nella top-K, ma anche della sua posizione.

Un positivo in posizione 1 vale più di un positivo in posizione 9.

È più informativa di HitRate perché premia i ranking che mettono il prodotto corretto più in alto.

### MRR@K

MRR@K significa Mean Reciprocal Rank.

Guarda la posizione del primo risultato rilevante e assegna:

```text
1 / rank
```

Esempi:

|Posizione positivo|MRR|
|---|---|
|1|1|
|2|0,5|
|5|0,2|
|10|0,1|

Se il positivo non è nei primi K, vale 0.

### Differenza tra NDCG e MRR

La differenza principale è:

- **MRR** usa `1/rank`, quindi penalizza fortemente il fatto che il positivo scenda di posizione;
    
- **NDCG** usa uno sconto logaritmico, quindi penalizza la posizione ma in modo diverso e più graduale.
    

Nel nostro caso, avendo un solo positivo per esempio, NDCG e MRR sono abbastanza simili come interpretazione. Però NDCG è più generale e adatta anche a scenari con più item rilevanti o con rilevanza graduata.

### Perché queste metriche sono adatte

Sono adatte perché il problema è top-K recommendation:

- il sistema non deve predire il rating esatto;
    
- deve ordinare prodotti candidati;
    
- interessa sapere se i prodotti rilevanti finiscono in alto;
    
- un utente reale vede solo una lista breve di suggerimenti.
    

---

## 10. Scelte metodologiche principali

|Scelta|Motivazione|Vantaggio|Limite|Da discutere col relatore|
|---|---|---|---|---|
|Uso di Electronics|Categoria ampia e coerente col prototipo e-commerce|22.974 prodotti finali con QA + metadata + rating|Dataset pesante e molto sparso lato utente|Confermare che sia la categoria principale|
|Intersezione QA + metadata + rating|Avere un catalogo unico per recommender e futuro QA|Coerenza tra moduli|Si eliminano prodotti non presenti in tutti i dataset|Spiegare bene l’assunzione `asin`/`parent_asin`|
|Filtraggio utenti/prodotti|Ridurre sparsità estrema|Dati più adatti ai modelli|Perdita di molti utenti|Confermare soglia `user3_item8`|
|Rating `>= 4` come positivo|Formulare top-N recommendation|Semplice e difendibile|Perde informazione sui rating 1-3|Confermare soglia positiva|
|Split temporale per utente|Simulare raccomandazione futura|Evita leakage più chiaramente|Non è un esperimento online reale|Confermare descrizione metodologica|
|Negative sampling|Valutazione più gestibile|100 negativi per positivo|Risultati dipendono dai negativi campionati|Chiedere se basta o serve full ranking|
|Baseline popularity|Riferimento minimo forte|Semplice, chiara, utile|Non personalizzata|Presentarla come baseline principale|
|ItemKNN|Modello collaborativo interpretabile|Facile da spiegare|Risultati bassi|Decidere se tenerlo come confronto|
|TruncatedSVD|Modello collaborativo a fattori latenti|Aggiunge personalizzazione compatta|Non studiato nel corso, va spiegato bene|Chiedere se è accettabile per la tesi|
|TF-IDF content-based|Usa metadati testuali|Utile per prodotti simili e ibrido|Debole da solo|Presentarlo come componente, non modello finale|
|Modello ibrido|Combina segnali diversi|Migliora NDCG rispetto a MostPopular|Miglioramento non enorme|Chiedere se basta come contributo sperimentale|
|Valutazione offline top-K|Standard per confronto modelli|Riproducibile|Non misura comportamento reale|Dichiarare bene il limite|
|QA rimandato|Evitare progetto troppo grande|Focus sul recommender|QA non implementato|Chiedere se va bene come estensione futura|

---

## 11. Codice principale da saper spiegare

### Tabella dei blocchi importanti

|Blocco|Dove|Cosa fa|Input|Output|Perché serve|Come lo spiegherei al relatore|
|---|---|---|---|---|---|---|
|Caricamento dati iniziale|Notebook 01|Scarica/legge QA, metadata e rating|Dataset Amazon|DataFrame/file filtrati|Costruire il catalogo base|“Parto da tre fonti e tengo solo i prodotti collegabili tra loro.”|
|`iter_historical_qa`|Notebook 01|Legge il file QA storico riga per riga|`qa_Electronics.json.gz`|Righe QA parseate|Evita di caricare tutto male/in modo rigido|“Il QA storico non è un parquet moderno, quindi lo leggo e lo normalizzo.”|
|Intersezione prodotti|Notebook 01|Tiene prodotti presenti in QA e metadata|ASIN/parent_ASIN|Lista prodotti comuni|Catalogo coerente|“Creo il sottoinsieme di prodotti su cui possono lavorare sia recommender sia QA.”|
|Scrittura Parquet|Notebook 01|Salva `items`, `qa`, `ratings`|DataFrame filtrati|File `.parquet`|Efficienza e riuso nei notebook successivi|“Uso parquet per non rifare ogni volta il filtraggio pesante.”|
|Pulizia duplicati|Notebook 02|Rimuove duplicati utente-prodotto|Rating grezzi|Interazioni pulite|Evitare doppioni nella matrice|“Tengo una sola interazione per coppia utente-prodotto, preferendo la più recente.”|
|Analisi utenti/prodotti|Notebook 02|Conta interazioni per utente e prodotto|Interazioni pulite|Tabelle distribuzioni|Capire sparsità|“Serve a scegliere soglie non arbitrarie.”|
|Scelta `user3_item8`|Notebook 02|Applica filtro iterativo|Interazioni pulite|Dataset candidato|Permettere split e ridurre item deboli|“Scelgo almeno 3 interazioni per utente e 8 per prodotto come compromesso.”|
|Feedback positivo|Notebook 03|Tiene rating `>= 4`|Dataset candidato|Interazioni positive|Trasformare in top-N recommendation|“Non predico il rating esatto, ma considero rilevanti i prodotti valutati bene.”|
|Mapping user/item|Notebook 03|Crea `user_idx` e `item_idx`|ID originali|ID numerici|Necessario per matrici e modelli|“Trasformo stringhe in indici interi continui.”|
|Split temporale|Notebook 03|Ultima interazione test, penultima validation|Interazioni positive ordinate|Train/validation/test|Evitare leakage|“Simulo il caso in cui voglio predire interazioni future.”|
|Negative sampling|Notebook 03|Campiona 100 negativi per positivo|Item train + storico utente|Tabelle candidate|Valutare ranking top-K|“Il modello deve scegliere il positivo tra 101 candidati.”|
|`rank_positive`|Notebook 04/05|Calcola posizione del positivo|Score candidati|Rank del positivo|Base delle metriche|“Se molti negativi superano il positivo, il rank peggiora.”|
|`calculate_topk_metrics`|Notebook 04/05|Calcola HitRate, Recall, NDCG, MRR|Lista rank|Tabella metriche|Valutazione uniforme|“Aggrego i rank su tutti gli esempi.”|
|`evaluate_model`|Notebook 04/05|Valuta un modello su tutti gli esempi|Samples + score function|Metriche + rank|Confronto modelli|“Ogni modello cambia solo nella funzione di scoring.”|
|`score_popularity`|Notebook 04/05|Score = frequenza item nel train|Item candidati|Score popularity|Baseline|“Non personalizza: ordina per popolarità globale.”|
|ItemKNN|Notebook 04|Trova item simili via cosine similarity|Matrice item-utente|Vicini item e score|Collaborative filtering interpretabile|“Raccomanda item simili a quelli già visti dall’utente.”|
|TruncatedSVD|Notebook 04|Crea embedding utente/item|Matrice train|Fattori latenti|Personalizzazione compatta|“Riduce la matrice sparsa in uno spazio latente.”|
|Costruzione testi prodotto|Notebook 05|Unisce titolo, categoria, store, feature, descrizioni|`items_df`|`content_text`|Base content-based|“Creo una descrizione testuale unica per ogni prodotto.”|
|TF-IDF|Notebook 05|Trasforma testi in vettori|`content_text`|Matrice item-termine|Similarità testuale|“Rappresento i prodotti con parole importanti e distintive.”|
|Profilo content-based utente|Notebook 05|Somma vettori TF-IDF dei prodotti train|Train + item TF-IDF|Matrice user-profile|Personalizzazione contenutistica|“Un utente è rappresentato dai contenuti dei prodotti apprezzati.”|
|`score_content_tfidf`|Notebook 05|Similarità utente-prodotto|Profilo utente + item TF-IDF|Score content|Modello content-based|“Più il prodotto è simile al profilo testuale, più sale nel ranking.”|
|Scoring ibrido|Notebook 05|Combina content, SVD, popularity|Tre score normalizzati|Score finale|Integrare segnali diversi|“Metto insieme popolarità, collaborazione e contenuto.”|
|Grid search pesi|Notebook 05|Prova combinazioni con step 0,05|Pesi possibili|Migliori configurazioni|Scegliere pesi su validation|“Scelgo i pesi senza usare il test, usando NDCG@10 su validation.”|

### Blocchi da saper spiegare bene a voce

#### Split temporale

Frase utile:

> “Per ogni utente ordino le interazioni nel tempo. Uso l’ultima come test, la penultima come validation e il resto come train. Così provo a simulare una raccomandazione futura e riduco il rischio di data leakage.”

#### Negative sampling

Frase utile:

> “Per ogni esempio di validation/test ho un prodotto positivo reale e 100 prodotti negativi campionati. Il modello assegna un punteggio a tutti e il positivo dovrebbe finire più in alto possibile. È una valutazione offline approssimata, non un ranking sull’intero catalogo.”

#### TruncatedSVD

Frase utile:

> “TruncatedSVD è un modello a fattori latenti: prende la matrice utente-prodotto molto sparsa e la approssima in uno spazio più piccolo. Ogni utente e ogni prodotto diventano vettori; il punteggio è il prodotto scalare tra i due vettori.”

#### TF-IDF

Frase utile:

> “TF-IDF rappresenta i prodotti tramite parole e bigrammi dei metadati. Le parole più distintive pesano di più. Poi creo un profilo dell’utente sommando i vettori dei prodotti che ha apprezzato nel train.”

#### Modello ibrido

Frase utile:

> “Il modello ibrido combina tre segnali: popolarità, SVD e contenuto testuale. La popolarità è forte ma non personalizzata; SVD aggiunge personalizzazione collaborativa; TF-IDF aggiunge informazione sui metadati. La combinazione migliore viene scelta su validation.”

---

## 12. Risultati ottenuti finora

### Risultati dataset

|Fase|Utenti|Prodotti|Interazioni / righe|Note|
|---|---|---|---|---|
|Notebook 01 finale|2.434.619 utenti nei rating|22.974|3.484.401 rating|Catalogo QA + metadata + rating|
|Notebook 02 dopo pulizia|2.434.619|22.974|3.447.171|Duplicati rimossi|
|Notebook 02 `user3_item8`|196.509|15.069|844.060|Dataset candidato|
|Notebook 03 rating `>=4` finale|131.398|12.306|550.548|Dataset positivo rifiltrato|
|Train|131.398|12.299 nel train|287.752|Addestramento|
|Validation eval|131.376 esempi|||1 positivo + 100 negativi|
|Test eval|131.352 esempi|||1 positivo + 100 negativi|

### Risultati principali validation@10

|Modello|Tipo|HitRate@10|NDCG@10|MRR@10|
|---|---|---|---|---|
|MostPopular|Baseline|0,464293|0,284317|0,229132|
|ItemKNN_100|Collaborativo item-item|0,152258|0,095706|0,078517|
|SVD_4|Fattori latenti|0,444381|0,275201|0,223258|
|ContentTFIDF|Content-based|0,274023|0,164241|0,130911|
|HybridGrid_SVD4_010_Content_035_Pop_055|Ibrido|0,500480|0,308938|0,249900|

Conclusione validation: il modello migliore è l’ibrido con pesi:

```text
SVD_4 = 0,10
ContentTFIDF = 0,35
Popularity = 0,55
```

### Risultati principali test@10

|Modello|Tipo|HitRate@10|NDCG@10|MRR@10|
|---|---|---|---|---|
|MostPopular|Baseline|0,480998|0,300195|0,244596|
|ItemKNN_100|Collaborativo item-item|0,125579|0,072880|0,056909|
|SVD_4|Fattori latenti|0,466898|0,295019|0,242076|
|ContentTFIDF|Content-based|0,223590|0,128317|0,099546|
|HybridGrid scelto su validation|Ibrido|0,485329|0,307328|0,252566|

### Miglioramento rispetto alla baseline

Confronto test@10:

|Metrica|MostPopular|Ibrido scelto su validation|Delta|
|---|---|---|---|
|HitRate@10|0,480998|0,485329|+0,004331|
|NDCG@10|0,300195|0,307328|+0,007133|
|MRR@10|0,244596|0,252566|+0,007970|

Interpretazione:

- l’ibrido migliora rispetto a MostPopular;
    
- il miglioramento non è enorme, ma è coerente;
    
- la popolarità rimane una componente molto importante;
    
- il contributo principale del Notebook 05 è mostrare che combinare segnali diversi può superare la baseline.
    

### Risultato da presentare con cautela

Alcune configurazioni della griglia ottengono risultati leggermente migliori sul test, per esempio:

```text
HybridGrid_SVD4_015_Content_030_Pop_055
NDCG@10 test = 0,309659
```

Però non va scelta come modello principale se non era la migliore su validation. Va eventualmente menzionata solo come configurazione vicina, non come modello selezionato.

---

## 13. Limiti del lavoro attuale

### 1. Dataset molto sparso

Anche dopo i filtri, la matrice utente-prodotto è molto sparsa.

Nel train del Notebook 04:

```text
densità = 0,017796%
```

Questo rende difficile imparare preferenze personalizzate robuste.

### 2. Molti utenti hanno poche interazioni

Nel dataset originale la mediana delle interazioni per utente è 1. Anche dopo i filtri, ogni utente ha almeno 3 interazioni positive, ma rimane uno storico molto limitato.

### 3. Valutazione offline

La valutazione è offline, su dati storici. Non misura:

- click reali nel prototipo;
    
- soddisfazione dell’utente;
    
- conversioni;
    
- comportamento durante una sessione.
    

### 4. Negative sampling artificiale

Ogni positivo viene confrontato con 100 negativi campionati. Questo è pratico, ma non equivale a ordinare tutto il catalogo.

Possibile rischio:

- risultati sensibili a quali negativi vengono campionati;
    
- modelli popularity-based possono essere favoriti se i negativi sono relativamente facili.
    

### 5. Bias verso prodotti popolari

MostPopular è molto forte. Questo suggerisce che il dataset ha un forte bias verso prodotti molto recensiti.

Rischio:

- raccomandare sempre prodotti popolari;
    
- ridurre personalizzazione;
    
- penalizzare prodotti di nicchia.
    

### 6. Cold start

Nel dataset filtrato gli item cold-start in validation/test sono pochi, ma il problema resta per un sistema reale:

- nuovo utente senza storico;
    
- nuovo prodotto senza interazioni;
    
- prodotto con pochi metadati.
    

Il content-based può aiutare per gli item, ma non risolve tutto.

### 7. Assenza di utenti reali nel prototipo

Finora il sistema è valutato solo sui dati storici. Non esiste ancora una demo con utenti reali o simulati che interagiscono con il sito.

### 8. Modello non industriale

Il modello è adatto a una tesi triennale e a un prototipo, ma non è un sistema industriale. Mancano:

- ranking su larga scala;
    
- aggiornamento online;
    
- gestione sessioni reali;
    
- monitoraggio;
    
- A/B testing;
    
- ottimizzazione per latenza;
    
- metriche business.
    

### 9. QA non ancora implementato

Il QA è stato preparato a livello di dati, ma non è ancora usato. Va presentato come estensione possibile, non come risultato già raggiunto.

### 10. Uso limitato delle recensioni testuali

Le recensioni testuali non sono ancora usate nel modello. Al momento si usano:

- rating;
    
- metadata prodotto;
    
- QA solo come dato disponibile ma non operativo.
    

Se si vuole usare il testo delle recensioni, bisogna ripensare l’estrazione dati.

### 11. Collegamento tra dataset 2023 e QA storico

Il collegamento tramite ASIN/parent_ASIN è pratico, ma va spiegato come assunzione. I dataset non sono perfettamente omogenei nel tempo.

### 12. Scelta dei pesi dell’ibrido

La grid search è utile, ma i pesi sono cercati su una griglia discreta. Non è una ottimizzazione sofisticata. Va bene per il progetto, ma va dichiarato.

---

## 14. Domande intelligenti da fare al relatore

1. Va bene mantenere il QA come estensione futura, senza implementarlo ora?
    
2. Per una tesi triennale, ha senso fermarsi a MostPopular, ItemKNN, SVD, TF-IDF e ibrido?
    
3. Il modello ibrido è sufficiente come contributo sperimentale?
    
4. Serve aggiungere un altro modello, oppure rischia di allargare troppo il lavoro?
    
5. La valutazione con 100 negative samples è accettabile per questa tesi?
    
6. Ha senso fare un Notebook 06 solo di analisi finale/grafici, senza nuovi modelli?
    
7. È meglio concentrarsi ora sul prototipo web o su ulteriori esperimenti?
    
8. Come presentare correttamente il fatto che MostPopular è molto forte?
    
9. Come spiegare il ruolo di TruncatedSVD se non è un modello visto direttamente nel corso?
    
10. Conviene usare le recensioni testuali, o è meglio lasciarle come limite/futuro sviluppo?
    
11. Il collegamento `asin`/`parent_asin` tra QA storico e Reviews 2023 è metodologicamente accettabile?
    
12. Come presentare correttamente l’uso di strumenti IA nella tesi e nel lavoro di supporto?
    

---

## 15. Come spiegare il progetto a voce in 3-5 minuti

Una possibile scaletta discorsiva:

> Ho impostato la prima parte della tesi come una pipeline sperimentale per un recommender e-commerce. Sono partito dai dataset Amazon del McAuley Lab, usando Amazon Reviews 2023 per metadati, rating e recensioni, e il dataset storico Amazon QA per le domande e risposte sui prodotti.
> 
> Inizialmente ho valutato diverse categorie, ma ho scelto Electronics perché è quella più adatta al prototipo: dopo l’intersezione tra QA, metadati e rating rimangono 22.974 prodotti, 180.976 righe QA e circa 3,48 milioni di rating.
> 
> Nel Notebook 02 ho analizzato la qualità dei dati e la sparsità. Il problema principale è che ci sono moltissimi utenti con una sola interazione, quindi ho confrontato diverse soglie di filtraggio. Ho scelto la configurazione `user3_item8`, cioè almeno 3 interazioni per utente e 8 per prodotto, perché permette di creare train, validation e test mantenendo comunque un catalogo abbastanza ampio.
> 
> Nel Notebook 03 ho trasformato il problema in top-N recommendation, considerando positivi i rating maggiori o uguali a 4. Dopo il rifiltro finale rimangono 131.398 utenti, 12.306 prodotti e 550.548 interazioni positive. Lo split è temporale per utente: ultima interazione nel test, penultima nella validation e il resto nel train. Per valutare i ranking ho generato 100 negativi per ogni positivo.
> 
> Nel Notebook 04 ho confrontato baseline e modelli collaborativi. La baseline MostPopular è molto forte e batte sia ItemKNN sia SVD. Il miglior SVD è SVD_4, che si avvicina alla baseline ma non la supera. Questo è un risultato importante perché mostra il peso della popolarità e della sparsità nel dataset.
> 
> Nel Notebook 05 ho aggiunto un modello content-based basato su TF-IDF dei metadati prodotto e poi un modello ibrido che combina TF-IDF, SVD_4 e popolarità. Il content-based puro non basta, ma l’ibrido migliora rispetto alla baseline. Il modello scelto su validation usa 0,10 SVD, 0,35 contenuto e 0,55 popolarità, e su test migliora NDCG@10 da 0,300 a 0,307.
> 
> Quindi finora il risultato principale è una pipeline completa e riproducibile: dataset, filtri, split, baseline, modelli collaborativi, content-based, ibrido e valutazione offline. Il prossimo passo sarebbe consolidare l’analisi finale e poi costruire un prototipo web leggero che usi il modello selezionato o raccomandazioni precomputate.

---

## 16. Prossimi passi consigliati

### Passi necessari

1. **Consolidare Notebook 05**
    
    - Verificare che tutti gli output siano salvati correttamente.
        
    - Chiarire nel commento finale che il modello scelto è quello migliore su validation, non quello migliore a posteriori sul test.
        
2. **Creare una piccola analisi finale**
    
    - Può essere un Notebook 06 oppure alcune celle finali nel Notebook 05.
        
    - Deve contenere:
        
        - confronto modelli principali;
            
        - grafici delle metriche;
            
        - miglioramento rispetto alla baseline;
            
        - commento critico sui risultati.
            
3. **Preparare dati per il prototipo**
    
    - prodotti per demo;
        
    - utenti demo;
        
    - raccomandazioni per utente;
        
    - prodotti popolari;
        
    - prodotti simili;
        
    - eventualmente embedding o matrici leggere.
        
4. **Costruire un backend leggero**
    
    - FastAPI o Flask;
        
    - endpoint per prodotti, utenti demo e raccomandazioni;
        
    - caricamento degli artefatti già salvati;
        
    - nessun retraining durante l’uso del sito.
        
5. **Costruire un frontend semplice**
    
    - catalogo prodotti;
        
    - selezione utente demo;
        
    - pagina prodotto;
        
    - raccomandazioni;
        
    - eventuale carrello/sessione simulata.
        
6. **Documentare i limiti**
    
    - sparsità;
        
    - offline evaluation;
        
    - negative sampling;
        
    - popularity bias;
        
    - QA non implementato;
        
    - recensioni testuali non usate.
        
7. **Preparare la parte metodologica**
    
    - spiegare dataset;
        
    - motivare filtri;
        
    - motivare metriche;
        
    - spiegare confronto con baseline;
        
    - dichiarare uso IA secondo le indicazioni dell’università.
        

### Passi opzionali

1. **Session-based personalization leggera**
    
    - Se l’utente clicca o aggiunge al carrello un prodotto, aggiornare temporaneamente i consigli usando prodotti simili.
        
    - Deve restare semplice.
        
2. **Prodotti simili**
    
    - Usare TF-IDF per mostrare “prodotti simili” nella pagina prodotto.
        
    - È coerente con il Notebook 05.
        
3. **QA retrieval-based**
    
    - Solo se rimane tempo.
        
    - Basato su QA già presenti o metadati.
        
    - Non costruire un chatbot generativo complesso.
        
4. **Grafici per tesi**
    
    - distribuzione rating;
        
    - distribuzione interazioni utente/prodotto;
        
    - confronto modelli;
        
    - delta rispetto alla baseline.
        

### Cose da evitare

- Non aggiungere modelli solo per “fare di più”.
    
- Non usare il test set per scegliere il modello.
    
- Non iniziare un QA complesso prima di finire recommender e prototipo.
    
- Non costruire un clone completo di Amazon.
    
- Non collegare direttamente il sito ai notebook.
    
- Non riaddestrare i modelli a ogni click.
    
- Non presentare l’ibrido come sistema industriale.
    
- Non ignorare il fatto che MostPopular è molto forte.
    

### Nota su Notebook 06

Un Notebook 06 ha senso solo se serve a raccogliere e visualizzare i risultati finali. Non dovrebbe introdurre nuovi modelli senza motivazione.

Possibile ruolo del Notebook 06:

```text
Notebook 06 - Analisi finale esperimenti
```

Contenuto consigliato:

- tabella finale modelli;
    
- grafici HitRate/NDCG/MRR;
    
- confronto baseline vs SVD vs ContentTFIDF vs Hybrid;
    
- analisi dei limiti;
    
- selezione definitiva del modello per il prototipo.
    

Alternativa: aggiungere poche celle finali al Notebook 05, se non si vuole creare un notebook quasi solo di visualizzazione.

---

## 17. Mini glossario

### Recommender system

Sistema che suggerisce item a un utente in base a dati storici, preferenze, comportamenti o contenuti.

### Collaborative filtering

Approccio che usa le interazioni utente-item. L’idea è che utenti o prodotti con comportamenti simili possano aiutare a fare raccomandazioni.

### Content-based filtering

Approccio che usa le caratteristiche degli item, ad esempio titolo, descrizione, categoria o metadati. Consiglia prodotti simili a quelli apprezzati dall’utente.

### Hybrid recommender

Sistema che combina più approcci, ad esempio collaborative filtering, content-based e popularity.

### Popularity baseline

Baseline che consiglia gli item più popolari nel training set. Non è personalizzata, ma spesso è forte.

### ItemKNN

Modello collaborative filtering che calcola similarità tra prodotti. Consiglia item simili a quelli già visti dall’utente.

### TruncatedSVD

Tecnica di riduzione dimensionale applicata alla matrice utente-prodotto. Produce embedding latenti per utenti e item.

### Embedding

Vettore numerico che rappresenta un utente, un prodotto o una parola in uno spazio latente.

### TF-IDF

Tecnica che rappresenta documenti/testi tramite parole pesate. Le parole distintive pesano più di quelle troppo comuni.

### Negative sampling

Tecnica per valutare o addestrare modelli usando un sottoinsieme di item negativi invece dell’intero catalogo.

### Train/validation/test

Divisione dei dati in:

- train per addestrare;
    
- validation per scegliere modelli/parametri;
    
- test per valutare il modello finale.
    

### HitRate

Percentuale di casi in cui il prodotto positivo compare nella top-K.

### Recall

Percentuale di item rilevanti recuperati nella top-K. In questo progetto coincide con HitRate perché c’è un solo positivo per esempio.

### NDCG

Metrica che premia il fatto di mettere item rilevanti in alto nel ranking.

### MRR

Metrica basata sull’inverso della posizione del primo item rilevante.

### Cold start

Problema che si verifica quando un utente o un prodotto ha poche o zero interazioni storiche.

### Sparsity

Sparsità della matrice utente-prodotto. Indica che la maggior parte delle coppie utente-item non ha interazioni osservate.

---

## Checklist prima dell’incontro

### Da rileggere

-  Scelta dataset Electronics e confronto con Beauty, Cell Phones, Video Games.
    
-  Numeri finali Notebook 01: 22.974 prodotti, 180.976 QA, 3.484.401 rating.
    
-  Motivazione del filtro `user3_item8`.
    
-  Scelta `rating >= 4` come feedback positivo.
    
-  Logica dello split temporale per utente.
    
-  Negative sampling: 1 positivo + 100 negativi.
    
-  Differenza tra HitRate, Recall, NDCG e MRR.
    
-  Perché MostPopular è una baseline forte.
    
-  Perché ItemKNN va male.
    
-  Cos’è TruncatedSVD e perché SVD_4 è stato mantenuto.
    
-  Come funziona TF-IDF nel Notebook 05.
    
-  Come funziona il modello ibrido.
    
-  Perché il modello va scelto su validation e non su test.
    

### Da verificare

-  Se citare o meno il numero di oltre 43 milioni di rating scansionati: nel Notebook 01 eseguito non è stampato, quindi va verificato prima di inserirlo nella tesi.
    
-  Che tutti gli output del Notebook 05 siano salvati correttamente.
    
-  Che non ci siano discrepanze tra notes vecchie e notebook finali, ad esempio numeri aggiornati dopo Electronics.
    
-  Se il relatore accetta la valutazione con negative sampling.
    
-  Se il relatore preferisce un Notebook 06 separato o solo celle finali nel Notebook 05.
    
-  Come dichiarare l’uso di ChatGPT/IA nella tesi in modo trasparente.
    

### Domande da portare

-  Va bene lasciare il QA come estensione futura?
    
-  I modelli testati sono sufficienti per una triennale?
    
-  Il miglioramento dell’ibrido rispetto a MostPopular è sufficiente come risultato?
    
-  Devo aggiungere un confronto con un altro modello o rischio di allargare troppo?
    
-  Conviene ora concentrarsi sul prototipo?
    
-  Come presentare correttamente i limiti del negative sampling e della valutazione offline?
    

### Frase finale da tenere pronta

> “Finora ho costruito una pipeline completa e riproducibile per il recommender: dataset, filtri, split temporale, negative sampling, baseline, modelli collaborativi, content-based e ibrido. Il risultato principale è che la popolarità è molto forte, ma un modello ibrido che combina popolarità, SVD e contenuto riesce a migliorare NDCG@10 rispetto alla baseline. Ora vorrei capire se fermare qui la parte sperimentale e passare al prototipo, oppure se serve un ulteriore confronto.”