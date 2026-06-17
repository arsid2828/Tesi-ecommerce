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


#schema risposta per health check
class HealthResponse(BaseModel):
    status: str


#Richiesta per la nuova product discovery AI-first
#La query e l'unico input utente: niente filtri manuali nel frontend
class DiscoverySearchRequest(BaseModel):
    query: str=""
    limit: int=Field(default=80,ge=1,le=200)
    use_ai_support: bool=True


#Evidenza locale usata per spiegare un prodotto in un ruolo
#source resta tecnica,source_label e il testo leggibile per la UI
class DiscoveryEvidence(BaseModel):
    source: str
    source_label: str
    text: str
    score: float


#Prodotto arricchito con motivazione ed evidenze locali
class DiscoveryProduct(Product):
    role_reason: str
    match_score: float
    evidence_sources: list[str]=Field(default_factory=list)
    evidence: list[DiscoveryEvidence]=Field(default_factory=list)


#Gruppo/cluster costruito per ruolo d'acquisto
#I prodotti sono scelti localmente; Gemini puo solo aiutare con copy e label
class DiscoveryRoleGroup(BaseModel):
    role_id: str
    label: str
    description: str
    size: int
    keywords: list[str]=Field(default_factory=list)
    products: list[DiscoveryProduct]
    reason: str | None=None


#Risposta della discovery a ruoli
class DiscoverySearchResponse(BaseModel):
    query: str
    answer: str
    total_candidates: int
    groups: list[DiscoveryRoleGroup]
    source_summary: dict[str,int]=Field(default_factory=dict)
    used_ai_support: bool=False
    fallback: bool=False


#Evidenza testuale recuperata localmente da QA/recensioni per spiegare la discovery
class ProductQAEvidence(BaseModel):
    source: str
    text: str
    score: float
