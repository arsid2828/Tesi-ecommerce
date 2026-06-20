import json
import logging
import math
import re
from dataclasses import dataclass
from typing import Any

from prototype.backend.schemas import (
    AmazonPageProduct,
    AmazonRecommendationCandidate,
    AmazonRecommendationGroup,
    AmazonRecommendationsResponse,
    ContextualRecommendationsResponse,
    DiscoveryEvidence,
    Product,
    RecommendationGroup,
    RecommendationProduct,
)
from prototype.backend.services.discovery_service import call_gemini
from prototype.backend.services.search_service import search_products

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    TfidfVectorizer=None
    cosine_similarity=None


logger=logging.getLogger(__name__)
DEFAULT_GROUP_LIMIT=4
LOCAL_PRODUCT_BASE_URL="http://localhost:3000/product.html"
DEFAULT_GEMINI_MODEL_NAME="Gemini"


@dataclass
class LocalCandidate:
    product: Product
    text_score: float
    category_score: float
    quality_score: float
    price_affinity: float
    diversity_score: float
    bundle_score: float
    brand: str | None


def popular_products(products: list[Product],limit: int=10) -> list[Product]:
    ordered=sorted(products,key=lambda product: _safe_float(product.popularity_score),reverse=True)
    return ordered[:max(1,limit)]


def contextual_recommendations(
    products: list[Product],
    item_id: str,
    evidence_service: Any,
    limit: int=DEFAULT_GROUP_LIMIT,
    use_ai_support: bool=True,
) -> ContextualRecommendationsResponse | None:
    source=next((product for product in products if product.item_id == item_id),None)
    if source is None:
        return None

    safe_limit=max(1,min(int(limit or DEFAULT_GROUP_LIMIT),8))
    candidates=[product for product in products if product.item_id != source.item_id]
    scored=_score_local_candidates(source,candidates)

    groups=_build_local_groups(source,products,scored,evidence_service,safe_limit)
    response=ContextualRecommendationsResponse(
        item_id=source.item_id,
        source_product=source,
        answer=_local_recommendation_answer(source,groups),
        groups=groups,
        used_ai_support=False,
        fallback=not bool(groups),
    )

    if use_ai_support and groups:
        try:
            return _apply_local_ai_support(response)
        except Exception as exc:
            logger.warning("Fallback copy raccomandazioni locali: %s",exc)
    return response


def organize_amazon_recommendations(
    product: AmazonPageProduct,
    candidates: list[AmazonRecommendationCandidate],
    limit: int=DEFAULT_GROUP_LIMIT,
    use_ai_support: bool=True,
) -> AmazonRecommendationsResponse:
    safe_limit=max(1,min(int(limit or DEFAULT_GROUP_LIMIT),8))
    normalized=_normalize_amazon_candidates(product,candidates)
    groups=_build_amazon_groups(product,normalized,safe_limit)
    response=AmazonRecommendationsResponse(
        asin=product.asin,
        title=product.title,
        answer=_amazon_answer(product,groups,len(normalized)),
        groups=groups,
        used_ai_support=False,
        fallback=not bool(groups),
    )

    if use_ai_support and groups:
        try:
            return _apply_amazon_ai_support(response)
        except Exception as exc:
            logger.warning("Fallback copy raccomandazioni Amazon: %s",exc)
    return response


def _score_local_candidates(source: Product,candidates: list[Product]) -> list[LocalCandidate]:
    text_scores=_text_similarity_scores(source,candidates)
    source_brand=_extract_brand(source.title)
    scored=[]
    for product,text_score in zip(candidates,text_scores,strict=False):
        category_score=1.0 if _normalize(product.category) == _normalize(source.category) else 0.0
        brand=_extract_brand(product.title)
        quality_score=_quality_score(product)
        price_affinity=_price_affinity(source.price,product.price)
        diversity_score=0.35
        if source_brand and brand and source_brand != brand:
            diversity_score=1.0
        elif not source_brand or not brand:
            diversity_score=0.6
        bundle_score=_bundle_score(source,product)
        scored.append(
            LocalCandidate(
                product=product,
                text_score=round(text_score,4),
                category_score=category_score,
                quality_score=quality_score,
                price_affinity=price_affinity,
                diversity_score=diversity_score,
                bundle_score=bundle_score,
                brand=brand,
            )
        )
    return scored


