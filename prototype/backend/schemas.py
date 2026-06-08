from pydantic import BaseModel,Field


#Schema prodotto usato da API e catalogo JSON
#I default gestiscono valori mancanti nel dataset senza rompere le risposte
#Questa classe e il contratto comune tra backend,frontend e servizi
class Product(BaseModel):
    item_id: str
    title: str
    category: str
    description: str | None=None
    price: float | None=None
    average_rating: float | None=None
    rating_count: int=0
    popularity_score: float=0.0
    image_url: str | None=None


#Profilo demo usato per scegliere il comportamento del recommender
#Il profilo caldo usa uno user_idx reale del dataset
#Il profilo cold start non ha storico e usa solo popularity
class RecommendationProfile(BaseModel):
    profile_id: str
    label: str
    description: str
    model: str
    user_idx: int | None=None
    user_id: str | None=None
    cold_start: bool=False


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


#Richiesta per ricerca con clustering sui risultati gia filtrati
#Field impone limiti direttamente nello schema,prima che arrivi alla logica
#Questo evita richieste troppo grandi o non valide
class ClusteredSearchRequest(BaseModel):
    query: str=""
    category: str | None=None
    limit: int=Field(default=40,ge=1,le=600) #vincola il numero di risultati accettato
    use_ai_labels: bool=True


#Singolo cluster di prodotti
#products contiene gli oggetti originali,non solo gli id
#keywords e reason servono per rendere spiegabile il raggruppamento
class ProductCluster(BaseModel):
    cluster_id: str
    label: str
    description: str
    size: int
    keywords: list[str]
    products: list[Product]
    reason: str | None=None


#risposta della ricerca clusterizzata
class ClusteredSearchResponse(BaseModel):
    query: str
    total_results: int
    clustered: bool
    clusters: list[ProductCluster]
    used_ai_labels: bool=False
    fallback: bool=False


#richiesta per QA grounded sul prodotto
class ProductQARequest(BaseModel):
    question: str
    use_ai: bool=True


#evidenza testuale usata nella risposta QA
class ProductQAEvidence(BaseModel):
    source: str
    text: str
    score: float


#Risposta QA del prodotto
#evidence mantiene traccia dei testi usati,cosi la risposta resta verificabile
#used_ai separa risposta generata da fallback locale
class ProductQAResponse(BaseModel):
    item_id: str
    question: str
    answer: str
    confidence: str
    used_ai: bool
    evidence: list[ProductQAEvidence]
