from prototype.backend.schemas import Product
from prototype.backend.services.query_utils import CatalogQuery


#Cerchiamo nei prodotti e ordiniamo con baseline popularity
#La ricerca resta semplice: filtro categoria e match testuale con sinonimi per concetto.
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
    if normalized_query:
        matcher=CatalogQuery(normalized_query)
        filtered=[product for product in filtered if matcher.relevance(product) > 0]
    #ordinati per popolarita
    ordered=sorted(filtered,key=lambda product: product.popularity_score,reverse=True)
    return ordered[:limit]
