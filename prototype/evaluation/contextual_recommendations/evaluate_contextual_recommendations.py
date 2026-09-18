"""Valuta otto prodotti congelati prima delle chiamate alla vera pagina prodotto.

Eseguire dalla root con .venv/Scripts/python.exe e il percorso di questo file.
--output permette una nuova cartella senza sovrascrivere valutazioni precedenti.
"""

import argparse
import csv
import hashlib
import json
import logging
import math
import sys
import time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import quote


ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
CATEGORIES=["Electronics","Office Products","Tools and Home Improvement",
            "Home and Kitchen","Automotive","Sports and Outdoors",
            "Patio Lawn and Garden","Toys and Games"]
FIELDS=["ID","Item_id","Prodotto","Categoria","Famiglia","N_simili_alternative",
        "N_utili_insieme","Prodotti_mostrati","Fallback","Nome_gruppo_simili",
        "Nome_gruppo_complementari"]
REVIEW_FIELDS=["ID_test","Prodotto_partenza","Item_id_partenza","Gruppo",
               "Item_id_raccomandato","Titolo_raccomandato","Categoria_raccomandato",
               "Prezzo_raccomandato","Posizione_nel_gruppo"]


def digest(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file,"sha256").hexdigest()


def finite(value) -> bool:
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def write_csv(path: Path,rows: list[dict],fields: list[str]) -> None:
    with path.open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path,data) -> None:
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")


