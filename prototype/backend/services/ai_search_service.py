import json
import logging
import os
from pathlib import Path
from typing import Any

from prototype.backend.schemas import AISearchResponse,AISearchResult,Product
from prototype.backend.services.recommendation_service import most_popular
from prototype.backend.services.search_service import search_products

#Import opzionale della libreria Gemini
#Se manca,o manca la chiave API,il servizio usa fallback locale
#Questo permette di avviare il prototipo anche senza configurazione AI
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai=None
    types=None


DEFAULT_GEMINI_MODEL="gemini-2.5-flash"
MAX_CANDIDATES_FOR_GEMINI=40
DESCRIPTION_MAX_CHARS=260
logger=logging.getLogger(__name__)


#Prepariamo solo i campi necessari: niente dati personali e niente catalogo completo
#L'AI riceve solo candidati gia scelti dalla ricerca locale
#Questo riduce token,costi e rischio di risposte fuori catalogo
def prepare_candidates_for_gemini(products: list[Product]) -> list[dict[str, Any]]:
    return [
        {
            "item_id": product.item_id,
            "title": product.title,
            "category": product.category,
            "description": _short_text(product.description),
            "average_rating": product.average_rating,
            "rating_count": product.rating_count,
            "popularity_score": product.popularity_score,
        }
        for product in products
    ]


#Prompt rigido: Gemini deve riordinare solo i candidati e rispondere in JSON
#Lo schema obbligatorio rende validabile la risposta
#La regola piu importante e non inventare item_id o caratteristiche
def build_gemini_prompt(
    query: str,
    question: str | None,
    category: str | None,
    limit: int,
    candidates: list[dict[str, Any]],
) -> str:
    payload={ #dati strutturati inseriti nel prompt
        "query": query,
        "question": question or "",
        "category": category or "",
        "max_results": limit,
        "candidates": candidates,
    }
    return (
        "Sei un assistente per ricerca prodotti e-commerce. "
        "Devi aiutare l'utente a scegliere i prodotti piu adatti alla sua richiesta. "
        "Puoi usare solo i prodotti candidati forniti. "
        "Non inventare prodotti, marche, prezzi o caratteristiche non presenti nei dati. "
        "Se un'informazione non e disponibile, non affermarla. "
        "Riordina i prodotti candidati in base alla query e alla domanda dell'utente. "
        "Restituisci solo JSON valido, senza Markdown e senza testo fuori dal JSON. "
        "Lo schema obbligatorio e: "
        '{"answer":"breve risposta generale per l\'utente","results":[{"item_id":"...","ai_score":0.0,"ai_reason":"spiegazione breve e concreta"}]}. '
        "ai_score deve essere tra 0 e 1. "
        "results deve contenere massimo max_results elementi. "
        "item_id deve essere uno degli item_id candidati. "
        "ai_reason deve essere breve, massimo 1-2 frasi.\n\n"
        f"Dati richiesta e candidati:\n{json.dumps(payload,ensure_ascii=False)}"
    )


#Chiamata Gemini isolata: se key/libreria mancano il chiamante usa fallback locale
#Qui non decidiamo fallback,solleviamo eccezioni gestite dal livello superiore
#La configurazione forza JSON per semplificare la validazione
def call_gemini(prompt: str) -> str:
    if genai is None:
        raise RuntimeError("Libreria google-genai non installata.")

    api_key=os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY non configurata.")

    model=os.getenv("GEMINI_MODEL",DEFAULT_GEMINI_MODEL)
    client=genai.Client(api_key=api_key)
    config=None
    if types is not None:
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json", #chiede al modello output JSON
        )
    response=client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return getattr(response,"text","") or ""


#Validiamo il JSON e scartiamo item_id non candidati o score non validi
#Questa e la barriera contro output AI inventati o fuori formato
#Manteniamo solo risultati controllabili nel catalogo locale
def validate_gemini_json(
    raw_response: str,
    candidate_ids: set[str],
    limit: int,
) -> tuple[str,list[dict[str, Any]]]:
    data=_parse_json_object(raw_response) #gestisce JSON puro o testo con JSON incluso
    answer=str(data.get("answer") or "Risultati riordinati in base alla richiesta.")
    raw_results=data.get("results")
    if not isinstance(raw_results,list):
        raise ValueError("Campo results mancante o non valido.")

    valid_results=[]
    seen_ids=set() #evita duplicati restituiti dal modello
    for item in raw_results:
        if not isinstance(item,dict):
            continue
        item_id=str(item.get("item_id") or "")
        if item_id not in candidate_ids or item_id in seen_ids: #scarta prodotti inventati o duplicati
            continue
        ai_score=item.get("ai_score")
        if not isinstance(ai_score,(int,float)) or not 0 <= float(ai_score) <= 1: #score deve essere normalizzato
            continue
        ai_reason=_short_text(str(item.get("ai_reason") or ""),max_chars=220)
        if not ai_reason:
            ai_reason="Consigliato per coerenza con la ricerca e con i dati disponibili."
        valid_results.append(
            {
                "item_id": item_id,
                "ai_score": float(ai_score),
                "ai_reason": ai_reason,
            }
        )
        seen_ids.add(item_id)
        if len(valid_results) >= limit:
            break

    if not valid_results:
        raise ValueError("Nessun risultato Gemini valido.")
    return _short_text(answer,max_chars=320),valid_results


