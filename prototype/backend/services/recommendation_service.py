import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from prototype.backend.schemas import Product,RecommendationProfile #schema product


HYBRID_MODEL_NAME="HybridGrid_SVD4_010_Content_035_Pop_055"
DEMO_HYBRID_PROFILE_ID="demo_hybrid"
DEMO_COLD_START_PROFILE_ID="demo_cold_start"
DEMO_USER_IDX=14054
HYBRID_WEIGHTS={"svd":0.10,"content":0.35,"popularity":0.55}


#Raccomandazione baseline: prodotti ordinati per popolarita decrescente
#Non usa profili utente,quindi e una baseline MostPopular pura
#Serve come confronto semplice per funzioni piu avanzate
def most_popular(products: list[Product],limit: int=10) -> list[Product]:
    ordered=sorted(products,key=lambda product: product.popularity_score,reverse=True) #crea copia ordinata senza mutare input
    return ordered[:limit]


#Servizio recommender collegato agli artifact dei notebook 04/05
#Per il profilo demo caldo calcola l'ibrido SVD+Content+Popularity
#Per il cold start usa solo la baseline di popolarita
class RecommendationService:
    def __init__(self,recommender_dir: Path,catalog_products: list[Product] | None=None):
        self.recommender_dir=recommender_dir
        self.models_dir=recommender_dir / "notebook04_models"
        self.hybrid_dir=recommender_dir / "notebook05_content_hybrid"
        self._products_by_item_idx: dict[int,Product]={}
        self._products_by_item_id: dict[str,Product]={}
        self._item_idx_by_item_id: dict[str,int]={}
        self._catalog_products_by_item_id: dict[str,Product]={}
        self._catalog_item_idxs=np.array([],dtype=np.int64)
        self._popularity_by_item_idx: dict[int,float]={}
        self._seen_by_user: dict[int,set[int]]={}
        self._user_id_by_idx: dict[int,str]={}
        self._all_item_idxs=np.array([],dtype=np.int64)
        self._max_popularity=0.0
        self._hybrid_artifacts_loaded=False
        self._svd_user_embeddings=None
        self._svd_item_embeddings=None
        self._item_tfidf_matrix=None
        self._user_content_profiles=None
        self._load_light_artifacts()
        if catalog_products is not None:
            self.set_catalog_products(catalog_products)

    #Carichiamo metadati e popularity subito per rendere disponibile il cold start
    #Gli artifact pesanti sparse/numpy vengono caricati solo al primo uso ibrido
    #Se qualche file manca,il servizio resta avviabile ma con meno raccomandazioni
    def _load_light_artifacts(self) -> None:
        self._load_products()
        self._load_popularity()
        self._load_demo_user()
        self._load_seen_items()

    #Trasformiamo items.parquet del recommender in Product compatibili col frontend
    #Il catalogo recommender e piu ampio del products_demo.json locale
    #Questi prodotti servono soprattutto per card consigliate e pagina dettaglio
    def _load_products(self) -> None:
        items_path=self.recommender_dir / "items.parquet"
        if not items_path.exists():
            return
        items_df=pd.read_parquet(items_path)
        for row in items_df.to_dict(orient="records"):
            product=self._row_to_product(row)
            item_idx=_safe_int(row.get("item_idx"))
            if item_idx is None:
                continue
            self._products_by_item_idx[item_idx]=product
            self._products_by_item_id[product.item_id]=product
            self._item_idx_by_item_id[product.item_id]=item_idx
        self._all_item_idxs=np.array(sorted(self._products_by_item_idx),dtype=np.int64)

    #Limitiamo le raccomandazioni ai prodotti realmente mostrati nel sito
    #HybridGrid puo scoreare solo item presenti anche negli artifact del recommender
    #L'output usa il Product del catalogo demo,cosi prezzo e dettagli restano coerenti
    def set_catalog_products(self,products: list[Product]) -> None:
        self._catalog_products_by_item_id={product.item_id:product for product in products}
        item_idxs=[
            self._item_idx_by_item_id[item_id]
            for item_id in self._catalog_products_by_item_id
            if item_id in self._item_idx_by_item_id
        ]
        self._catalog_item_idxs=np.array(sorted(set(item_idxs)),dtype=np.int64)

    #Leggiamo score di popolarita calcolati nel notebook
    #Lo score originale e un conteggio/interazione,qui lo normalizziamo solo nel Product
    #Per il ranking cold start usiamo il valore originale
    def _load_popularity(self) -> None:
        popularity_path=self.hybrid_dir / "popularity_scores.parquet"
        if not popularity_path.exists():
            popularity_path=self.models_dir / "popularity_scores.parquet"
        if not popularity_path.exists():
            return
        popularity_df=pd.read_parquet(popularity_path)
        self._popularity_by_item_idx={
            int(row.item_idx):float(row.popularity_score)
            for row in popularity_df.itertuples(index=False)
        }
        self._max_popularity=max(self._popularity_by_item_idx.values(),default=0.0)
        for item_idx,product in self._products_by_item_idx.items():
            product.popularity_score=self._normalized_popularity(item_idx)

    #Selezioniamo uno user reale del dataset per il profilo demo caldo
    #user_idx=14054 e stato scelto perche ha molte interazioni train
    #Il mapping permette di mostrare anche l'user_id originale
    def _load_demo_user(self) -> None:
        mapping_path=self.recommender_dir / "user_mapping.parquet"
        if not mapping_path.exists():
            return
        user_df=pd.read_parquet(mapping_path,columns=["user_id","user_idx"])
        match=user_df[user_df["user_idx"] == DEMO_USER_IDX]
        if not match.empty:
            self._user_id_by_idx[DEMO_USER_IDX]=str(match.iloc[0]["user_id"])

    #Carichiamo gli item gia visti dall'utente demo
    #Li escludiamo dalle raccomandazioni per non consigliare prodotti gia positivi
    #Per il cold start non ci sono item visti da escludere
    def _load_seen_items(self) -> None:
        train_path=self.recommender_dir / "train.parquet"
        if not train_path.exists():
            return
        train_df=pd.read_parquet(train_path,columns=["user_idx","item_idx"])
        user_rows=train_df[train_df["user_idx"] == DEMO_USER_IDX]
        self._seen_by_user[DEMO_USER_IDX]=set(int(value) for value in user_rows["item_idx"].dropna())

    #Carichiamo matrici pesanti solo quando serve il profilo ibrido
    #Gli array SVD e le matrici TF-IDF sono gli stessi usati dal Notebook 05
    #La cache evita ricaricamenti nelle richieste successive
    def _load_hybrid_artifacts(self) -> None:
        if self._hybrid_artifacts_loaded:
            return
        self._svd_user_embeddings=np.load(self.models_dir / "best_svd_user_embeddings.npy",mmap_mode="r")
        self._svd_item_embeddings=np.load(self.models_dir / "best_svd_item_embeddings.npy",mmap_mode="r")
        self._item_tfidf_matrix=sparse.load_npz(self.hybrid_dir / "item_tfidf_matrix.npz")
        self._user_content_profiles=sparse.load_npz(self.hybrid_dir / "user_content_profiles.npz")
        self._hybrid_artifacts_loaded=True

    #Restituiamo i profili disponibili alla UI
    #Il primo e il default personalizzato,il secondo simula un nuovo utente
    #Entrambi sono demo deterministicamente ripetibili
    def profiles(self) -> list[RecommendationProfile]:
        return [
            RecommendationProfile(
                profile_id=DEMO_HYBRID_PROFILE_ID,
                label="Profilo demo personalizzato",
                description="Utente reale del dataset; usa HybridGrid sui prodotti del catalogo sito.",
                model=HYBRID_MODEL_NAME,
                user_idx=DEMO_USER_IDX,
                user_id=self._user_id_by_idx.get(DEMO_USER_IDX),
                cold_start=False,
            ),
            RecommendationProfile(
                profile_id=DEMO_COLD_START_PROFILE_ID,
                label="Utente demo cold start",
                description="Nessuno storico disponibile; usa solo la popularity baseline del catalogo sito.",
                model="MostPopular",
                user_idx=None,
                user_id=None,
                cold_start=True,
            ),
        ]

    #Punto unico per generare raccomandazioni
    #Il profilo cold start forza popularity baseline
    #Qualsiasi profilo non riconosciuto ricade sul demo ibrido
    def recommend(self,profile_id: str | None=None,limit: int=10) -> list[Product]:
        safe_limit=max(1,min(int(limit or 10),200))
        if profile_id == DEMO_COLD_START_PROFILE_ID:
            return self._recommend_popularity(safe_limit)
        return self._recommend_hybrid(DEMO_USER_IDX,safe_limit)

    #Recuperiamo un prodotto raccomandato tramite parent_asin
    #Serve come fallback per /products/{item_id}
    #Permette di aprire dettagli anche per item non presenti nel catalogo demo locale
    def get_product(self,item_id: str) -> Product | None:
        return self._catalog_products_by_item_id.get(item_id) or self._products_by_item_id.get(item_id)

    #Baseline cold start basata sulla popolarita del catalogo del sito
    #Senza catalogo locale ricade sugli score notebook del recommender
    #In questo modo il profilo nuovo vede solo prodotti acquistabili nella demo
    def _recommend_popularity(self,limit: int) -> list[Product]:
        if self._catalog_products_by_item_id:
            return most_popular(list(self._catalog_products_by_item_id.values()),limit=limit)
        if self._popularity_by_item_idx:
            ordered=sorted(
                self._products_by_item_idx,
                key=lambda item_idx:(-self._popularity_by_item_idx.get(item_idx,0.0),item_idx),
            )
        else:
            ordered=sorted(
                self._products_by_item_idx,
                key=lambda item_idx:(-self._products_by_item_idx[item_idx].popularity_score,item_idx),
            )
        return [self._products_by_item_idx[item_idx] for item_idx in ordered[:limit]]

    #Raccomandazione ibrida per utente caldo
    #Calcola componenti sui candidati del catalogo sito non visti dall'utente
    #Replica la min-max normalization usata nel Notebook 05
    def _recommend_hybrid(self,user_idx: int,limit: int) -> list[Product]:
        try:
            self._load_hybrid_artifacts()
            candidate_item_idxs=self._candidate_item_idxs(user_idx)
            if len(candidate_item_idxs)==0:
                return self._recommend_popularity(limit)

            content_scores=self._content_scores(user_idx,candidate_item_idxs)
            svd_scores=self._svd_scores(user_idx,candidate_item_idxs)
            popularity_scores=self._popularity_scores(candidate_item_idxs)
            final_scores=(
                HYBRID_WEIGHTS["svd"]*_minmax_normalize_scores(svd_scores)
                +HYBRID_WEIGHTS["content"]*_minmax_normalize_scores(content_scores)
                +HYBRID_WEIGHTS["popularity"]*_minmax_normalize_scores(popularity_scores)
            )
            order=np.lexsort((candidate_item_idxs,-final_scores)) #score desc,item_idx asc
            top_item_idxs=candidate_item_idxs[order[:limit]]
            products=[self._product_for_item_idx(int(item_idx)) for item_idx in top_item_idxs]
            return self._fill_with_catalog_popularity(products,limit)
        except Exception:
            return self._recommend_popularity(limit)

    #Costruiamo candidati escludendo prodotti gia visti dall'utente demo
    #L'esclusione evita raccomandazioni gia consumate nel train
    #Gli item_idx restano allineati alle righe delle matrici salvate
    def _candidate_item_idxs(self,user_idx: int) -> np.ndarray:
        base_item_idxs=self._catalog_item_idxs if len(self._catalog_item_idxs)>0 else self._all_item_idxs
        seen=self._seen_by_user.get(user_idx,set())
        if not seen:
            return base_item_idxs
        return np.array([item_idx for item_idx in base_item_idxs if int(item_idx) not in seen],dtype=np.int64)

    #Recupera il Product da mostrare in UI partendo da item_idx del recommender
    #Quando il prodotto e nel catalogo demo preferiamo quella versione
    #Questo evita prezzi mancanti o metadati diversi rispetto al sito
    def _product_for_item_idx(self,item_idx: int) -> Product:
        product=self._products_by_item_idx[item_idx]
        return self._catalog_products_by_item_id.get(product.item_id,product)

    #Se l'overlap catalogo/recommender non basta,completiamo con popularity locale
    #Il ranking ibrido resta davanti,il riempimento serve solo a evitare griglie vuote
    #Tutti i prodotti aggiunti restano comunque dentro il catalogo del sito
    def _fill_with_catalog_popularity(self,products: list[Product],limit: int) -> list[Product]:
        if len(products)>=limit or not self._catalog_products_by_item_id:
            return products
        used_ids={product.item_id for product in products}
        for product in most_popular(list(self._catalog_products_by_item_id.values()),limit=len(self._catalog_products_by_item_id)):
            if product.item_id in used_ids:
                continue
            products.append(product)
            used_ids.add(product.item_id)
            if len(products)>=limit:
                break
        return products

    #Score content-based: similarita coseno tra profilo utente e item TF-IDF
    #Le matrici sono gia normalizzate nel Notebook 05
    #Il dot product produce uno score per ogni item candidato
    def _content_scores(self,user_idx: int,item_idxs: np.ndarray) -> np.ndarray:
        user_vector=self._user_content_profiles[int(user_idx)]
        if user_vector.nnz==0 or len(item_idxs)==0:
            return np.zeros(len(item_idxs),dtype=np.float64)
        item_vectors=self._item_tfidf_matrix[item_idxs]
        scores=item_vectors.dot(user_vector.T)
        return np.asarray(scores.toarray()).ravel().astype(np.float64)

    #Score SVD: prodotto scalare tra embedding utente e embedding item
    #Usa SVD_4,cioe lo stesso componente dell'ibrido scelto
    #Restituisce score grezzi da normalizzare nel mix finale
    def _svd_scores(self,user_idx: int,item_idxs: np.ndarray) -> np.ndarray:
        user_vector=self._svd_user_embeddings[int(user_idx)]
        item_matrix=self._svd_item_embeddings[item_idxs]
        return (item_matrix@user_vector).astype(np.float64)

    #Score popolarita grezzo per ogni item candidato
    #Mancanti diventano 0,come nel notebook
    #La normalizzazione avviene dopo sul set candidati
    def _popularity_scores(self,item_idxs: np.ndarray) -> np.ndarray:
        return np.array(
            [self._popularity_by_item_idx.get(int(item_idx),0.0) for item_idx in item_idxs],
            dtype=np.float64,
        )

    #Converte una riga parquet in Product API
    #Descrizione e prezzo vengono ripuliti per essere mostrati nel frontend
    #item_id usa parent_asin,coerente con il recommender
    def _row_to_product(self,row: dict[str,Any]) -> Product:
        item_idx=_safe_int(row.get("item_idx"))
        return Product(
            item_id=str(row.get("parent_asin") or ""),
            title=str(row.get("title") or "Titolo non disponibile"),
            category=str(row.get("category") or "Electronics"),
            description=_readable_text(row.get("description_json"),row.get("features_json"),row.get("details_json")),
            price=_clean_number(row.get("price"),default=None),
            average_rating=_clean_number(row.get("avg_rating"),default=None),
            rating_count=int(_clean_number(row.get("num_ratings"),default=0) or 0),
            popularity_score=self._normalized_popularity(item_idx) if item_idx is not None else 0.0,
            image_url=str(row.get("image_url")) if _has_value(row.get("image_url")) else None,
        )

    def _normalized_popularity(self,item_idx: int | None) -> float:
        if item_idx is None or self._max_popularity <= 0:
            return 0.0
        return round(self._popularity_by_item_idx.get(int(item_idx),0.0) / self._max_popularity,4)


