import json
import logging
import math
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prototype.backend.schemas import DiscoveryEvidence,DiscoveryProduct,DiscoveryRoleGroup,DiscoverySearchResponse,Product
from prototype.backend.services.query_utils import expand_query_terms,tokenize_query

# Servizio di product discovery a cluster.
# Recupera candidati localmente con una sola scansione del catalogo;
# Gemini puo creare i cluster solo con item_id gia presenti tra i candidati.
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai=None
    types=None


logger=logging.getLogger(__name__)
MAX_GROUP_PRODUCTS=4
MAX_EVIDENCE_PER_PRODUCT=3
MAX_AI_CANDIDATES=24
MAX_AI_GROUPS=6
DEFAULT_GEMINI_MODEL="gemini-2.5-flash"


# Restituisce i prodotti piu popolari del catalogo.
# Serve come fallback quando la query e vuota o non produce candidati sufficienti.
def most_popular(products: list[Product],limit: int=10) -> list[Product]:
    ordered=sorted(products,key=lambda product: product.popularity_score,reverse=True)
    return ordered[:limit]


# Chiama Gemini con output JSON per creare i cluster del sito.
# La funzione carica le variabili ambiente locali e fallisce se la chiave non esiste.
def call_gemini(prompt: str) -> str:
    if genai is None:
        raise RuntimeError("Libreria google-genai non installata.")

    _load_env_files()
    api_key=os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY non configurata.")

    model=os.getenv("GEMINI_MODEL",DEFAULT_GEMINI_MODEL)
    client=genai.Client(api_key=api_key)
    config=None
    if types is not None:
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        )
    response=client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    return getattr(response,"text","") or ""


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
            key,value=line.split("=",1)
            key=key.strip()
            value=value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key]=value


# Candidato discovery con score locali calcolati nella prima fase.
# evidence e evidence_sources vengono aggiunti solo dopo la formazione dei gruppi finali.
@dataclass
class ScoredProduct:
    product: Product
    match_score: float
    quality_score: float


# Punto di ingresso della discovery AI-first usata dal sito.
# retrieval_query e usata per recupero, scoring ed evidenze.
# grouping_request e passata a Gemini come criterio di organizzazione, senza alterare i candidati.
def discover_products(
    products: list[Product],
    query: str,
    evidence_service: Any,
    ai_query: str="",
    limit: int=80,
    use_ai_support: bool=True,
) -> DiscoverySearchResponse:
    retrieval_query=_short_text(query,max_chars=160)
    grouping_request=_short_text(ai_query,max_chars=240)
    safe_limit=max(1,min(int(limit or 80),200))
    query_terms=expand_query_terms(retrieval_query)
    candidates=_retrieve_candidates(products,retrieval_query,query_terms,safe_limit)

    scored=[
        _score_product(product=product,query_terms=query_terms)
        for product in candidates
    ]
    scored.sort(key=lambda item:(-item.quality_score,item.product.item_id))

    if use_ai_support and scored and retrieval_query.strip():
        try:
            response=_build_ai_groups(
                retrieval_query=retrieval_query,
                grouping_request=grouping_request,
                scored=scored,
                query_terms=query_terms,
                total_candidates=len(candidates),
                evidence_service=evidence_service,
            )
            return response
        except Exception as exc:
            logger.warning("Fallback discovery con cluster locale: %s",exc)

    return _build_fallback_response(
        retrieval_query=retrieval_query,
        grouping_request=grouping_request,
        scored=scored,
        total_candidates=len(candidates),
        evidence_service=evidence_service,
    )