def _build_local_groups(
    source: Product,
    all_products: list[Product],
    scored: list[LocalCandidate],
    evidence_service: Any,
    limit: int,
) -> list[RecommendationGroup]:
    seen={source.item_id}
    groups=[]

    similar_ranked=sorted(
        scored,
        key=lambda item: (
            -(0.50*item.text_score + 0.20*item.category_score + 0.18*item.quality_score + 0.12*item.price_affinity),
            item.product.item_id,
        ),
    )
    similar=_take_unique(similar_ranked,seen,limit)
    groups.append(
        _local_group(
            source=source,
            role_id="similar",
            label="Prodotti simili",
            description="Prodotti del catalogo locale con contenuto, categoria o segnali di qualita vicini al prodotto aperto.",
            candidates=similar,
            evidence_service=evidence_service,
            reason="Selezione calcolata localmente da titolo, descrizione, categoria, rating e popolarita.",
        )
    )

    alternative_ranked=sorted(
        scored,
        key=lambda item: (
            -(0.28*item.category_score + 0.22*item.quality_score + 0.20*item.price_affinity + 0.18*item.diversity_score + 0.12*item.text_score),
            item.product.item_id,
        ),
    )
    alternatives=_take_unique(alternative_ranked,seen,limit)
    if not alternatives:
        alternatives=_take_unique(alternative_ranked,{source.item_id},limit)
    groups.append(
        _local_group(
            source=source,
            role_id="alternatives",
            label="Scelte alternative",
            description="Alternative confrontabili prese dal dataset locale, utili se vuoi cambiare marca, prezzo o compromesso.",
            candidates=alternatives,
            evidence_service=evidence_service,
            reason="Le alternative restano nel catalogo locale e privilegiano diversita, qualita e prezzo vicino.",
        )
    )

    bundle_ranked=_bundle_candidates(source,all_products,scored)
    together=_take_unique(bundle_ranked,seen,limit)
    groups.append(
        _local_group(
            source=source,
            role_id="together",
            label="Da acquistare assieme",
            description="Prodotti complementari che possono affiancare quello aperto, sempre scelti dal dataset del sito.",
            candidates=together,
            evidence_service=evidence_service,
            reason="Il ruolo usa parole chiave di accessori o ricambi quando presenti; altrimenti applica un fallback locale su categoria, qualita e diversita.",
        )
    )

    return [group for group in groups if group is not None and group.products]


def _local_group(
    source: Product,
    role_id: str,
    label: str,
    description: str,
    candidates: list[LocalCandidate],
    evidence_service: Any,
    reason: str,
) -> RecommendationGroup | None:
    if not candidates:
        return None

    products=[
        _to_recommendation_product(source,item,role_id,reason,evidence_service)
        for item in candidates
    ]
    return RecommendationGroup(
        role_id=role_id,
        label=label,
        description=description,
        size=len(products),
        products=products,
        reason=reason,
    )


def _to_recommendation_product(
    source: Product,
    candidate: LocalCandidate,
    role_id: str,
    group_reason: str,
    evidence_service: Any,
) -> RecommendationProduct:
    product=candidate.product
    data=_product_dump(product)
    match_score=_role_score(candidate,role_id)
    evidence=_recommendation_evidence(source,product,evidence_service)
    return RecommendationProduct(
        **data,
        page_url=_local_product_url(product.item_id),
        role_reason=_local_product_reason(source,candidate,role_id,group_reason,evidence),
        match_score=round(match_score,4),
        evidence_sources=_unique_source_labels(evidence),
        evidence=evidence,
    )


