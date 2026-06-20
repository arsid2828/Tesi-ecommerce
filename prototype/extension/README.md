# Estensione Chrome demo locale

Questa cartella contiene una piccola estensione Chrome Manifest V3 per il prototipo e-commerce della tesi.

L'estensione non raccoglie dati personali, non salva cronologia utente e non interagisce con login, carrello o acquisti. Sul prototipo locale comunica con backend e frontend locali; sulle pagine Amazon reali si limita a riconoscere il prodotto visibile leggendo ASIN, titolo e immagine dalla pagina.

## Cosa fa

- mostra nel popup lo stato del backend locale;
- mostra la URL della tab corrente;
- rileva `item_id` quando la tab e' su `http://localhost:3000/product.html?id=...`;
- carica il dettaglio prodotto con immagine da `GET http://localhost:8000/products/{item_id}`;
- su pagine prodotto locali carica gruppi contestuali da `GET http://localhost:8000/recommendations/contextual/{item_id}`;
- mostra prodotti simili, scelte alternative e prodotti da acquistare assieme, tutti presi solo dal dataset locale;
- apre la pagina prodotto locale quando si clicca un consiglio;
- usa Gemini solo dal backend per rifinire label e motivazioni, senza permettere all'AI di scegliere o inventare prodotti;
- inserisce nella pagina prodotto locale un box con gli stessi consigli cliccabili;
- riconosce pagine prodotto Amazon reali su `amazon.it`, `amazon.com`, `amazon.co.uk`, `amazon.de`, `amazon.fr` e `amazon.es`;
- sulle pagine Amazon legge prodotti reali gia' visibili nel DOM della pagina, li organizza in gruppi e li rende cliccabili;
- se il backend e Gemini non sono disponibili, su Amazon mostra comunque un fallback con candidati reali letti dalla pagina.

## Avvio demo

Dal repository:

```bash
python -m uvicorn prototype.backend.app:app --port 8000
```

In un secondo terminale:

```bash
python -m http.server 3000 -d prototype/frontend
```

Poi:

1. aprire Chrome;
2. andare su `chrome://extensions`;
3. attivare `Developer mode`;
4. cliccare `Load unpacked`;
5. selezionare `prototype/extension/`;
6. aprire una pagina prodotto locale, per esempio `http://localhost:3000/product.html?id=<item_id>`;
7. aprire il popup dell'estensione: i consigli contestuali vengono caricati automaticamente.

## Test su Amazon reale

1. ricaricare l'estensione da `chrome://extensions`;
2. aprire una pagina prodotto Amazon, per esempio una URL nel formato `https://www.amazon.it/dp/<ASIN>`;
3. verificare che nella pagina compaia il box `Tesi E-commerce Demo`;
4. aprire il popup e controllare che mostri `Prodotto Amazon rilevato`, l'ASIN e, se la pagina contiene card correlate leggibili, consigli reali cliccabili.

## Limiti

Questa e' una demo per il prototipo di tesi. Il backend deve essere avviato manualmente e il catalogo locale deve esistere in `prototype/data/products_demo.json`.

Su Amazon reale l'estensione non fa crawling e non inventa risultati con Gemini. Prende solo link prodotto gia' presenti nella pagina corrente. Per cercare prodotti Amazon fuori dalla pagina servirebbe integrare nel backend una sorgente esterna esplicita, per esempio una API ufficiale/partner o un motore di ricerca con grounding, mantenendo Gemini come organizzatore e non come fonte non verificata.
