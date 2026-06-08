import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from prototype.backend.schemas import Product,ProductQAEvidence,ProductQAResponse
from prototype.backend.services.ai_search_service import call_gemini

#Import opzionale per retrieval TF-IDF
#Se scikit-learn non c'e,il servizio passa a scoring per overlap parole
#Questo evita che il QA smetta di funzionare per una dipendenza mancante
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    TfidfVectorizer=None
    cosine_similarity=None

#Import opzionale per leggere parquet di QA e review
#Senza pandas restano disponibili metadati e futuri JSON semplici
#Il backend non deve fallire solo per fonti opzionali mancanti
try:
    import pandas as pd
except ImportError:
    pd=None


logger=logging.getLogger(__name__)
NOT_ENOUGH_INFO="Non ho abbastanza informazioni nei dati disponibili per rispondere con sicurezza."
MAX_EVIDENCE=5
MIN_RELEVANT_SCORE=0.04


class ProductQAService:
    #Inizializziamo il servizio QA caricando fonti opzionali una sola volta
    #Le mappe raggruppano QA e review per item_id
    #Questo rende veloce la risposta durante le richieste API
    def __init__(self,data_dir: Path):
        self.data_dir=data_dir
        self._qa_by_id=defaultdict(list)
        self._reviews_by_id=defaultdict(list)
        self._load_optional_sources()

    #Risponde usando solo documenti collegati al prodotto richiesto
    #Prima recupera evidenze locali,poi opzionalmente chiede a Gemini di sintetizzarle
    #Se non trova evidenze,o l'AI fallisce,usa risposta controllata locale
    def answer_question(
        self,
        product: Product,
        question: str,
        use_ai: bool=True,
    ) -> ProductQAResponse:
        clean_question=_short_text(question,max_chars=500) #limita input troppo lunghi
        documents=self._build_documents(product) #solo fonti del prodotto corrente
        evidence=_retrieve_evidence(clean_question,documents) #top evidenze ordinate per rilevanza
        confidence=_confidence_from_evidence(evidence) #stima semplice basata sugli score

        if not evidence:
            return ProductQAResponse(
                item_id=product.item_id,
                question=clean_question,
                answer=NOT_ENOUGH_INFO,
                confidence="low",
                used_ai=False,
                evidence=[],
            )

        if use_ai:
            try:
                answer,ai_confidence=_answer_with_ai(product,clean_question,evidence) #Gemini vede solo evidenze recuperate
                return ProductQAResponse(
                    item_id=product.item_id,
                    question=clean_question,
                    answer=answer,
                    confidence=ai_confidence or confidence,
                    used_ai=True,
                    evidence=evidence,
                )
            except Exception as exc:
                logger.warning("Fallback QA locale: %s",exc)

        return ProductQAResponse(
            item_id=product.item_id,
            question=clean_question,
            answer=_local_extractive_answer(evidence,confidence),
            confidence=confidence,
            used_ai=False,
            evidence=evidence,
        )

    #Costruisce piccoli documenti testuali: metadata,descrizione,recensioni e QA
    #Ogni documento ha source e text per poter mostrare evidenze all'utente
    #Le review/QA sono limitate per evitare input troppo grandi
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

        for review in self._reviews_by_id.get(product.item_id,[])[:60]: #limite per controllare tempi e memoria
            text=_review_to_text(review)
            for chunk in _chunk_text(text,max_words=90):
                documents.append({"source": "review","text": chunk})

        for qa_pair in self._qa_by_id.get(product.item_id,[])[:60]:
            text=_qa_to_text(qa_pair)
            for chunk in _chunk_text(text,max_words=90):
                documents.append({"source": "qa","text": chunk})

        return [doc for doc in documents if doc["text"].strip()] #scarta chunk vuoti

    #Carica dati opzionali senza rendere obbligatorio nessun file esterno
    #Prima prova parquet prodotti dal notebook,poi eventuali JSON demo
    #Ogni loader gestisce da solo errori e file mancanti
    def _load_optional_sources(self) -> None:
        self._load_processed_parquet()
        for filename in ["qa_demo.json","product_qa_demo.json"]:
            self._load_json_qa(self.data_dir / filename)
        for filename in ["reviews_demo.json","product_reviews_demo.json"]:
            self._load_json_reviews(self.data_dir / filename)

    #Carichiamo parquet processati se disponibili
    #parent_asin collega QA/review al prodotto del catalogo
    #Gli errori vengono loggati ma non bloccano il backend
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
                    item_id=str(row.get("parent_asin") or row.get("item_id") or "") #compatibilita tra schemi diversi
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
                    item_id=str(row.get("parent_asin") or row.get("item_id") or row.get("asin") or "") #sceglie primo id disponibile
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