class ServiceLog(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages=[]

    def emit(self,record):
        self.messages.append(record.getMessage())


def select_products(products,raw_rows):
    # Nessuna raccomandazione o filtro sulla famiglia durante la selezione.
    id_counts=Counter(product.item_id for product in products)
    valid=[product for product in products if product.item_id.strip()
           and id_counts[product.item_id]==1 and product.title.strip()
           and product.category.strip() and finite(product.price) and product.price>0]
    raw_by_id={row["item_id"]:row for row in raw_rows}
    counts=Counter(product.category for product in valid)
    used=set()
    selected=[]
    for index,requested in enumerate(CATEGORIES,1):
        category=requested
        reason=""
        if not counts[category]:
            alternatives=[name for name in counts if name not in used and name not in CATEGORIES]
            if not alternatives:
                raise RuntimeError(f"Nessuna categoria sostitutiva disponibile per {requested}")
            category=sorted(alternatives,key=lambda name:(-counts[name],name))[0]
            reason=f"{requested}: nessun prodotto valido; scelta la categoria alternativa più rappresentata."
        used.add(category)
        pool=[product for product in valid if product.category==category]
        score_key="popularity_score"
        ranked=[product for product in pool if finite(raw_by_id[product.item_id].get(score_key))]
        if not ranked:
            score_key="rating_count"
            ranked=[product for product in pool if finite(raw_by_id[product.item_id].get(score_key))]
        if ranked:
            source=min(ranked,key=lambda product:(-raw_by_id[product.item_id][score_key],product.item_id))
            rule=f"Massimo {score_key}; parità risolta con item_id crescente"
        else:
            source=min(pool,key=lambda product:product.item_id)
            score_key="item_id"
            rule="item_id crescente: popularity_score e rating_count non disponibili"
        selected.append({"ID_test":f"R{index:02d}","item_id":source.item_id,
                         "titolo":source.title,"categoria":source.category,"prezzo":source.price,
                         "popularity_score":raw_by_id[source.item_id].get("popularity_score"),
                         "criterio_selezione":rule,"valore_selezione":raw_by_id[source.item_id].get(score_key),
                         "categoria_richiesta":requested,"motivo_sostituzione_categoria":reason,
                         "prodotti_validi_categoria":len(pool)})
    return selected


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    if any(path for path in output.iterdir() if path.name not in {Path(__file__).name,"README.md","__pycache__"}):
        parser.error("Output già presenti: usare --output con una nuova cartella.")

    from fastapi.testclient import TestClient
    from prototype.backend.app import app,catalog,DATA_PATH
    from prototype.backend.services import recommendation_service as service

    protected=[DATA_PATH]
    for directory in (ROOT/"prototype/backend",ROOT/"prototype/frontend",ROOT/"prototype/scripts",
                      ROOT/"prototype/evaluation/cluster_search"):
        protected.extend(path for path in directory.rglob("*")
                         if path.is_file() and "__pycache__" not in path.parts)
    fingerprints={path:digest(path) for path in protected}
    products=catalog.all_products()
    selected=select_products(products,json.loads(DATA_PATH.read_text(encoding="utf-8")))
    manifest={"created_at":datetime.now(timezone.utc).isoformat(),
              "selection_before_recommendations":True,
              "selection_rule":"Massimo popularity_score disponibile nella categoria; altrimenti rating_count, altrimenti item_id crescente. Parità: item_id crescente.",
              "eligibility":"Catalogo caricato dal servizio reale; item_id non vuoto e univoco, titolo e categoria non vuoti, prezzo finito positivo. Nessun requisito di famiglia riconosciuta o numero di raccomandazioni.",
              "catalog_sha256":fingerprints[DATA_PATH],
              "endpoint":"GET /recommendations/contextual/{item_id}?limit=4&use_ai_support=false",
              "transport":"FastAPI TestClient, app reale in-process",
              "fallback_column":"Flag fallback della risposta finale; eventuali warning di ripiego TF-IDF sono conservati nella diagnostica.",
              "tests":selected}
    manifest_path=output/"test_manifest.json"
    write_json(manifest_path,manifest)
    manifest_hash=digest(manifest_path)
    print("Manifest congelato prima delle raccomandazioni:",flush=True)
    for test in selected:
        print(json.dumps(test,ensure_ascii=True),flush=True)

    raw=output/"raw"
    raw.mkdir()
    rows=[]
    review=[]
    diagnostics=[]
    capture=ServiceLog()
    service.logger.addHandler(capture)
    try:
        with TestClient(app,raise_server_exceptions=False) as client:
            for test in selected:
                tid=test["ID_test"]
                row=dict.fromkeys(FIELDS,"")
                row.update(ID=tid,Item_id=test["item_id"],Prodotto=test["titolo"],Categoria=test["categoria"])
                source=catalog.get_product(test["item_id"])
                row["Famiglia"]=service._product_family(source) or ""
                capture.messages.clear()
                diagnostic={"ID":tid,"HTTP_status":"","Errore":"","Avvisi":"",
                            "Fallback_risposta":"","Used_ai_support":"",
                            "TFIDF_disponibile":service.TfidfVectorizer is not None and service.cosine_similarity is not None,
                            "Started_at":datetime.now(timezone.utc).isoformat()}
                started=time.monotonic()
                try:
                    response=client.get(f"/recommendations/contextual/{quote(test['item_id'],safe='')}",
                                        params={"limit":4,"use_ai_support":"false"})
                    diagnostic["HTTP_status"]=response.status_code
                    try:
                        data=response.json()
                    except ValueError:
                        (raw/f"{tid}.response.txt").write_bytes(response.content)
                        raise ValueError("Risposta non JSON; body conservato nel file .response.txt")
                    (raw/f"{tid}.json").write_bytes(response.content)
                    if not response.is_success:
                        raise RuntimeError(f"HTTP {response.status_code}; risposta completa in raw/{tid}.json")
                    groups=data["groups"]
                    similar=[group for group in groups if group["role_id"]=="similar_alternatives"]
                    complementary=[group for group in groups if group["role_id"]=="complementary"]
                    row.update(N_simili_alternative=sum(len(g["products"]) for g in similar),
                               N_utili_insieme=sum(len(g["products"]) for g in complementary),
                               Prodotti_mostrati=sum(len(g["products"]) for g in groups),
                               Fallback="Sì" if data["fallback"] else "No",
                               Nome_gruppo_simili="; ".join(g["label"] for g in similar),
                               Nome_gruppo_complementari="; ".join(g["label"] for g in complementary))
                    diagnostic.update(Fallback_risposta=data["fallback"],Used_ai_support=data["used_ai_support"])
                    for group in groups:
                        for position,product in enumerate(group["products"],1):
                            review.append({"ID_test":tid,"Prodotto_partenza":test["titolo"],
                                           "Item_id_partenza":test["item_id"],"Gruppo":group["label"],
                                           "Item_id_raccomandato":product["item_id"],
                                           "Titolo_raccomandato":product["title"],
                                           "Categoria_raccomandato":product["category"],
                                           "Prezzo_raccomandato":product["price"],
                                           "Posizione_nel_gruppo":position})
                except Exception as exc:
                    diagnostic["Errore"]=f"{type(exc).__name__}: {exc}"
                    write_json(raw/f"{tid}.error.json",diagnostic)
                diagnostic["Avvisi"]="; ".join(capture.messages)
                diagnostic["Durata_secondi"]=round(time.monotonic()-started,3)
                rows.append(row)
                diagnostics.append(diagnostic)
                write_csv(output/"contextual_recommendations.csv",rows,FIELDS)
                write_csv(output/"contextual_recommendations_review.csv",review,REVIEW_FIELDS)
                write_csv(output/"run_diagnostics.csv",diagnostics,list(diagnostic))
                print(json.dumps(row,ensure_ascii=True),flush=True)
    finally:
        service.logger.removeHandler(capture)
        assert digest(manifest_path)==manifest_hash,"Manifest modificato"
        assert all(digest(path)==value for path,value in fingerprints.items()),"File preesistente modificato"
    write_json(output/"verification.json",{
        "completed_at":datetime.now(timezone.utc).isoformat(),"n_tests":len(rows),
        "n_review_rows":len(review),"manifest_unchanged":True,
        "preexisting_files_unchanged":True,"protected_files":len(fingerprints),
        "errors":[d["ID"] for d in diagnostics if d["Errore"]],
        "fallback_ids":[r["ID"] for r in rows if r["Fallback"]=="Sì"]})


if __name__ == "__main__":
    main()
