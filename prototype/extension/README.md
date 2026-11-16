# Estensione Chrome

L’estensione mostra consigli nel popup a partire dalla scheda prodotto aperta. Sul sito locale usa il catalogo del prototipo. Su Amazon legge i prodotti correlati già presenti nella pagina e usa il backend, se disponibile, per rifinire i suggerimenti.

## Installazione locale

1. [Avvia la demo](../README.md) con frontend sulla porta 3000 e backend sulla porta 8000.
2. Apri `chrome://extensions` in Chrome e attiva **Modalità sviluppatore**.
3. Seleziona **Carica estensione non pacchettizzata** e scegli la cartella `prototype/extension/`.
4. Apri una scheda prodotto della demo e fai clic sull’icona dell’estensione.

Puoi provare il popup anche su una pagina prodotto di Amazon.it, Amazon.com, Amazon.co.uk, Amazon.de, Amazon.fr o Amazon.es. I suggerimenti dipendono dalle schede correlate che l’estensione riesce a leggere nella pagina. Il popup può mostrarli anche se il backend locale è spento.