def _minmax_normalize_scores(scores) -> np.ndarray:
    scores=np.asarray(scores,dtype=np.float64)
    if len(scores)==0:
        return scores
    scores=np.nan_to_num(scores,nan=0.0,posinf=0.0,neginf=0.0)
    min_score=float(np.min(scores))
    max_score=float(np.max(scores))
    if not np.isfinite(min_score) or not np.isfinite(max_score) or max_score <= min_score:
        return np.zeros(len(scores),dtype=np.float64)
    return (scores - min_score) / (max_score - min_score)


def _readable_text(*values) -> str:
    for value in values:
        parsed=_parse_json_value(value)
        if isinstance(parsed,list):
            parts=[str(item).strip() for item in parsed if str(item).strip()]
            if parts:
                return " ".join(parts)
        if isinstance(parsed,dict):
            parts=[
                f"{key}: {item}"
                for key,item in parsed.items()
                if isinstance(item,(str,int,float)) and _has_value(item)
            ]
            if parts:
                return " ".join(parts)
        if isinstance(parsed,str) and parsed.strip():
            return parsed.strip()
    return ""


def _parse_json_value(value):
    if not _has_value(value):
        return None
    if not isinstance(value,str):
        return value
    try:
        return json.loads(value)
    except Exception:
        return value


def _clean_number(value,default=0.0):
    if not _has_value(value):
        return default
    try:
        number=float(value)
    except (TypeError,ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def _safe_int(value) -> int | None:
    if not _has_value(value):
        return None
    try:
        return int(value)
    except (TypeError,ValueError):
        return None


def _has_value(value) -> bool:
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError,ValueError):
        pass
    return True
