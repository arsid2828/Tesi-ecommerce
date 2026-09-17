"""Valutazione fissa tramite POST /discover della vera app FastAPI.

Eseguire dalla root: .venv/Scripts/python.exe prototype/scripts/evaluate_cluster_search.py
Richiede httpx (TestClient). Nessun mock, retry o modifica alla configurazione AI.
--output permette una nuova cartella; una cartella gia popolata non viene sovrascritta.
"""

import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime,timezone
from pathlib import Path


ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
DEFAULT_OUTPUT=ROOT / "prototype" / "evaluation" / "cluster_search"
RUN_FIELDS=["ID","Tipo_test","Query","Criterio","N_cluster",
            "Prodotti_mostrati","Nomi_cluster","Vincoli_rispettati"]
GENERAL=["mouse","headphones","phone","printer","drill","vacuum",
         "car accessories","garden tools","fitness equipment","board game"]
CRITERIA=[("C01","G01","mouse","raggruppa per utilizzo"),
          ("C02","G03","phone","raggruppa per fascia di prezzo"),
          ("C03","G02","headphones","raggruppa per utilizzo")]
STABILITY=[("S01","G01","mouse",""),
           ("S02","C02","phone","raggruppa per fascia di prezzo"),
           ("S03","C03","headphones","raggruppa per utilizzo")]


def test_cases() -> list[tuple[str,str,str,str]]:
    cases=[(f"G{i:02d}","Generale",query,"") for i,query in enumerate(GENERAL,1)]
    cases.extend((cid,"Con criterio",query,criterion) for cid,_,query,criterion in CRITERIA)
    cases.extend((f"{sid}-R{repeat}","Stabilità",query,criterion)
                 for sid,_,query,criterion in STABILITY for repeat in (2,3))
    return cases


def yes_no(value: bool) -> str:
    return "Sì" if value else "No"


