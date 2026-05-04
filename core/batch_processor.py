import os
import zipfile
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed
from PyQt6.QtCore import QThread, pyqtSignal
import fitz

from .optical_engine import extract_data, ExtractionError
from .cv_aligner import calculate_alignment_shift, AlignmentError

def _process_single_pdf(pdf_path: str, template_dict: dict, export_dir: str) -> dict:
    file_name = os.path.basename(pdf_path)
    base_name = os.path.splitext(file_name)[0]

    try:
        # Auto-orientation check: if landscape, but template is portrait (0 rotation), we might need to adjust
        # For simplicity, if base_rotation is 0 but page is wider than tall, rotate 90
        # For now, we trust the template's base_rotation, or attempt auto-fix if match fails

        try:
            shift_x, shift_y = calculate_alignment_shift(pdf_path, template_dict, dpi=300)
        except AlignmentError as e:
            # Let's try auto-rotating if it failed and it's a landscape page
            try:
                doc = fitz.open(pdf_path)
                page = doc[0]
                is_landscape = page.rect.width > page.rect.height
                doc.close()

                if is_landscape and template_dict.get("base_rotation", 0) == 0:
                    # Temporarily override rotation for this file
                    temp_dict = template_dict.copy()
                    temp_dict["base_rotation"] = 90
                    shift_x, shift_y = calculate_alignment_shift(pdf_path, temp_dict, dpi=300)
                    template_dict = temp_dict # Keep it for extraction
                else:
                    raise e
            except Exception as e2:
                return {"pdf_name": file_name, "status": "Error", "message": f"Allineamento: {str(e2)}", "excel_path": None}

        try:
            df = extract_data(pdf_path, template_dict, shift_x, shift_y)
        except ExtractionError as e:
            return {"pdf_name": file_name, "status": "Error", "message": f"Estrazione: {str(e)}", "excel_path": None}

        excel_path = os.path.join(export_dir, f"{base_name}_extracted.xlsx")
        df.to_excel(excel_path, index=False)

        return {"pdf_name": file_name, "status": "Success", "message": "Estrazione completata", "excel_path": excel_path}

    except Exception as e:
        return {"pdf_name": file_name, "status": "Error", "message": f"Errore generico: {str(e)}", "excel_path": None}


class BatchWorker(QThread):
    progress_updated = pyqtSignal(int, int, str)
    file_processed = pyqtSignal(str, str, str)
    batch_finished = pyqtSignal(str)
    batch_error = pyqtSignal(str)

    def __init__(self, pdf_paths: list, template_dict: dict, output_zip_path: str, max_workers: int = None):
        super().__init__()
        self.pdf_paths = pdf_paths
        self.template_dict = template_dict
        self.output_zip_path = output_zip_path
        self.max_workers = max_workers or max(1, os.cpu_count() - 1)
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        total_files = len(self.pdf_paths)
        if total_files == 0:
            self.batch_error.emit("Nessun PDF fornito per l'elaborazione.")
            return

        output_dir = os.path.dirname(self.output_zip_path)
        temp_dir = os.path.join(output_dir, "temp_cptu_batch")
        os.makedirs(temp_dir, exist_ok=True)

        results_log = []
        processed_count = 0
        excel_files_to_zip = []

        self.progress_updated.emit(0, total_files, "Inizializzazione pool multiprocessing...")

        try:
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(_process_single_pdf, pdf, self.template_dict, temp_dir): pdf
                    for pdf in self.pdf_paths
                }

                for future in as_completed(futures):
                    if self._is_cancelled:
                        self.progress_updated.emit(processed_count, total_files, "Annullamento in corso...")
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
                    self.file_processed.emit(res["pdf_name"], res["status"], res["message"])
                    self.progress_updated.emit(processed_count, total_files, f"Elaborato {res['pdf_name']}")

            if self._is_cancelled:
                self.batch_error.emit("Elaborazione batch annullata dall'utente.")
                return

            self.progress_updated.emit(processed_count, total_files, "Generazione archivio ZIP finale...")

            log_df = pd.DataFrame(results_log)
            log_csv_path = os.path.join(temp_dir, "Batch_Report_Log.csv")
            log_df.to_csv(log_csv_path, index=False, sep=";", encoding="utf-8-sig")

            with zipfile.ZipFile(self.output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(log_csv_path, arcname="Batch_Report_Log.csv")
                for excel_file in excel_files_to_zip:
                    if os.path.exists(excel_file):
                        zipf.write(excel_file, arcname=os.path.basename(excel_file))

            for file_path in excel_files_to_zip + [log_csv_path]:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except OSError:
                    pass

            try:
                os.rmdir(temp_dir)
            except OSError:
                pass

            self.progress_updated.emit(total_files, total_files, "Batch completato!")
            self.batch_finished.emit(self.output_zip_path)

        except Exception as e:
            self.batch_error.emit(f"Errore critico durante l'orchestrazione del batch: {str(e)}")
