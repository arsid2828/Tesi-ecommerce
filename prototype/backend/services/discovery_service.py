import json
import logging
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prototype.backend.schemas import DiscoveryEvidence,DiscoveryProduct,DiscoveryRoleGroup,DiscoverySearchResponse,Product
from prototype.backend.services.search_service import search_products

# Servizio di product discovery a cluster.
# Recupera candidati ed evidenze localmente; Gemini puo creare i cluster solo con questi prodotti.
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
# Serve come fallback quando la query non produce candidati sufficienti.
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


# Candidato discovery con score e fonti gia calcolati.
# Tiene insieme prodotto, ranking locale, marca stimata ed evidenze mostrate in UI.
@dataclass
class ScoredProduct:
    product: Product
    match_score: float
    quality_score: float
    budget_score: float
    balanced_score: float
    brand: str | None
    evidence: list[DiscoveryEvidence]
    evidence_sources: list[str]


# Punto di ingresso della discovery AI-first usata dal sito.
# I candidati restano locali; Gemini, se attivo, decide cluster e appartenenze usando i loro item_id.
def discover_products(
    products: list[Product],
    query: str,
    evidence_service: Any,
    ai_query: str="",
    limit: int=80,
    use_ai_support: bool=True,
) -> DiscoverySearchResponse:
    clean_query=_short_text(query,max_chars=160)
    clean_ai_query=_short_text(ai_query,max_chars=240)
    intent_query=_short_text(" ".join(part for part in [clean_query,clean_ai_query] if part),max_chars=320)
    safe_limit=max(1,min(int(limit or 80),200))
    query_terms=_expanded_terms(intent_query)
    candidates=_collect_candidates(products,clean_query,query_terms,safe_limit)

    if not candidates:
        candidates=most_popular(products,limit=min(safe_limit,40))

    scored=[
        _score_product(
            product=product,
            query=intent_query,
            query_terms=query_terms,
            evidence_service=evidence_service,
        )
        for product in candidates
    ]
    scored.sort(key=lambda item:(-item.quality_score,item.product.item_id))

    base_response=DiscoverySearchResponse(
        query=clean_query,
        ai_query=clean_ai_query,
        answer="",
        total_candidates=len(candidates),
        groups=[],
        source_summary={},
        used_ai_support=False,
        fallback=not bool(clean_query.strip()),
    )

    if use_ai_support and scored:
        try:
            return _build_ai_groups(
                response=base_response,
                scored=scored,
                query_terms=query_terms,
            )
        except Exception as exc:
            logger.warning("Fallback discovery con cluster locali: %s",exc)

    fallback_groups=_build_role_groups(
        all_products=products,
        scored=scored,
        query=intent_query,
        query_terms=query_terms,
        evidence_service=evidence_service,
    )
    source_summary=_source_summary(fallback_groups)
    return DiscoverySearchResponse(
        query=clean_query,
        ai_query=clean_ai_query,
        answer=_local_answer(intent_query,fallback_groups,source_summary),
        total_candidates=len(candidates),
        groups=fallback_groups,
        source_summary=source_summary,
        used_ai_support=False,
        fallback=not bool(clean_query.strip()),
    )


def _collect_candidates(
    products: list[Product],
    query: str,
    query_terms: list[str],
    limit: int,
) -> list[Product]:
    seen=set()
    candidates=[]

    def add_many(items: list[Product]) -> None:
        for product in items:
            if product.item_id in seen:
                continue
            seen.add(product.item_id)
            candidates.append(product)

    if query.strip():
        add_many(search_products(products,query,limit=limit))
        for term in query_terms[:8]:
            add_many(search_products(products,term,limit=20))
    else:
        add_many(most_popular(products,limit=min(limit,40)))

    complement_terms=_complement_terms(_tokens(query))
    for term in complement_terms[:8]:
        add_many(search_products(products,term,limit=12))

    if len(candidates) < min(12,len(products)):
        add_many(most_popular(products,limit=20))

    return candidates[:limit]


