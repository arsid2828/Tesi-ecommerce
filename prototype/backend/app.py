from pathlib import Path

from fastapi import FastAPI,HTTPException,Query
from fastapi.middleware.cors import CORSMiddleware

from prototype.backend.schemas import AISearchRequest,AISearchResponse,CategorySummary,ClusteredSearchRequest,ClusteredSearchResponse,HealthResponse,Product,ProductQARequest,ProductQAResponse,RecommendationProfile
from prototype.backend.services.catalog_service import CatalogService
from prototype.backend.services.ai_search_service import ai_search_products
from prototype.backend.services.clustering_service import cluster_search_results
from prototype.backend.services.product_qa_service import ProductQAService
from prototype.backend.services.recommendation_service import DEMO_COLD_START_PROFILE_ID,DEMO_HYBRID_PROFILE_ID,RecommendationService
from prototype.backend.services.search_service import search_products


#Configuriamo i percorsi dei dati usati dal backend
#Il catalogo viene letto da JSON,mentre QA/review opzionali stanno nella stessa cartella
#Assumiamo che app.py resti dentro prototype/backend
DATA_PATH=Path(__file__).resolve().parents[1] / "data" / "products_demo.json" #risale a prototype e punta al catalogo
DATA_DIR=DATA_PATH.parent #cartella base per sorgenti QA/review
RECOMMENDER_DIR=Path(__file__).resolve().parents[2] / "data" / "processed" / "electronics_recommender" #artifact notebook 03-05

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
recommendation_service=RecommendationService(RECOMMENDER_DIR,catalog_products=catalog.all_products()) #limita consigli ai prodotti del sito


#endpoint di controllo dello stato del backend
@app.get("/health",response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


#endpoint catalogo con paginazione e filtro categoria
@app.get("/products",response_model=list[Product])
def products(
    limit: int=Query(default=30,ge=1,le=600),
    offset: int=Query(default=0,ge=0),
    category: str | None=None,
) -> list[Product]:
    return catalog.list_products(limit=limit,offset=offset,category=category)


#Endpoint dettaglio prodotto tramite item_id
#Se l'id non esiste usiamo HTTP 404,cosi il frontend distingue errore da prodotto vuoto
#La risposta e validata dallo schema Product
@app.get("/products/{item_id}",response_model=Product)
def product_detail(item_id: str) -> Product:
    product=catalog.get_product(item_id)
    if product is None:
        product=recommendation_service.get_product(item_id) #fallback per prodotti raccomandati dal dataset Electronics
    #se il prodotto non esiste restituiamo 404
    if product is None:
        raise HTTPException(status_code=404,detail="Product not found")
    return product


#Endpoint QA grounded sui dati disponibili del prodotto
#Prima validiamo prodotto e domanda,poi deleghiamo il retrieval al servizio dedicato
#Il parametro use_ai permette fallback locale quando Gemini non e disponibile
@app.post("/products/{item_id}/qa",response_model=ProductQAResponse)
def product_qa(item_id: str,request: ProductQARequest) -> ProductQAResponse:
    product=catalog.get_product(item_id)
    if product is None:
        product=recommendation_service.get_product(item_id)
    if product is None:
        raise HTTPException(status_code=404,detail="Product not found")
    if not request.question.strip(): #evita richieste vuote che renderebbero inutile il retrieval
        raise HTTPException(status_code=400,detail="Question is required")
    return product_qa_service.answer_question(
        product=product,
        question=request.question,
        use_ai=request.use_ai,
    )


#endpoint lista categorie con conteggio prodotti
@app.get("/categories",response_model=list[CategorySummary])
def categories() -> list[CategorySummary]:
    return catalog.categories()


#endpoint prodotti piu popolari
@app.get("/popular",response_model=list[Product])
def popular(limit: int=Query(default=20,ge=1,le=200)) -> list[Product]:
    return catalog.popular(limit=limit)


#Endpoint profili demo per il recommender
#Il frontend lo usa per scegliere tra utente caldo ibrido e cold start
#I profili sono fissi e riproducibili per la demo
@app.get("/recommendation-profiles",response_model=list[RecommendationProfile])
def recommendation_profiles() -> list[RecommendationProfile]:
    return recommendation_service.profiles()


#Endpoint raccomandazioni generali
#Default: profilo caldo con HybridGrid_SVD4_010_Content_035_Pop_055
#Cold start: profilo senza storico che usa MostPopular baseline
@app.get("/recommendations",response_model=list[Product])
def recommendations(
    profile_id: str | None=DEMO_HYBRID_PROFILE_ID,
    limit: int=Query(default=12,ge=1,le=200),
) -> list[Product]:
    return recommendation_service.recommend(profile_id=profile_id,limit=limit)


#Endpoint compatibility per popup estensione e vecchie note
#Espone esplicitamente la baseline popularity del recommender
#Resta diverso da /popular,che usa il catalogo locale demo
@app.get("/recommendations/popular",response_model=list[Product])
def recommendation_popular(limit: int=Query(default=12,ge=1,le=200)) -> list[Product]:
    return recommendation_service.recommend(profile_id=DEMO_COLD_START_PROFILE_ID,limit=limit)


#Endpoint ricerca testuale base
#Usa il catalogo gia caricato e applica filtri semplici lato backend
#L'ordinamento finale resta popularity-based per essere spiegabile
@app.get("/search",response_model=list[Product])
def search(
    q: str="",
    category: str | None=None,
    limit: int=Query(default=30,ge=1,le=600),
) -> list[Product]:
    return search_products(
        products=catalog.all_products(),
        query=q,
        category=category,
        limit=limit,
    )


#Endpoint ricerca con clustering locale e label AI opzionali
#Prima recuperiamo risultati testuali,poi clusterizziamo solo quel sottoinsieme
#L'AI puo rinominare i cluster ma non sceglie prodotti o membership
@app.post("/search/clustered",response_model=ClusteredSearchResponse)
def clustered_search(request: ClusteredSearchRequest) -> ClusteredSearchResponse:
    results=search_products(
        products=catalog.all_products(),
        query=request.query,
        category=request.category,
        limit=request.limit,
    )
    return cluster_search_results(
        products=results,
        query=request.query,
        use_ai_labels=request.use_ai_labels,
    )


#Endpoint ricerca assistita da Gemini con fallback locale
#Gemini lavora su candidati locali gia filtrati,non sul catalogo intero
#Se la chiamata AI fallisce,la risposta resta utile con risultati locali
@app.post("/ai-search",response_model=AISearchResponse)
def ai_search(request: AISearchRequest) -> AISearchResponse:
    return ai_search_products(
        products=catalog.all_products(),
        query=request.query,
        question=request.question,
        category=request.category,
        limit=request.limit,
    )


