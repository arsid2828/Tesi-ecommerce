# Estensione Chrome demo locale

Questa cartella contiene una piccola estensione Chrome Manifest V3 per il prototipo e-commerce della tesi.

L'estensione non raccoglie dati personali, non salva cronologia utente e non interagisce con login, carrello o acquisti. Sul prototipo locale comunica con backend e frontend locali; sulle pagine Amazon reali si limita a riconoscere il prodotto visibile leggendo ASIN, titolo e immagine dalla pagina.

## Cosa fa

- mostra nel popup lo stato del backend locale;
- mostra la URL della tab corrente;
- rileva `item_id` quando la tab e' su `http://localhost:3000/product.html?id=...`;
- carica il dettaglio prodotto con immagine da `GET http://localhost:8000/products/{item_id}`;
- carica 5 raccomandazioni baseline da `GET http://localhost:8000/recommendations/popular?limit=5`;
- se l'endpoint precedente non risponde, prova `GET http://localhost:8000/popular?limit=5`;
- mostra miniature prodotto nelle raccomandazioni quando `image_url` e' disponibile;
- inserisce nella pagina prodotto locale un piccolo box informativo della demo;
- riconosce pagine prodotto Amazon reali su `amazon.it`, `amazon.com`, `amazon.co.uk`, `amazon.de`, `amazon.fr` e `amazon.es`;
- sulle pagine Amazon mostra solo ASIN, titolo e immagine rilevati, senza chiamare il backend.

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
7. aprire il popup dell'estensione e cliccare `Carica prodotto`.

## Test su Amazon reale

1. ricaricare l'estensione da `chrome://extensions`;
2. aprire una pagina prodotto Amazon, per esempio una URL nel formato `https://www.amazon.it/dp/<ASIN>`;
3. verificare che nella pagina compaia il box `Tesi E-commerce Demo`;
4. aprire il popup e controllare che mostri `Prodotto Amazon rilevato` e l'ASIN.

## Limiti

Questa e' una demo per il prototipo di tesi. Le raccomandazioni sono baseline non personalizzate, il backend deve essere avviato manualmente e il collegamento con Amazon reale per ora e' limitato al solo riconoscimento del prodotto.
