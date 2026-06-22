import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix,load_npz
from sklearn.preprocessing import normalize


PROJECT_ROOT=Path(__file__).resolve().parents[2]
DEFAULT_RECOMMENDER_DIR=PROJECT_ROOT / "data" / "processed" / "test_dataset2_recommender"
DEFAULT_CATALOG_PATH=PROJECT_ROOT / "prototype" / "data" / "products_demo.json"
DEFAULT_OUTPUT_PATH=PROJECT_ROOT / "prototype" / "backend" / "assets" / "home_profiles.json"


def parse_args() -> argparse.Namespace:
    parser=argparse.ArgumentParser(
        description="Export the two reproducible recommendation profiles used by the prototype home."
    )
    parser.add_argument("--recommender-dir",type=Path,default=DEFAULT_RECOMMENDER_DIR)
    parser.add_argument("--catalog",type=Path,default=DEFAULT_CATALOG_PATH)
    parser.add_argument("--output",type=Path,default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--limit",type=int,default=24)
    return parser.parse_args()


def minmax(values: np.ndarray) -> np.ndarray:
    clean=np.nan_to_num(np.asarray(values,dtype=np.float64),nan=0.0,posinf=0.0,neginf=0.0)
    if clean.size == 0:
        return clean
    minimum=float(clean.min())
    maximum=float(clean.max())
    if maximum <= minimum:
        return np.zeros_like(clean)
    return (clean-minimum)/(maximum-minimum)


def load_best_model(recommender_dir: Path) -> tuple[dict,dict]:
    artifact_dir=recommender_dir / "notebook05_content_hybrid"
    summary=json.loads((artifact_dir / "notebook05_summary.json").read_text(encoding="utf-8"))
    model_name=summary["best_overall_model_validation"]
    weights_df=pd.read_csv(artifact_dir / "hybrid_grid_top_weights.csv")
    selected=weights_df.loc[weights_df["model"] == model_name].iloc[0]
    weights={
        "svd":float(selected["svd_weight"]),
        "content":float(selected["content_weight"]),
        "popularity":float(selected["popularity_weight"]),
    }
    model={
        "model_id":model_name,
        "name":"Miglior ibrido",
        "description":"Il modello con il miglior NDCG@10 sul validation set combina segnali collaborativi, contenuto e popolarità.",
        "weights":weights,
        "validation_metric_name":"NDCG@10",
        "validation_metric_value":float(summary["best_overall_validation_score"]),
    }
    return model,weights


def select_historical_user(train_df: pd.DataFrame) -> tuple[str,int,np.ndarray]:
    history_sizes=(
        train_df.groupby(["user_id","user_idx"])["item_idx"]
        .nunique()
        .sort_values(ascending=False)
    )
    user_id,user_idx=history_sizes.index[0]
    seen=np.unique(
        train_df.loc[train_df["user_idx"] == int(user_idx),"item_idx"].to_numpy(dtype=np.int64)
    )
    return str(user_id),int(user_idx),seen


def build_hybrid_recommendations(
    recommender_dir: Path,
    catalog_path: Path,
    limit: int,
) -> dict:
    artifact_dir=recommender_dir / "notebook05_content_hybrid"
    model,weights=load_best_model(recommender_dir)
    catalog=json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog_ids={
        str(product["item_id"])
        for product in catalog
        if product.get("price") is not None and float(product["price"]) > 0
    }

    train_df=pd.read_parquet(
        recommender_dir / "train.parquet",
        columns=["user_id","user_idx","item_idx"],
    )
    user_id,user_idx,train_seen=select_historical_user(train_df)

    known_frames=[train_df[["user_idx","item_idx"]]]
    for filename in ("validation_eval.parquet","test_eval.parquet"):
        known_frames.append(
            pd.read_parquet(recommender_dir / filename,columns=["user_idx","item_idx"])
        )
    known_df=pd.concat(known_frames,ignore_index=True)
    all_seen=set(
        known_df.loc[known_df["user_idx"] == user_idx,"item_idx"].astype(int).tolist()
    )

    items_df=pd.read_parquet(
        recommender_dir / "items.parquet",
        columns=["item_idx","parent_asin","category"],
    )
    candidates=items_df.loc[
        items_df["parent_asin"].isin(catalog_ids)
        & ~items_df["item_idx"].isin(all_seen)
    ].copy()
    candidate_indices=candidates["item_idx"].to_numpy(dtype=np.int64)

    item_tfidf=load_npz(artifact_dir / "item_tfidf_matrix.npz")
    user_profile=normalize(
        csr_matrix(item_tfidf[train_seen].sum(axis=0)),
        norm="l2",
        axis=1,
    )
    content_raw=np.asarray(item_tfidf[candidate_indices].dot(user_profile.T).toarray()).ravel()

    user_embeddings=np.load(
        recommender_dir / "notebook04_models" / "best_svd_user_embeddings.npy",
        mmap_mode="r",
    )
    item_embeddings=np.load(
        recommender_dir / "notebook04_models" / "best_svd_item_embeddings.npy",
        mmap_mode="r",
    )
    svd_raw=np.asarray(
        item_embeddings[candidate_indices] @ user_embeddings[user_idx]
    ).ravel()

    popularity_df=pd.read_parquet(artifact_dir / "popularity_scores.parquet")
    popularity_by_item=dict(
        zip(
            popularity_df["item_idx"].astype(int),
            popularity_df["popularity_score"].astype(float),
        )
    )
    popularity_raw=np.asarray(
        [popularity_by_item.get(int(item_idx),0.0) for item_idx in candidate_indices],
        dtype=np.float64,
    )

    components={
        "svd":minmax(svd_raw),
        "content":minmax(content_raw),
        "popularity":minmax(popularity_raw),
    }
    final_scores=sum(weights[name]*values for name,values in components.items())
    candidates["score"]=final_scores
    for name,values in components.items():
        candidates[f"{name}_component"]=values
    ranked=candidates.sort_values(
        ["score","item_idx"],
        ascending=[False,True],
    ).head(max(1,limit))

    seen_categories=items_df.loc[items_df["item_idx"].isin(train_seen),"category"]
    interests=[str(category) for category in seen_categories.value_counts().head(4).index]
    recommendations=[]
    for row in ranked.itertuples(index=False):
        recommendations.append(
            {
                "item_id":str(row.parent_asin),
                "score":round(float(row.score),6),
                "components":{
                    "svd":round(float(row.svd_component),6),
                    "content":round(float(row.content_component),6),
                    "popularity":round(float(row.popularity_component),6),
                },
            }
        )

    return {
        "profile_id":"dataset-user",
        "profile_type":"known_user",
        "label":"Utente dal dataset",
        "short_label":"Storico lungo",
        "description":"Profilo reale selezionato perché ha lo storico di training più lungo del dataset Amazon-like.",
        "dataset_user_id":user_id,
        "history_count":int(len(train_seen)),
        "known_interactions":int(len(all_seen)),
        "interests":interests,
        "algorithm":model,
        "recommendations":recommendations,
    }


def export_profiles(recommender_dir: Path,catalog_path: Path,output_path: Path,limit: int) -> dict:
    historical_profile=build_hybrid_recommendations(
        recommender_dir.resolve(),
        catalog_path.resolve(),
        limit,
    )
    payload={
        "dataset":"test_dataset2 / AmazonLike_v1",
        "profiles":[
            {
                "profile_id":"cold-start",
                "profile_type":"cold_start",
                "label":"Nuovo utente",
                "short_label":"Cold start",
                "description":"Nessuno storico disponibile: la home usa esclusivamente la baseline di popolarità.",
                "dataset_user_id":None,
                "history_count":0,
                "known_interactions":0,
                "interests":[],
                "algorithm":{
                    "model_id":"Popular",
                    "name":"Popular baseline",
                    "description":"Ordina i prodotti solo in base alla popolarità osservata nel catalogo.",
                    "weights":{"svd":0.0,"content":0.0,"popularity":1.0},
                    "validation_metric_name":None,
                    "validation_metric_value":None,
                },
            },
            historical_profile,
        ],
    }
    output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text(
        json.dumps(payload,ensure_ascii=False,indent=2),
        encoding="utf-8",
    )
    return payload


def main() -> None:
    args=parse_args()
    payload=export_profiles(
        args.recommender_dir,
        args.catalog,
        args.output,
        max(1,args.limit),
    )
    historical=payload["profiles"][1]
    print(f"Saved: {args.output.resolve()}")
    print(f"Historical user: {historical['dataset_user_id']}")
    print(f"Training history: {historical['history_count']}")
    print(f"Recommendations: {len(historical['recommendations'])}")


if __name__ == "__main__":
    main()
