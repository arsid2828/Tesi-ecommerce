I dati principali del prototipo si trovano nella cartella:

`prototype/data/`

Il file usato dal sito è:

`prototype/data/products_demo.json`

Attualmente il catalogo contiene 491 prodotti.

Ogni prodotto segue una struttura simile:

```
{
  "item_id": "...",
  "title": "...",
  "category": "...",
  "description": "...",
  "average_rating": 4.3,
  "rating_count": 120,
  "popularity_score": 0.87,
  "image_url": "https://..."
}
```

Il dataset demo contiene:

- categorie coerenti con il prototipo;
- immagini prodotto disponibili;
- valori puliti, senza `NaN`;
- campi utili per ricerca, visualizzazione e ordinamento per popolarità.

È stato inoltre creato il notebook:

`prototype/notebooks/01_prepare_prototype_amazon_like_intersection.ipynb`

Il notebook è una versione ridotta del Notebook 01 AmazonLike e serve a creare un dataset prototipo partendo da:

- metadata Amazon Reviews 2023;
- QA storico McAuley;
- rating/reviews Amazon Reviews 2023.

Gli output previsti includono:

- `items.parquet`;
- `qa.parquet`;
- `ratings.parquet`;
- `category_summary.csv`;
- `summary.json`;
- `products_demo.json`.

È stato corretto anche un problema sui percorsi: il notebook ora usa una root assoluta:

`PROJECT_ROOT = Path(r"C:\Users\arsid\Desktop\Tesi-ecommerce")`

In questo modo non crea più cartelle sbagliate dentro `prototype/notebooks/prototype/data`.

Sono state inoltre sistemate le categorie: il prototipo non usa più categorie grezze come `AMAZON FASHION` o `Premium Beauty`, ma categorie più coerenti tramite `source_category`.

Anche l’estrazione delle immagini è stata migliorata, recuperando URL da campi come `hi_res`, `large` e `thumb`.