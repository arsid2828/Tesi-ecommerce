Per la tesi scelgo di usare la famiglia dei dataset Amazon di McAuley, combinando un dataset di recensioni/prodotti con un dataset di question answering. Il dataset per la raccomandazione contiene utenti, prodotti, rating, recensioni e metadati dei prodotti; il dataset QA contiene domande e risposte associate ai prodotti Amazon. I due insiemi di dati vanno uniti tramite l’identificativo del prodotto, cioè l’`asin`, costruendo un catalogo unico formato solo dai prodotti presenti sia nelle recensioni/rating sia nelle domande/risposte. In questo modo il sistema di raccomandazione e il sistema QA lavorano sugli stessi prodotti: il primo può suggerire articoli usando rating, recensioni e interazioni utente-prodotto, mentre il secondo può rispondere alle domande usando recensioni, metadati e QA dello stesso prodotto.

Questa scelta è preferibile perché rende coerente il prototipo: ogni prodotto mostrato nel sito può essere raccomandato e, se presente nel sottoinsieme QA, può anche essere interrogato. Le alternative considerate erano Amazon Reviews 2023, più moderno e ricco ma meno immediato da collegare al dataset QA storico; Instacart, adatto al next-basket recommendation ma senza recensioni testuali; RetailRocket o Yoochoose, utili per dati impliciti e session-based recommendation ma meno adatti a un sito simil-Amazon con schede prodotto e QA; MovieLens, semplice per testare algoritmi ma non realmente e-commerce. 

Per questo la scelta più solida è usare dataset Amazon collegabili tramite `asin`, filtrando il catalogo sull’intersezione dei prodotti disponibili nei vari file.

Uso la survey "Information Discovery in E-commerce" come fonte secondaria per motivare la scelta metodologica e collocare i dataset Amazon nella letteratura su recommendation e QA in e-commerce.

Uso invece le pagine ufficiali McAuley/UCSD come fonte primaria per descrivere e scaricare i dataset: Amazon Product Data per recensioni, rating e metadati; Amazon Question/Answer Data per domande e risposte sui prodotti. I due dataset sono collegabili tramite ASIN, cioè l'identificativo del prodotto.


# CAMBIO IDEA
Abbiamo scelto i dataset per la tesi con l’obiettivo di costruire un prototipo e-commerce in cui **sistema di raccomandazione** e **sistema QA** lavorino sullo **stesso catalogo di prodotti**. Per questo non basta usare un dataset di recensioni e uno di domande/risposte separati: i prodotti devono essere collegabili tramite un identificativo comune.

## QUINDI
La scelta finale è usare **Amazon Reviews 2023** per il modulo di raccomandazione e i metadati prodotto, insieme all’**Amazon Question/Answer Data storico** per il modulo QA. Amazon Reviews 2023 è il dataset più recente del McAuley Lab e contiene recensioni, rating, testi, timestamp, utenti, metadati prodotto, categorie, descrizioni, prezzi e immagini. Per il QA, invece, non esiste una versione ufficiale “Amazon QA 2023”, quindi viene usato il dataset storico Amazon Question/Answer Data, legato ai lavori McAuley/Yang e Wan/McAuley del 2016, che contiene domande e risposte associate ai prodotti Amazon.

Abbiamo testato l’allineamento tra il dataset QA storico `Beauty` e due categorie di Amazon Reviews 2023: `All_Beauty` e `Beauty_and_Personal_Care`. L’intersezione è stata fatta confrontando l’`asin` del dataset QA con il `parent_asin` del dataset Amazon Reviews 2023. Il risultato ha mostrato che `All_Beauty` è poco adatto, perché ha solo **46 prodotti** in comune con il QA Beauty. Invece `Beauty_and_Personal_Care` è molto più compatibile: ha **2.620 prodotti** in comune con il QA Beauty, pari a circa il **44,7%** dei prodotti QA.

Successivamente abbiamo verificato che questi prodotti comuni avessero anche recensioni/rating nel dataset 2023. L’intersezione finale tra **QA Beauty**, **metadata 2023 Beauty_and_Personal_Care** e **review 2023 Beauty_and_Personal_Care** ha prodotto un catalogo finale di **2.619 prodotti**, con **615.015 recensioni/rating** e **543.992 utenti**. Questo significa che quasi tutti i prodotti comuni tra QA e metadati hanno anche recensioni, quindi il dataset finale è utilizzabile per il prototipo.

### La scelta finale dei dataset è quindi:

Recommendation e metadati:
Amazon Reviews 2023
categoria: Beauty_and_Personal_Care
config usate:
- raw_meta_Beauty_and_Personal_Care
- raw_review_Beauty_and_Personal_Care

Question Answering:
Amazon Question/Answer Data storico
categoria:
- QA_Beauty.json.gz

Il catalogo del sito sarà costruito usando solo i prodotti presenti in tutti e tre i blocchi:

prodotti con metadati 2023
∩ prodotti con recensioni/rating 2023
∩ prodotti con domande/risposte QA storico

Questa scelta è metodologicamente solida perché permette al recommender e al QA system di operare sugli stessi prodotti: il sistema di raccomandazione userà rating, recensioni e interazioni utente-prodotto, mentre il QA userà domande/risposte, recensioni e metadati relativi agli stessi item. Un limite da tenere presente è la possibile sparsità lato utente: ci sono molti utenti rispetto al numero di recensioni, quindi alcuni modelli collaborativi complessi potrebbero essere meno adatti. Tuttavia il dataset è più che sufficiente per baseline, modelli popularity-based, item-item, content-based e una prima estensione QA.