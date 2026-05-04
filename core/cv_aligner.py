import cv2
import numpy as np
import base64
import fitz

class AlignmentError(Exception):
    pass

def base64_to_cv2(base64_string: str) -> np.ndarray:
    img_data = base64.b64decode(base64_string)
    np_arr = np.frombuffer(img_data, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img

def calculate_alignment_shift(pdf_path: str, template_dict: dict, dpi: int = 300) -> tuple:
    marker_data = template_dict.get("alignment_marker")
    base_rotation = template_dict.get("base_rotation", 0)

    if not marker_data or not marker_data.get("image_base64"):
        return 0, 0

    try:
        marker_img = base64_to_cv2(marker_data["image_base64"])
        if marker_img is None:
            raise ValueError("Decodifica base64 del marker fallita.")
    except Exception as e:
        raise AlignmentError(f"Errore nel caricamento del marker salvato: {e}")

    min_conf = marker_data.get("min_confidence", 0.85)
    orig_rect_norm = marker_data.get("rect_norm")

    if not orig_rect_norm or len(orig_rect_norm) != 4:
        raise AlignmentError("Coordinate originali del marker non valide nel template.")

    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom).prerotate(base_rotation)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)

        target_img_rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        target_img = cv2.cvtColor(target_img_rgb, cv2.COLOR_RGB2BGR)

        page_w = pix.width
        page_h = pix.height
        del pix
        doc.close()
    except Exception as e:
        raise AlignmentError(f"Errore nel rendering del PDF per l'allineamento: {e}")

    search_margin_w = int(page_w * 0.15)
    search_margin_h = int(page_h * 0.15)

    orig_x0_px = int(orig_rect_norm[0] * page_w)
    orig_y0_px = int(orig_rect_norm[1] * page_h)

    search_x0 = max(0, orig_x0_px - search_margin_w)
    search_y0 = max(0, orig_y0_px - search_margin_h)
    search_x1 = min(page_w, int(orig_rect_norm[2] * page_w) + search_margin_w)
    search_y1 = min(page_h, int(orig_rect_norm[3] * page_h) + search_margin_h)

    search_area = target_img[search_y0:search_y1, search_x0:search_x1]

    if search_area.shape[0] < marker_img.shape[0] or search_area.shape[1] < marker_img.shape[1]:
        search_area = target_img
        search_x0 = 0
        search_y0 = 0

    res = cv2.matchTemplate(search_area, marker_img, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val < min_conf:
        del target_img
        raise AlignmentError(f"Allineamento fallito. Confidence score ({max_val:.2f}) inferiore alla soglia minima ({min_conf:.2f}).")

    found_x0_px = search_x0 + max_loc[0]
    found_y0_px = search_y0 + max_loc[1]

    shift_x = found_x0_px - orig_x0_px
    shift_y = found_y0_px - orig_y0_px

    del target_img
    return shift_x, shift_y