def _role_score(candidate: LocalCandidate,role_id: str) -> float:
    if role_id == "similar":
        return 0.50*candidate.text_score + 0.20*candidate.category_score + 0.18*candidate.quality_score + 0.12*candidate.price_affinity
    if role_id == "alternatives":
        return 0.28*candidate.category_score + 0.22*candidate.quality_score + 0.20*candidate.price_affinity + 0.18*candidate.diversity_score + 0.12*candidate.text_score
    if role_id == "together":
        return candidate.bundle_score
    return candidate.quality_score


def _local_product_reason(
    source: Product,
    candidate: LocalCandidate,
    role_id: str,
    group_reason: str,
    evidence: list[DiscoveryEvidence],
) -> str:
    sources=", ".join(_unique_source_labels(evidence)) or "metadati"
    if role_id == "similar":
        return (
            f"{group_reason} Similarita contenuto {candidate.text_score:.2f}; "
            f"categoria {'uguale' if candidate.category_score else 'diversa'}; fonti: {sources}."
        )
    if role_id == "alternatives":
        return (
            f"{group_reason} Prezzo vicino {candidate.price_affinity:.2f}, "
            f"qualita locale {candidate.quality_score:.2f}; fonti: {sources}."
        )
    if role_id == "together":
        return (
            f"{group_reason} Complementarita locale {candidate.bundle_score:.2f}; "
            f"non sostituisce {source.title}, lo affianca."
        )
    return f"{group_reason} Fonti: {sources}."


def _recommendation_evidence(
    source: Product,
    product: Product,
    evidence_service: Any,
) -> list[DiscoveryEvidence]:
    metadata=(
        f"Titolo: {product.title}. Categoria: {product.category}. "
        f"Prezzo: {_format_price(product.price)}. Rating: {_format_rating(product.average_rating)}. "
        f"Recensioni: {int(product.rating_count or 0)}."
    )
    evidence=[
        DiscoveryEvidence(
            source="metadata",
            source_label="metadati",
            text=_short_text(metadata,max_chars=260),
            score=1.0,
        )
    ]
    query=f"{source.title} {source.category} {product.title}"
    try:
        retrieved=evidence_service.evidence_for_product(product=product,query=query,max_items=2)
    except Exception as exc:
        logger.warning("Evidenze recommendation non recuperate per %s: %s",product.item_id,exc)
        retrieved=[]

    seen={metadata.lower()}
    for item in retrieved:
        text=_short_text(item.text,max_chars=260)
        dedupe=text.lower()
        if not text or dedupe in seen:
            continue
        evidence.append(
            DiscoveryEvidence(
                source=item.source or "metadata",
                source_label=_source_label(item.source),
                text=text,
                score=round(_safe_float(item.score),4),
            )
        )
        seen.add(dedupe)
    return evidence[:3]


def _bundle_candidates(
    source: Product,
    all_products: list[Product],
    scored: list[LocalCandidate],
) -> list[LocalCandidate]:
    complement_terms=_complement_terms(source)
    if not complement_terms:
        ranked=[item for item in scored if item.bundle_score > 0]
        return sorted(ranked,key=lambda item:(-item.bundle_score,item.product.item_id))

    by_id={item.product.item_id:item for item in scored}
    ids=[]
    for term in complement_terms:
        for product in search_products(all_products,term,limit=18):
            if product.item_id == source.item_id or product.item_id in ids:
                continue
            ids.append(product.item_id)

    term_matches=[
        by_id[item_id]
        for item_id in ids
        if item_id in by_id
    ]
    if term_matches:
        return sorted(term_matches,key=lambda item:(-item.bundle_score,-item.quality_score,item.product.item_id))
    ranked=[item for item in scored if item.bundle_score > 0]
    return sorted(ranked,key=lambda item:(-item.bundle_score,item.product.item_id))


def _take_unique(items: list[LocalCandidate],seen: set[str],limit: int) -> list[LocalCandidate]:
    selected=[]
    for item in items:
        if item.product.item_id in seen:
            continue
        selected.append(item)
        seen.add(item.product.item_id)
        if len(selected) >= limit:
            break
    return selected


