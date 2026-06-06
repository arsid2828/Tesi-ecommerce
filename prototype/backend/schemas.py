from pydantic import BaseModel


#schema prodotto usato da API e catalogo JSON
class Product(BaseModel): #singolo prodotto
    item_id: str
    title: str
    category: str
    description: str | None=None
    price: float | None=None
    average_rating: float | None=None
    rating_count: int=0
    popularity_score: float=0.0
    image_url: str | None=None


#schema categoria con numero di prodotti
class CategorySummary(BaseModel):
    category: str
    count: int


#schema risposta per health check
class HealthResponse(BaseModel):
    status: str


#richiesta per ricerca assistita da Gemini
class AISearchRequest(BaseModel):
    query: str=""
    question: str | None=None
    category: str | None=None
    limit: int=10


#risultato prodotto con spiegazione AI opzionale
class AISearchResult(Product):
    ai_score: float | None=None
    ai_reason: str | None=None


#risposta completa del nuovo endpoint AI
class AISearchResponse(BaseModel):
    query: str
    question: str | None=None
    mode: str
    answer: str
    results: list[AISearchResult]
    fallback: bool=False
