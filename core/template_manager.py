import json
import base64
import cv2
import numpy as np

class TemplateValidationError(Exception):
    """Custom exception per errori di validazione del formato del template JSON."""
    pass

class TemplateManager:
    """
    Gestisce il salvataggio, caricamento e validazione dei template JSON.
    """

    MAX_MARKER_PIXELS = 640000
    SCHEMA_VERSION = "1.0"

    @classmethod
    def _validate_schema(cls, template_dict: dict):
        if not isinstance(template_dict, dict):
            raise TemplateValidationError("Il template deve essere un dizionario.")

        if template_dict.get("version") != cls.SCHEMA_VERSION:
            raise TemplateValidationError(f"Versione template non supportata: {template_dict.get('version')}")

        boxes = template_dict.get("boxes")
        if not isinstance(boxes, list) or len(boxes) == 0:
            raise TemplateValidationError("Il template deve contenere una lista 'boxes' non vuota.")

        required_box_keys = {"param", "color_filter", "source_unit", "target_unit", "x_range", "y_range", "rect_norm"}
        for i, box in enumerate(boxes):
            if not isinstance(box, dict):
                raise TemplateValidationError(f"Il box all'indice {i} non è un dizionario.")

            missing_keys = required_box_keys - set(box.keys())
            if missing_keys:
                raise TemplateValidationError(f"Chiavi mancanti nel box {i}: {missing_keys}")

            rect = box["rect_norm"]
            if not isinstance(rect, (list, tuple)) or len(rect) != 4:
                raise TemplateValidationError(f"'rect_norm' nel box {i} deve essere una lista di 4 elementi [x0, y0, x1, y1].")
            if not all(isinstance(coord, (int, float)) and 0.0 <= coord <= 1.0 for coord in rect):
                raise TemplateValidationError(f"Le coordinate 'rect_norm' nel box {i} devono essere float compresi tra 0 e 1.")

            if box["rect_norm"][2] <= box["rect_norm"][0] or box["rect_norm"][3] <= box["rect_norm"][1]:
                raise TemplateValidationError(f"Coordinate box invalide nel box {i}: x1<=x0 o y1<=y0.")

        marker = template_dict.get("alignment_marker")
        if marker is not None:
            if not isinstance(marker, dict):
                raise TemplateValidationError("'alignment_marker' deve essere un dizionario.")
            if "image_base64" not in marker or "rect_norm" not in marker:
                raise TemplateValidationError("'alignment_marker' deve contenere 'image_base64' e 'rect_norm'.")

            rect = marker["rect_norm"]
            if not isinstance(rect, (list, tuple)) or len(rect) != 4:
                raise TemplateValidationError("'rect_norm' nel marker deve essere una lista di 4 elementi [x0, y0, x1, y1].")
            if not all(isinstance(coord, (int, float)) and 0.0 <= coord <= 1.0 for coord in rect):
                raise TemplateValidationError("Le coordinate 'rect_norm' nel marker devono essere float compresi tra 0 e 1.")

    @classmethod
    def load_template(cls, file_path: str) -> dict:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                template_dict = json.load(f)
        except json.JSONDecodeError as e:
            raise TemplateValidationError(f"Errore nel parsing del file JSON: {e}")
        except IOError as e:
            raise TemplateValidationError(f"Impossibile leggere il file: {e}")

        cls._validate_schema(template_dict)
        return template_dict

    @classmethod
    def cv2_to_base64(cls, image_array: np.ndarray) -> str:
        if image_array is None or image_array.size == 0:
            raise TemplateValidationError("L'immagine fornita per il marker è vuota o non valida.")

        pixels = image_array.shape[0] * image_array.shape[1]
        if pixels > cls.MAX_MARKER_PIXELS:
            raise TemplateValidationError(f"Marker ROI troppo grande ({pixels} pixel). Massimo consentito: {cls.MAX_MARKER_PIXELS}.")

        success, buffer = cv2.imencode('.png', image_array)
        if not success:
            raise TemplateValidationError("Errore durante la codifica PNG del marker.")

        return base64.b64encode(buffer).decode('utf-8')

    @classmethod
    def save_template_from_ui(cls,
                              file_path: str,
                              boxes_data: list,
                              template_name: str = "Custom Template",
                              marker_image: np.ndarray = None,
                              marker_rect_norm: list = None,
                              min_confidence: float = 0.85):
        template_dict = {
            "version": cls.SCHEMA_VERSION,
            "name": template_name,
            "boxes": boxes_data
        }

        if marker_image is not None and marker_rect_norm is not None:
            base64_str = cls.cv2_to_base64(marker_image)
            template_dict["alignment_marker"] = {
                "image_base64": base64_str,
                "rect_norm": marker_rect_norm,
                "min_confidence": min_confidence
            }

        cls._validate_schema(template_dict)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(template_dict, f, indent=4, ensure_ascii=False)
        except IOError as e:
            raise TemplateValidationError(f"Impossibile salvare il file su disco: {e}")
