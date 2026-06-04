Nel **Notebook 05 Electronics** abbiamo ottenuto questo: il dataset usato per gli esperimenti contiene **131.398 utenti**, **12.306 prodotti** e **550.548 interazioni finali**. Dai metadati dei prodotti abbiamo costruito testi completi senza prodotti vuoti, poi una rappresentazione **TF-IDF da 20.000 feature**.

Il modello **ContentTFIDF da solo** funziona, ma non abbastanza: su validation arriva a **NDCG@10 = 0,164**, quindi i soli metadati testuali non bastano per battere bene i modelli collaborativi.

Il risultato importante è il modello ibrido scelto su validation:

```
HybridGrid_SVD4_010_Content_035_Pop_055
```

cioè circa **10% SVD + 35% contenuto + 55% popolarità**. Su test ottiene:

```
HitRate@10 = 0,485329NDCG@10 = 0,307328MRR@10 = 0,252566
```

Rispetto a **MostPopular**, migliora poco ma migliora: **+0,007133 NDCG@10** sul test. Quindi abbiamo capito una cosa importante: nel dataset Electronics la **popolarità pesa molto**, il contenuto aiuta, mentre SVD da solo non basta a superare nettamente la baseline.

Per il futuro ci servono soprattutto tre cose: usare questo ibrido come modello principale del prototipo, usare **MostPopular** come fallback, e usare **ContentTFIDF** per i “prodotti simili”. Poi nel Notebook 06 bisogna fare analisi finale dei risultati, e nel Notebook 07 esportare prodotti, utenti demo, raccomandazioni e artefatti per il sito, coerentemente con il piano già fissato per passare dagli esperimenti al prototipo.