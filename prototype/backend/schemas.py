from pydantic import BaseModel


#Schema prodotto usato da API e catalogo JSON
class Product(BaseModel):
    item_id: str
    title: str
    category: str
    description: str | None=None
    average_rating: float | None=None
    rating_count: int=0
    popularity_score: float=0.0
    image_url: str | None=None


#Schema categoria con numero di prodotti
class CategorySummary(BaseModel):
    category: str
    count: int


#Schema risposta per health check
class HealthResponse(BaseModel):
    status: str