# Attraversa il catalogo una sola volta e calcola la rilevanza di ogni prodotto.
# Ordina per match_score desc, popularity_score desc, item_id asc.
# Se la query e vuota restituisce direttamente i piu popolari.
# Se i risultati sono insufficienti completa con prodotti popolari senza nuove ricerche.
def _retrieve_candidates(
    products: list[Product],
    query: str,
    query_terms: list[str],
    limit: int,
) -> list[Product]:
    if not query.strip():
        return most_popular(products,limit=min(limit,40))

    scored=[]
    for product in products:
        match=_text_relevance(product,query_terms)
        if match > 0:
            scored.append((match,product))

    scored.sort(key=lambda row:(-row[0],-_safe_float(row[1].popularity_score),row[1].item_id))
    result=[product for _match,product in scored]

    if len(result) < min(12,len(products)):
        seen={product.item_id for product in result}
        for product in most_popular(products,limit=20):
            if product.item_id not in seen:
                result.append(product)
                seen.add(product.item_id)

    return result[:limit]


# Calcola i punteggi locali di un prodotto senza costruire evidenze.
# Le evidenze vengono aggiunte separatamente solo sui prodotti finali.
def _score_product(
    product: Product,
    query_terms: list[str],
) -> ScoredProduct:
    match_score=_text_relevance(product,query_terms)
    rating_score=_rating_score(product)
    review_score=_review_count_score(product)
    popularity_score=_safe_float(product.popularity_score)
    quality_score=(
        0.48*match_score
        +0.20*rating_score
        +0.16*review_score
        +0.16*popularity_score
    )
    return ScoredProduct(
        product=product,
        match_score=round(match_score,4),
        quality_score=round(quality_score,4),
    )


# Costruisce la risposta di fallback con un solo gruppo locale.
# Usata quando use_ai_support=False, Gemini non e disponibile o risponde in modo invalido.
def _build_fallback_response(
    retrieval_query: str,
    grouping_request: str,
    scored: list[ScoredProduct],
    total_candidates: int,
    evidence_service: Any,
) -> DiscoverySearchResponse:
    groups=_build_fallback_group(scored)
    _attach_evidence_to_groups(groups,retrieval_query,evidence_service)
    source_summary=_source_summary(groups)
    return DiscoverySearchResponse(
        query=retrieval_query,
        ai_query=grouping_request,
        answer=_local_answer(retrieval_query,groups,source_summary),
        total_candidates=total_candidates,
        groups=groups,
        source_summary=source_summary,
        used_ai_support=False,
        fallback=True,
    )


# Crea un singolo gruppo di fallback con i migliori candidati per quality_score.
def _build_fallback_group(scored: list[ScoredProduct]) -> list[DiscoveryRoleGroup]:
    best=sorted(scored,key=lambda item:(-item.quality_score,item.product.item_id))
    seen: set[str]=set()
    unique=[]
    for item in best:
        if item.product.item_id in seen:
            continue
        seen.add(item.product.item_id)
        unique.append(item)
        if len(unique) >= MAX_GROUP_PRODUCTS:
            break
    if not unique:
        return []
    role_reason="Selezione locale basata su rilevanza, rating, recensioni e popolarita."
    products=[
        _to_discovery_product(item,"best_choice",role_reason,evidence=[],evidence_sources=[])
        for item in unique
    ]
    group=DiscoveryRoleGroup(
        role_id="best_choice",
        label="Migliore scelta",
        description="Prodotti con il miglior mix locale tra coerenza con la query, rating, recensioni e popolarita.",
        size=len(products),
        keywords=[],
        products=products,
        reason=role_reason,
    )
    return [group]


# Seleziona i candidati migliori da inviare a Gemini.
# Preferisce i prodotti con match_score > 0 mantenendo al massimo MAX_AI_CANDIDATES.
def _ai_candidate_pool(scored: list[ScoredProduct]) -> list[ScoredProduct]:
    relevant=[item for item in scored if item.match_score >= 0.08]
    pool=relevant or scored[:]
    ordered=pool + [item for item in scored if item not in pool]
    return ordered[:MAX_AI_CANDIDATES]


