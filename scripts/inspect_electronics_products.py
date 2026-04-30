# ============================================================
# INSPECT ELECTRONICS PRODUCTS
#
# Obiettivo:
# capire che prodotti ci sono nel sottoinsieme finale Electronics,
# cioè prodotti con:
# - QA storico
# - metadata Amazon Reviews 2023
# - rating/review Amazon Reviews 2023
#
# Input richiesti:
# data/processed/amazon_category_tests/Electronics/
# ├── valid_asins_Electronics_QA_Electronics.txt
# └── rating_counts_Electronics_QA_Electronics.csv
#
# Output prodotti:
# data/processed/amazon_category_tests/Electronics/inspection/
# ├── electronics_items_final.csv
# ├── electronics_items_summary.csv
# ├── electronics_leaf_categories.csv
# ├── electronics_top_products_by_ratings.csv
# ├── electronics_random_sample.csv
# └── electronics_quality_report.csv
# ============================================================

import ast
import json
from pathlib import Path

import pandas as pd
from tqdm import tqdm
from huggingface_hub import hf_hub_download


# ============================================================
# 1. CONFIGURAZIONE
# ============================================================

HF_REPO = "McAuley-Lab/Amazon-Reviews-2023"

CATEGORY = "Electronics"
QA_SLUG = "Electronics"

BASE_DIR = Path(".")
CATEGORY_DIR = BASE_DIR / "data" / "processed" / "amazon_category_tests" / CATEGORY
OUTPUT_DIR = CATEGORY_DIR / "inspection"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VALID_ASINS_PATH = CATEGORY_DIR / f"valid_asins_{CATEGORY}_QA_{QA_SLUG}.txt"
RATING_COUNTS_PATH = CATEGORY_DIR / f"rating_counts_{CATEGORY}_QA_{QA_SLUG}.csv"

METADATA_FILE = f"raw/meta_categories/meta_{CATEGORY}.jsonl"


# ============================================================
# 2. FUNZIONI UTILI
# ============================================================

def safe_parse_line(line):
    """
    Legge una riga JSON/JSON-like.
    Alcuni dataset Amazon usano formati non perfettamente standard,
    quindi usiamo json.loads e fallback ast.literal_eval.
    """
    line = line.strip()

    if not line:
        return None

    try:
        return json.loads(line)
    except Exception:
        return ast.literal_eval(line)


