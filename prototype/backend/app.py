from pathlib import Path

from fastapi import FastAPI,HTTPException,Query
from fastapi.middleware.cors import CORSMiddleware

from prototype.backend.schemas import AISearchRequest,AISearchResponse,CategorySummary,ClusteredSearchRequest,ClusteredSearchResponse,HealthResponse,Product,ProductQARequest,ProductQAResponse
from prototype.backend.services.catalog_service import CatalogService
from prototype.backend.services.ai_search_service import ai_search_products
from prototype.backend.services.clustering_service import cluster_search_results
from prototype.backend.services.product_qa_service import ProductQAService
from prototype.backend.services.search_service import search_products


#percorso del catalogo demo usato dal backend
DATA_PATH=Path(__file__).resolve().parents[1] / "data" / "products_demo.json"
DATA_DIR=DATA_PATH.parent

#creiamo l'app FastAPI del prototipo
app=FastAPI(title="E-commerce Product Discovery Prototype")

#abilitiamo CORS per il frontend locale
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#carichiamo il catalogo una volta all'avvio
catalog=CatalogService(DATA_PATH)
product_qa_service=ProductQAService(DATA_DIR)


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


#endpoint dettaglio prodotto tramite item_id
@app.get("/products/{item_id}",response_model=Product)
def product_detail(item_id: str) -> Product:
    product=catalog.get_product(item_id)
    #se il prodotto non esiste restituiamo 404
    if product is None:
        raise HTTPException(status_code=404,detail="Product not found")
    return product


#endpoint QA grounded sui dati disponibili del prodotto
@app.post("/products/{item_id}/qa",response_model=ProductQAResponse)
def product_qa(item_id: str,request: ProductQARequest) -> ProductQAResponse:
    product=catalog.get_product(item_id)
    if product is None:
        raise HTTPException(status_code=404,detail="Product not found")
    if not request.question.strip():
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


#endpoint ricerca testuale base
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


#endpoint ricerca con clustering locale e label AI opzionali
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


#endpoint ricerca assistita da Gemini con fallback locale
@app.post("/ai-search",response_model=AISearchResponse)
def ai_search(request: AISearchRequest) -> AISearchResponse:
    return ai_search_products(
        products=catalog.all_products(),
        query=request.query,
        question=request.question,
        category=request.category,
        limit=request.limit,
    )


