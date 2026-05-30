## Sul modello:
Il modello supera la baseline, ma il margine non è enorme. Potrei continuare a fare tuning, però non so se sia la scelta migliore: vorrei capire se conviene fermare qui la parte sperimentale e usare il modello migliore come base per un prototipo, oppure se secondo lei serve ancora rafforzare il confronto tra modelli.

## Sul prototipo:
Finora il recommender usa lo storico dei rating, quindi lavora su dati passati. Però in un contesto e-commerce reale sono molto importanti anche i segnali immediati della sessione: prodotti visualizzati, click, tempo di permanenza, aggiunta al carrello e acquisto. Vorrei quindi costruire un prototipo in cui il modello offline fornisce le raccomandazioni iniziali, mentre un livello session-based semplice aggiorna temporaneamente i consigli in base al comportamento corrente dell’utente.

## Sul sistema QA:
Ho iniziato a ragionare su una possibile estensione QA per prodotto. L’idea non sarebbe usare API esterne o un chatbot generico, ma costruire un sistema controllato che risponde alle domande usando solo evidenze presenti nei dati: metadati prodotto, QA storiche e recensioni testuali. Il sistema potrebbe recuperare frasi rilevanti dalle recensioni e generare una risposta breve, mostrando anche le evidenze usate.



1. Il livello raggiunto dal recommender è sufficiente per una tesi triennale, oppure serve migliorare ancora il modello?
2. È più utile investire tempo in altri modelli oppure in un prototipo web dimostrativo?
3. Ha senso includere una personalizzazione di sessione basata su click, view, carrello e acquisti simulati? E sistema QA?
4. Preferisce che il contributo finale sia soprattutto sperimentale, cioè confronto tra modelli, oppure applicativo, cioè prototipo funzionante?