def _text_similarity_scores(source: Product,candidates: list[Product]) -> list[float]:
    if not candidates:
        return []
    texts=[_product_text(product) for product in candidates]
    source_text=_product_text(source)
    if TfidfVectorizer is not None and cosine_similarity is not None:
        try:
            vectorizer=TfidfVectorizer(stop_words="english",ngram_range=(1,2),max_features=1800)
            matrix=vectorizer.fit_transform([source_text] + texts)
            scores=cosine_similarity(matrix[0],matrix[1:]).flatten()
            return [float(score) for score in scores]
        except Exception as exc:
            logger.warning("Fallback similarity overlap: %s",exc)
    return [_token_overlap(source_text,text) for text in texts]


def _bundle_score(source: Product,product: Product) -> float:
    source_tokens=set(_tokens(_product_text(source)))
    product_tokens=set(_tokens(_product_text(product)))
    complement_terms=set(_complement_terms(source))
    if not complement_terms:
        category_bridge=0.25 if _normalize(source.category) == _normalize(product.category) else 0.10
        diversity_bridge=0.18 if _extract_brand(source.title) != _extract_brand(product.title) else 0.06
        generic_score=category_bridge + diversity_bridge + 0.34*_quality_score(product)
        return round(min(generic_score,0.72),4)
    term_hits=sum(1 for term in complement_terms if term in _product_text(product))
    source_product_overlap=len(source_tokens & product_tokens) / max(1,len(source_tokens | product_tokens))
    category_diversity=0.18 if _normalize(source.category) != _normalize(product.category) else 0.04
    score=0.55*min(term_hits / max(1,len(complement_terms)),1.0)
    score += 0.20*_quality_score(product)
    score += 0.15*source_product_overlap
    score += category_diversity
    return round(min(score,1.0),4)


def _complement_terms(product: Product) -> list[str]:
    text=_product_text(product)
    mapping={
        "phone": ["case","charger","cable","screen protector","headphones","earbuds"],
        "smartphone": ["case","charger","cable","screen protector","headphones","earbuds"],
        "cell": ["case","charger","cable","screen protector","headphones"],
        "iphone": ["case","charger","cable","screen protector"],
        "camera": ["tripod","memory card","battery","lens","case"],
        "photo": ["tripod","memory card","battery","lens"],
        "printer": ["ink","cartridge","paper"],
        "ink": ["printer","paper","cartridge"],
        "filter": ["replacement","water filter","refrigerator"],
        "refrigerator": ["filter","replacement"],
        "laptop": ["mouse","keyboard","monitor","cable","charger"],
        "computer": ["mouse","keyboard","monitor","cable"],
        "mouse": ["keyboard","mouse pad","headset","usb"],
        "gaming": ["controller","keyboard","headset","mouse pad"],
        "xbox": ["controller","headset","charger"],
        "playstation": ["controller","headset","charger"],
        "vacuum": ["filter","replacement","bag","brush"],
    }
    terms=[]
    for key,values in mapping.items():
        if key in text:
            terms.extend(values)
    return _dedupe(terms)[:12]


def _apply_local_ai_support(response: ContextualRecommendationsResponse) -> ContextualRecommendationsResponse:
    payload={
        "source_product": {
            "item_id": response.source_product.item_id,
            "title": _short_text(response.source_product.title,120),
            "category": response.source_product.category,
        },
        "groups": [
            {
                "role_id": group.role_id,
                "label": group.label,
                "description": group.description,
                "reason": group.reason,
                "products": [
                    {
                        "item_id": product.item_id,
                        "title": _short_text(product.title,120),
                        "category": product.category,
                        "current_reason": _short_text(product.role_reason,160),
                        "sources": product.evidence_sources,
                    }
                    for product in group.products
                ],
            }
            for group in response.groups
        ],
    }
    prompt=(
        "Sei un assistente per una estensione e-commerce di una tesi. "
        "I prodotti sono gia stati scelti solo dal catalogo locale: non puoi aggiungere, rimuovere, riordinare o cambiare item_id. "
        "Puoi solo rendere piu chiari answer,label,description,reason e role_reason. "
        "Non inventare caratteristiche non presenti nei titoli, categorie o fonti indicate. "
        "Restituisci solo JSON valido senza Markdown. "
        'Schema: {"answer":"...","groups":[{"role_id":"...","label":"...","description":"...","reason":"...",'
        '"products":[{"item_id":"...","role_reason":"..."}]}]}. '
        "Answer massimo 2 frasi; testi brevi adatti a un popup.\n\n"
        f"Dati:\n{json.dumps(payload,ensure_ascii=False)}"
    )
    data=_parse_json_object(call_gemini(prompt))
    return _merge_local_ai_response(response,data)


