Notebook del prototipo :
## Condizioni di arresto

La scansione di una categoria termina quando viene raggiunto:

- il numero massimo di righe di metadati da analizzare;
- oppure il numero massimo di prodotti desiderato.

Questo impedisce scansioni infinite, ma introduce un possibile **bias d’ordine**: vengono privilegiati i primi prodotti validi incontrati nel file, non un campione casuale.
## Limite metodologico

La selezione prende le prime recensioni valide incontrate nello stream.

Quindi non si tratta di:

- un campione casuale;
- le recensioni più recenti;
- le recensioni più utili;
- una selezione bilanciata per rating.

È una scelta semplice e riproducibile, adatta al prototipo, ma deve essere dichiarata se le recensioni vengono analizzate sperimentalmente.