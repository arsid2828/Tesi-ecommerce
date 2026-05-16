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

## Cella 10:
soglie di qa: per prodotti, righe qa e rating
- 1 tutti
- 2 tieni 99%
- 3 sempre sopra 99%
- 4 91% prodotti, 96% righe, 97% rating
- 10 49% prodotti, 63% righe, 79% rating
- 20 rimane solo circa 0%
L’analisi mostra che quasi tutti i prodotti dispongono di almeno 3 righe QA. Una soglia pari a 4 mantiene ancora oltre il 91% dei prodotti e quasi il 98% delle interazioni rating. Soglie più alte, come 10 o 20, riducono sensibilmente il catalogo e non sono adatte come filtro principale per il recommender. Il QA verrà quindi considerato soprattutto come informazione aggiuntiva per il prototipo e come possibile base per un’estensione futura di Question Answering.