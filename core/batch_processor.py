import os
import zipfile
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from PyQt6.QtCore import QThread, pyqtSignal

# Importiamo le funzioni pure dai nostri moduli core
from .optical_engine import extract_data, ExtractionError
from .cv_aligner import calculate_alignment_shift, AlignmentError

def _process_single_pdf(pdf_path: str, template_dict: dict, export_dir: str) -> dict:
    """
    Funzione worker globale (indipendente dalla classe QThread) progettata per
    essere eseguita all'interno di un ProcessPoolExecutor.
    Non deve contenere riferimenti alla GUI o a oggetti PyQt non serializzabili (pickle).

    Args:
        pdf_path (str): Il percorso del PDF da elaborare.
        template_dict (dict): Il dizionario del template caricato.
        export_dir (str): La cartella temporanea in cui salvare il file Excel se va a buon fine.

    Returns:
        dict: Risultato dell'operazione contenente:
              {"pdf_name": str, "status": "Success" | "Error", "message": str, "excel_path": str | None}
    """
    file_name = os.path.basename(pdf_path)
    base_name = os.path.splitext(file_name)[0]

    try:
        # 1. Calcolo dell'allineamento
        try:
            shift_x, shift_y = calculate_alignment_shift(pdf_path, template_dict, dpi=300)
        except AlignmentError as e:
            # Fallimento nell'allineamento (es. confidence bassa)
            return {"pdf_name": file_name, "status": "Error", "message": f"Allineamento: {str(e)}", "excel_path": None}

        # 2. Estrazione dati raster
        try:
            df = extract_data(pdf_path, template_dict, shift_x, shift_y)
        except ExtractionError as e:
            # Fallimento nell'estrazione (es. nessun box o pdf vuoto/non valido)
            return {"pdf_name": file_name, "status": "Error", "message": f"Estrazione: {str(e)}", "excel_path": None}

        # 3. Salvataggio in Excel
        excel_path = os.path.join(export_dir, f"{base_name}_extracted.xlsx")
        df.to_excel(excel_path, index=False)

        return {"pdf_name": file_name, "status": "Success", "message": "Estrazione completata", "excel_path": excel_path}

    except Exception as e:
        # Catturiamo qualsiasi altro errore non previsto (es. file lock, permessi)
        return {"pdf_name": file_name, "status": "Error", "message": f"Errore generico: {str(e)}", "excel_path": None}


class BatchWorker(QThread):
    """
    Orchestratore QThread per gestire l'elaborazione in batch in background
    senza bloccare la GUI principale. Utilizza multiprocessing.ProcessPoolExecutor
    per superare i limiti del GIL e accelerare l'estrazione ottica.
    """

    # Segnali PyQt per comunicare con la UI
    progress_updated = pyqtSignal(int, int, str) # (corrente, totale, messaggio)
    file_processed = pyqtSignal(str, str, str)   # (nome_file, status, messaggio)
    batch_finished = pyqtSignal(str)             # (percorso_file_zip_generato)
    batch_error = pyqtSignal(str)                # (messaggio_di_errore_critico)

    def __init__(self, pdf_paths: list, template_dict: dict, output_zip_path: str, max_workers: int = None):
        """
        Args:
            pdf_paths (list): Lista di percorsi assoluti ai file PDF da elaborare.
            template_dict (dict): Il dizionario contenente la configurazione del template.
            output_zip_path (str): Il percorso dove l'utente vuole salvare l'archivio ZIP finale.
            max_workers (int, optional): Numero di processi da usare (default: max core disponibili - 1).
        """
        super().__init__()
        self.pdf_paths = pdf_paths
        self.template_dict = template_dict
        self.output_zip_path = output_zip_path

        # Lasciamo 1 core libero per non congelare completamente il sistema operativo dell'utente
        self.max_workers = max_workers or max(1, os.cpu_count() - 1)
        self._is_cancelled = False

    def cancel(self):
        """Metodo per richiedere la cancellazione anticipata del batch."""
        self._is_cancelled = True

    def run(self):
        """
        Entry point del QThread. Orchestrazione del batch.
        """
        total_files = len(self.pdf_paths)
        if total_files == 0:
            self.batch_error.emit("Nessun PDF fornito per l'elaborazione.")
            return

        # Creiamo una cartella temporanea (nella stessa dir dello zip) per raccogliere gli excel
        output_dir = os.path.dirname(self.output_zip_path)
        temp_dir = os.path.join(output_dir, "temp_cptu_batch")
        os.makedirs(temp_dir, exist_ok=True)

        results_log = []
        processed_count = 0
        excel_files_to_zip = []

        self.progress_updated.emit(0, total_files, "Inizializzazione pool multiprocessing...")

        try:
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                # Creiamo i job per il pool di processi
                futures = {
                    executor.submit(_process_single_pdf, pdf, self.template_dict, temp_dir): pdf
                    for pdf in self.pdf_paths
                }

                # Raccogliamo i risultati man mano che terminano
                for future in as_completed(futures):
                    if self._is_cancelled:
                        self.progress_updated.emit(processed_count, total_files, "Annullamento in corso...")
                        # Tenta di cancellare i job in sospeso
                        for f in futures:
                            f.cancel()
                        break

                    res = future.result()
                    results_log.append({
                        "File": res["pdf_name"],
                        "Status": res["status"],
                        "Message": res["message"]
                    })

                    if res["status"] == "Success" and res["excel_path"]:
                        excel_files_to_zip.append(res["excel_path"])

                    processed_count += 1

                    # Notifichiamo la UI del progresso e dell'esito del singolo file
                    self.file_processed.emit(res["pdf_name"], res["status"], res["message"])
                    self.progress_updated.emit(processed_count, total_files, f"Elaborato {res['pdf_name']}")

            if self._is_cancelled:
                self.batch_error.emit("Elaborazione batch annullata dall'utente.")
                return

            # Fase finale: Creazione log CSV e file ZIP
            self.progress_updated.emit(processed_count, total_files, "Generazione archivio ZIP finale...")

            log_df = pd.DataFrame(results_log)
            log_csv_path = os.path.join(temp_dir, "Batch_Report_Log.csv")
            log_df.to_csv(log_csv_path, index=False, sep=";", encoding="utf-8-sig") # utf-8-sig per l'apertura ottimale in Excel

            with zipfile.ZipFile(self.output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # Aggiungiamo il report
                zipf.write(log_csv_path, arcname="Batch_Report_Log.csv")
                # Aggiungiamo i file excel processati con successo
                for excel_file in excel_files_to_zip:
                    if os.path.exists(excel_file):
                        zipf.write(excel_file, arcname=os.path.basename(excel_file))

            # Pulizia dei file temporanei
            for file_path in excel_files_to_zip + [log_csv_path]:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except OSError:
                    pass # Ignoriamo file temporanei bloccati o non trovati

            try:
                os.rmdir(temp_dir)
            except OSError:
                pass

            self.progress_updated.emit(total_files, total_files, "Batch completato!")
            self.batch_finished.emit(self.output_zip_path)

        except Exception as e:
            self.batch_error.emit(f"Errore critico durante l'orchestrazione del batch: {str(e)}")
