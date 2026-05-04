import fitz  # PyMuPDF
import pandas as pd
import numpy as np
from scipy.interpolate import interp1d

class ExtractionError(Exception):
    pass

CONVERSION_FACTORS = {
    ("kPa", "MPa"): 0.001,
    ("MPa", "kPa"): 1000.0,
    ("kPa", "kPa"): 1.0,
    ("MPa", "MPa"): 1.0,
    ("m", "cm"): 100.0,
    ("cm", "m"): 0.01,
}

def get_color_mask(roi_array: np.ndarray, color_filter: str, custom_rgb: tuple = None) -> np.ndarray:
    r = roi_array[:, :, 0].astype(int)
    g = roi_array[:, :, 1].astype(int)
    b = roi_array[:, :, 2].astype(int)

    if color_filter == "Custom" and custom_rgb:
        cr, cg, cb = custom_rgb
        # Tolerance for custom RGB
        tol = 30
        return (np.abs(r - cr) < tol) & (np.abs(g - cg) < tol) & (np.abs(b - cb) < tol)
    elif color_filter == "Rosso":
        return (r > g + 15) & (r > b + 15)
    elif color_filter == "Blu":
        return (b > r + 15) & (b > g + 15)
    elif color_filter == "Verde":
        return (g > r + 15) & (g > b + 15)
    elif color_filter == "Nero/Grigio":
        return (np.abs(r - g) < 25) & (np.abs(g - b) < 25) & (r < 120)
    else: # "Tutti"
        return (r < 200) & (g < 200) & (b < 200)

def extract_data(pdf_path: str, template_dict: dict, shift_x: int = 0, shift_y: int = 0) -> pd.DataFrame:
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
    except Exception as e:
        raise ExtractionError(f"Impossibile aprire il file PDF: {e}")

    try:
        dpi = 300
        zoom = dpi / 72.0

        # Apply base rotation from template if present
        base_rotation = template_dict.get("base_rotation", 0)

        mat = fitz.Matrix(zoom, zoom).prerotate(base_rotation)

        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)
        img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)

        page_width_px = pix.width
        page_height_px = pix.height
        del pix
    except Exception as e:
        doc.close()
        raise ExtractionError(f"Errore durante il rendering del PDF: {e}")

    boxes = template_dict.get("boxes", [])
    if not boxes:
        doc.close()
        raise ExtractionError("Il template non contiene alcun bounding box.")

    y_maxs = [box.get("y_range", [0, 40.0])[1] for box in boxes]
    max_depth = max(y_maxs) if y_maxs else 40.0
    target_depths = np.arange(0.0, max_depth + 0.01, 0.01)
    df_final = pd.DataFrame({"Profondità (m)": target_depths})

    data_extracted = False

    for box in boxes:
        rect_norm = box.get("rect_norm")
        if not rect_norm or len(rect_norm) != 4:
            continue

        x0_px = int(rect_norm[0] * page_width_px)
        y0_px = int(rect_norm[1] * page_height_px)
        x1_px = int(rect_norm[2] * page_width_px)
        y1_px = int(rect_norm[3] * page_height_px)

        x0_px += shift_x
        x1_px += shift_x
        y0_px += shift_y
        y1_px += shift_y

        x0_px = max(0, min(page_width_px, x0_px))
        x1_px = max(0, min(page_width_px, x1_px))
        y0_px = max(0, min(page_height_px, y0_px))
        y1_px = max(0, min(page_height_px, y1_px))

        if x0_px >= x1_px or y0_px >= y1_px:
            continue

        roi = img_array[y0_px:y1_px, x0_px:x1_px]

        color_filter = box.get("color_filter", "Blu")
        custom_rgb = box.get("custom_rgb", None)
        mask = get_color_mask(roi, color_filter, custom_rgb)

        conversion = CONVERSION_FACTORS.get((box.get("source_unit", "MPa"), box.get("target_unit", "MPa")), 1.0)
        x_range = box.get("x_range", [0.0, 40.0])
        y_range = box.get("y_range", [0.0, 40.0])
        baseline_x = x_range[0]

        points = []

        for row_idx in range(roi.shape[0]):
            col_indices = np.where(mask[row_idx, :])[0]

            # Data Cleaning: Ignore isolated pixels or text by requiring a small cluster,
            # and ignore horizontal lines that span > 80% of the box
            if len(col_indices) > 0 and len(col_indices) < roi.shape[1] * 0.8:
                # Find the largest cluster of active pixels (simple heuristic: mean of all)
                # To be more robust, we just take the furthest point from baseline
                mapped_xs = np.interp(col_indices, [0, roi.shape[1]-1], x_range)
                dist = np.abs(mapped_xs - baseline_x)
                best_idx = np.argmax(dist)
                best_x = mapped_xs[best_idx] * conversion

                real_y = np.interp(row_idx, [0, roi.shape[0]-1], y_range)
                points.append((real_y, best_x))

        if points:
            data_extracted = True
            df_pts = pd.DataFrame(points, columns=['depth', 'val'])

            # Simple outlier removal: remove points that jump too much from neighbors
            df_pts['val_diff'] = df_pts['val'].diff().abs().fillna(0)
            # If the jump is extremely large compared to standard deviation, it might be an outlier
            std = df_pts['val'].std()
            if not pd.isna(std) and std > 0:
                # Filter out points where diff is > 3*std
                df_pts = df_pts[df_pts['val_diff'] < 3 * std]

            df_pts['depth_round'] = df_pts['depth'].round(3)
            df_pts = df_pts.groupby('depth_round')['val'].mean().reset_index()

            f_interp = interp1d(df_pts['depth_round'], df_pts['val'], bounds_error=False, fill_value=np.nan)
            col_name = f'{box.get("param", "unknown")} ({box.get("target_unit", "MPa")})'
            df_final[col_name] = f_interp(target_depths)

    doc.close()
    del img_array

    if not data_extracted or len(df_final.columns) == 1 or df_final.iloc[:, 1:].isna().all().all():
        raise ExtractionError("Nessun dato estratto per i box forniti.")

    return df_final
