import sys
import multiprocessing
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QHBoxLayout, QPushButton, QLabel, QStackedWidget
)
from PyQt6.QtCore import Qt
from ui.template_editor_view import TemplateEditorView
from ui.batch_view import BatchDashboardView
from ui.quick_digitizer_view import QuickDigitizerView # To be implemented

class HomeDashboard(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("CPTU Vector Digitizer Pro")
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #3498db; margin-bottom: 20px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Seleziona un modulo operativo:")
        subtitle.setStyleSheet("font-size: 16px; margin-bottom: 40px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        btn_template = self.create_module_button("🛠️\nTemplate Creator", "Definisci box e marker su un PDF campione")
        btn_quick = self.create_module_button("⚡\nQuick Digitizer", "Analizza ed esporta una singola prova al volo")
        btn_batch = self.create_module_button("🚀\nBatch Processor", "Elaborazione massiva di intere cartelle")

        btn_template.clicked.connect(lambda: self.main_window.switch_to_module("template"))
        btn_quick.clicked.connect(lambda: self.main_window.switch_to_module("quick"))
        btn_batch.clicked.connect(lambda: self.main_window.switch_to_module("batch"))

        btn_layout.addWidget(btn_template)
        btn_layout.addWidget(btn_quick)
        btn_layout.addWidget(btn_batch)

        layout.addLayout(btn_layout)

    def create_module_button(self, text, tooltip):
        btn = QPushButton(text)
        btn.setFixedSize(200, 150)
        btn.setToolTip(tooltip)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #3c3f41;
                border: 2px solid #555;
                border-radius: 10px;
                font-size: 18px;
                font-weight: bold;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #4b4d4f;
                border-color: #3498db;
            }
        """)
        return btn

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CPTU Vector Digitizer Pro - Enterprise Edition")
        self.setGeometry(100, 100, 1300, 850)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.home_view = HomeDashboard(self)
        self.editor_view = TemplateEditorView()
        self.batch_view = BatchDashboardView()
        self.quick_view = QuickDigitizerView()

        self.stacked_widget.addWidget(self.home_view)
        self.stacked_widget.addWidget(self.editor_view)
        self.stacked_widget.addWidget(self.quick_view)
        self.stacked_widget.addWidget(self.batch_view)

        # We need a way to go back home from modules
        self.add_home_button(self.editor_view)
        self.add_home_button(self.quick_view)
        self.add_home_button(self.batch_view)

        self.apply_dark_theme()

    def add_home_button(self, view):
        # Find the main layout of the view and add a home button at the top
        if view.layout():
            home_btn = QPushButton("🏠 Torna alla Home")
            home_btn.setFixedWidth(150)
            home_btn.setStyleSheet("background-color: #2c3e50; padding: 5px; margin: 5px;")
            home_btn.clicked.connect(lambda: self.stacked_widget.setCurrentWidget(self.home_view))
            view.layout().insertWidget(0, home_btn)

    def switch_to_module(self, module_name):
        if module_name == "template":
            self.stacked_widget.setCurrentWidget(self.editor_view)
        elif module_name == "quick":
            self.stacked_widget.setCurrentWidget(self.quick_view)
        elif module_name == "batch":
            self.stacked_widget.setCurrentWidget(self.batch_view)

    def apply_dark_theme(self):
        dark_stylesheet = """
        QMainWindow { background-color: #2b2b2b; }
        """
        self.setStyleSheet(dark_stylesheet)

if __name__ == '__main__':
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)

    font = app.font()
    font.setFamily("Arial")
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
