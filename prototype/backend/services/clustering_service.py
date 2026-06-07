import json
import logging
import re
from collections import Counter,defaultdict
from typing import Any

from prototype.backend.schemas import ClusteredSearchResponse,Product,ProductCluster
from prototype.backend.services.ai_search_service import call_gemini

try:
    from sklearn.cluster import MiniBatchKMeans
    from sklearn.feature_extraction.text import TfidfVectorizer
except ImportError:
    MiniBatchKMeans=None
    TfidfVectorizer=None


logger=logging.getLogger(__name__)
RANDOM_STATE=42
MAX_KEYWORDS=6
MAX_TITLES_FOR_AI=5


#funzione principale usata dall'endpoint: lavora solo sui risultati ricevuti
def cluster_search_results(
    products: list[Product],
    query: str,
    use_ai_labels: bool=True,
) -> ClusteredSearchResponse:
    safe_products=list(products)
    if not safe_products:
        return ClusteredSearchResponse(
            query=query,
            total_results=0,
            clustered=False,
            clusters=[],
        )

    cluster_count=_choose_cluster_count(len(safe_products))
    if cluster_count <= 1 or TfidfVectorizer is None or MiniBatchKMeans is None:
        clusters=[_build_single_cluster(safe_products)]
        return _label_response(
            query=query,
            products=safe_products,
            clusters=clusters,
            clustered=False,
            use_ai_labels=use_ai_labels,
            local_fallback=TfidfVectorizer is None or MiniBatchKMeans is None,
        )

    try:
        clusters=_build_kmeans_clusters(safe_products,cluster_count)
    except Exception as exc:
        logger.warning("Fallback clustering locale: %s",exc)
        clusters=[_build_single_cluster(safe_products)]
        return _label_response(
            query=query,
            products=safe_products,
            clusters=clusters,
            clustered=False,
            use_ai_labels=use_ai_labels,
            local_fallback=True,
        )

    if len(clusters) <= 1:
        clustered=False
    else:
        clustered=True

    return _label_response(
        query=query,
        products=safe_products,
        clusters=clusters,
        clustered=clustered,
        use_ai_labels=use_ai_labels,
        local_fallback=False,
    )


#numero di gruppi semplice e spiegabile per il prototipo
def _choose_cluster_count(total_results: int) -> int:
    if total_results < 6:
        return 1
    if total_results <= 15:
        return 2
    if total_results <= 40:
        return 3
    return 5 if total_results > 80 else 4


#clustering locale con TF-IDF sui testi dei prodotti gia filtrati
def _build_kmeans_clusters(products: list[Product],cluster_count: int) -> list[ProductCluster]:
    texts=[_product_text(product) for product in products]
    vectorizer=TfidfVectorizer(
        stop_words="english",
        ngram_range=(1,2),
        max_features=900,
        min_df=1,
    )
    matrix=vectorizer.fit_transform(texts)
    if matrix.shape[1] == 0:
        return [_build_single_cluster(products)]

    safe_cluster_count=min(cluster_count,len(products))
    model=MiniBatchKMeans(
        n_clusters=safe_cluster_count,
        random_state=RANDOM_STATE,
        n_init=10,
        batch_size=max(20,len(products)),
    )
    labels=model.fit_predict(matrix)

    grouped=defaultdict(list)
    for index,label in enumerate(labels):
        grouped[int(label)].append(index)

    raw_clusters=[]
    for indexes in grouped.values():
        if not indexes:
            continue
        cluster_products=[products[index] for index in indexes]
        keywords=_keywords_for_indexes(matrix,vectorizer,indexes)
        raw_clusters.append((cluster_products,keywords))

    #cluster piu grandi prima, con id ricalcolati e stabili per la risposta
    raw_clusters.sort(key=lambda item: (-len(item[0]),_cluster_sort_key(item[0])))
    clusters=[]
    for index,(cluster_products,keywords) in enumerate(raw_clusters,start=1):
        clusters.append(_build_cluster(index,cluster_products,keywords))
    return clusters


def _build_single_cluster(products: list[Product]) -> ProductCluster:
    keywords=_fallback_keywords([_product_text(product) for product in products])
    return ProductCluster(
        cluster_id="cluster_1",
        label="Risultati principali",
        description="Gruppo unico con i prodotti piu coerenti con la ricerca.",
        size=len(products),
        keywords=keywords,
        products=products,
        reason="I risultati sono pochi oppure il clustering locale non e disponibile.",
    )


def _build_cluster(index: int,products: list[Product],keywords: list[str]) -> ProductCluster:
    label=_local_label(index,keywords)
    return ProductCluster(
        cluster_id=f"cluster_{index}",
        label=label,
        description=_local_description(keywords),
        size=len(products),
        keywords=keywords,
        products=products,
        reason="Prodotti raggruppati in base alla similarita TF-IDF su titolo, categoria e descrizione.",
    )


