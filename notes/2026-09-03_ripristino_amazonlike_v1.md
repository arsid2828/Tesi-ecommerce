Ripristino AmazonLike_v1 e verifica ItemKNN — 3 settembre 2026. Tutti i cinque notebook Amazon-like sono stati eseguiti integralmente, in ordine 01→05, con un kernel nuovo per ciascuno. Anche Electronics 04 è stato rieseguito integralmente da kernel pulito. Tutti i notebook sono stati salvati dopo il completamento.

File modificati: [01_prepare_amazon_like_intersection.ipynb](C:/Users/arsid/Desktop/Tesi-ecommerce/notebooks/test_dataset2/01_prepare_amazon_like_intersection.ipynb), [02_explore_amazon_like_dataset.ipynb](C:/Users/arsid/Desktop/Tesi-ecommerce/notebooks/test_dataset2/02_explore_amazon_like_dataset.ipynb), [03_prepare_amazon_like_recommender_splits.ipynb](C:/Users/arsid/Desktop/Tesi-ecommerce/notebooks/test_dataset2/03_prepare_amazon_like_recommender_splits.ipynb), [04_train_amazon_like_recommender_models.ipynb](C:/Users/arsid/Desktop/Tesi-ecommerce/notebooks/test_dataset2/04_train_amazon_like_recommender_models.ipynb), [05_amazon_like_content_based_hybrid_recommender.ipynb](C:/Users/arsid/Desktop/Tesi-ecommerce/notebooks/test_dataset2/05_amazon_like_content_based_hybrid_recommender.ipynb), [04_train_recommender_models.ipynb](C:/Users/arsid/Desktop/Tesi-ecommerce/notebooks/04_train_recommender_models.ipynb). Le modifiche alla tesi presenti prima del lavoro sono state conservate; il prototipo non è stato modificato.

Configurazione originale recuperata dal commit Git `ad12afb425ff451a829ed539fe850c9d1cf2c9c3` del 29 maggio 2026 (`scaricato reviews da amazon reviews2023`), ultima versione a sei categorie prima del passaggio alla v2. Confermata dai riepiloghi e dagli artefatti v1 ancora presenti. I Notebook 02, 03 e 05 coincidono nelle sorgenti con questa revisione; per il Notebook 01 sono stati aggiunti soltanto controlli di riuso dei file esistenti. Le modifiche locali già presenti per la cosine binaria e per il caricamento di `split_summary` sono state conservate.

Configurazione finale: `DATASET_NAME="test_dataset2"`, `DATASET_LABEL="AmazonLike_v1"`, `MAX_REVIEWS_SCAN_BY_CATEGORY=None`, `SAVE_TEXT_OFREVIEW=True`, `FORCE_REBUILD_RATINGS=False`. Nessun limite al numero di prodotti, ai metadati o ai rating salvati. `hf_category` e `qa_slug` sono uguali nelle sei categorie:

| Categoria | hf_category / qa_slug | group |
| --- | --- | --- |
| Electronics | Electronics | tech |
| Cell Phones and Accessories | Cell_Phones_and_Accessories | tech |
| Video Games | Video_Games | tech |
| Software | Software | tech |
| Office Products | Office_Products | office |
| Appliances | Appliances | home |

Il Notebook 01 ha ricostruito integralmente metadati, QA filtrati e riepiloghi. Ha riutilizzato i rating v1 esistenti dopo aver verificato identità del dataset, categorie, conteggi, schema e appartenenza di ogni prodotto alla categoria corretta. Il file `ratings.parquet` è rimasto identico byte per byte (SHA-256). Anche tutti i raw QA, inclusi i file convertiti già presenti, hanno conservato gli hash originali. Nessun artefatto della v2 è stato letto dai notebook ripristinati; le sue cartelle sono rimaste separate.

Dataset finale: 32,266 prodotti, 5,245,310 rating/interazioni e 256,988 QA. Tutte e tre le tabelle contengono esattamente le sei categorie richieste; prodotti univoci, corrispondenza completa fra metadati, rating e QA e conteggi coerenti con `summary.json` e `category_summary.csv`.