#Recupera evidenze rilevanti per la domanda
#Prima prova TF-IDF+cosine similarity,poi fallback overlap parole
#Deduplica testi simili e limita il numero di evidenze mostrate
def _retrieve_evidence(question: str,documents: list[dict[str,str]]) -> list[ProductQAEvidence]:
    if not question.strip() or not documents:
        return []

    texts=[doc["text"] for doc in documents]
    query_text=_expand_question(question) #aggiunge sinonimi IT/EN per migliorare recall
    try:
        scores=_tfidf_scores(query_text,texts)
    except Exception as exc:
        logger.warning("Fallback scoring QA: %s",exc)
        scores=_overlap_scores(query_text,texts)

    ranked=sorted(enumerate(scores),key=lambda item: item[1],reverse=True) #ordina documenti per rilevanza
    evidence=[]
    seen_texts=set()
    for index,score in ranked:
        if score < MIN_RELEVANT_SCORE: #interrompe quando le evidenze diventano troppo deboli
            break
        text=_short_text(texts[index],max_chars=520)
        dedupe_key=text.lower() #deduplica semplice su testo normalizzato
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


#Calcola score TF-IDF tra domanda e documenti
#Aggiungiamo la domanda in coda alla matrice per confrontarla con tutti i testi
#Il risultato e una lista di similarita allineata ai documenti originali
def _tfidf_scores(query_text: str,texts: list[str]) -> list[float]:
    if TfidfVectorizer is None or cosine_similarity is None:
        raise RuntimeError("scikit-learn non disponibile.")
    vectorizer=TfidfVectorizer(
        stop_words="english",
        ngram_range=(1,2),
        max_features=1600,
    )
    matrix=vectorizer.fit_transform(texts + [query_text]) #ultima riga=domanda
    similarities=cosine_similarity(matrix[-1],matrix[:-1]).flatten() #confronta domanda contro documenti
    return [float(score) for score in similarities]


#Fallback senza scikit-learn
#Usa Jaccard tra parole della domanda e parole del documento
#Meno preciso di TF-IDF ma comprensibile e robusto
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
        scores.append(len(query_tokens & text_tokens) / len(query_tokens | text_tokens)) #intersezione/unione
    return scores


#Chiede a Gemini una risposta sintetica grounded
#Il payload contiene solo prodotto,domanda ed evidenze recuperate
#La risposta deve essere JSON per poter validare answer e confidence
def _answer_with_ai(
    product: Product,
    question: str,
    evidence: list[ProductQAEvidence],
) -> tuple[str,str | None]:
    payload={
        "product": {
            "item_id": product.item_id,
            "title": _short_text(product.title,max_chars=180),
            "category": product.category,
        },
        "question": question,
        "evidence": [
            {
                "source": item.source,
                "text": item.text,
                "score": item.score,
            }
            for item in evidence
        ],
    }
    prompt=(
        "Sei un assistente QA per una pagina prodotto e-commerce. "
        "Rispondi in italiano usando solo le evidenze fornite. "
        "Non usare conoscenza esterna e non inventare caratteristiche. "
        "Se le evidenze non bastano, dillo chiaramente con questa frase: "
        f"'{NOT_ENOUGH_INFO}' "
        "Restituisci solo JSON valido senza Markdown. "
        'Schema obbligatorio: {"answer":"...","confidence":"low|medium|high"}. '
        "La risposta deve essere breve, concreta e citare che deriva dai dati disponibili.\n\n"
        f"Dati:\n{json.dumps(payload,ensure_ascii=False)}"
    )
    raw_response=call_gemini(prompt)
    data=_parse_json_object(raw_response) #gestisce anche risposte con testo extra
    answer=_short_text(data.get("answer"),max_chars=760)
    if not answer:
        raise ValueError("Risposta QA AI vuota.")
    confidence=str(data.get("confidence") or "").lower()
    if confidence not in {"low","medium","high"}:
        confidence=None
    return answer,confidence


#Risposta locale estrattiva
#Non inventa frasi nuove:riassume usando snippet delle evidenze migliori
#Se la confidenza e bassa,preferisce dichiarare informazione insufficiente
def _local_extractive_answer(evidence: list[ProductQAEvidence],confidence: str) -> str:
    if not evidence:
        return NOT_ENOUGH_INFO
    if confidence == "low":
        return NOT_ENOUGH_INFO

    answer_evidence=sorted(evidence,key=lambda item: _answer_source_priority(item.source))[:3] #preferisce QA/descrizione a review
    snippets=[_short_text(item.text,max_chars=220) for item in answer_evidence]
    return (
        "Dai dati disponibili emergono queste evidenze: "
        + " ".join(snippets)
    )