def _label_response(
    query: str,
    products: list[Product],
    clusters: list[ProductCluster],
    clustered: bool,
    use_ai_labels: bool,
    local_fallback: bool,
) -> ClusteredSearchResponse:
    used_ai=False
    if use_ai_labels and clusters:
        try:
            clusters=_apply_ai_labels(query,clusters)
            used_ai=True
        except Exception as exc:
            logger.warning("Fallback label cluster: %s",exc)

    return ClusteredSearchResponse(
        query=query,
        total_results=len(products),
        clustered=clustered,
        clusters=clusters,
        used_ai_labels=used_ai,
        fallback=local_fallback or (use_ai_labels and not used_ai),
    )


#Gemini puo solo rinominare/spiegare cluster gia creati localmente
def _apply_ai_labels(query: str,clusters: list[ProductCluster]) -> list[ProductCluster]:
    payload={
        "query": query,
        "clusters": [
            {
                "cluster_id": cluster.cluster_id,
                "keywords": cluster.keywords,
                "representative_titles": [
                    _short_text(product.title,max_chars=120)
                    for product in cluster.products[:MAX_TITLES_FOR_AI]
                ],
            }
            for cluster in clusters
        ],
    }
    prompt=(
        "Sei un assistente per product discovery e-commerce. "
        "Ricevi cluster gia calcolati localmente: non puoi cambiare prodotti, item_id o membership. "
        "Genera solo label e descrizioni brevi in italiano, chiare per un utente finale. "
        "Usa solo query, keyword e titoli rappresentativi forniti. "
        "Non inventare caratteristiche non presenti nei dati. "
        "Restituisci solo JSON valido senza Markdown. "
        'Schema obbligatorio: {"clusters":[{"cluster_id":"cluster_1","label":"...","description":"...","reason":"..."}]}. '
        "La description deve essere massimo una frase; reason massimo una frase.\n\n"
        f"Dati:\n{json.dumps(payload,ensure_ascii=False)}"
    )
    raw_response=call_gemini(prompt)
    data=_parse_json_object(raw_response)
    raw_clusters=data.get("clusters")
    if not isinstance(raw_clusters,list):
        raise ValueError("Campo clusters mancante.")

    labels_by_id={}
    valid_ids={cluster.cluster_id for cluster in clusters}
    for item in raw_clusters:
        if not isinstance(item,dict):
            continue
        cluster_id=str(item.get("cluster_id") or "")
        if cluster_id not in valid_ids:
            continue
        label=_short_text(item.get("label"),max_chars=80)
        description=_short_text(item.get("description"),max_chars=180)
        reason=_short_text(item.get("reason"),max_chars=180)
        if label and description:
            labels_by_id[cluster_id]={
                "label": label,
                "description": description,
                "reason": reason or None,
            }

    if not labels_by_id:
        raise ValueError("Nessuna label AI valida.")

    relabeled=[]
    for cluster in clusters:
        label_data=labels_by_id.get(cluster.cluster_id)
        if not label_data:
            relabeled.append(cluster)
            continue
        relabeled.append(
            ProductCluster(
                cluster_id=cluster.cluster_id,
                label=label_data["label"],
                description=label_data["description"],
                size=cluster.size,
                keywords=cluster.keywords,
                products=cluster.products,
                reason=label_data["reason"] or cluster.reason,
            )
        )
    return relabeled


def _product_text(product: Product) -> str:
    parts=[
        product.title or "",
        product.category or "",
        product.description or "",
        getattr(product,"brand",None) or "",
    ]
    if product.average_rating:
        parts.append(f"average rating {product.average_rating}")
    if product.rating_count:
        parts.append(f"rating count {product.rating_count}")
    return " ".join(str(part) for part in parts if part).strip()


def _keywords_for_indexes(matrix,vectorizer,indexes: list[int]) -> list[str]:
    feature_names=vectorizer.get_feature_names_out()
    centroid=matrix[indexes].mean(axis=0).A1
    top_indexes=centroid.argsort()[::-1]
    keywords=[]
    for feature_index in top_indexes:
        if centroid[feature_index] <= 0:
            break
        keyword=str(feature_names[feature_index]).strip()
        if not keyword or keyword in keywords:
            continue
        keywords.append(keyword)
        if len(keywords) >= MAX_KEYWORDS:
            break
    return keywords


def _fallback_keywords(texts: list[str]) -> list[str]:
    joined=" ".join(texts).lower()
    tokens=[
        token
        for token in re.findall(r"[a-z0-9][a-z0-9-]{2,}",joined)
        if token not in _basic_stopwords()
    ]
    counts=Counter(tokens)
    return [word for word,_count in counts.most_common(MAX_KEYWORDS)]


def _local_label(index: int,keywords: list[str]) -> str:
    if keywords:
        return f"Gruppo {index}: {', '.join(keywords[:3])}"
    return f"Gruppo {index}"


def _local_description(keywords: list[str]) -> str:
    if keywords:
        return "Prodotti accomunati da parole chiave come " + ", ".join(keywords[:4]) + "."
    return "Prodotti simili in base ai campi testuali disponibili."


def _cluster_sort_key(products: list[Product]) -> str:
    if not products:
        return ""
    return (products[0].category or products[0].title or "").lower()


def _parse_json_object(raw_response: str) -> dict[str, Any]:
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


def _basic_stopwords() -> set[str]:
    return {
        "the","and","for","with","from","this","that","are","you","your",
        "product","products","description","rating","count","average",
        "una","uno","con","per","del","della","dei","gli","che","non",
    }
