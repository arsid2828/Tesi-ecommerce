import argparse
import ast
import json
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd


#radice del progetto usata per risolvere percorsi relativi
PROJECT_ROOT=Path(__file__).resolve().parents[2]

#alias supportati per normalizzare colonne diverse
COLUMN_ALIASES={
    "item_id": ["item_id","parent_asin","asin"],
    "title": ["title","product_title","name"],
    "category": ["category","main_category","categories","source_category"],
    "description": [
        "description",
        "features",
        "details",
        "about_product",
        "description_json",
        "features_json",
        "details_json",
    ],
    "average_rating": ["average_rating","avg_rating","rating","stars"],
    "rating_count": ["rating_count","review_count","ratings_count","count","num_ratings"],
    "image_url": ["image_url","image","main_image","images","large","hi_res"],
}

#pattern per trovare URL immagine nei campi testuali
URL_RE=re.compile(r"https?://[^\s'\"<>]+")


#leggiamo i parametri da riga di comando
def parse_args() -> argparse.Namespace:
    parser=argparse.ArgumentParser(description="Export a small demo catalog for the prototype.")
    parser.add_argument("--input",required=True,help="Input parquet/csv/json/jsonl file.")
    parser.add_argument("--output",default="prototype/data/products_demo.json")
    parser.add_argument("--limit",type=int,default=200)
    return parser.parse_args()


#carichiamo input parquet,csv,json o jsonl
def read_input(path: Path) -> pd.DataFrame:
    suffixes="".join(path.suffixes).lower()
    #input parquet
    if suffixes.endswith(".parquet"):
        return pd.read_parquet(path)
    #input csv anche compresso
    if suffixes.endswith(".csv") or suffixes.endswith(".csv.gz"):
        return pd.read_csv(path)
    #input jsonl anche compresso
    if suffixes.endswith(".jsonl") or suffixes.endswith(".jsonl.gz"):
        return pd.read_json(path,lines=True)
    #input json anche compresso
    if suffixes.endswith(".json") or suffixes.endswith(".json.gz"):
        return pd.read_json(path)
    raise ValueError(f"Unsupported input format: {path}")


#troviamo la prima colonna esistente tra gli alias
def find_column(df: pd.DataFrame,aliases: list[str]) -> str | None:
    normalized={column.lower(): column for column in df.columns}
    #scorriamo gli alias in ordine di preferenza
    for alias in aliases:
        if alias.lower() in normalized:
            return normalized[alias.lower()]
    return None


#convertiamo valori testuali,liste e dizionari in testo leggibile
def clean_text(value: Any,default: str="") -> str:
    #valori mancanti diventano fallback
    if is_missing(value):
        return default
    parsed=parse_nested(value)
    #liste trasformate in frase unica
    if isinstance(parsed,list):
        return " ".join(clean_text(item) for item in parsed if not is_missing(item)).strip()
    #dizionari trasformati in coppie chiave-valore
    if isinstance(parsed,dict):
        parts=[]
        for key,item in parsed.items():
            if isinstance(item,(str,int,float)):
                parts.append(f"{key}: {item}")
        return " ".join(parts).strip()
    text=str(parsed).strip()
    return text if text else default


#normalizziamo la categoria prodotto
def clean_category(value: Any) -> str:
    #categoria mancante
    if is_missing(value):
        return "Uncategorized"
    parsed=parse_nested(value)
    #se e una gerarchia usiamo la categoria piu specifica
    if isinstance(parsed,list) and parsed:
        return clean_text(parsed[-1],default="Uncategorized")
    return clean_text(parsed,default="Uncategorized")


#convertiamo un valore in numero con fallback
def clean_number(value: Any,default: float=0.0) -> float:
    #valore mancante
    if is_missing(value):
        return default
    #conversione numerica protetta
    try:
        number=float(value)
    except (TypeError,ValueError):
        return default
    #escludiamo NaN e infiniti
    if math.isnan(number) or math.isinf(number):
        return default
    return number


#proviamo a interpretare stringhe JSON o literal Python
def parse_nested(value: Any) -> Any:
    #i valori non stringa restano invariati
    if not isinstance(value,str):
        return value
    text=value.strip()
    #stringa vuota
    if not text:
        return text
    #evitiamo parsing su testo normale
    if text[0] not in "[{\"'":
        return value
    #tentiamo parser JSON e literal Python
    for parser in (json.loads,ast.literal_eval):
        try:
            return parser(text)
        except (ValueError,SyntaxError,TypeError,json.JSONDecodeError):
            continue
    return value


#controlliamo valori mancanti in modo robusto
def is_missing(value: Any) -> bool:
    #none e sempre mancante
    if value is None:
        return True
    #pandas gestisce NaN e valori simili
    try:
        return bool(pd.isna(value))
    except (TypeError,ValueError):
        return False


#estraiamo il primo URL immagine valido
def extract_image_url(value: Any) -> str | None:
    #senza valore non abbiamo immagine
    if is_missing(value):
        return None
    parsed=parse_nested(value)
    #stringa con URL diretto
    if isinstance(parsed,str):
        match=URL_RE.search(parsed)
        return match.group(0) if match else None
    #dizionario con possibili chiavi immagine
    if isinstance(parsed,dict):
        for key in ("large","hi_res","image_url","main_image","url"):
            if key in parsed:
                url=extract_image_url(parsed[key])
                if url:
                    return url
        for item in parsed.values():
            url=extract_image_url(item)
            if url:
                return url
    #lista di immagini o oggetti immagine
    if isinstance(parsed,list):
        for item in parsed:
            url=extract_image_url(item)
            if url:
                return url
    return None


