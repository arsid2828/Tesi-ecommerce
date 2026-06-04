from prototype.backend.schemas import Product


#Cerchiamo nei prodotti e ordiniamo con baseline popularity
def search_products(
    products: list[Product],
    query: str | None,
    category: str | None=None,
    limit: int=30,
) -> list[Product]:
    filtered=products
    #Applichiamo prima il filtro categoria
    if category:
        normalized_category=category.lower()
        filtered=[
            product for product in filtered if product.category.lower() == normalized_category
        ]

    normalized_query=(query or "").strip().lower()
    #Se la query e valorizzata filtriamo sui campi testuali
    if normalized_query:
        filtered=[
            product
            for product in filtered
            if _matches_query(product,normalized_query)
        ]

    ordered=sorted(filtered,key=lambda product: product.popularity_score,reverse=True)
    return ordered[:limit]


#Verifichiamo se la query compare nei campi cercabili
def _matches_query(product: Product,query: str) -> bool:
    searchable_text=" ".join(
        [
            product.title or "",
            product.category or "",
            product.description or "",
        ]
    ).lower()
    return query in searchable_text