| Categoria | Prodotti | Rating/interazioni | QA |
| --- | --- | --- | --- |
| Electronics | 22,974 | 3,484,401 | 180,976 |
| Cell Phones and Accessories | 4,705 | 804,494 | 38,582 |
| Video Games | 607 | 243,902 | 6,601 |
| Software | 647 | 78,369 | 5,723 |
| Office Products | 2,702 | 518,978 | 20,244 |
| Appliances | 631 | 115,166 | 4,862 |

Percorsi degli output:

- [test_dataset2_intersection](C:/Users/arsid/Desktop/Tesi-ecommerce/data/processed/test_dataset2_intersection)
- [test_dataset2_intersection/analysis](C:/Users/arsid/Desktop/Tesi-ecommerce/data/processed/test_dataset2_intersection/analysis)
- [test_dataset2_recommender](C:/Users/arsid/Desktop/Tesi-ecommerce/data/processed/test_dataset2_recommender)
- [test_dataset2_recommender/notebook04_models](C:/Users/arsid/Desktop/Tesi-ecommerce/data/processed/test_dataset2_recommender/notebook04_models)
- [test_dataset2_recommender/notebook05_content_hybrid](C:/Users/arsid/Desktop/Tesi-ecommerce/data/processed/test_dataset2_recommender/notebook05_content_hybrid)
- [electronics_recommender/notebook04_models](C:/Users/arsid/Desktop/Tesi-ecommerce/data/processed/electronics_recommender/notebook04_models)

I file dei Notebook 02–05 sono stati rigenerati: candidati, analisi, train/validation/test, evaluation set, negativi, mapping, metriche, rank, vicini ItemKNN, embedding SVD e artefatti TF-IDF/ibridi. Elenco completo con hash: [final_artifact_manifest.json](C:/Users/arsid/Desktop/Tesi-ecommerce/data/audits/amazonlike_v1_restore_20260903/final_artifact_manifest.json).

Differenze rispetto a prima: i vecchi artefatti v1 riportavano già 32,266 prodotti, 5,245,310 interazioni e 256,988 QA; i conteggi ripristinati coincidono. La v2 usata dai notebook prima del ripristino aveva 11,451 prodotti, 125,029 interazioni e 94,100 QA, con 16 categorie. Sono stati ripristinati `user3_item8` e 100 negativi, al posto dei valori v2 `user3_item5` e 50. I percorsi salvati nei riepiloghi ora partono dalla radice del progetto e non dal vecchio percorso annidato sotto `notebooks/test_dataset2/data`.

Differenza di schema rispetto ai vecchi artefatti v1: candidati e split ora conservano anche `review_title` e `review_text`, come previsto da `SAVE_TEXT_OFREVIEW=True` nella configurazione recuperata. Tutte le colonne candidate preesistenti e l’ordine delle righe sono identici. Rimuovendo soltanto queste due colonne e riscrivendo i cinque parquet train/validation/test/eval per il confronto, si ottengono esattamente gli hash originali. Anche mapping, QA, prodotti, storico del rifiltraggio e campioni negativi sono identici byte per byte. Queste colonne testuali non sono usate dai modelli collaborativi o dal TF-IDF dei metadati dei prodotti.

Filtri e split originali: deduplicazione utente-prodotto mantenendo l’ultima interazione; almeno 3 interazioni per utente e 8 per prodotto; feedback positivo con rating ≥4; rifiltraggio iterativo con le stesse soglie; ultima interazione in test, penultima in validation, precedenti in training; seed 42. Il Notebook 02 produce 1,494,991 interazioni candidate, 336,898 utenti e 22,664 prodotti.

| Quantità dopo Notebook 03 | Valore |
| --- | --- |
| Interazioni positive finali | 992,235 |
| Utenti | 229,426 |
| Prodotti | 19,000 |
| Training | 533,383 |
| Validation | 229,426 |
| Test | 229,426 |
| Validation valutabile | 229,415 |
| Test valutabile | 229,395 |