# Costruisce la risposta con cluster Gemini.
# Invia a Gemini solo item_id e metadati; non include evidence pre-calcolate.
# Le evidenze vengono aggiunte dopo la validazione, solo sui prodotti finali.
def _build_ai_groups(
    retrieval_query: str,
    grouping_request: str,
    scored: list[ScoredProduct],
    query_terms: list[str],
    total_candidates: int,
    evidence_service: Any,
) -> DiscoverySearchResponse:
    candidate_pool=_ai_candidate_pool(scored)
    payload={
        "catalog_query": retrieval_query,
        "user_grouping_request": grouping_request,
        "constraints": {
            "min_groups": 2,
            "max_groups": MAX_AI_GROUPS,
            "max_products_per_group": MAX_GROUP_PRODUCTS,
        },
        "candidates": [
            {
                "item_id": item.product.item_id,
                "title": _short_text(item.product.title,max_chars=140),
                "category": _short_text(item.product.category,max_chars=80),
                "description": _short_text(item.product.description,max_chars=220),
                "price": item.product.price,
                "average_rating": item.product.average_rating,
                "rating_count": item.product.rating_count,
                "popularity_score": item.product.popularity_score,
                "local_match_score": item.match_score,
            }
            for item in candidate_pool
        ],
    }
    prompt=(
        "Sei il motore di clustering di una demo di product discovery e-commerce. "
        "Ricevi una query catalogo, un criterio opzionale dell'utente e candidati recuperati localmente. "
        "Crea da zero cluster utili e specifici per la richiesta: non partire da ruoli predefiniti. "
        "Scegli il numero, i nomi e le appartenenze in base alle differenze realmente visibili nei dati. "
        "Usa da 2 a 6 cluster, massimo 4 prodotti per cluster e non ripetere lo stesso item_id. "
        "Ogni gruppo deve contenere almeno un item_id presente nei candidati; non inventare prodotti, "
        "caratteristiche, prezzi, fonti o item_id. Se un criterio non e supportato dai dati, non usarlo. "
        "Scrivi answer, label, description e reason in italiano. "
        "Restituisci solo JSON valido senza Markdown. "
        'Schema: {"answer":"...","groups":[{"cluster_id":"...","label":"...",'
        '"description":"...","reason":"...","item_ids":["..."]}]}. '
        "Answer massimo 2 frasi; description e reason massimo 1 frase.\n\n"
        f"Dati:\n{json.dumps(payload,ensure_ascii=False)}"
    )
    raw_response=call_gemini(prompt)
    data=_parse_json_object(raw_response)
    answer=_short_text(data.get("answer"),max_chars=420)
    raw_groups=data.get("groups")
    if not isinstance(raw_groups,list):
        raise ValueError("Campo groups mancante.")

    scored_by_id={item.product.item_id:item for item in candidate_pool}
    assigned_ids: set[str]=set()
    used_role_ids: set[str]=set()
    groups=[]
    for index,raw_item in enumerate(raw_groups[:MAX_AI_GROUPS],start=1):
        if not isinstance(raw_item,dict):
            continue
        label=_short_text(raw_item.get("label"),max_chars=80)
        description=_short_text(raw_item.get("description"),max_chars=180)
        reason=_short_text(raw_item.get("reason"),max_chars=180)
        raw_item_ids=raw_item.get("item_ids")
        if not label or not description or not isinstance(raw_item_ids,list):
            continue
        selected=[]
        for raw_id in raw_item_ids:
            item_id=str(raw_id or "")
            if item_id not in scored_by_id or item_id in assigned_ids:
                continue
            selected.append(scored_by_id[item_id])
            assigned_ids.add(item_id)
            if len(selected) >= MAX_GROUP_PRODUCTS:
                break
        if not selected:
            continue
        role_id=_unique_role_id(
            raw_item.get("cluster_id") or label,
            index=index,
            used=used_role_ids,
        )
        used_role_ids.add(role_id)
        role_reason=reason or description
        products=[
            _to_discovery_product(item,role_id,role_reason,evidence=[],evidence_sources=[])
            for item in selected
        ]
        group=DiscoveryRoleGroup(
            role_id=role_id,
            label=label,
            description=description,
            size=len(products),
            keywords=[],
            products=products,
            reason=role_reason,
        )
        groups.append(group)

    if len(groups) < 2:
        raise ValueError("Gemini non ha restituito almeno due cluster validi.")

    _attach_evidence_to_groups(groups,retrieval_query,evidence_service)
    source_summary=_source_summary(groups)
    if not answer:
        answer=_local_answer(retrieval_query,groups,source_summary)
    return DiscoverySearchResponse(
        query=retrieval_query,
        ai_query=grouping_request,
        answer=answer,
        total_candidates=total_candidates,
        groups=groups,
        source_summary=source_summary,
        used_ai_support=True,
        fallback=False,
    )


