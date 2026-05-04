import sys
import os
import fitz
import numpy as np
import cv2
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QFileDialog,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsPixmapItem,
    QFormLayout, QLineEdit, QComboBox, QGroupBox, QScrollArea, QMessageBox,
    QListWidget, QListWidgetItem, QAbstractItemView
)
from PyQt6.QtCore import Qt, QRectF, pyqtSignal, QPointF
from PyQt6.QtGui import QImage, QPixmap, QPen, QColor, QBrush, QPainter

# Import per validazione ed eventuale estrazione della ROI del marker
from core.template_manager import TemplateManager

class ResizableRectItem(QGraphicsRectItem):
    """Un rettangolo QGraphicsItem che l'utente può spostare e ridimensionare trascinando i bordi."""
    handleSize = 8.0
    handleSpace = -4.0

    handleCursors = {
        1: Qt.CursorShape.SizeFDiagCursor, # Top-Left
        2: Qt.CursorShape.SizeVerCursor,   # Top
        3: Qt.CursorShape.SizeBDiagCursor, # Top-Right
        4: Qt.CursorShape.SizeHorCursor,   # Right
        5: Qt.CursorShape.SizeFDiagCursor, # Bottom-Right
        6: Qt.CursorShape.SizeVerCursor,   # Bottom
        7: Qt.CursorShape.SizeBDiagCursor, # Bottom-Left
        8: Qt.CursorShape.SizeHorCursor    # Left
    }

    def __init__(self, rect: QRectF, box_id: str, is_marker=False, parent=None):
        super().__init__(rect, parent)
        self.box_id = box_id
        self.is_marker = is_marker
        self.handles = {}
        self.handleSelected = None
        self.mousePressPos = None
        self.mousePressRect = None
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.updateHandlesPos()
        self.setPen(QPen(QColor("yellow") if is_marker else QColor("red"), 2, Qt.PenStyle.SolidLine))
        self.setBrush(QBrush(QColor(255, 255, 0, 50) if is_marker else QColor(255, 0, 0, 50)))

    def handleAt(self, point: QPointF):
        for k, v, in self.handles.items():
            if v.contains(point):
                return k
        return None

    def hoverMoveEvent(self, moveEvent):
        if self.isSelected():
            handle = self.handleAt(moveEvent.pos())
            cursor = Qt.CursorShape.ArrowCursor if handle is None else self.handleCursors[handle]
            self.setCursor(cursor)
        super().hoverMoveEvent(moveEvent)

    def hoverLeaveEvent(self, moveEvent):
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverLeaveEvent(moveEvent)

    def mousePressEvent(self, mouseEvent):
        self.handleSelected = self.handleAt(mouseEvent.pos())
        if self.handleSelected:
            self.mousePressPos = mouseEvent.pos()
            self.mousePressRect = self.boundingRect()
        super().mousePressEvent(mouseEvent)

    def mouseMoveEvent(self, mouseEvent):
        if self.handleSelected is not None:
            self.interactiveResize(mouseEvent.pos())
        else:
            super().mouseMoveEvent(mouseEvent)

    def mouseReleaseEvent(self, mouseEvent):
        super().mouseReleaseEvent(mouseEvent)
        self.handleSelected = None
        self.mousePressPos = None
        self.mousePressRect = None
        self.update()

    def interactiveResize(self, mousePos: QPointF):
        rect = self.rect()
        diff = mousePos - self.mousePressPos

        if self.handleSelected == 1: # Top-Left
            rect.setTopLeft(self.mousePressRect.topLeft() + diff)
        elif self.handleSelected == 2: # Top
            rect.setTop(self.mousePressRect.top() + diff.y())
        elif self.handleSelected == 3: # Top-Right
            rect.setTopRight(self.mousePressRect.topRight() + diff)
        elif self.handleSelected == 4: # Right
            rect.setRight(self.mousePressRect.right() + diff.x())
        elif self.handleSelected == 5: # Bottom-Right
            rect.setBottomRight(self.mousePressRect.bottomRight() + diff)
        elif self.handleSelected == 6: # Bottom
            rect.setBottom(self.mousePressRect.bottom() + diff.y())
        elif self.handleSelected == 7: # Bottom-Left
            rect.setBottomLeft(self.mousePressRect.bottomLeft() + diff)
        elif self.handleSelected == 8: # Left
            rect.setLeft(self.mousePressRect.left() + diff.x())

        self.setRect(rect)
        self.updateHandlesPos()

    def updateHandlesPos(self):
        s = self.handleSize
        b = self.boundingRect()
        self.handles[1] = QRectF(b.left(), b.top(), s, s)
        self.handles[2] = QRectF(b.center().x() - s / 2, b.top(), s, s)
        self.handles[3] = QRectF(b.right() - s, b.top(), s, s)
        self.handles[4] = QRectF(b.right() - s, b.center().y() - s / 2, s, s)
        self.handles[5] = QRectF(b.right() - s, b.bottom() - s, s, s)
        self.handles[6] = QRectF(b.center().x() - s / 2, b.bottom() - s, s, s)
        self.handles[7] = QRectF(b.left(), b.bottom() - s, s, s)
        self.handles[8] = QRectF(b.left(), b.center().y() - s / 2, s, s)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.isSelected():
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(QColor(0, 255, 0, 255)))
            painter.setPen(QPen(QColor(0, 0, 0, 255), 1.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            for _, rect in self.handles.items():
                painter.drawRect(rect)


class PDFViewer(QGraphicsView):
    """QGraphicsView specializzata per visualizzare il PDF e disegnare le ROI."""

    boxAdded = pyqtSignal(str, bool) # id_box, is_marker
    boxSelected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True)
        self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

        self.zoom_level = 1.0
        self.current_pdf_path = None
        self.pdf_pixmap_item = None
        self.drawing_mode = None # 'box' o 'marker' o None
        self.temp_rect = None
        self.start_pos = None

        self.boxes = {} # id -> ResizableRectItem
        self.box_counter = 1
        self.marker_item = None

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            zoomInFactor = 1.25
            zoomOutFactor = 1 / zoomInFactor

            oldPos = self.mapToScene(event.position().toPoint())

            if event.angleDelta().y() > 0:
                zoomFactor = zoomInFactor
            else:
                zoomFactor = zoomOutFactor

            self.scale(zoomFactor, zoomFactor)
            self.zoom_level *= zoomFactor

            newPos = self.mapToScene(event.position().toPoint())
            delta = newPos - oldPos
            self.translate(delta.x(), delta.y())
        else:
            super().wheelEvent(event)

    def load_pdf(self, path: str):
        self.current_pdf_path = path
        self.scene.clear()
        self.boxes.clear()
        self.marker_item = None
        self.box_counter = 1

        try:
            doc = fitz.open(path)
            page = doc[0]
            # Render visuale a 150 DPI
            mat = fitz.Matrix(150 / 72.0, 150 / 72.0)
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)

            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(img)
            self.pdf_pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self.pdf_pixmap_item)
            self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
            doc.close()
        except Exception as e:
            QMessageBox.critical(self, "Errore PDF", f"Impossibile aprire il PDF: {e}")

    def mousePressEvent(self, event):
        if self.drawing_mode and event.button() == Qt.MouseButton.LeftButton:
            self.start_pos = self.mapToScene(event.position().toPoint())
            self.temp_rect = QGraphicsRectItem(QRectF(self.start_pos, self.start_pos))
            pen_color = QColor("yellow") if self.drawing_mode == 'marker' else QColor("red")
            self.temp_rect.setPen(QPen(pen_color, 2, Qt.PenStyle.DashLine))
            self.scene.addItem(self.temp_rect)
            return # Consumiamo l'evento

        super().mousePressEvent(event)

        # Gestione selezione
        item = self.scene.itemAt(self.mapToScene(event.position().toPoint()), self.transform())
        if isinstance(item, ResizableRectItem):
            self.boxSelected.emit(item.box_id)

    def mouseMoveEvent(self, event):
        if self.drawing_mode and self.temp_rect and self.start_pos:
            current_pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self.start_pos, current_pos).normalized()
            self.temp_rect.setRect(rect)
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.drawing_mode and self.temp_rect:
            current_pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self.start_pos, current_pos).normalized()
            self.scene.removeItem(self.temp_rect)
            self.temp_rect = None
            self.start_pos = None

            if rect.width() > 10 and rect.height() > 10:
                is_marker = self.drawing_mode == 'marker'
                if is_marker and self.marker_item:
                    self.scene.removeItem(self.marker_item) # Rimuovi il vecchio marker

                box_id = "marker" if is_marker else f"box_{self.box_counter}"
                new_box = ResizableRectItem(rect, box_id, is_marker)
                self.scene.addItem(new_box)

                if is_marker:
                    self.marker_item = new_box
                else:
                    self.boxes[box_id] = new_box
                    self.box_counter += 1

                self.boxAdded.emit(box_id, is_marker)
                self.boxSelected.emit(box_id)
                self.scene.clearSelection()
                new_box.setSelected(True)

            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.drawing_mode = None
            return

        super().mouseReleaseEvent(event)