#normalizziamo tutte le righe nel formato prodotto demo
def normalize_rows(df: pd.DataFrame) -> pd.DataFrame:
    columns={field: find_column(df,aliases) for field,aliases in COLUMN_ALIASES.items()}
    #item id e titolo sono campi minimi obbligatori
    if columns["item_id"] is None or columns["title"] is None:
        raise ValueError("Input must contain at least item_id/parent_asin/asin and title/name.")

    rows=[]
    #convertiamo ogni riga valida in record prodotto
    for _,row in df.iterrows():
        title=clean_text(row[columns["title"]])
        #scartiamo prodotti senza titolo
        if not title:
            continue

        rating_count=int(clean_number(row[columns["rating_count"]],0)) if columns["rating_count"] else 0
        average_rating=(
            round(clean_number(row[columns["average_rating"]],0),2)
            if columns["average_rating"]
            else 0.0
        )

        #aggiungiamo il prodotto normalizzato
        rows.append(
            {
                "item_id": clean_text(row[columns["item_id"]]),
                "title": title,
                "category": clean_category(row[columns["category"]]) if columns["category"] else "Uncategorized",
                "description": clean_text(row[columns["description"]],default=title)
                if columns["description"]
                else title,
                "average_rating": average_rating,
                "rating_count": rating_count,
                "image_url": extract_image_url(row[columns["image_url"]]) if columns["image_url"] else None,
            }
        )

    #evitiamo duplicati sullo stesso item_id
    normalized=pd.DataFrame(rows).drop_duplicates(subset=["item_id"])
    return normalized


#calcoliamo la baseline di popolarita
def add_popularity_score(df: pd.DataFrame) -> pd.DataFrame:
    df=df.copy()
    max_count=df["rating_count"].max() if "rating_count" in df else 0
    #caso principale: rating_count normalizzato
    if max_count and max_count > 0:
        df["popularity_score"]=(df["rating_count"] / max_count).round(4)
    #fallback: rating medio normalizzato
    elif "average_rating" in df and df["average_rating"].max() > 0:
        df["popularity_score"]=(df["average_rating"] / 5.0).clip(0,1).round(4)
    #fallback finale: nessuna popolarita disponibile
    else:
        df["popularity_score"]=0.0
    return df


#selezioniamo un catalogo piccolo e bilanciato
def select_balanced_catalog(df: pd.DataFrame,limit: int) -> pd.DataFrame:
    #ordiniamo prima i prodotti piu recensiti
    df=df.sort_values(
        by=["rating_count","popularity_score"],
        ascending=[False,False],
    )

    #usiamo al massimo otto categorie principali
    categories=df["category"].value_counts().head(8).index.tolist()
    selected_frames=[]
    per_category=max(1,math.ceil(limit / max(1,len(categories))))

    #prendiamo un numero simile di prodotti per categoria
    for category in categories:
        category_rows=df[df["category"] == category].head(per_category)
        selected_frames.append(category_rows)

    selected=pd.concat(selected_frames,ignore_index=True) if selected_frames else df.head(0)
    #completiamo il limite se alcune categorie hanno pochi prodotti
    if len(selected) < limit:
        missing=limit - len(selected)
        extra=df[~df["item_id"].isin(selected["item_id"])].head(missing)
        selected=pd.concat([selected,extra],ignore_index=True)

    return selected.head(limit).sort_values("popularity_score",ascending=False)


#esportiamo il catalogo finale su JSON
def export_catalog(input_path: Path,output_path: Path,limit: int) -> pd.DataFrame:
    #carichiamo e normalizziamo i dati
    df=read_input(input_path)
    normalized=add_popularity_score(normalize_rows(df))
    selected=select_balanced_catalog(normalized,min(limit,200))

    #prepariamo cartella output e record finali
    output_path.parent.mkdir(parents=True,exist_ok=True)
    records=selected[
        [
            "item_id",
            "title",
            "category",
            "description",
            "average_rating",
            "rating_count",
            "popularity_score",
            "image_url",
        ]
    ].to_dict(orient="records")

    #scriviamo il JSON demo
    output_path.write_text(
        json.dumps(records,ensure_ascii=False,indent=2),
        encoding="utf-8",
    )
    return selected


#stampiamo statistiche finali dell'export
def print_stats(df: pd.DataFrame,output_path: Path) -> None:
    print(f"Saved: {output_path}")
    print(f"Products: {len(df)}")
    print(f"Categories: {df['category'].nunique()}")
    print(f"With images: {int(df['image_url'].notna().sum())}")
    print("Top categories:")
    #mostriamo distribuzione categorie
    for category,count in df["category"].value_counts().items():
        print(f"  - {category}: {count}")


#punto di ingresso dello script
def main() -> None:
    args=parse_args()
    input_path=(PROJECT_ROOT / args.input).resolve()
    output_path=(PROJECT_ROOT / args.output).resolve()

    #verifichiamo che il file input esista
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    #eseguiamo export e riepilogo
    selected=export_catalog(input_path,output_path,args.limit)
    print_stats(selected,output_path)


#avviamo lo script solo da riga di comando
if __name__ == "__main__":
    main()