#Stima confidenza in base allo score migliore e al numero di evidenze
#Le soglie sono euristiche semplici,non metriche statistiche
#Servono per mostrare un segnale leggibile nel frontend
def _confidence_from_evidence(evidence: list[ProductQAEvidence]) -> str:
    if not evidence:
        return "low"
    best=evidence[0].score
    if best >= 0.32 and len(evidence) >= 2:
        return "high"
    if best >= 0.07:
        return "medium"
    return "low"


def _answer_source_priority(source: str) -> int:
    priorities={
        "qa": 0,
        "description": 1,
        "metadata": 2,
        "review": 3,
    }
    return priorities.get(source,4)


#Trasforma una review in testo ricercabile
#Aggiunge parole di sentimento derivate dal rating per aiutare query tipo "problemi"
#Non cambia il dato originale,aggiunge solo indizi testuali per retrieval
def _review_to_text(review: dict[str,Any]) -> str:
    rating=review.get("rating")
    sentiment=""
    try:
        rating_number=float(rating)
        if rating_number <= 2:
            sentiment="recensione negativa problema difetto criticita" #aiuta query su difetti/criticita
        elif rating_number >= 4:
            sentiment="recensione positiva soddisfazione" #aiuta query su soddisfazione/qualita
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


#Divide testi lunghi in chunk sovrapposti
#Lo overlap evita di perdere contesto al confine tra due blocchi
#Chunk troppo grandi renderebbero il retrieval meno preciso
def _chunk_text(text: str,max_words: int=85) -> list[str]:
    words=str(text or "").split()
    if not words:
        return []
    chunks=[]
    step=max(1,max_words - 15) #overlap di circa 15 parole tra chunk
    for start in range(0,len(words),step):
        chunk=" ".join(words[start:start + max_words]).strip()
        if chunk:
            chunks.append(chunk)
        if start + max_words >= len(words):
            break
    return chunks


#Espande la domanda con sinonimi utili al dataset
#Molti testi sono in inglese,mentre l'utente puo chiedere in italiano
#La query espansa aumenta recall senza modificare la domanda mostrata
def _expand_question(question: str) -> str:
    tokens=_tokens(question)
    expansions=[question]
    synonym_map={
        "batteria": "battery battery life lasts duration charge",
        "dura": "lasts duration long life",
        "durata": "duration battery life",
        "telefono": "phone cell smartphone",
        "telefoni": "phone cell smartphone",
        "fotocamera": "camera photo pictures",
        "foto": "camera photo pictures",
        "gaming": "gaming game video games performance",
        "giochi": "games gaming video games",
        "compatibile": "compatible compatibility fit works with",
        "iphone": "iphone ios apple phone",
        "problemi": "problem issue broken defect negative complaint",
        "problema": "problem issue broken defect negative complaint",
        "negative": "negative low rating problem complaint",
        "negativa": "negative low rating problem complaint",
        "recensioni": "review reviews rating feedback",
        "economico": "cheap budget price low cost",
        "prezzo": "price cost cheap budget",
        "qualita": "quality good bad",
        "installare": "install installation setup",
        "installa": "install installation setup remove replace",
        "installazione": "install installation setup remove replace",
        "filtro": "filter water filter replacement",
        "filtri": "filter water filter replacement",
    }
    for token in tokens:
        if token in synonym_map:
            expansions.append(synonym_map[token])
    return " ".join(expansions)


#Carica record JSON in formati diversi
#Accetta lista diretta,dizionario con items o dizionario per item_id
#Questo rende flessibili futuri file demo manuali
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
                        item.setdefault("item_id",key) #usa la chiave esterna come id se manca nel record
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


#Parsa JSON robusto per risposte AI
#Se il modello aggiunge testo,proviamo a ritagliare il primo oggetto JSON
#Se non e un dict,il chiamante attiva fallback
def _parse_json_object(raw_response: str) -> dict[str,Any]:
    try:
        data=json.loads(raw_response)
    except json.JSONDecodeError:
        start=raw_response.find("{")
        end=raw_response.rfind("}")
        if start < 0 or end < start:
            raise
        data=json.loads(raw_response[start:end + 1]) #ritaglio dal primo { all'ultimo }
    if not isinstance(data,dict):
        raise ValueError("La risposta AI non e un oggetto JSON.")
    return data


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