class TemplateEditorView(QWidget):
    """View principale per l'Editor dei Template."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Template Editor")
        # Dati configurati per ogni box
        self.box_data = {}
        self.setup_ui()
        self.apply_dark_theme()

    def setup_ui(self):
        main_layout = QHBoxLayout(self)

        # -- SINISTRA: Toolbar e PDF Viewer --
        left_layout = QVBoxLayout()

        toolbar_layout = QHBoxLayout()
        self.btn_load = QPushButton("📄 Carica PDF Campione")
        self.btn_add_box = QPushButton("➕ Disegna Data Box")
        self.btn_add_marker = QPushButton("🎯 Disegna Marker CV")

        toolbar_layout.addWidget(self.btn_load)
        toolbar_layout.addWidget(self.btn_add_box)
        toolbar_layout.addWidget(self.btn_add_marker)
        toolbar_layout.addStretch()

        self.viewer = PDFViewer()

        left_layout.addLayout(toolbar_layout)
        left_layout.addWidget(self.viewer)

        # -- DESTRA: Pannello di Configurazione --
        right_panel = QWidget()
        right_panel.setFixedWidth(350)
        right_layout = QVBoxLayout(right_panel)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        self.config_group = QGroupBox("Proprietà Box Selezionato")
        form_layout = QFormLayout()

        self.f_param = QComboBox()
        self.f_param.addItems(["qc", "fs", "u"])

        self.f_color = QComboBox()
        self.f_color.addItems(["Blu", "Rosso", "Verde", "Nero/Grigio", "Tutti"])

        self.f_x_min = QLineEdit("0.0")
        self.f_x_max = QLineEdit("40.0")
        self.f_y_min = QLineEdit("0.0")
        self.f_y_max = QLineEdit("40.0")

        self.f_unit_src = QComboBox()
        self.f_unit_src.addItems(["MPa", "kPa"])

        self.f_unit_dst = QComboBox()
        self.f_unit_dst.addItems(["MPa", "kPa"])

        form_layout.addRow("Parametro:", self.f_param)
        form_layout.addRow("Colore:", self.f_color)
        form_layout.addRow("X Min:", self.f_x_min)
        form_layout.addRow("X Max:", self.f_x_max)
        form_layout.addRow("Y Inizio (m):", self.f_y_min)
        form_layout.addRow("Y Fine (m):", self.f_y_max)
        form_layout.addRow("Unità Sorgente:", self.f_unit_src)
        form_layout.addRow("Unità Destinazione:", self.f_unit_dst)

        self.btn_save_box = QPushButton("Salva Proprietà Box")
        form_layout.addRow(self.btn_save_box)
        self.config_group.setLayout(form_layout)
        self.config_group.setEnabled(False)

        self.btn_save_template = QPushButton("💾 Salva Template JSON")
        self.btn_save_template.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold; padding: 10px;")

        right_layout.addWidget(QLabel("Elementi Disegnati:"))
        right_layout.addWidget(self.list_widget)
        right_layout.addWidget(self.config_group)
        right_layout.addStretch()
        right_layout.addWidget(self.btn_save_template)

        main_layout.addLayout(left_layout)
        main_layout.addWidget(right_panel)

        # Connessioni
        self.btn_load.clicked.connect(self.load_pdf)
        self.btn_add_box.clicked.connect(lambda: self.set_drawing_mode('box'))
        self.btn_add_marker.clicked.connect(lambda: self.set_drawing_mode('marker'))
        self.viewer.boxAdded.connect(self.on_box_added)
        self.viewer.boxSelected.connect(self.on_box_selected)
        self.list_widget.currentItemChanged.connect(self.on_list_item_selected)
        self.btn_save_box.clicked.connect(self.save_current_box_props)
        self.btn_save_template.clicked.connect(self.save_template)

    def apply_dark_theme(self):
        dark_stylesheet = """
        QWidget { background-color: #2b2b2b; color: #e0e0e0; font-family: Arial; }
        QPushButton { background-color: #3c3f41; border: 1px solid #555; border-radius: 4px; padding: 6px; }
        QPushButton:hover { background-color: #4b4d4f; }
        QLineEdit, QComboBox { background-color: #3c3f41; border: 1px solid #555; padding: 4px; border-radius: 2px; }
        QGraphicsView { border: none; background-color: #1e1e1e; }
        QListWidget { background-color: #3c3f41; border: 1px solid #555; }
        QListWidget::item:selected { background-color: #007acc; }
        QGroupBox { border: 1px solid #555; margin-top: 10px; }
        QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 3px; }
        """
        self.setStyleSheet(dark_stylesheet)

    def load_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona PDF", "", "PDF Files (*.pdf)")
        if path:
            self.list_widget.clear()
            self.box_data.clear()
            self.viewer.load_pdf(path)

    def set_drawing_mode(self, mode):
        if not self.viewer.current_pdf_path:
            QMessageBox.warning(self, "Attenzione", "Carica prima un PDF.")
            return
        self.viewer.drawing_mode = mode
        self.viewer.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.viewer.setCursor(Qt.CursorShape.CrossCursor)

    def on_box_added(self, box_id, is_marker):
        if is_marker:
            # Rimuovi vecchio marker dalla lista se esiste
            for i in range(self.list_widget.count()):
                if self.list_widget.item(i).text() == "marker":
                    self.list_widget.takeItem(i)
                    break

        item = QListWidgetItem(box_id)
        self.list_widget.addItem(item)
        if not is_marker:
            # Inizializza dati default
            self.box_data[box_id] = {
                "param": "qc", "color_filter": "Blu", "source_unit": "MPa",
                "target_unit": "MPa", "x_range": [0.0, 40.0], "y_range": [0.0, 40.0]
            }

    def on_box_selected(self, box_id):
        # Sincronizza lista
        items = self.list_widget.findItems(box_id, Qt.MatchFlag.MatchExactly)
        if items:
            self.list_widget.setCurrentItem(items[0])

    def on_list_item_selected(self, current, previous):
        if not current:
            self.config_group.setEnabled(False)
            return

        box_id = current.text()
        if box_id == "marker":
            self.config_group.setEnabled(False) # Marker non ha config parametri
            # Evidenzia marker
            self.viewer.scene.clearSelection()
            if self.viewer.marker_item: self.viewer.marker_item.setSelected(True)
        else:
            self.config_group.setEnabled(True)
            data = self.box_data.get(box_id, {})
            self.f_param.setCurrentText(data.get("param", "qc"))
            self.f_color.setCurrentText(data.get("color_filter", "Blu"))
            self.f_x_min.setText(str(data.get("x_range", [0,0])[0]))
            self.f_x_max.setText(str(data.get("x_range", [0,0])[1]))
            self.f_y_min.setText(str(data.get("y_range", [0,0])[0]))
            self.f_y_max.setText(str(data.get("y_range", [0,0])[1]))
            self.f_unit_src.setCurrentText(data.get("source_unit", "MPa"))
            self.f_unit_dst.setCurrentText(data.get("target_unit", "MPa"))

            # Evidenzia box
            self.viewer.scene.clearSelection()
            box = self.viewer.boxes.get(box_id)
            if box: box.setSelected(True)

    def save_current_box_props(self):
        current_item = self.list_widget.currentItem()
        if not current_item: return
        box_id = current_item.text()
        if box_id == "marker": return

        try:
            self.box_data[box_id] = {
                "param": self.f_param.currentText(),
                "color_filter": self.f_color.currentText(),
                "x_range": [float(self.f_x_min.text()), float(self.f_x_max.text())],
                "y_range": [float(self.f_y_min.text()), float(self.f_y_max.text())],
                "source_unit": self.f_unit_src.currentText(),
                "target_unit": self.f_unit_dst.currentText()
            }
            QMessageBox.information(self, "OK", f"Proprietà di {box_id} salvate in RAM.")
        except ValueError:
            QMessageBox.warning(self, "Errore Formato", "Assicurati che i valori Min e Max siano numerici.")

    def _get_normalized_rect(self, item: QGraphicsRectItem) -> list:
        # Cruciale: calcoliamo le coordinate relative alla scena (che corrisponde all'immagine base)
        rect = item.sceneBoundingRect()
        scene_rect = self.viewer.scene.sceneRect()

        x0 = rect.left() / scene_rect.width()
        y0 = rect.top() / scene_rect.height()
        x1 = rect.right() / scene_rect.width()
        y1 = rect.bottom() / scene_rect.height()

        # Clamp tra 0 e 1
        return [max(0.0, min(1.0, c)) for c in [x0, y0, x1, y1]]

    def extract_marker_roi_300dpi(self, rect_norm: list) -> np.ndarray:
        """Estrae l'immagine del marker direttamente dal PDF a 300 DPI per il cv_aligner."""
        if not self.viewer.current_pdf_path:
            return None

        doc = fitz.open(self.viewer.current_pdf_path)
        page = doc[0]
        mat = fitz.Matrix(300 / 72.0, 300 / 72.0)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)

        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)

        x0 = int(rect_norm[0] * pix.width)
        y0 = int(rect_norm[1] * pix.height)
        x1 = int(rect_norm[2] * pix.width)
        y1 = int(rect_norm[3] * pix.height)

        roi_rgb = img_array[y0:y1, x0:x1]
        roi_bgr = cv2.cvtColor(roi_rgb, cv2.COLOR_RGB2BGR)

        del pix
        doc.close()
        return roi_bgr

    def save_template(self):
        if not self.viewer.boxes:
            QMessageBox.warning(self, "Errore", "Disegna almeno un Data Box.")
            return

        boxes_data = []
        for box_id, box_item in self.viewer.boxes.items():
            if box_id not in self.box_data:
                QMessageBox.warning(self, "Errore", f"Proprietà per {box_id} non salvate!")
                return
            b_data = self.box_data[box_id].copy()
            b_data["rect_norm"] = self._get_normalized_rect(box_item)
            boxes_data.append(b_data)

        marker_img = None
        marker_rect_norm = None

        if self.viewer.marker_item:
            marker_rect_norm = self._get_normalized_rect(self.viewer.marker_item)
            marker_img = self.extract_marker_roi_300dpi(marker_rect_norm)

        path, _ = QFileDialog.getSaveFileName(self, "Salva Template JSON", "", "JSON Files (*.json)")
        if not path: return

        try:
            TemplateManager.save_template_from_ui(
                file_path=path,
                boxes_data=boxes_data,
                template_name=os.path.basename(path),
                marker_image=marker_img,
                marker_rect_norm=marker_rect_norm
            )
            QMessageBox.information(self, "Successo", "Template salvato e validato correttamente!")
        except Exception as e:
            QMessageBox.critical(self, "Errore Salvataggio", str(e))
