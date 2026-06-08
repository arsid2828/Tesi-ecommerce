import json
import math
from collections import Counter #per contare occorrenze di ogni categoria
from pathlib import Path 

from prototype.backend.schemas import CategorySummary,Product #schemi pydantic definiti nel backend


#Classe che gestisce il catalogo dei prodotti
#Carica il JSON una volta e crea anche un indice item_id->Product
#Il catalogo viene tenuto in memoria per rendere veloci le API demo
class CatalogService:
    def __init__(self,data_path: Path):
        self.data_path=data_path #salva percorso del file
        self._products=self._load_products() #carica i prodotti dal json
        self._by_id={product.item_id: product for product in self._products} #lookup O(1) per dettaglio prodotto

    #Carichiamo il JSON e ordiniamo per popolarita
    #Scartiamo prodotti senza prezzo per evitare card poco realistiche
    #Se il file manca,il backend resta avviabile con lista vuota
    def _load_products(self) -> list[Product]:
        #se il file manca il prototipo parte con catalogo vuoto
        if not self.data_path.exists():
            return []

        #leggiamo i record dal file demo
        with self.data_path.open("r",encoding="utf-8") as file:
            rows=json.load(file) #lista di dizionari

        #prende ogni riga del json, la pulisce e la trasforma in un ogg Product, ** serve a spacchettare come parametri
        products=[Product(**self._clean_row(row)) for row in rows] #** passa le chiavi del dict ai campi Pydantic
        products=[product for product in products if self._has_price(product)]
        return sorted(products,key=lambda item: item.popularity_score,reverse=True) #ordina per popolarità

    #Ripuliamo valori NaN letti dal JSON demo
    #Pydantic e JSON non gestiscono bene NaN come valore valido
    #Convertire a None rende le risposte API serializzabili
    def _clean_row(self,row: dict) -> dict:
        return {key:self._clean_value(value) for key,value in row.items()} #applica la pulizia campo per campo

    #convertiamo NaN in None per Pydantic e JSON validi
    @staticmethod
    def _clean_value(value):
        if isinstance(value,float) and math.isnan(value): #float e nan, converte in None
            return None
        return value

    #teniamo nel sito solo prodotti con prezzo disponibile
    @staticmethod
    def _has_price(product: Product) -> bool:
        return product.price is not None and product.price > 0

    #restituiamo lista di prodotti filtrati e paginati
    def list_products(
        self,
        limit: int=30, #max prodotti nella pagina
        offset: int=0, #da che posizione iniziare
        category: str | None=None, #categoria, opzionale
    ) -> list[Product]: 
        products=self._filter_by_category(self._products,category) #filtra se c'è categoria
        return products[offset:offset + limit] #slice, da offset a offset+limit 

    #recuperiamo un prodotto singolo tramite item_id
    def get_product(self,item_id: str) -> Product | None:
        return self._by_id.get(item_id)

    #Calcoliamo le categorie disponibili
    #Counter aggrega i prodotti per categoria
    #La lista finale e ordinata alfabeticamente per rendere stabile la select
    def categories(self) -> list[CategorySummary]:
        counts=Counter(product.category for product in self._products) #conteggio per categoria
        return [
            CategorySummary(category=category,count=count) #ogni categoria trasformata in oggetto pydantic
            for category,count in sorted(counts.items(),key=lambda row: row[0].lower()) #ordina categorie alfabeticamente, ignorando maiuscole
        ]

    #restituiamo i prodotti gia ordinati per popolarita, top20
    def popular(self,limit: int=20) -> list[Product]:
        return self._products[:limit]

    #restituiamo una copia della lista prodotti
    def all_products(self) -> list[Product]:
        return list(self._products)

    #Applichiamo il filtro categoria quando presente
    #Il confronto e case-insensitive per evitare differenze tra UI e dataset
    #Senza categoria restituiamo la lista originale gia ordinata
    @staticmethod
    def _filter_by_category(products: list[Product],category: str | None) -> list[Product]:
        #senza categoria manteniamo tutti i prodotti
        if not category:
            return products
        normalized=category.lower() #in minuscolo
        return [product for product in products if product.category.lower() == normalized] #filtra solo prod che hanno categoria che coincide, case insensitive
