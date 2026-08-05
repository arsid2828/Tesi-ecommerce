import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from prototype.backend.schemas import Product,ProductQAEvidence
from prototype.backend.services.query_utils import expand_query_text

# Servizio di evidenze locali per discovery e raccomandazioni.
# Recupera metadati, QA e recensioni da file locali senza chiamare servizi esterni.
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    TfidfVectorizer=None
    cosine_similarity=None

try:
    import pandas as pd
except ImportError:
    pd=None


logger=logging.getLogger(__name__)
MAX_EVIDENCE=5
MIN_RELEVANT_SCORE=0.04


class ProductQAService:
    # Servizio di retrieval locale per la discovery.
    # Carica QA e recensioni una sola volta, ma non espone piu una chat prodotto.
    def __init__(self,data_dir: Path):
        self.data_dir=data_dir
        self._qa_by_id=defaultdict(list)
        self._reviews_by_id=defaultdict(list)
        self._load_optional_sources()

    # Restituisce evidenze testuali pertinenti per un prodotto e una query.
    # Combina metadati sempre disponibili con QA/recensioni se i file esistono.
    def evidence_for_product(
        self,
        product: Product,
        query: str,
        max_items: int=4,
    ) -> list[ProductQAEvidence]:
        clean_query=_short_text(query or product.title,max_chars=500)
        documents=self._build_documents(product)
        return _retrieve_evidence(clean_query,documents)[:max(0,max_items)]

    # Costruisce documenti recuperabili per un singolo prodotto.
    # Ogni documento mantiene una source per spiegare alla UI da dove arriva l'evidenza.
    def _build_documents(self,product: Product) -> list[dict[str,str]]:
        documents=[]
        metadata_parts=[
            f"Titolo: {product.title}",
            f"Categoria: {product.category}",
            f"Prezzo: {product.price}" if product.price is not None else "",
            f"Rating medio: {product.average_rating}" if product.average_rating else "",
            f"Numero recensioni: {product.rating_count}" if product.rating_count else "",
        ]
        documents.append(
            {
                "source": "metadata",
                "text": ". ".join(part for part in metadata_parts if part),
            }
        )

        for chunk in _chunk_text(product.description or ""):
            documents.append({"source": "description","text": chunk})

        for review in self._reviews_by_id.get(product.item_id,[])[:60]:
            text=_review_to_text(review)
            for chunk in _chunk_text(text,max_words=90):
                documents.append({"source": "review","text": chunk})

        for qa_pair in self._qa_by_id.get(product.item_id,[])[:60]:
            text=_qa_to_text(qa_pair)
            for chunk in _chunk_text(text,max_words=90):
                documents.append({"source": "qa","text": chunk})

        return [doc for doc in documents if doc["text"].strip()]

    # Carica tutte le sorgenti opzionali supportate.
    # I parquet processed sono la sorgente principale; i JSON demo restano fallback leggeri.
    def _load_optional_sources(self) -> None:
        self._load_processed_parquet()
        for filename in ["qa_demo.json","product_qa_demo.json"]:
            self._load_json_qa(self.data_dir / filename)
        for filename in ["reviews_demo.json","product_reviews_demo.json"]:
            self._load_json_reviews(self.data_dir / filename)

    # Carica QA e review dai parquet prodotti nella preparazione dati.
    # Se pandas o i file non sono disponibili, la demo continua con soli metadati.
    def _load_processed_parquet(self) -> None:
        if pd is None:
            return

        processed_dir=self.data_dir / "processed" / "prototype_amazon_like_intersection"
        qa_path=processed_dir / "qa.parquet"
        ratings_path=processed_dir / "ratings.parquet"

        if qa_path.exists():
            try:
                qa_df=pd.read_parquet(qa_path)
                for row in qa_df.to_dict(orient="records"):
                    item_id=str(row.get("parent_asin") or row.get("item_id") or "")
                    if not item_id:
                        continue
                    self._qa_by_id[item_id].append(
                        {
                            "question": row.get("question"),
                            "answer": row.get("answer"),
                        }
                    )
            except Exception as exc:
                logger.warning("QA parquet non caricato: %s",exc)

        if ratings_path.exists():
            try:
                ratings_df=pd.read_parquet(ratings_path)
                for row in ratings_df.to_dict(orient="records"):
                    item_id=str(row.get("parent_asin") or row.get("item_id") or row.get("asin") or "")
                    if not item_id:
                        continue
                    self._reviews_by_id[item_id].append(
                        {
                            "rating": row.get("rating"),
                            "title": row.get("review_title"),
                            "text": row.get("review_text"),
                        }
                    )
            except Exception as exc:
                logger.warning("Reviews parquet non caricato: %s",exc)

    # Carica QA opzionali in formato JSON.
    # Supporta vari nomi campo per riusare piccoli dataset dimostrativi.
    def _load_json_qa(self,path: Path) -> None:
        if not path.exists():
            return
        try:
            records=_load_json_records(path)
            for row in records:
                item_id=_record_item_id(row)
                if not item_id:
                    continue
                self._qa_by_id[item_id].append(
                    {
                        "question": row.get("question") or row.get("q"),
                        "answer": row.get("answer") or row.get("a"),
                    }
                )
        except Exception as exc:
            logger.warning("QA JSON non caricato da %s: %s",path,exc)

    # Carica recensioni opzionali in formato JSON.
    # I record vengono indicizzati per item_id e usati solo come evidenze locali.
    def _load_json_reviews(self,path: Path) -> None:
        if not path.exists():
            return
        try:
            records=_load_json_records(path)
            for row in records:
                item_id=_record_item_id(row)
                if not item_id:
                    continue
                self._reviews_by_id[item_id].append(
                    {
                        "rating": row.get("rating") or row.get("stars"),
                        "title": row.get("review_title") or row.get("title"),
                        "text": row.get("review_text") or row.get("text"),
                    }
                )
        except Exception as exc:
            logger.warning("Reviews JSON non caricato da %s: %s",path,exc)


