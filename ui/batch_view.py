import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QProgressBar, QPlainTextEdit, QListWidget, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, QUrl
from core.template_manager import TemplateManager, TemplateValidationError
from core.batch_processor import BatchWorker

class DragDropListWidget(QListWidget):
    """QListWidget personalizzata per accettare file PDF tramite Drag & Drop."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            urls = event.mimeData().urls()
            for url in urls:
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if path.lower().endswith('.pdf'):
                        # Evita duplicati
                        items = self.findItems(path, Qt.MatchFlag.MatchExactly)
                        if not items:
                            self.addItem(path)
        else:
            event.ignore()

class BatchDashboardView(QWidget):
    """View per la gestione del caricamento batch e monitoraggio esecuzione."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.template_dict = None
        self.worker = None
        self.setup_ui()
        self.apply_dark_theme()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # -- SEZIONE SUPERIORE: Template e Controlli --
        top_layout = QHBoxLayout()

        self.btn_load_template = QPushButton("📂 Carica Template JSON")
        self.btn_load_template.setFixedWidth(200)
        self.lbl_template_name = QLabel("Nessun template selezionato")
        self.lbl_template_name.setStyleSheet("color: #e74c3c; font-weight: bold;")

        top_layout.addWidget(self.btn_load_template)
        top_layout.addWidget(self.lbl_template_name)
        top_layout.addStretch()

        # -- SEZIONE CENTRALE: File List e Log --
        center_layout = QHBoxLayout()

        # Colonna Sinistra: PDF List
        pdf_group = QGroupBox("PDF da elaborare (Drag & Drop)")
        pdf_layout = QVBoxLayout(pdf_group)
        self.pdf_list = DragDropListWidget()
        btn_clear_list = QPushButton("Svuota Lista")
        btn_add_files = QPushButton("Aggiungi Files...")

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(btn_add_files)
        btn_layout.addWidget(btn_clear_list)

        pdf_layout.addWidget(self.pdf_list)
        pdf_layout.addLayout(btn_layout)

        # Colonna Destra: Log
        log_group = QGroupBox("Terminale di Log")
        log_layout = QVBoxLayout(log_group)
        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        log_layout.addWidget(self.log_console)

        center_layout.addWidget(pdf_group, stretch=1)
        center_layout.addWidget(log_group, stretch=2)

        # -- SEZIONE INFERIORE: Progress e Azioni --
        bottom_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)

        action_layout = QHBoxLayout()
        self.btn_start = QPushButton("🚀 AVVIA BATCH")
        self.btn_start.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
        self.btn_cancel = QPushButton("⏹ Annulla")
        self.btn_cancel.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; font-size: 14px; padding: 10px;")
        self.btn_cancel.setEnabled(False)

        action_layout.addWidget(self.btn_start)
        action_layout.addWidget(self.btn_cancel)

        bottom_layout.addWidget(self.progress_bar)
        bottom_layout.addLayout(action_layout)

        # Assemblaggio
        main_layout.addLayout(top_layout)
        main_layout.addLayout(center_layout)
        main_layout.addLayout(bottom_layout)

        # Connessioni
        self.btn_load_template.clicked.connect(self.load_template)
        btn_add_files.clicked.connect(self.add_files_dialog)
        btn_clear_list.clicked.connect(self.pdf_list.clear)
        self.btn_start.clicked.connect(self.start_batch)
        self.btn_cancel.clicked.connect(self.cancel_batch)

    def apply_dark_theme(self):
        dark_stylesheet = """
        QWidget { background-color: #2b2b2b; color: #e0e0e0; font-family: Arial; }
        QPushButton { background-color: #3c3f41; border: 1px solid #555; border-radius: 4px; padding: 6px; }
        QPushButton:hover { background-color: #4b4d4f; }
        QListWidget, QPlainTextEdit { background-color: #1e1e1e; border: 1px solid #555; }
        QGroupBox { border: 1px solid #555; margin-top: 10px; font-weight: bold; }
        QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 5px; }
        QProgressBar { border: 1px solid #555; border-radius: 4px; text-align: center; }
        QProgressBar::chunk { background-color: #007acc; width: 20px; }
        """
        self.setStyleSheet(dark_stylesheet)

    def log_msg(self, msg: str, level: str = "INFO"):
        color = "#e0e0e0"
        if level == "SUCCESS": color = "#2ecc71"
        elif level == "ERROR": color = "#e74c3c"
        elif level == "WARNING": color = "#f39c12"

        html_msg = f"<span style='color:{color}'>[{level}] {msg}</span>"
        self.log_console.appendHtml(html_msg)

    def load_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "Carica Template JSON", "", "JSON Files (*.json)")
        if not path: return

        try:
            self.template_dict = TemplateManager.load_template(path)
            template_name = self.template_dict.get("name", os.path.basename(path))
            self.lbl_template_name.setText(f"Template Attivo: {template_name}")
            self.lbl_template_name.setStyleSheet("color: #2ecc71; font-weight: bold;")
            self.log_msg(f"Template '{template_name}' validato e caricato.", "SUCCESS")
        except TemplateValidationError as e:
            QMessageBox.critical(self, "Errore Template", str(e))
            self.template_dict = None
            self.lbl_template_name.setText("Nessun template selezionato")
            self.lbl_template_name.setStyleSheet("color: #e74c3c; font-weight: bold;")

    def add_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Seleziona PDF", "", "PDF Files (*.pdf)")
        for path in paths:
            if not self.pdf_list.findItems(path, Qt.MatchFlag.MatchExactly):
                self.pdf_list.addItem(path)

    def start_batch(self):
        if not self.template_dict:
            QMessageBox.warning(self, "Attenzione", "Devi caricare un Template JSON prima di avviare il batch.")
            return

        pdf_paths = [self.pdf_list.item(i).text() for i in range(self.pdf_list.count())]
        if not pdf_paths:
            QMessageBox.warning(self, "Attenzione", "La lista dei PDF è vuota.")
            return

        output_zip, _ = QFileDialog.getSaveFileName(self, "Salva Report e Dati ZIP", "Batch_Output.zip", "ZIP Files (*.zip)")
        if not output_zip: return

        # UI Lock
        self.btn_start.setEnabled(False)
        self.btn_load_template.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.pdf_list.setEnabled(False)
        self.log_console.clear()

        # Init Worker
        self.worker = BatchWorker(pdf_paths, self.template_dict, output_zip)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.file_processed.connect(self.on_file_processed)
        self.worker.batch_finished.connect(self.on_batch_finished)
        self.worker.batch_error.connect(self.on_batch_error)

        self.log_msg("Inizio elaborazione batch...", "INFO")
        self.worker.start()

    def cancel_batch(self):
        if self.worker and self.worker.isRunning():
            self.log_msg("Richiesta annullamento in corso...", "WARNING")
            self.btn_cancel.setEnabled(False)
            self.worker.cancel()

    def update_progress(self, current, total, message):
        if total > 0:
            val = int((current / total) * 100)
            self.progress_bar.setValue(val)
        self.log_msg(message, "INFO")

    def on_file_processed(self, file_name, status, message):
        level = "SUCCESS" if status == "Success" else "ERROR"
        self.log_msg(f"{file_name} -> {message}", level)

    def on_batch_finished(self, zip_path):
        self.log_msg(f"Batch completato! File salvato in: {zip_path}", "SUCCESS")
        self._unlock_ui()
        QMessageBox.information(self, "Completato", f"Elaborazione terminata con successo.\nArchivio creato:\n{zip_path}")

    def on_batch_error(self, error_msg):
        self.log_msg(f"Errore Batch: {error_msg}", "ERROR")
        self._unlock_ui()
        QMessageBox.critical(self, "Errore Critico", error_msg)

    def _unlock_ui(self):
        self.btn_start.setEnabled(True)
        self.btn_load_template.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.pdf_list.setEnabled(True)
        self.progress_bar.setValue(0)