def _score_product(
    product: Product,
    query: str,
    query_terms: list[str],
    evidence_service: Any,
) -> ScoredProduct:
    match_score=_text_relevance(product,query_terms)
    rating_score=_rating_score(product)
    review_score=_review_count_score(product)
    popularity_score=_safe_float(product.popularity_score)
    price_score=_price_score(product)
    quality_score=(
        0.48*match_score
        +0.20*rating_score
        +0.16*review_score
        +0.16*popularity_score
    )
    budget_score=(
        0.46*match_score
        +0.34*price_score
        +0.12*rating_score
        +0.08*review_score
    )
    balanced_score=(
        0.38*match_score
        +0.25*rating_score
        +0.20*review_score
        +0.17*price_score
    )
    evidence=_evidence_for_product(product,query,query_terms,evidence_service)
    return ScoredProduct(
        product=product,
        match_score=round(match_score,4),
        quality_score=round(quality_score,4),
        budget_score=round(budget_score,4),
        balanced_score=round(balanced_score,4),
        brand=_extract_brand(product.title),
        evidence=evidence,
        evidence_sources=_unique_source_labels(evidence),
    )


def _build_role_groups(
    all_products: list[Product],
    scored: list[ScoredProduct],
    query: str,
    query_terms: list[str],
    evidence_service: Any,
) -> list[DiscoveryRoleGroup]:
    primary_terms=_primary_terms(query)
    direct_relevant=_products_matching_terms(scored,primary_terms)
    relevant=direct_relevant or _relevant_products(scored)
    groups=[]

    groups.append(
        _group_from_scored(
            role_id="best_choice",
            label="Migliore scelta",
            description="Prodotti con il miglior mix locale tra coerenza con la query, rating, recensioni e popolarita.",
            scored_items=sorted(relevant,key=lambda item:(-item.quality_score,item.product.item_id))[:MAX_GROUP_PRODUCTS],
            query_terms=query_terms,
            role_reason="Scelta prioritaria per coerenza con la ricerca e segnali locali forti.",
        )
    )
    groups.append(
        _group_from_scored(
            role_id="budget",
            label="Economici",
            description="Alternative pertinenti con prezzo piu basso tra i candidati trovati.",
            scored_items=sorted(relevant,key=lambda item:(item.product.price or math.inf,-item.match_score))[:MAX_GROUP_PRODUCTS],
            query_terms=query_terms,
            role_reason="Utile se il prezzo pesa piu della popolarita o della completezza delle informazioni.",
        )
    )
    groups.append(
        _group_from_scored(
            role_id="balanced",
            label="Compromesso qualita/prezzo",
            description="Prodotti che bilanciano pertinenza, prezzo, rating e numero di recensioni.",
            scored_items=sorted(relevant,key=lambda item:(-item.balanced_score,item.product.item_id))[:MAX_GROUP_PRODUCTS],
            query_terms=query_terms,
            role_reason="Buon compromesso quando non vuoi solo il prodotto top o quello meno caro.",
        )
    )

    brand_group=_same_brand_group(relevant,query_terms)
    if brand_group is not None:
        groups.append(brand_group)

    complementary=_complementary_group(
        all_products=all_products,
        already_scored=scored,
        query=query,
        query_terms=query_terms,
        evidence_service=evidence_service,
    )
    if complementary is not None:
        groups.append(complementary)

    groups.append(
        _group_from_scored(
            role_id="popular_alternatives",
            label="Alternative popolari",
            description="Prodotti vicini alla query con forte segnale di popolarita o molte recensioni.",
            scored_items=sorted(relevant,key=lambda item:(-_safe_float(item.product.popularity_score),-item.product.rating_count))[:MAX_GROUP_PRODUCTS],
            query_terms=query_terms,
            role_reason="Interessante se vuoi partire da prodotti gia molto presenti nei dati del catalogo.",
        )
    )

    return [group for group in groups if group is not None and group.products]


def _relevant_products(scored: list[ScoredProduct]) -> list[ScoredProduct]:
    if not scored:
        return []
    strong=[item for item in scored if item.match_score >= 0.08]
    return strong or scored[:min(len(scored),12)]


def _products_matching_terms(scored: list[ScoredProduct],terms: list[str]) -> list[ScoredProduct]:
    if not terms:
        return []
    surface_matched=[
        item for item in scored
        if any(term in _product_surface_text(item.product) for term in terms)
    ]
    matched=surface_matched or [
        item for item in scored
        if any(term in _product_text(item.product) for term in terms)
    ]
    matched.sort(key=lambda item:(-item.quality_score,item.product.item_id))
    return matched


