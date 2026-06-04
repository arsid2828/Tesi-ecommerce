# Roadmap prototipo product discovery e-commerce

## Obiettivo attuale

Il lavoro sui notebook di analisi e valutazione dei modelli può fermarsi temporaneamente. La nuova fase consiste nel trasformare i dati e i risultati ottenuti in un prototipo applicativo minimale, utile per testare funzionalità di ricerca, raccomandazione e, in seguito, AI conversazionale.

L’obiettivo non è costruire un clone completo di Amazon, ma un prototipo controllato di e-commerce basato su dataset Amazon-like.

## Idea centrale

Costruire un sito e-commerce minimale che permetta di:

1. visualizzare prodotti del dataset;
2. cercare prodotti tramite barra di ricerca;
3. ordinare i risultati inizialmente per popolarità;
4. aprire una pagina dettaglio prodotto;
5. mostrare raccomandazioni baseline basate su popolarità;
6. preparare la struttura per aggiungere in futuro ricerca semantica, clustering, AI esterna, chatbot e possibile estensione browser.

## Principio metodologico

La prima versione deve essere semplice, funzionante e verificabile.

Non bisogna iniziare subito da chatbot, API AI o estensione Chrome. Prima serve una base stabile:

- dati esportati in formato adatto al sito;
- backend funzionante;
- frontend minimale;
- ricerca testuale base;
- raccomandazioni popularity baseline.

Solo dopo si valuta cosa aggiungere.

## Struttura consigliata del progetto

Le cartelle principali sono:

- `notebooks/`: esperimenti, analisi, training e valutazione;
- `data/`: dati grezzi, processati e dati demo;
- `scripts/`: script eseguibili, ad esempio export del catalogo demo;
- `src/`: codice riutilizzabile tra notebook e backend;
- `backend/`: API FastAPI del prototipo;
- `frontend/`: sito web minimale;
- `extension/`: eventuale estensione Chrome futura;
- `notes/`: appunti, roadmap e documentazione per la tesi.

Il sito non deve dipendere direttamente dai notebook. I notebook producono file esportati; il backend legge quei file; il frontend comunica con il backend.

## Fase 1 — Export del dataset demo

Creare uno script che prepari un sottoinsieme del dataset Amazon-like per il prototipo.

Output previsto:

```text
data/demo/products_demo.json