# Aggiunge evidence ed evidence_sources ai DiscoveryProduct gia creati nei gruppi finali.
# Chiama evidence_service solo per item_id unici; usa una cache per richiesta.
# Usa retrieval_query (mai ai_query) come contesto di recupero.
def _attach_evidence_to_groups(
    groups: list[DiscoveryRoleGroup],
    retrieval_query: str,
    evidence_service: Any,
) -> None:
    cache: dict[str,tuple[list[DiscoveryEvidence],list[str]]]={}
    for group in groups:
        for dp in group.products:
            item_id=dp.item_id
            if item_id not in cache:
                product=Product(
                    item_id=dp.item_id,
                    title=dp.title,
                    category=dp.category,
                    description=dp.description,
                    price=dp.price,
                    average_rating=dp.average_rating,
                    rating_count=dp.rating_count,
                    popularity_score=dp.popularity_score,
                    image_url=dp.image_url,
                )
                ev=_evidence_for_product(product,retrieval_query,evidence_service)
                sources=_unique_source_labels(ev)
                cache[item_id]=(ev,sources)
            ev,sources=cache[item_id]
            dp.evidence=ev
            dp.evidence_sources=sources


# Costruisce le evidenze testuali per un singolo prodotto usando evidence_service.
# Sempre include un documento di metadati; aggiunge poi le evidenze recuperate.
def _evidence_for_product(
    product: Product,
    query: str,
    evidence_service: Any,
) -> list[DiscoveryEvidence]:
    metadata_text=(
        f"Titolo: {product.title}. Categoria: {product.category}. "
        f"Prezzo: {_format_price(product.price)}. Rating: {format_rating(product.average_rating)}. "
        f"Recensioni: {int(product.rating_count or 0)}."
    )
    evidence=[
        DiscoveryEvidence(
            source="metadata",
            source_label="metadati",
            text=_short_text(metadata_text,max_chars=360),
            score=1.0,
        )
    ]
    retrieval=query or product.title
    try:
        retrieved=evidence_service.evidence_for_product(
            product=product,
            query=retrieval,
            max_items=MAX_EVIDENCE_PER_PRODUCT,
        )
    except Exception as exc:
        logger.warning("Evidenze discovery non recuperate per %s: %s",product.item_id,exc)
        retrieved=[]

    seen={metadata_text.lower()}
    for item in retrieved:
        text=_short_text(item.text,max_chars=360)
        dedupe=text.lower()
        if not text or dedupe in seen:
            continue
        source=str(item.source or "metadata")
        evidence.append(
            DiscoveryEvidence(
                source=source,
                source_label=_source_label(source),
                text=text,
                score=round(float(item.score or 0),4),
            )
        )
        seen.add(dedupe)
    return evidence[:1 + MAX_EVIDENCE_PER_PRODUCT]


# Crea un DiscoveryProduct a partire da uno ScoredProduct con evidence gia note.
def _to_discovery_product(
    item: ScoredProduct,
    role_id: str,
    role_reason: str,
    evidence: list[DiscoveryEvidence],
    evidence_sources: list[str],
) -> DiscoveryProduct:
    product=item.product
    data=product.model_dump() if hasattr(product,"model_dump") else product.dict()
    local_reason=_product_reason(item,role_id,role_reason)
    return DiscoveryProduct(
        **data,
        role_reason=local_reason,
        match_score=item.match_score,
        evidence_sources=evidence_sources,
        evidence=evidence,
    )