Controlli split superati: nessun duplicato utente-item fra gli split, ID delle interazioni disgiunti, mapping completi e contigui, almeno un elemento di training per ogni utente, ordine temporale train≤validation≤test. Sono presenti 19 parità di timestamp fra ultimo train e validation e 10 fra validation e test: viene conservato lo spareggio originale tramite `interaction_id`, senza cambiare lo split. Esclusi dalla valutazione gli item cold start secondo il codice originale: 4 in validation e 4 in test.

Ogni esempio valutabile contiene un positivo e 100 negativi distinti, tutti presenti nel training ed esclusi dallo storico positivo completo dell’utente. Campionamento originale `mixed_category`: obiettivo di 50 negativi dalla stessa categoria, completamento dal pool globale. Nessun leakage rilevato dai controlli su interazioni e candidati.

ItemKNN in entrambi i Notebook 04: `USE_RATING_VALUES=False`; ogni interazione positiva osservata vale 1; gli zeri indicano assenza di interazione. Le celle ItemKNN sono identiche: `item_user_matrix=train_matrix.T.tocsr().astype(np.float32)` e `NearestNeighbors(...,metric="cosine",algorithm="brute",...)`. Nessun adjusted cosine, `adjusted_train_matrix`, `user_means` o sottrazione della media utente. Restano invariati rimozione dell’item stesso, filtro delle similarità ≤0, primi K vicini, `neighbor_lookup` e scoring dallo storico positivo.

| Dataset | Righe training | nnz | Min | Max | Valori distinti | Duplicati |
| --- | --- | --- | --- | --- | --- | --- |
| Electronics | 287752 | 287752 | 1.0 | 1.0 | [1.0] | 0 |
| AmazonLike_v1 | 533383 | 533383 | 1.0 | 1.0 | [1.0] | 0 |

Per entrambi sono stati anche confrontati 200 valori di similarità salvati con la formula del coseno calcolata direttamente sulla matrice binaria: verifiche superate entro 1e-6. I notebook interrompono l’esecuzione prima della valutazione se rilevano duplicati o valori non binari.

Electronics 04: migliore su validation MostPopular; migliore SVD SVD_4. Tutte le metriche coincidono con gli output locali precedenti. Gli hash dei dataset e degli split Electronics sono invariati. Risultati validation:

| Modello | HitRate@10 | Recall@10 | NDCG@10 | MRR@10 |
| --- | --- | --- | --- | --- |
| MostPopular | 0.464293 | 0.464293 | 0.284317 | 0.229132 |
| ItemKNN_5 | 0.106785 | 0.106785 | 0.060816 | 0.047120 |
| ItemKNN_10 | 0.112068 | 0.112068 | 0.066000 | 0.052254 |
| ItemKNN_50 | 0.133860 | 0.133860 | 0.083730 | 0.068605 |
| ItemKNN_100 | 0.152258 | 0.152258 | 0.095706 | 0.078517 |
| SVD_2 | 0.434189 | 0.434189 | 0.269721 | 0.219165 |
| SVD_4 | 0.444381 | 0.444381 | 0.275201 | 0.223258 |
| SVD_6 | 0.443468 | 0.443468 | 0.273863 | 0.221809 |
| SVD_8 | 0.438398 | 0.438398 | 0.270965 | 0.219558 |
| SVD_10 | 0.438703 | 0.438703 | 0.270385 | 0.218657 |
| SVD_12 | 0.434828 | 0.434828 | 0.267599 | 0.216214 |
| SVD_16 | 0.426037 | 0.426037 | 0.262517 | 0.212279 |
| SVD_24 | 0.408065 | 0.408065 | 0.248977 | 0.200116 |
| SVD_32 | 0.395810 | 0.395810 | 0.240402 | 0.192737 |

Risultati Electronics sul test:

