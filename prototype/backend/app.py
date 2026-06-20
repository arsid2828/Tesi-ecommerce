from pathlib import Path

from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware

from prototype.backend.schemas import (
    AmazonRecommendationsRequest,
    AmazonRecommendationsResponse,
    ContextualRecommendationsResponse,
    DiscoverySearchRequest,
    DiscoverySearchResponse,
    HealthResponse,
    Product,
)
from prototype.backend.services.catalog_service import CatalogService
from prototype.backend.services.discovery_service import discover_products
from prototype.backend.services.product_qa_service import ProductQAService
from prototype.backend.services.recommendation_service import (
    contextual_recommendations,
    organize_amazon_recommendations,
    popular_products,
)


#Configuriamo i percorsi dei dati usati dal backend
#Il catalogo viene letto da JSON,mentre QA/review opzionali stanno nella stessa cartella
#Assumiamo che app.py resti dentro prototype/backend
DATA_PATH=Path(__file__).resolve().parents[1] / "data" / "products_demo.json" #risale a prototype e punta al catalogo
DATA_DIR=DATA_PATH.parent #cartella base per sorgenti QA/review

#Creiamo l'app FastAPI del prototipo
#Qui definiamo anche CORS per permettere al frontend statico di chiamare il backend
#La configurazione e aperta per una demo locale,non per produzione
app=FastAPI(title="E-commerce Product Discovery Prototype")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#Carichiamo servizi condivisi una sola volta all'avvio
#Gli endpoint riusano queste istanze invece di rileggere i file a ogni richiesta
#Questo rende la demo piu veloce ma richiede riavvio se cambiano i dati
catalog=CatalogService(DATA_PATH) #indicizza prodotti per item_id
product_qa_service=ProductQAService(DATA_DIR) #precarica sorgenti QA/review opzionali


#endpoint di controllo dello stato del backend
@app.get("/health",response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


#Endpoint dettaglio prodotto tramite item_id
#Se l'id non esiste usiamo HTTP 404,cosi il frontend distingue errore da prodotto vuoto
#La risposta e validata dallo schema Product
@app.get("/products/{item_id}",response_model=Product)
def product_detail(item_id: str) -> Product:
    product=catalog.get_product(item_id)
    #se il prodotto non esiste restituiamo 404
    if product is None:
        raise HTTPException(status_code=404,detail="Product not found")
    return product


#Endpoint baseline di popolarita usato come fallback da frontend/estensione
@app.get("/popular",response_model=list[Product])
def popular(limit: int=10) -> list[Product]:
    safe_limit=max(1,min(int(limit or 10),50))
    return popular_products(catalog.all_products(),limit=safe_limit)


#Alias semantico per raccomandazioni popolari
@app.get("/recommendations/popular",response_model=list[Product])
def recommendations_popular(limit: int=10) -> list[Product]:
    return popular(limit=limit)


#Raccomandazioni contestuali per estensione su pagine prodotto locali
#I prodotti sono scelti solo dal dataset locale; Gemini puo solo rifinire copy e label
@app.get("/recommendations/contextual/{item_id}",response_model=ContextualRecommendationsResponse)
def recommendations_contextual(
    item_id: str,
    limit: int=4,
    use_ai_support: bool=True,
) -> ContextualRecommendationsResponse:
    response=contextual_recommendations(
        products=catalog.all_products(),
        item_id=item_id,
        evidence_service=product_qa_service,
        limit=limit,
        use_ai_support=use_ai_support,
    )
    if response is None:
        raise HTTPException(status_code=404,detail="Product not found")
    return response


#Organizza prodotti Amazon reali gia estratti dalla pagina corrente dell'utente
#Il backend non inventa prodotti Amazon: se la pagina non espone candidati,restituisce gruppi vuoti
@app.post("/amazon/recommendations",response_model=AmazonRecommendationsResponse)
def amazon_recommendations(request: AmazonRecommendationsRequest) -> AmazonRecommendationsResponse:
    return organize_amazon_recommendations(
        product=request.product,
        candidates=request.candidates,
        limit=request.limit,
        use_ai_support=request.use_ai_support,
    )


#Nuova ricerca AI-first: un solo input testuale e output a ruoli
#La scelta prodotti resta locale; Gemini puo solo rifinire copy e label
@app.post("/discover",response_model=DiscoverySearchResponse)
def discover(request: DiscoverySearchRequest) -> DiscoverySearchResponse:
    return discover_products(
        products=catalog.all_products(),
        query=request.query,
        evidence_service=product_qa_service,
        limit=request.limit,
        use_ai_support=request.use_ai_support,
    )


