## Commenti finali

Il Notebook 02 ha permesso di analizzare il dataset Electronics costruito nel Notebook 01, verificando la qualità dei dati, la copertura dei prodotti e la distribuzione delle interazioni utente-prodotto.

I controlli iniziali mostrano che il dataset è coerente: tutti i prodotti presenti nei rating e nelle domande/risposte QA sono presenti anche nei metadati, le colonne principali non presentano valori nulli e i rating sono tutti validi. È stata inoltre rimossa una piccola quota di duplicati sulle coppie `user_id` + `parent_asin`, mantenendo una sola interazione per coppia utente-prodotto.

L’analisi ha evidenziato una forte sparsità lato utenti: molti utenti hanno una sola interazione, rendendo necessario applicare una soglia minima per poter costruire uno split temporale train/validation/test. Al contrario, i prodotti risultano mediamente più rappresentati, quindi il filtro sui prodotti può essere usato come pulizia leggera per rimuovere item con pochissimo segnale collaborativo.

Dopo il confronto tra diverse configurazioni di filtro, è stata scelta provvisoriamente la configurazione `user3_item8`, che mantiene:

- 196.509 utenti;
- 15.069 prodotti;
- 844.060 interazioni.

Questa configurazione rappresenta un compromesso tra ampiezza del dataset e qualità del segnale: ogni utente ha almeno 3 interazioni, quindi è possibile costruire uno split train/validation/test, e ogni prodotto ha almeno 8 interazioni, riducendo i prodotti con supporto troppo debole.

Il QA non è stato usato come filtro principale, perché il sistema di raccomandazione si baserà inizialmente sui rating/interazioni. Tuttavia, la presenza di domande e risposte rimane utile per il prototipo e per una possibile estensione futura verso un sistema di Question Answering sui prodotti.

Il Notebook 03 partirà quindi dalla configurazione scelta per costruire i dataset di train, validation e test e per iniziare il confronto tra baseline semplici e primi modelli di raccomandazione.