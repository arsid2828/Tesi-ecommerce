La cartella `scripts/` contiene script Python riutilizzabili fuori dai notebook.

---

## `scripts/export_demo_catalog.py`

Questo script serve a generare un catalogo demo in formato JSON partendo da un file di input.

Supporta diversi formati:

- Parquet;
- CSV;
- JSON;
- JSONL.

Lo script può essere avviato da terminale, ad esempio:

```
python prototype/scripts/export_demo_catalog.py --input data/processed/test_dataset2_intersection/items.parquet --output prototype/data/products_demo.json --limit 200
```

### Cosa fa lo script

Lo script:

- legge il file di input;
- riconosce colonne anche se hanno nomi diversi;
- normalizza `item_id`, titolo, categoria, descrizione, prezzo, rating, numero recensioni e immagine;
- converte liste e dizionari in testo leggibile;
- estrae il primo URL immagine disponibile;
- elimina duplicati sullo stesso `item_id`;
- calcola `popularity_score`;
- seleziona un catalogo bilanciato tra categorie;
- salva il risultato in `products_demo.json`;
- stampa statistiche finali.

### Alias colonne

Lo script è flessibile perché accetta nomi diversi per le stesse informazioni.

Ad esempio, per l’id prodotto può usare:

```
item_id
parent_asin
asin
```

Per il titolo può usare:

```
title
product_title
name
```

Per il numero recensioni può usare:

```
rating_count
review_count
ratings_count
count
num_ratings
```

Questa flessibilità è utile perché i dataset Amazon possono avere colonne con nomi diversi a seconda della fase di preprocessing.

### Popolarità

Lo script calcola:

```
popularity_score = rating_count normalizzato
```

Se `rating_count` non è disponibile, usa il rating medio come fallback. Se non c’è nemmeno quello, assegna popolarità zero.

### Bilanciamento categorie

Lo script prova a non prendere prodotti solo dalla categoria dominante. Prende al massimo le categorie principali e seleziona un numero simile di prodotti da ciascuna.

Attualmente lo script limita il catalogo esportato a massimo 200 prodotti tramite:

```
min(limit,200)
```

Quindi, se in futuro si vogliono esportare più di 200 prodotti con questo script, bisogna modificare quella parte.

---