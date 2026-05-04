import os
import fitz
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from core.template_manager import TemplateManager
from core.optical_engine import extract_data
from core.cv_aligner import calculate_alignment_shift

class QuickDigitizerView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.template_dict = None
        self.current_pdf_path = None
        self.extracted_df = None
        self.setup_ui()
        self.apply_dark_theme()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)

        # -- Top Controls --
        top_layout = QHBoxLayout()
        self.btn_load_template = QPushButton("📂 Carica Template JSON")
        self.lbl_template_name = QLabel("Nessun template selezionato")
        self.lbl_template_name.setStyleSheet("color: #e74c3c; font-weight: bold;")

        self.btn_load_pdf = QPushButton("📄 Seleziona PDF Singolo")
        self.lbl_pdf_name = QLabel("Nessun file selezionato")
        self.lbl_pdf_name.setStyleSheet("color: #e74c3c; font-weight: bold;")

        top_layout.addWidget(self.btn_load_template)
        top_layout.addWidget(self.lbl_template_name)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_load_pdf)
        top_layout.addWidget(self.lbl_pdf_name)

        # -- Center: Matplotlib Canvas --
        self.canvas = FigureCanvas(Figure(figsize=(10, 6)))
        self.ax_layout = None

        # -- Bottom Controls --
        bottom_layout = QHBoxLayout()
        self.btn_extract = QPushButton("⚡ Analizza ed Estrai")
        self.btn_extract.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; padding: 10px;")

        self.btn_export = QPushButton("💾 Esporta Excel")
        self.btn_export.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 10px;")
        self.btn_export.setEnabled(False)

        bottom_layout.addWidget(self.btn_extract)
        bottom_layout.addWidget(self.btn_export)

        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.canvas, stretch=1)
        main_layout.addLayout(bottom_layout)

        # Connections
        self.btn_load_template.clicked.connect(self.load_template)
        self.btn_load_pdf.clicked.connect(self.load_pdf)
        self.btn_extract.clicked.connect(self.run_extraction)
        self.btn_export.clicked.connect(self.export_excel)

    def apply_dark_theme(self):
        dark_stylesheet = """
        QWidget { background-color: #2b2b2b; color: #e0e0e0; font-family: Arial; }
        QPushButton { background-color: #3c3f41; border: 1px solid #555; border-radius: 4px; padding: 6px; }
        QPushButton:hover { background-color: #4b4d4f; }
        """
        self.setStyleSheet(dark_stylesheet)

    def load_template(self):
        path, _ = QFileDialog.getOpenFileName(self, "Carica Template JSON", "", "JSON Files (*.json)")
        if path:
            try:
                self.template_dict = TemplateManager.load_template(path)
                self.lbl_template_name.setText(f"Template: {os.path.basename(path)}")
                self.lbl_template_name.setStyleSheet("color: #2ecc71; font-weight: bold;")
            except Exception as e:
                QMessageBox.critical(self, "Errore", str(e))

    def load_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona PDF", "", "PDF Files (*.pdf)")
        if path:
            self.current_pdf_path = path
            self.lbl_pdf_name.setText(f"PDF: {os.path.basename(path)}")
            self.lbl_pdf_name.setStyleSheet("color: #2ecc71; font-weight: bold;")

    def run_extraction(self):
        if not self.template_dict or not self.current_pdf_path:
            QMessageBox.warning(self, "Attenzione", "Carica sia un Template che un PDF prima di estrarre.")
            return

        self.btn_extract.setEnabled(False)
        self.btn_extract.setText("Elaborazione in corso...")
        QApplication.processEvents()

        try:
            try:
                shift_x, shift_y = calculate_alignment_shift(self.current_pdf_path, self.template_dict, dpi=300)
            except Exception as e:
                # Auto rotation fallback
                doc = fitz.open(self.current_pdf_path)
                is_landscape = doc[0].rect.width > doc[0].rect.height
                doc.close()
                if is_landscape and self.template_dict.get("base_rotation", 0) == 0:
                    temp_dict = self.template_dict.copy()
                    temp_dict["base_rotation"] = 90
                    shift_x, shift_y = calculate_alignment_shift(self.current_pdf_path, temp_dict, dpi=300)
                    self.template_dict = temp_dict
                else:
                    raise e

            df = extract_data(self.current_pdf_path, self.template_dict, shift_x, shift_y)
            self.extracted_df = df
            self.plot_data(df)
            self.btn_export.setEnabled(True)
            QMessageBox.information(self, "Successo", "Estrazione completata con successo.")

        except Exception as e:
            QMessageBox.critical(self, "Errore Estrazione", str(e))
            self.extracted_df = None
            self.btn_export.setEnabled(False)
        finally:
            self.btn_extract.setEnabled(True)
            self.btn_extract.setText("⚡ Analizza ed Estrai")

    def plot_data(self, df):
        fig = self.canvas.figure
        fig.clear()

        # Find columns (excluding depth)
        cols = [c for c in df.columns if c != "Profondità (m)"]
        if not cols: return

        n_plots = len(cols)
        axes = fig.subplots(1, n_plots, sharey=True)
        if n_plots == 1: axes = [axes]

        colors = ['b', 'r', 'g', 'c', 'm']

        for idx, col in enumerate(cols):
            ax = axes[idx]
            df_clean = df.dropna(subset=[col])
            ax.plot(df_clean[col], df_clean["Profondità (m)"], color=colors[idx % len(colors)], linewidth=1.5)
            ax.set_title(col)
            ax.grid(True)
            if idx == 0:
                ax.invert_yaxis()
                ax.set_ylabel("Profondità (m)")

        fig.tight_layout()
        self.canvas.draw()

    def export_excel(self):
        if self.extracted_df is None: return
        path, _ = QFileDialog.getSaveFileName(self, "Esporta Excel", "Quick_Extraction.xlsx", "Excel Files (*.xlsx)")
        if path:
            try:
                self.extracted_df.to_excel(path, index=False)
                QMessageBox.information(self, "Successo", "Dati esportati correttamente.")
            except Exception as e:
                QMessageBox.critical(self, "Errore", f"Impossibile salvare il file: {e}")
