"""Confronto descrittivo: quattro GET /search e lettura dei cluster già salvati.

Eseguire con il Python del progetto. --output richiede una cartella senza output.
Non invoca discovery o Gemini e non riordina la risposta del backend.
"""

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime,timezone
from pathlib import Path


ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
CASES=[("T01","mouse","G01"),("T02","phone","G03"),
       ("T03","drill","G05"),("T04","board game","G10")]
SUMMARY=["ID","Query","Cluster_test","N_risultati_tradizionale",
         "N_prodotti_clusterizzata","N_cluster","Nomi_cluster","Prodotti_comuni","Overlap_percent"]
DETAIL=["ID","Query","Item_id","Titolo","Cluster","Presente_nella_tradizionale",
        "Posizione_nella_tradizionale"]
TRADITIONAL=["ID","Query","N_risultati_tradizionale","Item_id","Titolo","Categoria",
             "Prezzo","Rating","Numero_valutazioni","Posizione_nella_lista"]


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file,"sha256").hexdigest()


def write_csv(path,rows,fields):
    with path.open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    if any(p for p in output.iterdir() if p.name not in {Path(__file__).name,"README.md","__pycache__"}):
        parser.error("Output già presenti: scegliere una nuova cartella con --output.")

    # Impronte prima di qualunque richiesta; include tutte le valutazioni precedenti.
    protected=[ROOT/"prototype/data/products_demo.json"]
    for directory in ("backend","frontend","scripts","evaluation/cluster_search",
                      "evaluation/contextual_recommendations"):
        protected.extend(p for p in (ROOT/"prototype"/directory).rglob("*")
                         if p.is_file() and "__pycache__" not in p.parts)
    fingerprints={path:digest(path) for path in protected}
    sources={cid:ROOT/"prototype/evaluation/cluster_search/raw"/f"{cid}.json" for _,_,cid in CASES}
    clusters={cid:json.loads(path.read_bytes()) for cid,path in sources.items()}
    for _,query,cid in CASES:
        assert clusters[cid]["query"]==query and clusters[cid]["ai_query"]==""
    manifest={"created_at":datetime.now(timezone.utc).isoformat(),
              "endpoint":"GET /search","limit":80,"transport":"FastAPI TestClient, app reale",
              "ordering":"Ordine originale del backend, popularity_score decrescente; nessun riordinamento",
              "cluster_sources":[{"ID":tid,"query":query,"Cluster_test":cid,
                                  "path":str(sources[cid].relative_to(ROOT)),
                                  "sha256":fingerprints[sources[cid]]} for tid,query,cid in CASES],
              "overlap_formula":"Presenze di prodotti clusterizzati con item_id nella lista tradizionale / totale presenze nei cluster * 100",
              "zero_denominator":"Percentuale vuota se nessun prodotto clusterizzato",
              "positions":"Posizioni da 1 nell'ordine restituito; cella vuota se assente o richiesta fallita"}
    write_json(output/"test_manifest.json",manifest)
    raw=output/"raw"
    raw.mkdir()
    from fastapi.testclient import TestClient
    from prototype.backend.app import app

    summaries=[]
    details=[]
    traditional_rows=[]
    diagnostics=[]
    with TestClient(app,raise_server_exceptions=False) as client:
        for tid,query,cid in CASES:
            data=clusters[cid]
            groups=data["groups"]
            shown=[(g,p) for g in groups for p in g["products"]]
            row=dict.fromkeys(SUMMARY,"")
            row.update(ID=tid,Query=query,Cluster_test=cid,N_prodotti_clusterizzata=len(shown),
                       N_cluster=len(groups),Nomi_cluster="; ".join(g["label"] for g in groups))
            diagnostic={"ID":tid,"HTTP_status":"","Errore":""}
            positions=None
            try:
                response=client.get("/search",params={"query":query,"limit":80})
                diagnostic["HTTP_status"]=response.status_code
                try:
                    products=response.json()
                except ValueError:
                    (raw/f"traditional_{tid}.response.txt").write_bytes(response.content)
                    raise ValueError("Risposta non JSON; body conservato nel file .response.txt")
                (raw/f"traditional_{tid}.json").write_bytes(response.content)
                if not response.is_success:
                    raise RuntimeError(f"HTTP {response.status_code}; dettagli nel JSON finale")
                if not isinstance(products,list):
                    raise ValueError("La risposta finale non è una lista")
                positions={}
                for index,product in enumerate(products,1):
                    positions.setdefault(product["item_id"],index)
                    traditional_rows.append({"ID":tid,"Query":query,"N_risultati_tradizionale":len(products),
                                             "Item_id":product["item_id"],"Titolo":product["title"],
                                             "Categoria":product["category"],"Prezzo":product["price"],
                                             "Rating":product["average_rating"],"Numero_valutazioni":product["rating_count"],
                                             "Posizione_nella_lista":index})
                common=sum(product["item_id"] in positions for _,product in shown)
                row.update(N_risultati_tradizionale=len(products),Prodotti_comuni=common,
                           Overlap_percent=common/len(shown)*100 if shown else "")
            except Exception as exc:
                positions=None
                diagnostic["Errore"]=f"{type(exc).__name__}: {exc}"
                write_json(raw/f"traditional_{tid}.error.json",diagnostic)
            for group,product in shown:
                present=product["item_id"] in positions if positions is not None else None
                details.append({"ID":tid,"Query":query,"Item_id":product["item_id"],
                                "Titolo":product["title"],"Cluster":group["label"],
                                "Presente_nella_tradizionale":("Sì" if present else "No") if present is not None else "",
                                "Posizione_nella_tradizionale":positions.get(product["item_id"],"") if positions is not None else ""})
            summaries.append(row)
            diagnostics.append(diagnostic)
            write_csv(output/"search_comparison.csv",summaries,SUMMARY)
            write_csv(output/"search_comparison_products.csv",details,DETAIL)
            write_csv(output/"traditional_search_products.csv",traditional_rows,TRADITIONAL)
            write_csv(output/"run_diagnostics.csv",diagnostics,list(diagnostic))
            print(json.dumps(row,ensure_ascii=True),flush=True)
    assert all(digest(path)==value for path,value in fingerprints.items()),"File preesistente modificato"
    write_json(output/"verification.json",{
        "completed_at":datetime.now(timezone.utc).isoformat(),"traditional_requests":len(CASES),
        "cluster_requests":0,"gemini_calls":0,"protected_files_unchanged":len(fingerprints),
        "cluster_sources_unchanged":True,"errors":[r for r in diagnostics if r["Errore"]],
        "summary_rows":len(summaries),"cluster_product_rows":len(details),
        "traditional_product_rows":len(traditional_rows)})


if __name__ == "__main__":
    main()