def write_csv(path: Path,rows: list[dict],fields: list[str] | None=None) -> None:
    # UTF-8 con BOM per mantenere accenti leggibili anche in Excel.
    with path.open("w",encoding="utf-8-sig",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def final_metrics(data: dict) -> dict:
    # Si legge esclusivamente il JSON finale restituito dall'endpoint.
    groups=data["groups"]
    ids=[product["item_id"] for group in groups for product in group["products"]]
    labels=[group["label"] for group in groups]
    valid=(2 <= len(groups) <= 6
           and all(len(group["products"]) <= 4 for group in groups)
           and len(ids) == len(set(ids)))
    return {"N_cluster":len(groups),"Prodotti_mostrati":len(ids),
            "Nomi_cluster":"; ".join(labels),"Vincoli_rispettati":yes_no(valid),
            "ids":set(ids),"labels":labels}


class DiscoveryLog(logging.Handler):
    # Ascolta i warning gia emessi dal servizio, senza intercettare output Gemini.
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages=[]

    def emit(self,record):
        self.messages.append(record.getMessage())


def comparisons(output: Path,runs: dict,metrics: dict,diagnostics: dict) -> None:
    criterion_rows=[]
    for cid,base,query,criterion in CRITERIA:
        row={"ID_base":base,"ID_con_criterio":cid,"Query":query,"Criterio_aggiunto":criterion}
        for field in ("N_cluster","Nomi_cluster","Prodotti_mostrati"):
            row[f"{field}_senza_criterio"]=runs[base][field]
            row[f"{field}_con_criterio"]=runs[cid][field]
        row.update(Esito_senza_criterio=diagnostics[base]["Esito"],
                   Esito_con_criterio=diagnostics[cid]["Esito"])
        criterion_rows.append(row)
    write_csv(output / "criterion_comparison.csv",criterion_rows)

    stability_rows=[]
    for sid,base,query,criterion in STABILITY:
        ids=[base,f"{sid}-R2",f"{sid}-R3"]
        row={"Caso":sid,"Query":query,"Criterio":criterion or "assente"}
        for number,tid in enumerate(ids,1):
            row[f"ID_R{number}"]=tid
            for field in ("N_cluster","Nomi_cluster","Prodotti_mostrati"):
                row[f"{field}_R{number}"]=runs[tid][field]
            row[f"Esito_R{number}"]=diagnostics[tid]["Esito"]
        row.update(N_cluster_identico="",Nomi_cluster_identici="",
                   Insieme_prodotti_identico="",Prodotti_comuni="")
        if all(tid in metrics for tid in ids):
            a,b,c=[metrics[tid] for tid in ids]
            row.update(
                N_cluster_identico=yes_no(a["N_cluster"] == b["N_cluster"] == c["N_cluster"]),
                Nomi_cluster_identici=yes_no(a["labels"] == b["labels"] == c["labels"]),
                Insieme_prodotti_identico=yes_no(a["ids"] == b["ids"] == c["ids"]),
                Prodotti_comuni=len(a["ids"] & b["ids"] & c["ids"]),
            )
        stability_rows.append(row)
    write_csv(output / "stability_comparison.csv",stability_rows)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    args=parser.parse_args()
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    if any(output.iterdir()):
        parser.error("La cartella output non e vuota. Usare --output con una nuova cartella.")
    raw=output / "raw"
    raw.mkdir()
    cases=test_cases()
    manifest={"started_at":datetime.now(timezone.utc).isoformat(),
              "endpoint":"POST /discover","transport":"FastAPI TestClient, app reale in-process",
              "limit":80,"use_ai_support":True,"automatic_retries":0,
              "cases":[{"ID":tid,"query":query,"ai_query":criterion}
                       for tid,_,query,criterion in cases],
              "name_comparison":"Etichette esatte, stesso ordine, senza normalizzazione",
              "product_comparison":"Insiemi di item_id finali, ordine ignorato",
              "fallback_comparison":"Incluso e segnalato dagli esiti; non equivale a Gemini"}
    (output / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")

    capture=DiscoveryLog()
    service_logger=logging.getLogger("prototype.backend.services.discovery_service")
    service_logger.addHandler(capture)
    client=None
    startup_error=""
    try:
        from fastapi.testclient import TestClient
        from prototype.backend.app import app
        client=TestClient(app,raise_server_exceptions=False)
        client.__enter__()
    except Exception as exc:
        startup_error=f"Avvio app: {type(exc).__name__}: {exc}"

    runs={}
    metrics={}
    diagnostics={}
    try:
        for tid,kind,query,criterion in cases:
            row=dict.fromkeys(RUN_FIELDS,"")
            row.update(ID=tid,Tipo_test=kind,Query=query,Criterio=criterion or "assente")
            diagnostic={"ID":tid,"Esito":"Errore","HTTP_status":"",
                        "Fallback":"","Used_ai_support":"","Errore":"","Avvisi":""}
            capture.messages.clear()
            start=time.monotonic()
            print(f"{tid}: {query} / {criterion or 'assente'}",flush=True)
            try:
                if startup_error:
                    raise RuntimeError(startup_error)
                response=client.post("/discover",json={"query":query,"ai_query":criterion,
                                                        "limit":80,"use_ai_support":True})
                diagnostic["HTTP_status"]=response.status_code
                try:
                    data=response.json()
                except ValueError:
                    (raw / f"{tid}.response.txt").write_bytes(response.content)
                    raise ValueError(f"HTTP {response.status_code}: risposta non JSON, conservata in raw/{tid}.response.txt")
                # Conserva i byte della risposta, senza aggiungere o rimuovere campi.
                (raw / f"{tid}.json").write_bytes(response.content)
                if not response.is_success:
                    raise RuntimeError(f"HTTP {response.status_code}; risposta completa in raw/{tid}.json")
                result=final_metrics(data)
                metrics[tid]=result
                row.update({field:result[field] for field in RUN_FIELDS if field in result})
                diagnostic.update(Fallback=yes_no(data["fallback"]),
                                  Used_ai_support=yes_no(data["used_ai_support"]),
                                  Esito="Fallback" if data["fallback"] else
                                  ("Gemini" if data["used_ai_support"] else "Locale senza AI"))
            except Exception as exc:
                diagnostic["Errore"]=f"{type(exc).__name__}: {exc}"
                (raw / f"{tid}.error.json").write_text(
                    json.dumps({"ID":tid,"error":diagnostic["Errore"]},ensure_ascii=False,indent=2),encoding="utf-8")
            diagnostic["Avvisi"]="; ".join(capture.messages)
            diagnostic["Durata_secondi"]=round(time.monotonic()-start,3)
            runs[tid]=row
            diagnostics[tid]=diagnostic
            # Salvataggio progressivo: gli esiti gia ottenuti sopravvivono a interruzioni.
            write_csv(output / "cluster_search_runs.csv",list(runs.values()),RUN_FIELDS)
            write_csv(output / "run_diagnostics.csv",list(diagnostics.values()))
            print(f"  {diagnostic['Esito']}: cluster={row['N_cluster']}, prodotti={row['Prodotti_mostrati']}, vincoli={row['Vincoli_rispettati']}",flush=True)
        comparisons(output,runs,metrics,diagnostics)
        manifest["completed_at"]=datetime.now(timezone.utc).isoformat()
        manifest["completed_runs"]=len(runs)
        (output / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    finally:
        service_logger.removeHandler(capture)
        if client is not None and not startup_error:
            client.__exit__(None,None,None)
    print(f"Output: {output}",flush=True)


if __name__ == "__main__":
    main()