def _same_brand_group(
    scored: list[ScoredProduct],
    query_terms: list[str],
) -> DiscoveryRoleGroup | None:
    if not scored:
        return None
    top=scored[0]
    if not top.brand:
        return None
    same_brand=[item for item in scored if item.brand == top.brand]
    if len(same_brand) < 2:
        return None
    return _group_from_scored(
        role_id="same_brand",
        label=f"Stessa marca: {top.brand}",
        description=f"Prodotti collegati alla marca {top.brand} trovati tra i candidati locali.",
        scored_items=sorted(same_brand,key=lambda item:(-item.quality_score,item.product.item_id))[:MAX_GROUP_PRODUCTS],
        query_terms=query_terms,
        role_reason=f"Raggruppato per continuita di marca con il candidato principale {top.brand}.",
    )


def _complementary_group(
    all_products: list[Product],
    already_scored: list[ScoredProduct],
    query: str,
    query_terms: list[str],
    evidence_service: Any,
) -> DiscoveryRoleGroup | None:
    complement_terms=_complement_terms(_tokens(query))
    if not complement_terms:
        return None

    direct_ids={item.product.item_id for item in already_scored[:8]}
    candidates=[]
    seen=set()
    for term in complement_terms:
        for product in search_products(all_products,term,limit=16):
            if product.item_id in direct_ids or product.item_id in seen:
                continue
            seen.add(product.item_id)
            candidates.append(product)
    if not candidates:
        return None

    complement_query=" ".join([query] + complement_terms[:6]).strip()
    scored=[
        _score_product(product,complement_query,_expanded_terms(complement_query),evidence_service)
        for product in candidates
    ]
    scored.sort(key=lambda item:(-item.quality_score,item.product.item_id))
    return _group_from_scored(
        role_id="complementary",
        label="Da usare insieme",
        description="Prodotti complementari che possono affiancare la richiesta principale.",
        scored_items=scored[:MAX_GROUP_PRODUCTS],
        query_terms=query_terms + complement_terms,
        role_reason="Complementare alla query: individuato con termini locali collegati all'uso probabile.",
    )


def _group_from_scored(
    role_id: str,
    label: str,
    description: str,
    scored_items: list[ScoredProduct],
    query_terms: list[str],
    role_reason: str,
) -> DiscoveryRoleGroup | None:
    unique=[]
    seen=set()
    for item in scored_items:
        if item.product.item_id in seen:
            continue
        seen.add(item.product.item_id)
        unique.append(item)
    if not unique:
        return None

    products=[
        _to_discovery_product(item,role_id,role_reason)
        for item in unique
    ]
    return DiscoveryRoleGroup(
        role_id=role_id,
        label=label,
        description=description,
        size=len(products),
        keywords=_keywords_for_products([item.product for item in unique],query_terms),
        products=products,
        reason=role_reason,
    )


def _to_discovery_product(
    item: ScoredProduct,
    role_id: str,
    role_reason: str,
) -> DiscoveryProduct:
    product=item.product
    data=product.model_dump() if hasattr(product,"model_dump") else product.dict()
    local_reason=_product_reason(item,role_id,role_reason)
    return DiscoveryProduct(
        **data,
        role_reason=local_reason,
        match_score=item.match_score,
        evidence_sources=item.evidence_sources,
        evidence=item.evidence,
    )


def _product_reason(
    item: ScoredProduct,
    role_id: str,
    role_reason: str,
) -> str:
    product=item.product
    sources=", ".join(item.evidence_sources) if item.evidence_sources else "metadati"
    base=f"{role_reason} Fonti locali: {sources}."
    if role_id == "budget":
        return f"{base} Prezzo rilevato: {_format_price(product.price)}."
    if role_id == "balanced":
        return f"{base} Bilancia rating {format_rating(product.average_rating)} e prezzo {_format_price(product.price)}."
    if role_id == "same_brand":
        return f"{base} Marca stimata dal titolo: {item.brand or 'N/D'}."
    if role_id == "complementary":
        return f"{base} Non sostituisce necessariamente il prodotto cercato: lo affianca."
    return f"{base} Match locale con la query: {item.match_score:.2f}."