# Recupera le evidenze piu pertinenti tra i documenti disponibili.
# Usa TF-IDF quando possibile e fallback overlap se scikit-learn non e installato.
def _retrieve_evidence(question: str,documents: list[dict[str,str]]) -> list[ProductQAEvidence]:
    if not question.strip() or not documents:
        return []

    texts=[doc["text"] for doc in documents]
    query_text=expand_query_text(question)
    try:
        scores=_tfidf_scores(query_text,texts)
    except Exception as exc:
        logger.warning("Fallback scoring QA: %s",exc)
        scores=_overlap_scores(query_text,texts)

    ranked=sorted(enumerate(scores),key=lambda item: item[1],reverse=True)
    evidence=[]
    seen_texts=set()
    for index,score in ranked:
        if score < MIN_RELEVANT_SCORE:
            break
        text=_short_text(texts[index],max_chars=520)
        dedupe_key=text.lower()
        if dedupe_key in seen_texts:
            continue
        evidence.append(
            ProductQAEvidence(
                source=documents[index]["source"],
                text=text,
                score=round(float(score),4),
            )
        )
        seen_texts.add(dedupe_key)
        if len(evidence) >= MAX_EVIDENCE:
            break
    return evidence


def _tfidf_scores(query_text: str,texts: list[str]) -> list[float]:
    if TfidfVectorizer is None or cosine_similarity is None:
        raise RuntimeError("scikit-learn non disponibile.")
    vectorizer=TfidfVectorizer(
        stop_words="english",
        ngram_range=(1,2),
        max_features=1600,
    )
    matrix=vectorizer.fit_transform(texts + [query_text])
    similarities=cosine_similarity(matrix[-1],matrix[:-1]).flatten()
    return [float(score) for score in similarities]


def _overlap_scores(query_text: str,texts: list[str]) -> list[float]:
    query_tokens=set(_tokens(query_text))
    if not query_tokens:
        return [0.0 for _text in texts]
    scores=[]
    for text in texts:
        text_tokens=set(_tokens(text))
        if not text_tokens:
            scores.append(0.0)
            continue
        scores.append(len(query_tokens & text_tokens) / len(query_tokens | text_tokens))
    return scores


def _review_to_text(review: dict[str,Any]) -> str:
    rating=review.get("rating")
    sentiment=""
    try:
        rating_number=float(rating)
        if rating_number <= 2:
            sentiment="recensione negativa problema difetto criticita"
        elif rating_number >= 4:
            sentiment="recensione positiva soddisfazione"
    except (TypeError,ValueError):
        pass

    parts=[
        sentiment,
        f"Valutazione recensione: {rating}" if rating is not None else "",
        f"Titolo recensione: {review.get('title')}" if review.get("title") else "",
        f"Testo recensione: {review.get('text')}" if review.get("text") else "",
    ]
    return ". ".join(str(part) for part in parts if part)


def _qa_to_text(qa_pair: dict[str,Any]) -> str:
    parts=[
        f"Domanda storica: {qa_pair.get('question')}" if qa_pair.get("question") else "",
        f"Risposta storica: {qa_pair.get('answer')}" if qa_pair.get("answer") else "",
    ]
    return ". ".join(part for part in parts if part)


def _chunk_text(text: str,max_words: int=85) -> list[str]:
    words=str(text or "").split()
    if not words:
        return []
    chunks=[]
    step=max(1,max_words - 15)
    for start in range(0,len(words),step):
        chunk=" ".join(words[start:start + max_words]).strip()
        if chunk:
            chunks.append(chunk)
        if start + max_words >= len(words):
            break
    return chunks




def _load_json_records(path: Path) -> list[dict[str,Any]]:
    data=json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data,list):
        return [row for row in data if isinstance(row,dict)]
    if isinstance(data,dict):
        if isinstance(data.get("items"),list):
            return [row for row in data["items"] if isinstance(row,dict)]
        records=[]
        for key,value in data.items():
            if isinstance(value,list):
                for row in value:
                    if isinstance(row,dict):
                        item=dict(row)
                        item.setdefault("item_id",key)
                        records.append(item)
        return records
    return []


def _record_item_id(row: dict[str,Any]) -> str:
    return str(
        row.get("item_id")
        or row.get("parent_asin")
        or row.get("asin")
        or row.get("product_id")
        or ""
    )


def _short_text(value: Any,max_chars: int=320) -> str:
    text=" ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3].rstrip() + "..."


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9-]{2,}",str(text or "").lower())
        if token not in _basic_stopwords()
    ]


def _basic_stopwords() -> set[str]:
    return {
        "the","and","for","with","from","this","that","are","you","your",
        "una","uno","con","per","del","della","dei","gli","che","non",
        "questo","questa","sono","come","nei","dati","available",
    }