def _merge_local_ai_response(
    response: ContextualRecommendationsResponse,
    data: dict[str,Any],
) -> ContextualRecommendationsResponse:
    answer=_short_text(data.get("answer"),max_chars=360) or response.answer
    group_updates={}
    product_updates={}
    valid_group_ids={group.role_id for group in response.groups}
    valid_item_ids={product.item_id for group in response.groups for product in group.products}
    for item in data.get("groups",[]):
        if not isinstance(item,dict):
            continue
        role_id=str(item.get("role_id") or "")
        if role_id not in valid_group_ids:
            continue
        group_updates[role_id]={
            "label": _short_text(item.get("label"),80),
            "description": _short_text(item.get("description"),180),
            "reason": _short_text(item.get("reason"),180),
        }
        for product_item in item.get("products",[]):
            if not isinstance(product_item,dict):
                continue
            item_id=str(product_item.get("item_id") or "")
            if item_id not in valid_item_ids:
                continue
            reason=_short_text(product_item.get("role_reason"),220)
            if reason:
                product_updates[item_id]=reason

    groups=[]
    for group in response.groups:
        update=group_updates.get(group.role_id,{})
        products=[
            _copy_recommendation_product(product,product_updates.get(product.item_id))
            for product in group.products
        ]
        groups.append(
            RecommendationGroup(
                role_id=group.role_id,
                label=update.get("label") or group.label,
                description=update.get("description") or group.description,
                size=group.size,
                products=products,
                reason=update.get("reason") or group.reason,
            )
        )
    return ContextualRecommendationsResponse(
        item_id=response.item_id,
        source_product=response.source_product,
        answer=answer,
        groups=groups,
        used_ai_support=True,
        fallback=response.fallback,
    )


def _copy_recommendation_product(product: RecommendationProduct,role_reason: str | None) -> RecommendationProduct:
    data=product.model_dump() if hasattr(product,"model_dump") else product.dict()
    if role_reason:
        data["role_reason"]=role_reason
    return RecommendationProduct(**data)


def _normalize_amazon_candidates(
    source: AmazonPageProduct,
    candidates: list[AmazonRecommendationCandidate],
) -> list[AmazonRecommendationCandidate]:
    source_asin=_normalize_asin(source.asin)
    seen=set()
    normalized=[]
    for raw in candidates:
        title=_short_text(raw.title,max_chars=180)
        product_url=_safe_url(raw.product_url)
        if not title or not product_url:
            continue
        asin=_normalize_asin(raw.asin) or _asin_from_url(product_url)
        dedupe_key=asin or product_url
        if not dedupe_key or dedupe_key in seen or asin == source_asin:
            continue
        seen.add(dedupe_key)
        role=_normalize_amazon_role(raw.source_role) or _infer_amazon_role(source,raw)
        score=_amazon_candidate_score(source,title,role)
        normalized.append(
            AmazonRecommendationCandidate(
                asin=asin,
                title=title,
                product_url=product_url,
                image_url=_safe_url(raw.image_url),
                price=_short_text(raw.price,max_chars=40) or None,
                rating=_short_text(raw.rating,max_chars=80) or None,
                source_label=_short_text(raw.source_label,max_chars=90) or "Amazon pagina corrente",
                source_role=role,
                role_reason=_amazon_product_reason(role,raw.source_label,score),
                match_score=score,
            )
        )
    return normalized


