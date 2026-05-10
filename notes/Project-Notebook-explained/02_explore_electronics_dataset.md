## Prime celle del notebook02:
I controlli iniziali mostrano che il dataset Electronics è coerente: tutti i prodotti presenti nei rating e nelle domande/risposte sono contenuti nella tabella dei metadati, e le colonne principali non presentano valori nulli. La distribuzione dei rating è fortemente sbilanciata verso valutazioni positive, come spesso accade nei dataset di recensioni e-commerce. È stata inoltre rilevata una piccola quota di duplicati per coppia utente-prodotto, che verrà gestita mantenendo una sola interazione per ciascuna coppia user_id-parent_asin. Le analisi successive useranno quindi una versione pulita dei rating.

- Struttura dei file: ottima
- Coerenza tra items, ratings e QA: ottima
- Valori nulli: ottimo
- Rating validi: ottimo
- Distribuzione rating: normale ma sbilanciata verso 5 stelle
- Timestamp: utile per split temporale
- Duplicati: presenti, non gravi, ma da gestire
- Sparsità utenti: probabilmente molto alta

Il dataset contiene interazioni distribuite su un ampio arco temporale, con una forte concentrazione tra 2013 e 2016. Questo aspetto va considerato nella fase di valutazione, perché in un dominio come Electronics la rilevanza dei prodotti può cambiare nel tempo.

## Cella 8:

La distribuzione delle interazioni per utente mostra una forte sparsità: la mediana è pari a 1 e il 75% degli utenti ha una sola interazione. Questo rende difficile costruire raccomandazioni personalizzate per la maggior parte degli utenti senza applicare filtri. Nelle celle successive verranno quindi confrontate diverse soglie minime di interazioni per utente.

La soglia utenti >= 3 interazioni sembra la candidata migliore, perché consente uno split train/validation/test per utente mantenendo comunque oltre 200.000 utenti. Soglie più alte, come >=5 o >=10, riducono molto il numero di utenti e rischiano di rendere il dataset meno rappresentativo. 
La soglia sugli utenti ha un impatto molto forte: la maggior parte degli utenti ha poche interazioni. Tuttavia, imponendo almeno 3 interazioni per utente rimangono ancora 206.190 utenti, 22.115 prodotti e 889.471 interazioni, pari al 25,8% delle interazioni totali. Questa soglia appare adatta per costruire successivamente uno split train/validation/test per utente, ma dovrà essere valutata insieme a una soglia minima sul numero di interazioni per prodotto.

## Cella 9:
A differenza degli utenti, i prodotti risultano mediamente più rappresentati: la mediana è pari a 52 interazioni per prodotto e il 75% dei prodotti ha al massimo 137 interazioni. La distribuzione resta comunque sbilanciata, con pochi prodotti molto popolari che raggiungono migliaia di interazioni. Questo suggerisce che un filtro minimo sui prodotti può essere applicato, ma non deve essere troppo aggressivo per non ridurre inutilmente il catalogo.