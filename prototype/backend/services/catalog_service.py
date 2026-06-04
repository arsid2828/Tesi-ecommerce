import json
import math
from collections import Counter
from pathlib import Path

from prototype.backend.schemas import CategorySummary,Product


#Servizio per caricare e leggere il catalogo demo
class CatalogService:
    #Inizializziamo cache prodotti e indice per item_id
    def __init__(self,data_path: Path):
        self.data_path=data_path
        self._products=self._load_products()
        self._by_id={product.item_id: product for product in self._products}

    #Carichiamo il JSON e ordiniamo per popolarita
    def _load_products(self) -> list[Product]:
        #Se il file manca il prototipo parte con catalogo vuoto
        if not self.data_path.exists():
            return []

        #Leggiamo i record dal file demo
        with self.data_path.open("r",encoding="utf-8") as file:
            rows=json.load(file)

        #Convertiamo i record in schema Product
        products=[Product(**self._clean_row(row)) for row in rows]
        return sorted(products,key=lambda item: item.popularity_score,reverse=True)

    #Ripuliamo valori NaN letti dal JSON demo
    def _clean_row(self,row: dict) -> dict:
        return {key:self._clean_value(value) for key,value in row.items()}

    #Convertiamo NaN in None per Pydantic e JSON validi
    @staticmethod
    def _clean_value(value):
        if isinstance(value,float) and math.isnan(value):
            return None
        return value

    #Restituiamo prodotti filtrati e paginati
    def list_products(
        self,
        limit: int=30,
        offset: int=0,
        category: str | None=None,
    ) -> list[Product]:
        products=self._filter_by_category(self._products,category)
        return products[offset:offset + limit]

    #Recuperiamo un prodotto singolo tramite item_id
    def get_product(self,item_id: str) -> Product | None:
        return self._by_id.get(item_id)

    #Calcoliamo le categorie disponibili
    def categories(self) -> list[CategorySummary]:
        counts=Counter(product.category for product in self._products)
        return [
            CategorySummary(category=category,count=count)
            for category,count in sorted(counts.items(),key=lambda row: row[0].lower())
        ]

    #Restituiamo i prodotti gia ordinati per popolarita
    def popular(self,limit: int=20) -> list[Product]:
        return self._products[:limit]

    #Restituiamo una copia della lista prodotti
    def all_products(self) -> list[Product]:
        return list(self._products)

    #Applichiamo il filtro categoria quando presente
    @staticmethod
    def _filter_by_category(products: list[Product],category: str | None) -> list[Product]:
        #Senza categoria manteniamo tutti i prodotti
        if not category:
            return products
        normalized=category.lower()
        return [product for product in products if product.category.lower() == normalized]