def _build_amazon_groups(
    product: AmazonPageProduct,
    candidates: list[AmazonRecommendationCandidate],
    limit: int,
) -> list[AmazonRecommendationGroup]:
    if not candidates:
        return []
    groups=[]
    seen=set()
    role_defs=[
        (
            "similar",
            "Prodotti simili su Amazon",
            "Prodotti reali letti dalla pagina Amazon e collegati a sezioni di confronto o similarita.",
            "similar",
        ),
        (
            "alternatives",
            "Alternative reali",
            "Altri prodotti Amazon disponibili tra i suggerimenti visibili nella pagina.",
            "alternative",
        ),
        (
            "together",
            "Spesso acquistati insieme",
            "Prodotti reali estratti da sezioni Amazon orientate ad acquisto congiunto o accessori.",
            "together",
        ),
    ]
    for role_id,label,description,role_key in role_defs:
        ranked=sorted(
            [candidate for candidate in candidates if candidate.source_role == role_key],
            key=lambda candidate:(-candidate.match_score,candidate.title),
        )
        selected=[]
        for candidate in ranked:
            key=candidate.asin or candidate.product_url
            if key in seen:
                continue
            selected.append(candidate)
            seen.add(key)
            if len(selected) >= limit:
                break
        if selected:
            groups.append(
                AmazonRecommendationGroup(
                    role_id=role_id,
                    label=label,
                    description=description,
                    size=len(selected),
                    products=selected,
                    reason=f"Organizzato dai candidati reali visibili su {product.asin}.",
                )
            )
    if not groups:
        selected=sorted(candidates,key=lambda candidate:(-candidate.match_score,candidate.title))[:limit]
        groups.append(
            AmazonRecommendationGroup(
                role_id="page_suggestions",
                label="Suggerimenti reali nella pagina",
                description="Prodotti Amazon rilevati nel DOM della pagina corrente.",
                size=len(selected),
                products=selected,
                reason="Fallback: la pagina non esponeva sezioni riconoscibili, quindi mostro candidati reali trovati.",
            )
        )
    return groups


def _apply_amazon_ai_support(response: AmazonRecommendationsResponse) -> AmazonRecommendationsResponse:
    payload={
        "source_product": {
            "asin": response.asin,
            "title": _short_text(response.title,160),
        },
        "groups": [
            {
                "role_id": group.role_id,
                "label": group.label,
                "description": group.description,
                "reason": group.reason,
                "products": [
                    {
                        "asin": product.asin,
                        "title": product.title,
                        "source_label": product.source_label,
                        "current_reason": product.role_reason,
                    }
                    for product in group.products
                ],
            }
            for group in response.groups
        ],
    }
    prompt=(
        "Sei un assistente per organizzare suggerimenti Amazon reali gia estratti dalla pagina corrente. "
        "Non hai accesso alla navigazione web e non puoi inventare prodotti, ASIN, prezzi o link. "
        "Puoi solo riscrivere answer,label,description,reason e role_reason dei candidati presenti. "
        "Non cambiare prodotti, ASIN, ordine o URL. Restituisci solo JSON valido senza Markdown. "
        'Schema: {"answer":"...","groups":[{"role_id":"...","label":"...","description":"...","reason":"...",'
        '"products":[{"asin":"...","title":"...","role_reason":"..."}]}]}.\n\n'
        f"Dati:\n{json.dumps(payload,ensure_ascii=False)}"
    )
    data=_parse_json_object(call_gemini(prompt))
    return _merge_amazon_ai_response(response,data)