def _evidence_for_product(
    product: Product,
    query: str,
    query_terms: list[str],
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
    retrieval_query=query or " ".join(query_terms) or product.title
    try:
        retrieved=evidence_service.evidence_for_product(
            product=product,
            query=retrieval_query,
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


def _price_score(product: Product) -> float:
    price=_safe_float(product.price)
    if price <= 0:
        return 0.0
    return round(1 / (1 + math.log10(price + 1)),4)


def _expanded_terms(query: str) -> list[str]:
    tokens=_tokens(query)
    terms=[query.strip().lower()] if query.strip() else []
    synonyms={
        "mouse": ["wireless","programmable","gaming mouse"],
        "gaming": ["game","video games","wireless","controller"],
        "telefono": ["phone","smartphone","cell phone"],
        "telefoni": ["phone","smartphone","cell phone"],
        "cellulare": ["phone","smartphone","cell phone"],
        "fotocamera": ["camera","photo"],
        "camera": ["photo","pictures"],
        "economico": ["cheap","budget","low price"],
        "cuffie": ["headphones","earbuds","headset"],
        "stampante": ["printer","ink"],
        "filtro": ["filter","replacement"],
        "batteria": ["battery","charge"],
    }
    for token in tokens:
        terms.append(token)
        terms.extend(synonyms.get(token,[]))
    return _dedupe(terms)[:18]


def _primary_terms(query: str) -> list[str]:
    tokens=_tokens(query)
    broad_terms={
        "wireless","gaming","economico","economici","cheap","budget","low",
        "buona","buono","good","batteria","battery","qualita","quality",
        "migliore","best","prezzo","price",
    }
    noun_map={
        "telefono": ["phone","smartphone","cell phone"],
        "telefoni": ["phone","smartphone","cell phone"],
        "cellulare": ["phone","smartphone","cell phone"],
        "cellulari": ["phone","smartphone","cell phone"],
        "filtro": ["filter"],
        "filtri": ["filter"],
        "acqua": ["water"],
        "frigorifero": ["refrigerator"],
        "fotocamera": ["camera"],
        "cuffie": ["headphones","headset","earbuds"],
        "stampante": ["printer"],
    }
    terms=[]
    for token in tokens:
        if token in broad_terms:
            continue
        terms.extend(noun_map.get(token,[token]))
    return _dedupe(terms)


def _complement_terms(query_terms: list[str]) -> list[str]:
    joined=" ".join(query_terms).lower()
    complement_map={
        "mouse": ["keyboard","headset","mouse pad"],
        "gaming": ["controller","keyboard","headset","xbox","playstation"],
        "phone": ["case","charger","cable","screen protector","headphones"],
        "smartphone": ["case","charger","cable","headphones"],
        "camera": ["tripod","memory card","battery","lens"],
        "printer": ["ink","paper","cartridge"],
        "ink": ["printer","paper"],
        "filter": ["replacement","water filter","refrigerator"],
        "laptop": ["mouse","keyboard","monitor","cable"],
        "computer": ["mouse","keyboard","monitor","cable"],
    }
    terms=[]
    for key,values in complement_map.items():
        if key in joined:
            terms.extend(values)
    return _dedupe(terms)


def _keywords_for_products(products: list[Product],query_terms: list[str]) -> list[str]:
    query_tokens=set(_tokens(" ".join(query_terms)))
    counts=Counter()
    for product in products:
        text=" ".join([product.title or "",product.category or "",product.description or ""])
        for token in _tokens(text):
            if token in query_tokens:
                continue
            counts[token]+=1
    return [token for token,_count in counts.most_common(6)]


def _local_answer(
    query: str,
    groups: list[DiscoveryRoleGroup],
    source_summary: dict[str,int],
) -> str:
    source_text=", ".join(f"{label}: {count}" for label,count in source_summary.items()) or "metadati locali"
    if query.strip():
        return (
            f"Ho analizzato \"{query}\" e creato {len(groups)} gruppi per ruolo usando solo dati locali. "
            f"Le fonti usate nelle motivazioni sono: {source_text}."
        )
    return (
        f"Mostro gruppi iniziali basati sui prodotti piu popolari del catalogo locale. "
        f"Le fonti usate nelle motivazioni sono: {source_text}."
    )


def _build_ai_groups(
    response: DiscoverySearchResponse,
    scored: list[ScoredProduct],
    query_terms: list[str],
) -> DiscoverySearchResponse:
    candidate_pool=_ai_candidate_pool(scored)
    payload={
        "catalog_query": response.query,
        "user_grouping_request": response.ai_query,
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
                "local_evidence": [
                    {
                        "source": evidence.source_label,
                        "text": _short_text(evidence.text,max_chars=260),
                    }
                    for evidence in item.evidence[:2]
                ],
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
    assigned_ids=set()
    used_role_ids=set()
    groups=[]
    for index,item in enumerate(raw_groups[:MAX_AI_GROUPS],start=1):
        if not isinstance(item,dict):
            continue
        label=_short_text(item.get("label"),max_chars=80)
        description=_short_text(item.get("description"),max_chars=180)
        reason=_short_text(item.get("reason"),max_chars=180)
        raw_item_ids=item.get("item_ids")
        if not label or not description or not isinstance(raw_item_ids,list):
            continue
        selected=[]
        for raw_item_id in raw_item_ids:
            item_id=str(raw_item_id or "")
            if item_id not in scored_by_id or item_id in assigned_ids:
                continue
            selected.append(scored_by_id[item_id])
            assigned_ids.add(item_id)
            if len(selected) >= MAX_GROUP_PRODUCTS:
                break
        if not selected:
            continue
        role_id=_unique_role_id(
            item.get("cluster_id") or label,
            index=index,
            used=used_role_ids,
        )
        used_role_ids.add(role_id)
        groups.append(
            _group_from_scored(
                role_id=role_id,
                label=label,
                description=description,
                scored_items=selected,
                query_terms=query_terms,
                role_reason=reason or description,
            )
        )

    groups=[group for group in groups if group is not None]
    if len(groups) < 2:
        raise ValueError("Gemini non ha restituito almeno due cluster validi.")

    source_summary=_source_summary(groups)
    if not answer:
        answer=_local_answer(" ".join([response.query,response.ai_query]).strip(),groups,source_summary)
    return DiscoverySearchResponse(
        query=response.query,
        ai_query=response.ai_query,
        answer=answer,
        total_candidates=response.total_candidates,
        groups=groups,
        source_summary=source_summary,
        used_ai_support=True,
        fallback=response.fallback,
    )


def _ai_candidate_pool(scored: list[ScoredProduct]) -> list[ScoredProduct]:
    relevant=_relevant_products(scored)
    ordered=relevant + [item for item in scored if item not in relevant]
    return ordered[:MAX_AI_CANDIDATES]


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


def _source_summary(groups: list[DiscoveryRoleGroup]) -> dict[str,int]:
    counts=Counter()
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


def _extract_brand(title: str | None) -> str | None:
    tokens=[
        token.strip("-_.,:;()[]{}")
        for token in str(title or "").split()
        if token.strip("-_.,:;()[]{}")
    ]
    stopwords={"the","a","an","new","for","with","and","pack","set","mini","large","small"}
    for token in tokens[:4]:
        clean=re.sub(r"[^A-Za-z0-9]","",token)
        if len(clean) < 2 or clean.lower() in stopwords:
            continue
        if clean.isdigit():
            continue
        return clean[:32]
    return None


def _product_text(product: Product) -> str:
    return " ".join([
        product.title or "",
        product.category or "",
        product.description or "",
    ]).lower()


def _product_surface_text(product: Product) -> str:
    return " ".join([
        product.title or "",
        product.category or "",
    ]).lower()


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9-]{2,}",str(text or "").lower())
        if token not in _stopwords()
    ]


def _stopwords() -> set[str]:
    return {
        "the","and","for","with","from","this","that","are","you","your","into",
        "product","products","description","rating","count","average","available",
        "una","uno","con","per","del","della","dei","gli","che","non","come",
    }


def _dedupe(values: list[str]) -> list[str]:
    result=[]
    for value in values:
        clean=str(value or "").strip().lower()
        if clean and clean not in result:
            result.append(clean)
    return result


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
