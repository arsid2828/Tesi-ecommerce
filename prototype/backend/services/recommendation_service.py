from prototype.backend.schemas import Product


#Raccomandazione baseline: prodotti ordinati per popolarita
def most_popular(products: list[Product],limit: int=10) -> list[Product]:
    ordered=sorted(products,key=lambda product: product.popularity_score,reverse=True)
    return ordered[:limit]