def _merge_amazon_ai_response(
    response: AmazonRecommendationsResponse,
    data: dict[str,Any],
) -> AmazonRecommendationsResponse:
    answer=_short_text(data.get("answer"),max_chars=360) or response.answer
    group_updates={}
    product_updates={}
    valid_group_ids={group.role_id for group in response.groups}
    valid_keys={
        product.asin or product.title
        for group in response.groups
        for product in group.products
    }
    for item in data.get("groups",[]):
        if not isinstance(item,dict):
            continue
        role_id=str(item.get("role_id") or "")
        if role_id not in valid_group_ids:
            continue
        group_updates[role_id]={
            "label": _short_text(item.get("label"),80),
            "description": _short_text(item.get("description"),180),
            "reason": _short_text(item.get("reason"),180),
        }
        for product_item in item.get("products",[]):
            if not isinstance(product_item,dict):
                continue
            key=str(product_item.get("asin") or product_item.get("title") or "")
            if key not in valid_keys:
                continue
            reason=_short_text(product_item.get("role_reason"),220)
            if reason:
                product_updates[key]=reason

    groups=[]
    for group in response.groups:
        update=group_updates.get(group.role_id,{})
        products=[]
        for product in group.products:
            key=product.asin or product.title
            data_product=product.model_dump() if hasattr(product,"model_dump") else product.dict()
            if product_updates.get(key):
                data_product["role_reason"]=product_updates[key]
            products.append(AmazonRecommendationCandidate(**data_product))
        groups.append(
            AmazonRecommendationGroup(
                role_id=group.role_id,
                label=update.get("label") or group.label,
                description=update.get("description") or group.description,
                size=group.size,
                products=products,
                reason=update.get("reason") or group.reason,
            )
        )
    return AmazonRecommendationsResponse(
        asin=response.asin,
        title=response.title,
        answer=answer,
        groups=groups,
        used_ai_support=True,
        fallback=response.fallback,
    )


def _infer_amazon_role(source: AmazonPageProduct,candidate: AmazonRecommendationCandidate) -> str:
    hint=f"{candidate.source_role or ''} {candidate.source_label or ''}".lower()
    if any(token in hint for token in ["together","bought","bundle","frequently","acquistati","insieme","accessori"]):
        return "together"
    if any(token in hint for token in ["similar","compare","confronta","simili","related"]):
        return "similar"
    source_text=_normalize(source.title)
    candidate_text=_normalize(candidate.title)
    if _token_overlap(source_text,candidate_text) >= 0.08:
        return "similar"
    if _looks_complementary(source_text,candidate_text):
        return "together"
    return "alternative"


def _normalize_amazon_role(value: str | None) -> str | None:
    role=str(value or "").strip().lower()
    if role in {"similar","together","alternative"}:
        return role
    if role == "alternatives":
        return "alternative"
    return None


def _amazon_candidate_score(source: AmazonPageProduct,title: str,role: str) -> float:
    overlap=_token_overlap(_normalize(source.title),_normalize(title))
    role_boost={"similar":0.35,"together":0.28,"alternative":0.18}.get(role,0.12)
    return round(min(1.0,role_boost + 0.65*overlap),4)


def _amazon_product_reason(role: str,source_label: str | None,score: float) -> str:
    origin=source_label or "sezione visibile nella pagina Amazon"
    if role == "together":
        return f"Candidato reale letto da {origin}; possibile acquisto insieme, score pagina {score:.2f}."
    if role == "similar":
        return f"Candidato reale letto da {origin}; vicino al prodotto aperto, score pagina {score:.2f}."
    return f"Candidato reale letto da {origin}; alternativa disponibile tra i suggerimenti visibili."


def _looks_complementary(source_text: str,candidate_text: str) -> bool:
    accessory_terms={"case","charger","cable","cover","screen","protector","battery","tripod","ink","cartridge","filter","keyboard","mouse","headset"}
    source_terms=set(_tokens(source_text))
    candidate_terms=set(_tokens(candidate_text))
    return bool(candidate_terms & accessory_terms) and not bool(source_terms & candidate_terms)


def _local_recommendation_answer(source: Product,groups: list[RecommendationGroup]) -> str:
    if not groups:
        return f"Non ho trovato raccomandazioni contestuali locali per {source.title}."
    labels=", ".join(group.label for group in groups)
    return f"Ho creato consigli contestuali per {source.title} usando solo il catalogo locale: {labels}."


def _amazon_answer(
    product: AmazonPageProduct,
    groups: list[AmazonRecommendationGroup],
    candidate_count: int,
) -> str:
    if not groups:
        return (
            "Non ho trovato card prodotto reali gia visibili nella pagina Amazon corrente. "
            "Per cercare prodotti Amazon fuori pagina serve una sorgente esterna ufficiale o un motore di ricerca collegato al backend."
        )
    return (
        f"Ho organizzato {candidate_count} candidati reali letti dalla pagina Amazon per {product.asin}. "
        "Gemini puo rifinire le etichette, ma non inventa prodotti o link."
    )