def load_valid_asins(path):
    """
    Carica gli ASIN finali della categoria.
    Questi sono i prodotti che hanno QA + metadata + rating.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"File ASIN finali non trovato: {path}\n"
            "Devi prima eseguire lo script di intersezione."
        )

    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def flatten_list(value):
    """
    Appiattisce liste annidate.
    Serve per gestire il campo categories.
    """
    result = []

    def _flatten(x):
        if isinstance(x, list):
            for item in x:
                _flatten(item)
        else:
            result.append(x)

    _flatten(value)
    return result


def extract_leaf_category(categories):
    """
    Estrae una categoria finale leggibile dal campo categories.

    Esempio:
    ['Electronics', 'Headphones', 'Earbud Headphones']
    -> 'Earbud Headphones'
    """
    if isinstance(categories, list) and len(categories) > 0:
        flat = flatten_list(categories)
        flat = [x for x in flat if isinstance(x, str) and x.strip()]

        if flat:
            return flat[-1]

    return None


def extract_category_path(categories):
    """
    Restituisce il percorso categoria come stringa leggibile.
    """
    if isinstance(categories, list) and len(categories) > 0:
        flat = flatten_list(categories)
        flat = [x for x in flat if isinstance(x, str) and x.strip()]

        if flat:
            return " > ".join(flat)

    return None


def get_main_image(images):
    """
    Estrae una immagine principale dal campo images.
    Nei metadata 2023, images è spesso una lista di dizionari:
    [{'hi_res': ..., 'large': ..., 'thumb': ..., 'variant': ...}]
    """
    if isinstance(images, list) and len(images) > 0:
        for image in images:
            if isinstance(image, dict):
                return (
                    image.get("hi_res")
                    or image.get("large")
                    or image.get("thumb")
                )

    if isinstance(images, dict):
        return (
            images.get("hi_res")
            or images.get("large")
            or images.get("thumb")
        )

    return None


def has_non_empty_text(value):
    """
    Controlla se un campo testuale/lista è valorizzato.
    """
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    if isinstance(value, list):
        return len(value) > 0

    return True


def download_metadata_file():
    """
    Scarica/recupera da cache il file metadata Electronics da Hugging Face.
    """
    print(f"Scarico/recupero metadata da Hugging Face: {METADATA_FILE}")

    return hf_hub_download(
        repo_id=HF_REPO,
        repo_type="dataset",
        filename=METADATA_FILE,
    )


def filter_metadata_by_asins(metadata_path, valid_asins):
    """
    Legge il metadata JSONL completo di Electronics e tiene solo
    i prodotti presenti nel catalogo finale.
    """
    rows = []

    with open(metadata_path, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc="Filtro metadata Electronics"):
            row = safe_parse_line(line)

            if row is None:
                continue

            asin = row.get("parent_asin")

            if asin in valid_asins:
                rows.append(row)

    return pd.DataFrame(rows)


# ============================================================
# 3. MAIN
# ============================================================

def main():
    print("=" * 80)
    print("INSPEZIONE PRODOTTI ELECTRONICS")
    print("=" * 80)

    # ------------------------------------------------------------
    # A. Carica ASIN finali
    # ------------------------------------------------------------

    valid_asins = load_valid_asins(VALID_ASINS_PATH)

    print(f"Prodotti finali attesi: {len(valid_asins):,}")

    # ------------------------------------------------------------
    # B. Scarica metadata Amazon Reviews 2023
    # ------------------------------------------------------------

    metadata_path = download_metadata_file()

    # ------------------------------------------------------------
    # C. Filtra metadata sui prodotti finali
    # ------------------------------------------------------------

    items = filter_metadata_by_asins(metadata_path, valid_asins)

    print(f"Prodotti trovati nei metadata filtrati: {len(items):,}")

    if items.empty:
        raise RuntimeError("Nessun prodotto trovato. Controlla gli ASIN finali.")

    # ------------------------------------------------------------
    # D. Arricchisci tabella prodotti
    # ------------------------------------------------------------

    items["leaf_category"] = items["categories"].apply(extract_leaf_category)
    items["category_path"] = items["categories"].apply(extract_category_path)
    items["main_image_url"] = items["images"].apply(get_main_image)

    # ------------------------------------------------------------
    # E. Unisci conteggi rating
    # ------------------------------------------------------------

    if not RATING_COUNTS_PATH.exists():
        raise FileNotFoundError(
            f"File conteggi rating non trovato: {RATING_COUNTS_PATH}"
        )

    rating_counts = pd.read_csv(RATING_COUNTS_PATH)

    items = items.merge(
        rating_counts,
        on="parent_asin",
        how="left"
    )

    items["n_ratings"] = items["n_ratings"].fillna(0).astype(int)

    # ------------------------------------------------------------
    # F. Report qualità metadata
    # ------------------------------------------------------------

    quality_report = {
        "n_products": len(items),
        "with_title": int(items["title"].apply(has_non_empty_text).sum()) if "title" in items else 0,
        "with_description": int(items["description"].apply(has_non_empty_text).sum()) if "description" in items else 0,
        "with_features": int(items["features"].apply(has_non_empty_text).sum()) if "features" in items else 0,
        "with_price": int(items["price"].notna().sum()) if "price" in items else 0,
        "with_images": int(items["main_image_url"].notna().sum()),
        "with_leaf_category": int(items["leaf_category"].notna().sum()),
        "avg_ratings_per_product": float(items["n_ratings"].mean()),
        "median_ratings_per_product": float(items["n_ratings"].median()),
        "max_ratings_per_product": int(items["n_ratings"].max()),
    }

    quality_df = pd.DataFrame([quality_report])

    # ------------------------------------------------------------
    # G. Tabelle utili
    # ------------------------------------------------------------

    summary_cols = [
        "parent_asin",
        "title",
        "store",
        "main_category",
        "leaf_category",
        "category_path",
        "average_rating",
        "rating_number",
        "n_ratings",
        "price",
        "main_image_url",
    ]

    summary_cols = [c for c in summary_cols if c in items.columns]

    items_summary = items[summary_cols].copy()

    leaf_categories = (
        items["leaf_category"]
        .value_counts(dropna=False)
        .reset_index()
    )

    leaf_categories.columns = ["leaf_category", "n_products"]

    top_products = (
        items_summary
        .sort_values("n_ratings", ascending=False)
        .head(100)
    )

    random_sample = items_summary.sample(
        n=min(100, len(items_summary)),
        random_state=42
    )

    # ------------------------------------------------------------
    # H. Salvataggio
    # ------------------------------------------------------------

    items_path = OUTPUT_DIR / "electronics_items_final.csv"
    summary_path = OUTPUT_DIR / "electronics_items_summary.csv"
    leaf_categories_path = OUTPUT_DIR / "electronics_leaf_categories.csv"
    top_products_path = OUTPUT_DIR / "electronics_top_products_by_ratings.csv"
    sample_path = OUTPUT_DIR / "electronics_random_sample.csv"
    quality_path = OUTPUT_DIR / "electronics_quality_report.csv"

    items.to_csv(items_path, index=False)
    items_summary.to_csv(summary_path, index=False)
    leaf_categories.to_csv(leaf_categories_path, index=False)
    top_products.to_csv(top_products_path, index=False)
    random_sample.to_csv(sample_path, index=False)
    quality_df.to_csv(quality_path, index=False)

    # ------------------------------------------------------------
    # I. Output a schermo
    # ------------------------------------------------------------

    print("\n" + "=" * 80)
    print("REPORT QUALITÀ")
    print("=" * 80)
    print(quality_df.to_string(index=False))

    print("\n" + "=" * 80)
    print("TOP 30 SOTTOCATEGORIE")
    print("=" * 80)
    print(leaf_categories.head(30).to_string(index=False))

    print("\n" + "=" * 80)
    print("TOP 30 PRODOTTI PER NUMERO DI RATING")
    print("=" * 80)

    display_cols = [
        "parent_asin",
        "title",
        "store",
        "leaf_category",
        "average_rating",
        "rating_number",
        "n_ratings",
        "price",
    ]

    display_cols = [c for c in display_cols if c in top_products.columns]

    print(top_products[display_cols].head(30).to_string(index=False))

    print("\n" + "=" * 80)
    print("FILE SALVATI")
    print("=" * 80)
    print(f"Prodotti completi:       {items_path}")
    print(f"Prodotti summary:        {summary_path}")
    print(f"Sottocategorie:          {leaf_categories_path}")
    print(f"Top prodotti:            {top_products_path}")
    print(f"Sample casuale:          {sample_path}")
    print(f"Quality report:          {quality_path}")


if __name__ == "__main__":
    main()