from prototype.backend.schemas import Product #schema product


#raccomandazione baseline: prodotti ordinati per popolarità decrescente
def most_popular(products: list[Product],limit: int=10) -> list[Product]:
    ordered=sorted(products,key=lambda product: product.popularity_score,reverse=True) #fa copia ordinata
    return ordered[:limit]
