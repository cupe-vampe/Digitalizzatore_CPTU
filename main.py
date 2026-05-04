import sys
import multiprocessing
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget
from ui.template_editor_view import TemplateEditorView
from ui.batch_view import BatchDashboardView

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CPTU Vector Digitizer Pro - Enterprise Edition")
        self.setGeometry(100, 100, 1200, 800)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.editor_tab = TemplateEditorView()
        self.batch_tab = BatchDashboardView()

        self.tabs.addTab(self.editor_tab, "🛠️ Template Editor")
        self.tabs.addTab(self.batch_tab, "🚀 Batch Processing")

        self.apply_dark_theme()

    def apply_dark_theme(self):
        # Stile globale per la finestra principale e i tab
        dark_stylesheet = """
        QMainWindow {
            background-color: #2b2b2b;
        }
        QTabWidget::pane {
            border: 1px solid #555;
            background: #2b2b2b;
        }
        QTabBar::tab {
            background: #3c3f41;
            color: #e0e0e0;
            padding: 10px 20px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            font-weight: bold;
            border: 1px solid #555;
            border-bottom: none;
        }
        QTabBar::tab:selected {
            background: #007acc;
            color: white;
        }
        QTabBar::tab:hover:!selected {
            background: #4b4d4f;
        }
        """
        self.setStyleSheet(dark_stylesheet)

if __name__ == '__main__':
    # CRITICAL: Necessario per supportare ProcessPoolExecutor (multiprocessing)
    # negli eseguibili compilati su Windows senza creare fork bombs.
    multiprocessing.freeze_support()

    app = QApplication(sys.argv)

    # Font base
    font = app.font()
    font.setFamily("Arial")
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
