from prototype.backend.schemas import Product


#cerchiamo nei prodotti e ordiniamo con baseline popularity
def search_products(
    products: list[Product],
    query: str | None, #testo scritto dall'utente
    category: str | None=None, #categoria opzionale
    limit: int=30,
) -> list[Product]:
    filtered=products #copia che filtriamo
    #applichiamo prima il filtro categoria
    if category:
        normalized_category=category.lower()
        filtered=[
            product for product in filtered if product.category.lower() == normalized_category
        ]

    normalized_query=(query or "").strip().lower() #se query none diventa vuota, toglie spazi inutili e converte in minuscolo
    #filtriamo sui campi testuali
    if normalized_query:
        filtered=[
            product
            for product in filtered
            if _matches_query(product,normalized_query)
        ]
    #ordinati per popolarità
    ordered=sorted(filtered,key=lambda product: product.popularity_score,reverse=True)
    return ordered[:limit]


#verifichiamo se la query compare nei campi cercabili
def _matches_query(product: Product,query: str) -> bool:
    searchable_text=" ".join( #unisce, titolo categoria e descrizione
        [
            product.title or "",
            product.category or "",
            product.description or "",
        ]
    ).lower()
    return query in searchable_text #se presente, ritorna true, sennò false