| Modello | HitRate@10 | Recall@10 | NDCG@10 | MRR@10 |
| --- | --- | --- | --- | --- |
| MostPopular | 0.480998 | 0.480998 | 0.300195 | 0.244596 |
| ItemKNN_5 | 0.092865 | 0.092865 | 0.049650 | 0.036722 |
| ItemKNN_10 | 0.096024 | 0.096024 | 0.052610 | 0.039611 |
| ItemKNN_50 | 0.109614 | 0.109614 | 0.062603 | 0.048454 |
| ItemKNN_100 | 0.125579 | 0.125579 | 0.072880 | 0.056909 |
| SVD_2 | 0.455836 | 0.455836 | 0.286942 | 0.234960 |
| SVD_4 | 0.466898 | 0.466898 | 0.295019 | 0.242076 |
| SVD_6 | 0.464858 | 0.464858 | 0.292300 | 0.239100 |
| SVD_8 | 0.458988 | 0.458988 | 0.288635 | 0.236114 |
| SVD_10 | 0.455273 | 0.455273 | 0.285002 | 0.232539 |
| SVD_12 | 0.448665 | 0.448665 | 0.279262 | 0.227070 |
| SVD_16 | 0.437938 | 0.437938 | 0.272268 | 0.221236 |
| SVD_24 | 0.411870 | 0.411870 | 0.253445 | 0.204694 |
| SVD_32 | 0.397124 | 0.397124 | 0.242729 | 0.195289 |

AmazonLike_v1 04: migliore su validation MostPopular; migliore SVD SVD_4. La selezione usa esclusivamente NDCG@10 sulla validation e precede la valutazione test. Tutte le 14 configurazioni previste sono state mantenute. Tutte le metriche coincidono con gli artefatti v1 precedenti. Risultati validation:

| Modello | HitRate@10 | Recall@10 | NDCG@10 | MRR@10 |
| --- | --- | --- | --- | --- |
| MostPopular | 0.479790 | 0.479790 | 0.291976 | 0.234440 |
| ItemKNN_5 | 0.105351 | 0.105351 | 0.061755 | 0.048772 |
| ItemKNN_10 | 0.111130 | 0.111130 | 0.067197 | 0.054090 |
| ItemKNN_50 | 0.132228 | 0.132228 | 0.084458 | 0.070063 |
| ItemKNN_100 | 0.148103 | 0.148103 | 0.095527 | 0.079550 |
| SVD_2 | 0.456409 | 0.456409 | 0.279107 | 0.224708 |
| SVD_4 | 0.463505 | 0.463505 | 0.284039 | 0.228983 |
| SVD_6 | 0.463366 | 0.463366 | 0.283892 | 0.228814 |
| SVD_8 | 0.462529 | 0.462529 | 0.283430 | 0.228474 |
| SVD_10 | 0.459190 | 0.459190 | 0.280559 | 0.225742 |
| SVD_12 | 0.454316 | 0.454316 | 0.275948 | 0.221252 |
| SVD_16 | 0.453432 | 0.453432 | 0.276135 | 0.221724 |
| SVD_24 | 0.441846 | 0.441846 | 0.267185 | 0.213614 |
| SVD_32 | 0.432923 | 0.432923 | 0.262177 | 0.209811 |

Risultati AmazonLike_v1 sul test:

| Modello | HitRate@10 | Recall@10 | NDCG@10 | MRR@10 |
| --- | --- | --- | --- | --- |
| MostPopular | 0.500303 | 0.500303 | 0.309639 | 0.251085 |
| ItemKNN_5 | 0.094536 | 0.094536 | 0.050802 | 0.037688 |
| ItemKNN_10 | 0.098006 | 0.098006 | 0.053913 | 0.040682 |
| ItemKNN_50 | 0.110988 | 0.110988 | 0.063725 | 0.049483 |
| ItemKNN_100 | 0.123272 | 0.123272 | 0.071765 | 0.056165 |
| SVD_2 | 0.478062 | 0.478062 | 0.297560 | 0.242046 |
| SVD_4 | 0.487604 | 0.487604 | 0.305384 | 0.249333 |
| SVD_6 | 0.486977 | 0.486977 | 0.304710 | 0.248590 |
| SVD_8 | 0.484836 | 0.484836 | 0.303347 | 0.247473 |
| SVD_10 | 0.478986 | 0.478986 | 0.298570 | 0.243034 |
| SVD_12 | 0.469954 | 0.469954 | 0.290251 | 0.234974 |
| SVD_16 | 0.467495 | 0.467495 | 0.289300 | 0.234479 |
| SVD_24 | 0.448693 | 0.448693 | 0.273580 | 0.219779 |
| SVD_32 | 0.436657 | 0.436657 | 0.266610 | 0.214378 |

