import json
from pathlib import Path
from typing import Any

from prototype.backend.schemas import (
    HomeProfile,
    HomeRecommendationProduct,
    HomeRecommendationsResponse,
    Product,
)
from prototype.backend.services.recommendation_service import popular_products


# Servizio delle due home dimostrative.
# Legge profili e ranking pre-esportati senza caricare matrici recommender durante la demo.
class HomeRecommendationService:
    # Carica il file home_profiles.json e crea indice per profile_id.
    # Il backend puo cosi rispondere velocemente a cold-start e utente storico.
    def __init__(self,profiles_path: Path):
        self.profiles_path=profiles_path
        self._rows=self._load_rows()
        self._by_id={str(row["profile_id"]):row for row in self._rows}

    # Legge il payload JSON dei profili home.
    # Se il file manca restituisce lista vuota e gli endpoint gestiscono il caso senza crash.
    def _load_rows(self) -> list[dict[str,Any]]:
        if not self.profiles_path.exists():
            return []
        payload=json.loads(self.profiles_path.read_text(encoding="utf-8"))
        return list(payload.get("profiles",[]))

    # Restituisce i profili disponibili alla UI.
    # Sono validati dallo schema HomeProfile prima di arrivare al frontend.
    def profiles(self) -> list[HomeProfile]:
        return [HomeProfile(**row) for row in self._rows]

    # Costruisce le raccomandazioni della home selezionata.
    # Cold-start usa Popular, mentre il profilo dataset usa ranking ibrido esportato.
    def recommendations(
        self,
        profile_id: str,
        products: list[Product],
        limit: int=24,
    ) -> HomeRecommendationsResponse | None:
        row=self._by_id.get(profile_id)
        if row is None:
            return None

        safe_limit=max(1,min(int(limit or 24),24))
        profile=HomeProfile(**row)
        if profile.profile_type == "cold_start":
            ranked=self._popular_recommendations(products,safe_limit)
        else:
            ranked=self._hybrid_recommendations(row,products,safe_limit)
        return HomeRecommendationsResponse(profile=profile,products=ranked)

    # Genera prodotti home per il profilo senza storico.
    # Ogni item riceve rank, score e motivazione della baseline Popular.
    @staticmethod
    def _popular_recommendations(
        products: list[Product],
        limit: int,
    ) -> list[HomeRecommendationProduct]:
        ranked=popular_products(products,limit=limit)
        return [
            HomeRecommendationProduct(
                **HomeRecommendationService._product_data(product),
                rank=rank,
                recommendation_score=round(float(product.popularity_score),6),
                recommendation_reason=(
                    "Popular baseline: posizione determinata solo dalla popolarità osservata nel catalogo."
                ),
            )
            for rank,product in enumerate(ranked,start=1)
        ]

    # Genera prodotti home per l'utente storico.
    # Incrocia item_id raccomandati con il catalogo demo filtrato e acquistabile.
    @staticmethod
    def _hybrid_recommendations(
        profile_row: dict[str,Any],
        products: list[Product],
        limit: int,
    ) -> list[HomeRecommendationProduct]:
        products_by_id={product.item_id:product for product in products}
        ranked=[]
        for recommendation in profile_row.get("recommendations",[]):
            product=products_by_id.get(str(recommendation.get("item_id","")))
            if product is None:
                continue
            components=recommendation.get("components",{})
            ranked.append(
                HomeRecommendationProduct(
                    **HomeRecommendationService._product_data(product),
                    rank=len(ranked)+1,
                    recommendation_score=round(float(recommendation.get("score",0.0)),6),
                    recommendation_reason=(
                        "Ibrido: "
                        f"contenuto {float(components.get('content',0.0)):.0%}, "
                        f"SVD {float(components.get('svd',0.0)):.0%}, "
                        f"popolarità {float(components.get('popularity',0.0)):.0%}."
                    ),
                )
            )
            if len(ranked) >= limit:
                break
        return ranked

    # Converte un Product in dizionario compatibile con Pydantic v1/v2.
    # Serve a creare modelli estesi senza dipendere dalla versione installata.
    @staticmethod
    def _product_data(product: Product) -> dict[str,Any]:
        if hasattr(product,"model_dump"):
            return product.model_dump()
        return product.dict()