# Genera la motivazione del prodotto nel gruppo.
def _product_reason(
    item: ScoredProduct,
    role_id: str,
    role_reason: str,
) -> str:
    base=role_reason
    return f"{base} Match locale con la query: {item.match_score:.2f}."


def _local_answer(
    query: str,
    groups: list[DiscoveryRoleGroup],
    source_summary: dict[str,int],
) -> str:
    source_text=", ".join(f"{label}: {count}" for label,count in source_summary.items()) or "metadati locali"
    if query.strip():
        return (
            f"Ho analizzato \"{query}\" e creato {len(groups)} gruppi usando solo dati locali. "
            f"Le fonti usate nelle motivazioni sono: {source_text}."
        )
    return (
        f"Mostro gruppi iniziali basati sui prodotti piu popolari del catalogo locale. "
        f"Le fonti usate nelle motivazioni sono: {source_text}."
    )


def _text_relevance(product: Product,terms: list[str]) -> float:
    if not terms:
        return 0.25*_safe_float(product.popularity_score)
    title=(product.title or "").lower()
    category=(product.category or "").lower()
    description=(product.description or "").lower()
    score=0.0
    max_score=max(1.0,len(terms)*4.5)
    for term in terms:
        if not term:
            continue
        if term in title:
            score += 2.8
        if term in category:
            score += 1.4
        if term in description:
            score += 1.0
    return round(min(score / max_score,1.0),4)


def _rating_score(product: Product) -> float:
    rating=_safe_float(product.average_rating)
    return round(min(max(rating / 5,0),1),4)


def _review_count_score(product: Product) -> float:
    count=max(0,int(product.rating_count or 0))
    if count <= 0:
        return 0.0
    return round(min(math.log10(count + 1) / 5,1),4)


def _source_summary(groups: list[DiscoveryRoleGroup]) -> dict[str,int]:
    from collections import Counter
    counts: Counter[str]=Counter()
    for group in groups:
        for product in group.products:
            for label in product.evidence_sources:
                counts[label]+=1
    return dict(sorted(counts.items(),key=lambda row: row[0]))


def _unique_source_labels(evidence: list[DiscoveryEvidence]) -> list[str]:
    labels=[]
    for item in evidence:
        if item.source_label not in labels:
            labels.append(item.source_label)
    return labels


def _source_label(source: str) -> str:
    if source == "review":
        return "recensioni"
    if source == "qa":
        return "qa"
    return "metadati"


def _unique_role_id(value: Any,index: int,used: set[str]) -> str:
    base=re.sub(r"[^a-z0-9]+","_",str(value or "").lower()).strip("_")[:48]
    if not base:
        base=f"gemini_cluster_{index}"
    candidate=base
    suffix=2
    while candidate in used:
        candidate=f"{base[:44]}_{suffix}"
        suffix+=1
    return candidate


def _parse_json_object(raw_response: str) -> dict[str,Any]:
    try:
        data=json.loads(raw_response)
    except json.JSONDecodeError:
        start=raw_response.find("{")
        end=raw_response.rfind("}")
        if start < 0 or end < start:
            raise
        data=json.loads(raw_response[start:end + 1])
    if not isinstance(data,dict):
        raise ValueError("La risposta AI non e un oggetto JSON.")
    return data


def _short_text(value: Any,max_chars: int=260) -> str:
    text=" ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3].rstrip() + "..."


def _safe_float(value: Any) -> float:
    try:
        number=float(value)
    except (TypeError,ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return number


def _format_price(value: Any) -> str:
    price=_safe_float(value)
    if price <= 0:
        return "N/D"
    return f"{price:.2f} USD"


def format_rating(value: Any) -> str:
    rating=_safe_float(value)
    return f"{rating:.1f}" if rating > 0 else "N/D"
