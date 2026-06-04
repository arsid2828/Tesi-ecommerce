from pathlib import Path

from fastapi import FastAPI,HTTPException,Query
from fastapi.middleware.cors import CORSMiddleware

from prototype.backend.schemas import CategorySummary,HealthResponse,Product
from prototype.backend.services.catalog_service import CatalogService
from prototype.backend.services.recommendation_service import most_popular
from prototype.backend.services.search_service import search_products


#Percorso del catalogo demo usato dal backend
DATA_PATH=Path(__file__).resolve().parents[1] / "data" / "products_demo.json"

#Creiamo l'app FastAPI del prototipo
app=FastAPI(title="E-commerce Product Discovery Prototype")

#Abilitiamo CORS per il frontend locale
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#Carichiamo il catalogo una volta all'avvio
catalog=CatalogService(DATA_PATH)


#Endpoint di controllo dello stato del backend
@app.get("/health",response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


#Endpoint catalogo con paginazione e filtro categoria
@app.get("/products",response_model=list[Product])
def products(
    limit: int=Query(default=30,ge=1,le=200),
    offset: int=Query(default=0,ge=0),
    category: str | None=None,
) -> list[Product]:
    return catalog.list_products(limit=limit,offset=offset,category=category)


#Endpoint dettaglio prodotto tramite item_id
@app.get("/products/{item_id}",response_model=Product)
def product_detail(item_id: str) -> Product:
    product=catalog.get_product(item_id)
    #Se il prodotto non esiste restituiamo 404
    if product is None:
        raise HTTPException(status_code=404,detail="Product not found")
    return product


#Endpoint lista categorie con conteggio prodotti
@app.get("/categories",response_model=list[CategorySummary])
def categories() -> list[CategorySummary]:
    return catalog.categories()


#Endpoint prodotti piu popolari
@app.get("/popular",response_model=list[Product])
def popular(limit: int=Query(default=20,ge=1,le=200)) -> list[Product]:
    return catalog.popular(limit=limit)


#Endpoint ricerca testuale base
@app.get("/search",response_model=list[Product])
def search(
    q: str="",
    category: str | None=None,
    limit: int=Query(default=30,ge=1,le=200),
) -> list[Product]:
    return search_products(
        products=catalog.all_products(),
        query=q,
        category=category,
        limit=limit,
    )


#Endpoint raccomandazioni baseline MostPopular
@app.get("/recommendations/popular",response_model=list[Product])
def popular_recommendations(limit: int=Query(default=10,ge=1,le=200)) -> list[Product]:
    return most_popular(catalog.all_products(),limit=limit)
