from prototype.backend.schemas import Product #schema product


#Raccomandazione baseline: prodotti ordinati per popolarita decrescente
#Non usa profili utente,quindi e una baseline MostPopular pura
#Serve come confronto semplice per funzioni piu avanzate
def most_popular(products: list[Product],limit: int=10) -> list[Product]:
    ordered=sorted(products,key=lambda product: product.popularity_score,reverse=True) #crea copia ordinata senza mutare input
    return ordered[:limit]