#Funzione principale usata dall'endpoint FastAPI
#Prima crea candidati locali,poi lascia Gemini solo riordinare/spiegare
#In caso di errore ritorna una risposta locale con fallback=True
def ai_search_products(
    products: list[Product],
    query: str,
    question: str | None=None,
    category: str | None=None,
    limit: int=10,
) -> AISearchResponse:
    safe_limit=max(1,min(limit,50)) #limita richieste troppo grandi
    local_candidates=search_products(
        products=products,
        query=query,
        category=category,
        limit=MAX_CANDIDATES_FOR_GEMINI,
    )

    #se la ricerca testuale non trova candidati, restiamo locali con prodotti popolari
    if not local_candidates:
        category_pool=search_products( #se query fallisce,prova almeno la categoria
            products=products,
            query="",
            category=category,
            limit=MAX_CANDIDATES_FOR_GEMINI,
        )
        local_candidates=category_pool or most_popular(products,limit=MAX_CANDIDATES_FOR_GEMINI) #fallback finale

    compact_candidates=prepare_candidates_for_gemini(local_candidates[:MAX_CANDIDATES_FOR_GEMINI]) #taglia catalogo prima dell'AI
    prompt=build_gemini_prompt(query,question,category,safe_limit,compact_candidates)
    product_by_id={product.item_id: product for product in local_candidates} #serve per ricostruire oggetti Product

    try:
        raw_response=call_gemini(prompt)
        answer,ai_items=validate_gemini_json(
            raw_response=raw_response,
            candidate_ids=set(product_by_id), #solo id presenti nei candidati sono validi
            limit=safe_limit,
        )
    except Exception as exc:
        logger.warning("Fallback ricerca AI: %s",exc)
        return _local_fallback_response(
            query=query,
            question=question,
            products=local_candidates[:safe_limit],
            reason="Risultato basato sulla ricerca locale.",
        )

    results=[
        _merge_product_with_ai(
            product=product_by_id[item["item_id"]],
            ai_score=item["ai_score"],
            ai_reason=item["ai_reason"],
        )
        for item in ai_items
    ]
    return AISearchResponse(
        query=query,
        question=question,
        mode="ai_search",
        answer=answer,
        results=results,
        fallback=False,
    )


#Risposta locale quando Gemini non e disponibile o non valida
#Mantiene lo stesso schema AISearchResponse del caso AI
#Il frontend puo mostrare un avviso usando fallback=True
def _local_fallback_response(
    query: str,
    question: str | None,
    products: list[Product],
    reason: str,
) -> AISearchResponse:
    return AISearchResponse(
        query=query,
        question=question,
        mode="local_fallback",
        answer="Gemini non disponibile: risultati ordinati con ricerca locale.",
        results=[
            _merge_product_with_ai(product,ai_score=None,ai_reason=reason)
            for product in products
        ],
        fallback=True,
    )


#Unisce prodotto Pydantic con campi AI opzionali
#Supporta sia Pydantic v2(model_dump) sia v1(dict)
#Non modifica il Product originale
def _merge_product_with_ai(
    product: Product,
    ai_score: float | None,
    ai_reason: str,
) -> AISearchResult:
    data=product.model_dump() if hasattr(product,"model_dump") else product.dict() #compatibilita Pydantic v1/v2
    return AISearchResult(**data,ai_score=ai_score,ai_reason=ai_reason)


#Parsa JSON robusto per risposte Gemini
#Se il modello aggiunge testo,ritaglia dal primo { all'ultimo }
#Se il risultato non e dict,il chiamante usera fallback
def _parse_json_object(raw_response: str) -> dict[str, Any]:
    try:
        data=json.loads(raw_response)
    except json.JSONDecodeError:
        start=raw_response.find("{")
        end=raw_response.rfind("}")
        if start < 0 or end < start:
            raise
        data=json.loads(raw_response[start:end + 1]) #recupera oggetto JSON incorporato
    if not isinstance(data,dict):
        raise ValueError("La risposta Gemini non e un oggetto JSON.")
    return data


def _short_text(value: str | None,max_chars: int=DESCRIPTION_MAX_CHARS) -> str:
    text=" ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3].rstrip() + "..."


#Carichiamo variabili da .env locale senza sovrascrivere quelle gia impostate
#Controlliamo prima root progetto,poi cartella prototype
#Non sovrascrivere os.environ permette configurazioni esterne piu forti
def _load_env_files() -> None:
    prototype_dir=Path(__file__).resolve().parents[2]
    project_dir=prototype_dir.parent
    for env_path in [project_dir / ".env",prototype_dir / ".env"]:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line=raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key,value=line.split("=",1) #split solo sul primo = per valori complessi
            key=key.strip()
            value=value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key]=value


_load_env_files()