In queste valutazioni c’è un solo positivo per esempio, quindi HitRate@10 e Recall@10 coincidono. Le prestazioni inferiori di ItemKNN sono state conservate come risultato sperimentale, senza modificare gli altri modelli.

AmazonLike_v1 05: TF-IDF originale, 20.000 feature, unigrammi e bigrammi, min_df=2, max_df=0,85 e stop word inglesi. I profili usano soltanto il training. Embedding SVD e segnali di popolarità provengono dal Notebook 04 appena eseguito. Ricerca originale di 231 combinazioni, passo 0,05, esclusivamente sulla validation; mantenute le prime cinque per i rank dettagliati e la valutazione test. Migliore modello: `HybridGrid_SVD4_010_Content_025_Pop_065`.

Anche tutte le metriche del Notebook 05 coincidono con quelle degli artefatti v1 precedenti. Il modello 15/25/60 ottiene sul test un NDCG@10 leggermente superiore (0,316955), ma la configurazione selezionata rimane 10/25/65, scelta sulla validation.

Risultati Notebook 05 sulla validation, limitati ai modelli portati al test; tutte le 231 configurazioni sono nel CSV della griglia:

| Modello | HitRate@10 | Recall@10 | NDCG@10 | MRR@10 |
| --- | --- | --- | --- | --- |
| ContentTFIDF | 0.255642 | 0.255642 | 0.151124 | 0.119436 |
| HybridGrid_SVD4_005_Content_030_Pop_065 | 0.508781 | 0.508781 | 0.311643 | 0.250950 |
| HybridGrid_SVD4_010_Content_025_Pop_065 | 0.512765 | 0.512765 | 0.311657 | 0.249826 |
| HybridGrid_SVD4_010_Content_030_Pop_060 | 0.508476 | 0.508476 | 0.311628 | 0.251021 |
| HybridGrid_SVD4_015_Content_025_Pop_060 | 0.512373 | 0.512373 | 0.311641 | 0.249922 |
| HybridGrid_SVD4_015_Content_030_Pop_055 | 0.508066 | 0.508066 | 0.311526 | 0.251013 |
| Hybrid_Content70_Pop30 | 0.418495 | 0.418495 | 0.232203 | 0.175309 |
| Hybrid_SVD70_Content30 | 0.484951 | 0.484951 | 0.298243 | 0.240749 |
| Hybrid_SVD50_Content25_Pop25 | 0.503232 | 0.503232 | 0.306525 | 0.246009 |
| Hybrid_SVD40_Content40_Pop20 | 0.484746 | 0.484746 | 0.302864 | 0.246908 |

Risultati Notebook 05 sul test:

