La cartella `notebooks/` contiene il notebook usato per preparare il dataset del prototipo.

---

## `notebooks/01_prepare_prototype_amazon_like_intersection.ipynb`

Questo notebook crea una versione piccola, varia e bilanciata del dataset Amazon-like da usare nel prototipo web.

Interseca tre fonti:

1. metadata Amazon Reviews 2023;
2. QA storico McAuley;
3. rating/reviews Amazon Reviews 2023.

L’obiettivo è ottenere prodotti che abbiano contemporaneamente:

```
metadati prodotto
+
domande/risposte QA
+
rating/recensioni
```

Gli output previsti sono:

```
prototype/data/processed/prototype_amazon_like_intersection/items.parquet
prototype/data/processed/prototype_amazon_like_intersection/qa.parquet
prototype/data/processed/prototype_amazon_like_intersection/ratings.parquet
prototype/data/processed/prototype_amazon_like_intersection/category_summary.csv
prototype/data/processed/prototype_amazon_like_intersection/summary.json
prototype/data/products_demo.json
```

Nel tuo zip questi file non ci sono perché la cartella `data/` è stata rimossa.

### Cosa fa il notebook

Il notebook:

- definisce le categorie da usare nel prototipo;
- imposta limiti bassi per non creare un dataset troppo grande;
- legge o scarica i file QA storici;
- converte il QA storico in formato JSONL più gestibile;
- aggiunge `parent_asin` per collegare QA e metadata;
- carica i metadata Amazon Reviews 2023;
- tiene solo i prodotti che compaiono anche nel QA;
- estrae informazioni prodotto come titolo, categoria, prezzo, rating e immagine;
- salva i prodotti in `items.parquet`;
- filtra le domande/risposte solo sui prodotti presenti nei metadata;
- salva il QA filtrato in `qa.parquet`;
- scansiona le review Amazon Reviews 2023;
- salva solo le interazioni relative ai prodotti selezionati;
- salva i rating in `ratings.parquet`;
- riallinea items e QA ai soli prodotti che hanno anche rating;
- genera un riepilogo per categoria;
- genera `summary.json`;
- esporta `products_demo.json`, usato direttamente dal backend;
- controlla quanti prodotti hanno o non hanno prezzo.

### Scelta metodologica

Questo notebook è utile perché separa la fase dati dalla fase applicativa.

Il sito non deve interrogare direttamente il notebook. Il notebook produce file puliti; il backend legge il JSON demo; il frontend chiama il backend.

### Nota tecnica

Il notebook contiene un percorso assoluto Windows:

```
C:\Users\arsid\Desktop\Tesi-ecommerce
```

Questo va bene sul tuo computer, ma se il progetto viene eseguito altrove bisogna modificare `PROJECT_ROOT`.