from pathlib import Path

from fastapi import FastAPI,HTTPException,Query
from fastapi.middleware.cors import CORSMiddleware

from prototype.backend.schemas import AISearchRequest,AISearchResponse,CategorySummary,HealthResponse,Product
from prototype.backend.services.catalog_service import CatalogService
from prototype.backend.services.ai_search_service import ai_search_products
from prototype.backend.services.search_service import search_products


#percorso del catalogo demo usato dal backend
DATA_PATH=Path(__file__).resolve().parents[1] / "data" / "products_demo.json"

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