| Modello | HitRate@10 | Recall@10 | NDCG@10 | MRR@10 |
| --- | --- | --- | --- | --- |
| ContentTFIDF | 0.205855 | 0.205855 | 0.115320 | 0.088055 |
| Hybrid_Content70_Pop30 | 0.394058 | 0.394058 | 0.205998 | 0.148748 |
| Hybrid_SVD70_Content30 | 0.478637 | 0.478637 | 0.303228 | 0.249315 |
| Hybrid_SVD50_Content25_Pop25 | 0.499601 | 0.499601 | 0.313166 | 0.255802 |
| Hybrid_SVD40_Content40_Pop20 | 0.472909 | 0.472909 | 0.302276 | 0.249949 |
| HybridGrid_SVD4_010_Content_025_Pop_065 | 0.508559 | 0.508559 | 0.316937 | 0.257954 |
| HybridGrid_SVD4_005_Content_030_Pop_065 | 0.501628 | 0.501628 | 0.314528 | 0.256941 |
| HybridGrid_SVD4_015_Content_025_Pop_060 | 0.507975 | 0.507975 | 0.316955 | 0.258152 |
| HybridGrid_SVD4_010_Content_030_Pop_060 | 0.501096 | 0.501096 | 0.314581 | 0.257160 |
| HybridGrid_SVD4_015_Content_030_Pop_055 | 0.500525 | 0.500525 | 0.314461 | 0.257176 |

Errori e anomalie: nessun errore nelle esecuzioni finali dei sei notebook. Nei rating iniziali il Notebook 02 rileva 104.203 righe appartenenti a 47.889 coppie utente-prodotto duplicate: la deduplicazione originale rimuove 56.314 righe e lascia 5.188.996 interazioni pulite. Non sono stati trovati duplicati nelle matrici di training. Le parità temporali e l’esclusione degli item cold start sono documentate sopra e rispettano il comportamento originale. È stato conservato il caricamento esplicito di `split_summary` già presente nelle modifiche locali. Eventuali avvisi non bloccanti delle librerie sono registrati in [final_checks.json](C:/Users/arsid/Desktop/Tesi-ecommerce/data/audits/amazonlike_v1_restore_20260903/final_checks.json).

Esecuzioni complete e salvataggi verificati. Orari UTC; ciascuna sequenza di execution_count riparte da 1:

| Notebook | Celle codice | Inizio UTC | Fine UTC | Secondi |
| --- | --- | --- | --- | --- |
| [01_prepare_amazon_like_intersection.ipynb](C:/Users/arsid/Desktop/Tesi-ecommerce/notebooks/test_dataset2/01_prepare_amazon_like_intersection.ipynb) | 12 | 2026-09-03T14:35:03.958885Z | 2026-09-03T14:49:29.364663Z | 867.3 |
| [02_explore_amazon_like_dataset.ipynb](C:/Users/arsid/Desktop/Tesi-ecommerce/notebooks/test_dataset2/02_explore_amazon_like_dataset.ipynb) | 32 | 2026-09-03T14:49:48.391798Z | 2026-09-03T14:59:27.139029Z | 580.5 |
| [03_prepare_amazon_like_recommender_splits.ipynb](C:/Users/arsid/Desktop/Tesi-ecommerce/notebooks/test_dataset2/03_prepare_amazon_like_recommender_splits.ipynb) | 26 | 2026-09-03T14:59:43.256939Z | 2026-09-03T15:00:33.924216Z | 52.3 |
| [04_train_amazon_like_recommender_models.ipynb](C:/Users/arsid/Desktop/Tesi-ecommerce/notebooks/test_dataset2/04_train_amazon_like_recommender_models.ipynb) | 24 | 2026-09-03T15:01:36.431982Z | 2026-09-03T15:13:32.447044Z | 717.8 |
| [05_amazon_like_content_based_hybrid_recommender.ipynb](C:/Users/arsid/Desktop/Tesi-ecommerce/notebooks/test_dataset2/05_amazon_like_content_based_hybrid_recommender.ipynb) | 29 | 2026-09-03T15:14:11.692333Z | 2026-09-03T15:39:23.428478Z | 1513.8 |
| [04_train_recommender_models.ipynb](C:/Users/arsid/Desktop/Tesi-ecommerce/notebooks/04_train_recommender_models.ipynb) | 23 | 2026-09-03T14:35:33.772484Z | 2026-09-03T14:42:50.778077Z | 438.9 |

Evidenze, configurazione originale, copie precedenti, log e controlli sono conservati in [data/audits/amazonlike_v1_restore_20260903](C:/Users/arsid/Desktop/Tesi-ecommerce/data/audits/amazonlike_v1_restore_20260903).
