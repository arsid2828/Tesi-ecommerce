# Estensione Chrome demo locale

Questa cartella contiene una piccola estensione Chrome Manifest V3 per il prototipo e-commerce della tesi.

L'estensione non fa scraping di siti reali, non raccoglie dati personali, non salva cronologia utente e comunica solo con il backend e il frontend locali del progetto.

## Cosa fa

- mostra nel popup lo stato del backend locale;
- mostra la URL della tab corrente;
- rileva `item_id` quando la tab e' su `http://localhost:3000/product.html?id=...`;
- carica il dettaglio prodotto con immagine da `GET http://localhost:8000/products/{item_id}`;
- carica 5 raccomandazioni baseline da `GET http://localhost:8000/recommendations/popular?limit=5`;
- se l'endpoint precedente non risponde, prova `GET http://localhost:8000/popular?limit=5`;
- mostra miniature prodotto nelle raccomandazioni quando `image_url` e' disponibile;
- inserisce nella pagina prodotto locale un piccolo box informativo della demo.

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

## Limiti

Questa e' solo una demo locale per il prototipo di tesi. Le raccomandazioni sono baseline non personalizzate, il backend deve essere avviato manualmente e l'estensione riconosce solo la pagina prodotto servita da `localhost:3000`.
