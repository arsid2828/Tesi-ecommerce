from prototype.backend.schemas import Product
from prototype.backend.services.query_utils import expand_query_terms


#Cerchiamo nei prodotti e ordiniamo con baseline popularity
#La ricerca resta semplice: filtro categoria, match testuale e fallback con sinonimi condivisi
#Il risultato viene sempre riordinato per popolarita per mantenere una baseline chiara
def search_products(
    products: list[Product],
    query: str | None,
    category: str | None=None,
    limit: int=30,
) -> list[Product]:
    filtered=products
    #applichiamo prima il filtro categoria
    if category:
        normalized_category=category.lower()
        filtered=[
            product for product in filtered if product.category.lower() == normalized_category
        ]

    normalized_query=(query or "").strip().lower()
    #filtriamo sui campi testuali
    if normalized_query:
        exact_matches=[
            product
            for product in filtered
            if _matches_query(product,normalized_query)
        ]
        #se la query esatta non trova nulla, usiamo l'espansione condivisa dei sinonimi
        if exact_matches:
            filtered=exact_matches
        else:
            query_tokens=[token for token in normalized_query.split() if len(token) > 1]
            all_token_matches=[
                product
                for product in filtered
                if query_tokens and all(_matches_query(product,token) for token in query_tokens)
            ]
            if all_token_matches:
                filtered=all_token_matches
            else:
                expanded_terms=expand_query_terms(normalized_query)
                filtered=[
                    product
                    for product in filtered
                    if any(_matches_query(product,term) for term in expanded_terms)
                ]
    #ordinati per popolarita
    ordered=sorted(filtered,key=lambda product: product.popularity_score,reverse=True)
    return ordered[:limit]


#Verifichiamo se la query compare nei campi cercabili
#Unifichiamo titolo, categoria e descrizione in un solo testo normalizzato
def _matches_query(product: Product,query: str) -> bool:
    searchable_text=" ".join([
        product.title or "",
        product.category or "",
        product.description or "",
    ]).lower()
    return query in searchable_text
