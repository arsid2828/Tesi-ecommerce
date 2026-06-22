from prototype.backend.schemas import Product


#Cerchiamo nei prodotti e ordiniamo con baseline popularity
#La ricerca resta semplice: filtro categoria,match testuale e fallback con sinonimi
#Il risultato viene sempre riordinato per popolarita per mantenere una baseline chiara
def search_products(
    products: list[Product],
    query: str | None, #testo scritto dall'utente
    category: str | None=None, #categoria opzionale
    limit: int=30,
) -> list[Product]:
    filtered=products #lista corrente su cui applichiamo filtri progressivi
    #applichiamo prima il filtro categoria
    if category:
        normalized_category=category.lower()
        filtered=[
            product for product in filtered if product.category.lower() == normalized_category
        ]

    normalized_query=(query or "").strip().lower() #gestisce None e normalizza confronto testuale
    #filtriamo sui campi testuali
    if normalized_query:
        exact_matches=[
            product
            for product in filtered
            if _matches_query(product,normalized_query)
        ]
        #se la query esatta non trova nulla, usiamo pochi sinonimi utili al dataset demo
        if exact_matches:
            filtered=exact_matches
        else:
            query_tokens=[token for token in normalized_query.split() if len(token) > 1]
            all_token_matches=[
                product
                for product in filtered
                if query_tokens and all(_matches_query(product,token) for token in query_tokens)
            ]
            if all_token_matches:
                filtered=all_token_matches
            else:
                expanded_terms=_expanded_query_terms(normalized_query) #aggiunge sinonimi IT->EN utili al dataset
                filtered=[
                    product
                    for product in filtered
                    if any(_matches_query(product,term) for term in expanded_terms)
                ]
    #ordinati per popolarità
    ordered=sorted(filtered,key=lambda product: product.popularity_score,reverse=True)
    return ordered[:limit]


#Verifichiamo se la query compare nei campi cercabili
#Unifichiamo titolo,categoria e descrizione in un solo testo normalizzato
#Questo e semplice ma spiegabile per una demo didattica
def _matches_query(product: Product,query: str) -> bool:
    searchable_text=" ".join( #unisce, titolo categoria e descrizione
        [
            product.title or "",
            product.category or "",
            product.description or "",
        ]
    ).lower()
    return query in searchable_text #se presente, ritorna true, sennò false


#Espandiamo la query con pochi sinonimi manuali
#Serve per collegare ricerche in italiano a titoli/descrizioni spesso in inglese
#La lista unique_terms evita duplicati mantenendo l'ordine originale
def _expanded_query_terms(query: str) -> list[str]:
    synonyms={
        "telefono": ["phone","cell phone","smartphone"],
        "telefoni": ["phone","cell phone","smartphone"],
        "cellulare": ["phone","cell phone","smartphone"],
        "cellulari": ["phone","cell phone","smartphone"],
        "fotocamera": ["camera","photo"],
        "foto": ["camera","photo"],
        "batteria": ["battery","charge"],
        "gaming": ["gaming","game","video games"],
        "giochi": ["game","video games"],
        "economico": ["cheap","budget","low price"],
        "economici": ["cheap","budget","low price"],
        "accessori": ["accessories"],
        "cuffie": ["headphones","earbuds"],
        "custodia": ["case","cover"],
    }
    terms=[query]
    for token in query.split():
        terms.extend(synonyms.get(token,[])) #se il token non ha sinonimi non aggiunge nulla

    unique_terms=[]
    for term in terms:
        clean=term.strip().lower()
        if clean and clean not in unique_terms: #deduplica preservando ordine
            unique_terms.append(clean)
    return unique_terms
