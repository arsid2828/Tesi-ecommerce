import json
import math
from pathlib import Path

from prototype.backend.schemas import Product


class CatalogService:
    def __init__(self,data_path: Path):
        self.data_path=data_path
        self._products=self._load_products()
        self._by_id={product.item_id: product for product in self._products}

    def _load_products(self) -> list[Product]:
        if not self.data_path.exists():
            return []

        with self.data_path.open("r",encoding="utf-8") as file:
            rows=json.load(file)

        products=[Product(**self._clean_row(row)) for row in rows]
        products=[product for product in products if self._has_price(product)]
        return sorted(products,key=lambda item: item.popularity_score,reverse=True)

    def get_product(self,item_id: str) -> Product | None:
        return self._by_id.get(item_id)

    def all_products(self) -> list[Product]:
        return list(self._products)

    def _clean_row(self,row: dict) -> dict:
        return {key:self._clean_value(value) for key,value in row.items()}

    @staticmethod
    def _clean_value(value):
        if isinstance(value,float) and math.isnan(value):
            return None
        return value

    @staticmethod
    def _has_price(product: Product) -> bool:
        return product.price is not None and product.price > 0