def _product_dump(product: Product) -> dict[str,Any]:
    return product.model_dump() if hasattr(product,"model_dump") else product.dict()


def _product_text(product: Product) -> str:
    return " ".join([
        product.title or "",
        product.category or "",
        product.description or "",
    ]).lower()


def _quality_score(product: Product) -> float:
    rating=min(max(_safe_float(product.average_rating) / 5,0),1)
    reviews=_review_count_score(product)
    popularity=min(max(_safe_float(product.popularity_score),0),1)
    return round(0.48*rating + 0.30*reviews + 0.22*popularity,4)


def _review_count_score(product: Product) -> float:
    count=max(0,int(product.rating_count or 0))
    if count <= 0:
        return 0.0
    return round(min(math.log10(count + 1) / 5,1),4)


def _price_affinity(source_price: Any,candidate_price: Any) -> float:
    source=_safe_float(source_price)
    candidate=_safe_float(candidate_price)
    if source <= 0 or candidate <= 0:
        return 0.45
    distance=abs(math.log10(source + 1) - math.log10(candidate + 1))
    return round(1 / (1 + distance),4)


def _token_overlap(left: str,right: str) -> float:
    left_tokens=set(_tokens(left))
    right_tokens=set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return round(len(left_tokens & right_tokens) / len(left_tokens | right_tokens),4)


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
        "amazon","real","reale",
    }


def _extract_brand(title: str | None) -> str | None:
    tokens=[
        token.strip("-_.,:;()[]{}")
        for token in str(title or "").split()
        if token.strip("-_.,:;()[]{}")
    ]
    stopwords={"the","a","an","new","for","with","and","pack","set","mini","large","small"}
    for token in tokens[:4]:
        clean=re.sub(r"[^A-Za-z0-9]","",token)
        if len(clean) < 2 or clean.lower() in stopwords or clean.isdigit():
            continue
        return clean[:32]
    return None


def _safe_url(value: Any) -> str | None:
    text=_short_text(value,max_chars=500)
    if not text or not re.match(r"^https?://",text,re.I):
        return None
    return text


def _asin_from_url(value: str | None) -> str | None:
    text=str(value or "")
    match=re.search(r"/(?:dp|gp/product|product)/([A-Z0-9]{10})(?:[/?#]|$)",text,re.I)
    if match:
        return _normalize_asin(match.group(1))
    match=re.search(r"(?:[?&](?:asin|ASIN|pd_rd_i)=)([A-Z0-9]{10})(?:&|$)",text,re.I)
    if match:
        return _normalize_asin(match.group(1))
    return None


def _normalize_asin(value: Any) -> str | None:
    text=str(value or "").strip().upper()
    return text if re.fullmatch(r"[A-Z0-9]{10}",text) else None


def _local_product_url(item_id: str) -> str:
    return f"{LOCAL_PRODUCT_BASE_URL}?id={item_id}"


def _source_label(source: str | None) -> str:
    if source == "review":
        return "recensioni"
    if source == "qa":
        return "qa"
    return "metadati"


def _unique_source_labels(evidence: list[DiscoveryEvidence]) -> list[str]:
    labels=[]
    for item in evidence:
        if item.source_label not in labels:
            labels.append(item.source_label)
    return labels


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


def _dedupe(values: list[str]) -> list[str]:
    result=[]
    for value in values:
        clean=str(value or "").strip().lower()
        if clean and clean not in result:
            result.append(clean)
    return result


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _safe_float(value: Any) -> float:
    try:
        number=float(value)
    except (TypeError,ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return number


def _short_text(value: Any,max_chars: int=260) -> str:
    text=" ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3].rstrip() + "..."


def _format_price(value: Any) -> str:
    price=_safe_float(value)
    if price <= 0:
        return "N/D"
    return f"{price:.2f} USD"


def _format_rating(value: Any) -> str:
    rating=_safe_float(value)
    return f"{rating:.1f}" if rating > 0 else "N/D"
