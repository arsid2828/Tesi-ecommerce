import re
from typing import Any

from prototype.backend.schemas import Product


# Sinonimi per il recupero di evidenze nelle recensioni e nelle QA.
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


# Il catalogo usa equivalenze piu strette del recupero di evidenze testuali.
_CATALOG_ALIASES={
    term: group
    for group in (
        ("book","books","libro","libri","paperback","hardcover"),
        ("board game","board games","gioco da tavolo","giochi da tavolo"),
        ("game","games","gioco","giochi"),
        ("mouse","mice","trackball"),
        ("wireless","cordless","senza fili"),
        ("gaming","gamer"),
        ("printer","printers","stampante","stampanti"),
        ("phone","phones","smartphone","smartphones","cell phone","telefono","telefoni","cellulare","cellulari"),
        ("case","cover","custodia"),
        ("headphones","headset","earbuds","earphones","cuffie","auricolari"),
        ("vacuum","aspirapolvere"),
        ("camera","cameras","fotocamera","fotocamere"),
        ("filter","filters","filtro","filtri"),
        ("battery","batteries","batteria","batterie"),
        ("accessory","accessories","accessorio","accessori"),
        ("xbox 360","xbox360"),
        ("tp-link","tp link"),
    )
    for term in group
}
_CATALOG_ALIASES["playstation"]=("playstation","ps2","ps3","ps4","ps5","psp","ps vita")
for generation in range(2,6):
    platform=(f"playstation {generation}",f"ps{generation}")
    _CATALOG_ALIASES.update(dict.fromkeys(platform,platform))
_CATALOG_TOKEN=re.compile(
    r"\b(?:iphone|xbox|playstation)\s+\d+[a-z]*\b|"
    r"\b(?:board games?|gioch[io] da tavolo|senza fili|ps vita|xbox one|wii u|tp link)\b|[^\W_]+(?:-[^\W_]+)*"
)
_TITLE_TERMS={
    "book","board game","mouse","wireless","gaming","printer","laser","phone","case","headphones",
    "bluetooth","vacuum","playstation","psp","ps vita","xbox","xbox one","wii","wii u","hdmi","dog","collar","tp-link",
}
_BOOK_FORMAT=re.compile(r"\b(?:paperback|hardcover)\b",re.I)
_TITLE_EXCLUSIONS={
    "book": re.compile(r"\b(?:planner|book (?:stand|cover|light|shelf)|coloring book app)\b",re.I),
    "mouse": re.compile(
        r"\b(?:mickey|minnie|rodent|traps?|pest|glue boards?|mouse (?:pads?|mats?)|"
        r"(?:receivers?|cases?) for [^,;]*\b(?:mouse|mice)|replacement feet)\b",re.I,
    ),
    "printer": re.compile(
        r"\b(?:(?:ink|toner) (?:car?tridges?|refill|for)|car?tridges? ink|"
        r"(?:labels?|stickers?|cables?|paper)\b.*\b(?:for|works with)|"
        r"compatible to\b.*\bprinters?|printers? (?:ink|cables?|paper|stands?))\b",re.I,
    ),
    "phone": re.compile(
        r"\b(?:phone (?:number|mounts?|holders?|stands?|cases?|adapters?|plans?|(?:replacement )?batter(?:y|ies))|"
        r"screen protectors?|holster|stylus|armband|pouch|casepouchholster|headset adapters?|"
        r"airtime|activation kit|signal booster|mini speaker system|printers?)\b",re.I,
    ),
    "headphones": re.compile(
        r"\b(?:ear (?:pads?|cushions?)|replacement (?:single )?(?:pads?|cushions?)|windscreens?|headphone stand|car stereo|"
        r"charg(?:e|ing) case|headsets? (?:adapters?|dongles?|jacks?)|"
        r"(?:adapter|dongle)\b.*\b(?:compatible|headsets?))\b",re.I,
    ),
    "vacuum": re.compile(
        r"\b(?:vacuum seal(?:er|ing)|vacuum pumps?|vacuum breakers?|storage space saver bags?|"
        r"(?:replacement|water|dust cup|vacuum) filters?|replacement parts?|outer bags?|vacuum belts?|"
        r"vacuum (?:cleaner )?(?:disposable |replacement )?bags?)\b",re.I,
    ),
    "collar": re.compile(r"\b(?:collar batter(?:y|ies)|tags? for)\b",re.I),
}
_ACCESSORY_TERMS={
    "adapter","battery","cable","cartridge","cartuccia","case","filter","ink","mat","pad","paper","receiver","replacement","toner",
}


def _catalog_term_groups(text: Any) -> list[tuple[str,...]]:
    query=" ".join(str(text or "").lower().split())
    tokens=[query] if query in _CATALOG_ALIASES else _CATALOG_TOKEN.findall(query)
    return list(dict.fromkeys(
        _CATALOG_ALIASES.get(token,(token,))
        for token in tokens
        if token not in _STOPWORDS and token not in {"da","di","il","la","in"}
    ))


def expand_query_terms(text: Any) -> list[str]:
    return _dedupe([term for group in _catalog_term_groups(text) for term in group])


def _catalog_pattern(terms: tuple[str,...]) -> re.Pattern:
    alternatives=[
        r"[\W_]+".join(re.escape(word) for word in re.findall(r"[^\W_]+",term))
        for term in terms
    ]
    return re.compile(r"(?<!\w)(?:"+"|".join(alternatives)+r")(?!\w)",re.I)


class CatalogQuery:
    """Compila i concetti una volta e richiede una corrispondenza per ciascuno."""

    def __init__(self,query: str):
        groups=_catalog_term_groups(query)
        concepts={group[0] for group in groups}
        self.books_only=concepts == {"book"}
        self.patterns=[
            (_catalog_pattern(group),
             (group[0] in _TITLE_TERMS and not self.books_only) or any(char.isdigit() for char in group[0]))
            for group in groups
        ]
        self.excluded_titles=[
            _TITLE_EXCLUSIONS[concept] for concept in concepts if concept in _TITLE_EXCLUSIONS
        ] if not concepts & _ACCESSORY_TERMS else []
        self.gaming_only=concepts == {"gaming"}
        self.phone_only=concepts == {"phone"}

    def relevance(self,product: Product) -> float:
        title=product.title
        if any(pattern.search(title) for pattern in self.excluded_titles):
            return 0.0
        if self.gaming_only and product.category == "Toys and Games":
            return 0.0
        if self.phone_only and product.category in {"Toys and Games","Home and Kitchen","Pet Supplies"}:
            return 0.0
        if self.books_only and product.category.lower() != "books" and not _BOOK_FORMAT.search(title):
            return 0.0
        score=0.0
        for pattern,title_required in self.patterns:
            title_hit=bool(pattern.search(title))
            if title_required and not title_hit:
                return 0.0
            category_hit=bool(pattern.search(product.category))
            description_hit=bool(pattern.search(product.description or ""))
            if not (title_hit or category_hit or description_hit):
                return 0.0
            score+=2.8*title_hit + 1.4*category_hit + 1.0*description_hit
        return round(min(score / max(1.0,len(self.patterns)*4.5),1.0),4)


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
