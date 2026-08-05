import re
from typing import Any


#Mappa centralizzata dei sinonimi usata da discovery, search e product_qa.
#Copre termini italiani comuni del dataset demo e li espande verso l'inglese.
#Non modificare questa struttura senza aggiornare i test di sinonimi.
SYNONYM_MAP: dict[str,list[str]]={
    "mouse": ["wireless","programmable","gaming mouse"],
    "gaming": ["game","video games","wireless","controller"],
    "giochi": ["game","video games","gaming"],
    "telefono": ["phone","smartphone","cell phone"],
    "telefoni": ["phone","smartphone","cell phone"],
    "cellulare": ["phone","smartphone","cell phone"],
    "cellulari": ["phone","smartphone","cell phone"],
    "fotocamera": ["camera","photo","pictures"],
    "foto": ["camera","photo","pictures"],
    "camera": ["photo","pictures"],
    "economico": ["cheap","budget","low price"],
    "economici": ["cheap","budget","low price"],
    "cuffie": ["headphones","earbuds","headset"],
    "stampante": ["printer","ink"],
    "filtro": ["filter","replacement","water filter"],
    "filtri": ["filter","replacement","water filter"],
    "batteria": ["battery","charge","battery life"],
    "accessori": ["accessories"],
    "custodia": ["case","cover"],
    "dura": ["lasts","duration","long life"],
    "durata": ["duration","battery life"],
    "compatibile": ["compatible","compatibility","fit","works with"],
    "iphone": ["iphone","ios","apple","phone"],
    "problemi": ["problem","issue","broken","defect","negative","complaint"],
    "problema": ["problem","issue","broken","defect","negative","complaint"],
    "recensioni": ["review","reviews","rating","feedback"],
    "prezzo": ["price","cost","cheap","budget"],
    "qualita": ["quality","good","bad"],
    "installare": ["install","installation","setup"],
    "installa": ["install","installation","setup","remove","replace"],
    "installazione": ["install","installation","setup","remove","replace"],
}

#Stopword condivise usate da tokenize_query.
_STOPWORDS: set[str]={
    "the","and","for","with","from","this","that","are","you","your","into",
    "product","products","description","rating","count","average","available",
    "una","uno","con","per","del","della","dei","gli","che","non","come",
    "questo","questa","sono","nei","dati",
}


#Tokenizza il testo in token alfanumerici di almeno 3 caratteri, senza stopword.
def tokenize_query(text: Any) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9-]{2,}",str(text or "").lower())
        if token not in _STOPWORDS
    ]


#Deduplica mantenendo l'ordine originale.
def _dedupe(values: list[str]) -> list[str]:
    result=[]
    for value in values:
        clean=str(value or "").strip().lower()
        if clean and clean not in result:
            result.append(clean)
    return result


#Restituisce lista di termini espansi per recupero e ranking dei candidati.
#Include la query originale, i token singoli e i sinonimi di ciascuno.
def expand_query_terms(text: Any) -> list[str]:
    query=str(text or "").strip().lower()
    tokens=tokenize_query(query)
    terms=[query] if query else []
    for token in tokens:
        terms.append(token)
        terms.extend(SYNONYM_MAP.get(token,[]))
    return _dedupe(terms)[:18]


#Restituisce la query come stringa unica arricchita con i sinonimi.
#Usata da ProductQAService per migliorare il TF-IDF retrieval.
def expand_query_text(text: Any) -> str:
    query=str(text or "").strip()
    tokens=tokenize_query(query)
    parts=[query]
    for token in tokens:
        expansions=SYNONYM_MAP.get(token)
        if expansions:
            parts.append(" ".join(expansions))
    return " ".join(parts)
