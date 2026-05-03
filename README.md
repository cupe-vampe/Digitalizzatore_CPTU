# CPTU Vector Digitizer Pro 📈

Un'applicazione desktop sviluppata in Python (Tkinter) per l'estrazione precisa e automatizzata dei dati geotecnici (resistenza alla punta `qc`, attrito laterale `fs`, pressione interstiziale `u`) direttamente dalle scansioni vettoriali in PDF delle prove penetrometriche CPTU.

## 🚀 Caratteristiche Principali

A differenza dei normali digitalizzatori basati su immagini o OCR, questo tool **legge direttamente la matematica del PDF vettoriale**, garantendo una precisione assoluta:

*   **Interfaccia Grafica Intuitiva:** Strumenti CAD-like (Pan, Zoom, Selezione, Disegno maschere).
*   **Rotazione di Precisione:** Possibilità di raddrizzare PDF con rotazioni decimali per un allineamento perfetto con la griglia.
*   **Motore di Estrazione Vettoriale:** Cattura segmenti e curve di Bézier calcolandone l'esatta posizione spaziale.
*   **Filtri Ottici e Geometrici Avanzati:** 
    *   Algoritmo di distanza Euclidea dei colori per isolare singole curve (Rosso, Blu, Verde).
    *   Filtro anti-cornice e anti-campitura (scarta ombreggiature, griglie e riempimenti).
*   **Gestione Unità di Misura:** Conversione integrata in fase di esportazione (es. da kPa a MPa).
*   **Preview Interattiva:** Controllo visivo dei dati estratti tramite grafici matplotlib prima del salvataggio.
*   **Export Diretto in Excel:** Generazione automatica di un DataFrame pandas pulito ed esportazione in `.xlsx`.

## 🛠️ Installazione

1. Clona la repository:
   ```bash
   git clone [https://github.com/TUO-NOME-UTENTE/cptu-vector-digitizer.git](https://github.com/TUO-NOME-UTENTE/cptu-vector-digitizer.git)
