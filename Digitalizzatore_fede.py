import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import fitz  # PyMuPDF
from PIL import Image, ImageTk
import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import platform

CONVERSION_FACTORS = {
    ("kPa", "MPa"): 0.001,
    ("MPa", "kPa"): 1000.0,
    ("kPa", "kPa"): 1.0,
    ("MPa", "MPa"): 1.0,
    ("m", "cm"): 100.0,
    ("cm", "m"): 0.01,
}

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, current_shortcuts):
        super().__init__(parent)
        self.title("Impostazioni Scorciatoie")
        self.geometry("300x250")
        self.result = None
        self.attributes('-topmost', True)

        self.entries = {}
        row = 0
        tk.Label(self, text="Modifica i tasti di scelta rapida:", font=("Arial", 10, "bold")).grid(row=row, columnspan=2, pady=10)
        
        for action, key in current_shortcuts.items():
            row += 1
            tk.Label(self, text=f"Strumento {action.capitalize()}:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
            var = tk.StringVar(value=key)
            entry = tk.Entry(self, textvariable=var, width=5, justify="center")
            entry.grid(row=row, column=1, padx=10, pady=5)
            self.entries[action] = var

        row += 1
        tk.Button(self, text="Salva", command=self.save, bg="lightgreen", width=10).grid(row=row, columnspan=2, pady=15)

    def save(self):
        self.result = {action: var.get().lower() for action, var in self.entries.items()}
        self.destroy()

class CalibrationDialog(tk.Toplevel):
    def __init__(self, parent, existing_data=None):
        super().__init__(parent)
        self.title("Calibrazione Cella")
        self.geometry("450x500")
        self.result = None
        self.delete_flag = False
        self.attributes('-topmost', True)
        
        row = 0
        tk.Label(self, text="Parametro:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        self.param_var = tk.StringVar(value=existing_data.get('param', "qc") if existing_data else "qc")
        ttk.Combobox(self, textvariable=self.param_var, values=["qc", "fs", "u"]).grid(row=row, column=1, padx=10, pady=5)

        row += 1
        tk.Label(self, text="Colore del tracciato:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        default_color = existing_data.get('color_filter', "Blu") if existing_data else "Blu"
        self.color_var = tk.StringVar(value=default_color)
        ttk.Combobox(self, textvariable=self.color_var, values=["Rosso", "Blu", "Verde", "Nero/Grigio", "Tutti"]).grid(row=row, column=1, padx=10, pady=5)
        
        row += 1
        tk.Label(self, text="Unità di misura (Sorgente PDF):").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        self.source_unit_var = tk.StringVar(value=existing_data.get('source_unit', "MPa") if existing_data else "MPa")
        ttk.Combobox(self, textvariable=self.source_unit_var, values=["MPa", "kPa"]).grid(row=row, column=1, padx=10, pady=5)

        row += 1
        tk.Label(self, text="Unità di misura (Output Excel):").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        self.target_unit_var = tk.StringVar(value=existing_data.get('target_unit', "MPa") if existing_data else "MPa")
        ttk.Combobox(self, textvariable=self.target_unit_var, values=["MPa", "kPa"]).grid(row=row, column=1, padx=10, pady=5)
        
        row += 1
        tk.Label(self, text="Valore Minimo (Asse X Sorgente):").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        self.xmin_var = tk.StringVar(value=str(existing_data.get('x_range', (0.0, 40.0))[0]) if existing_data else "0.0")
        tk.Entry(self, textvariable=self.xmin_var).grid(row=row, column=1, padx=10, pady=5)
        
        row += 1
        tk.Label(self, text="Valore Massimo (Asse X Sorgente):").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        self.xmax_var = tk.StringVar(value=str(existing_data.get('x_range', (0.0, 40.0))[1]) if existing_data else "40.0")
        tk.Entry(self, textvariable=self.xmax_var).grid(row=row, column=1, padx=10, pady=5)
        
        row += 1
        tk.Label(self, text="Profondità Inizio (Asse Y, m):").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        self.ymin_var = tk.StringVar(value=str(existing_data.get('y_range', (0.0, 40.0))[0]) if existing_data else "0.0")
        tk.Entry(self, textvariable=self.ymin_var).grid(row=row, column=1, padx=10, pady=5)
        
        row += 1
        tk.Label(self, text="Profondità Fine (Asse Y, m):").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        self.ymax_var = tk.StringVar(value=str(existing_data.get('y_range', (0.0, 40.0))[1]) if existing_data else "40.0")
        tk.Entry(self, textvariable=self.ymax_var).grid(row=row, column=1, padx=10, pady=5)
        
        row += 1
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=row, columnspan=2, pady=15)
        
        tk.Button(btn_frame, text="Salva", command=self.save, bg="lightgreen", width=10).pack(side=tk.LEFT, padx=5)
        if existing_data:
            tk.Button(btn_frame, text="Elimina Box", command=self.delete_box, bg="salmon", width=10).pack(side=tk.LEFT, padx=5)

    def save(self):
        try:
            xmin = float(self.xmin_var.get().replace(',', '.'))
            xmax = float(self.xmax_var.get().replace(',', '.'))
            ymin = float(self.ymin_var.get().replace(',', '.'))
            ymax = float(self.ymax_var.get().replace(',', '.'))

            self.result = {
                "param": self.param_var.get(),
                "color_filter": self.color_var.get(),
                "source_unit": self.source_unit_var.get(),
                "target_unit": self.target_unit_var.get(),
                "x_range": (xmin, xmax),
                "y_range": (ymin, ymax),
                "calibrated": True
            }
            self.destroy()
        except ValueError:
            messagebox.showerror("Errore", "Inserisci solo numeri validi (usa punto o virgola).", parent=self)

    def delete_box(self):
        self.delete_flag = True
        self.destroy()

class PreviewWindow(tk.Toplevel):
    def __init__(self, parent, df):
        super().__init__(parent)
        self.title("Controllo Grafico Dati Estratti")
        self.geometry("1100x800")
        self.df = df
        
        top_frame = tk.Frame(self, pady=10)
        top_frame.pack(fill=tk.X)
        
        self.info_label = tk.Label(top_frame, text="Passa il cursore sul grafico per leggere i valori esatti", font=("Arial", 12, "bold"), fg="blue")
        self.info_label.pack(side=tk.LEFT, padx=20)
        
        tk.Button(top_frame, text="💾 Salva in Excel", font=("Arial", 12, "bold"), bg="#2ecc71", fg="white", 
                  command=self.save_excel).pack(side=tk.RIGHT, padx=20)
        
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(10, 6), sharey=True)
        ax1.invert_yaxis()
        
        col_qc = next((c for c in df.columns if 'qc' in c.lower()), None)
        col_fs = next((c for c in df.columns if 'fs' in c.lower()), None)
        col_u  = next((c for c in df.columns if 'u' in c.lower()), None)
        
        if col_qc:
            ax1.plot(df[col_qc], df['Profondità (m)'], 'b-', linewidth=1.2)
            ax1.set_title(col_qc); ax1.grid(True)
        if col_fs:
            ax2.plot(df[col_fs], df['Profondità (m)'], 'r-', linewidth=1.2)
            ax2.set_title(col_fs); ax2.grid(True)
        if col_u:
            ax3.plot(df[col_u], df['Profondità (m)'], 'g-', linewidth=1.2)
            ax3.set_title(col_u)
            ax3.axvline(0, color='black', lw=1)
            ax3.grid(True)
            
        plt.tight_layout()
        
        canvas = FigureCanvasTkAgg(fig, master=self)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        def on_hover(event):
            if event.inaxes:
                x, y = event.xdata, event.ydata
                param_name = event.inaxes.get_title()
                self.info_label.config(text=f"Parametro: {param_name} | Valore: {x:.3f} | Profondità: {y:.2f} m")

        fig.canvas.mpl_connect("motion_notify_event", on_hover)

    def save_excel(self):
        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if save_path:
            self.df.to_excel(save_path, index=False)
            messagebox.showinfo("Successo", f"Esportazione Excel completata in:\n{save_path}")
            self.destroy()

class CPTUApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CPTU Vector Digitizer Pro")
        self.state('zoomed')
        
        self.pdf_doc = None
        self.pdf_page = None
        self.scale_factor = 1.0
        self.rotation_angle = 0.0
        self.matrix = fitz.Matrix(1, 1) 
        
        self.calibrations = {} 
        self.snap_points = []
        
        self.grid_visible = False
        self.grid_lines = []
        
        self.current_tool = 'select'
        self.selected_box = None
        self.drag_mode = None
        
        self.shortcuts = {'disegna': 'd', 'seleziona': 's', 'pan': 'p', 'calibra': 'c'}
        
        self.setup_ui()
        self.bind("<KeyPress>", self.on_key_press)

    def setup_ui(self):
        self.welcome_frame = tk.Frame(self, bg="#2c3e50")
        self.welcome_frame.place(relwidth=1, relheight=1)
        
        tk.Label(self.welcome_frame, text="Ciao Geo_02, cosa vuoi digitalizzare oggi?", 
                 font=("Helvetica", 24, "bold"), fg="white", bg="#2c3e50").pack(pady=150)
        tk.Button(self.welcome_frame, text="START", font=("Helvetica", 16, "bold"), bg="#27ae60", fg="white", padx=40, pady=10, command=self.start_app).pack()
        
        self.main_frame = tk.Frame(self)
        
        top_bar = tk.Frame(self.main_frame, bg="#ecf0f1", pady=5)
        top_bar.pack(side=tk.TOP, fill=tk.X)
        
        tk.Button(top_bar, text="Carica PDF", command=self.load_pdf, bg="#3498db", fg="white", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="Ruota PDF", command=self.rotate_pdf).pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="Griglia Guida On/Off", command=self.toggle_grid).pack(side=tk.LEFT, padx=5)
        tk.Button(top_bar, text="⚙️ Impostazioni", command=self.open_settings).pack(side=tk.RIGHT, padx=10)
        tk.Button(top_bar, text="Esporta ed Estrai", command=self.process_and_export, bg="#2ecc71", fg="white", font=("Arial", 10, "bold")).pack(side=tk.RIGHT, padx=5)
        
        self.toolbar = tk.Frame(self.main_frame, bg="#34495e", width=60)
        self.toolbar.pack(side=tk.LEFT, fill=tk.Y)
        
        self.btn_select = tk.Button(self.toolbar, text=f"^\nSeleziona\n({self.shortcuts['seleziona'].upper()})", command=lambda: self.set_tool('select'))
        self.btn_select.pack(pady=10, padx=5, fill=tk.X)
        
        self.btn_draw = tk.Button(self.toolbar, text=f"[ ]\nDisegna\n({self.shortcuts['disegna'].upper()})", command=lambda: self.set_tool('draw'))
        self.btn_draw.pack(pady=10, padx=5, fill=tk.X)
        
        self.btn_pan = tk.Button(self.toolbar, text=f"<>\nPan\n({self.shortcuts['pan'].upper()})", command=lambda: self.set_tool('pan'))
        self.btn_pan.pack(pady=10, padx=5, fill=tk.X)
        
        self.btn_zoom_in = tk.Button(self.toolbar, text="+\nZoom In", command=lambda: self.zoom(1.2))
        self.btn_zoom_in.pack(pady=10, padx=5, fill=tk.X)
        
        self.btn_zoom_out = tk.Button(self.toolbar, text="-\nZoom Out", command=lambda: self.zoom(0.8))
        self.btn_zoom_out.pack(pady=10, padx=5, fill=tk.X)

        tk.Frame(self.toolbar, height=2, bg="gray").pack(fill=tk.X, pady=10)

        self.btn_calibrate = tk.Button(self.toolbar, text=f"⚙️\nCalibra\n({self.shortcuts['calibra'].upper()})", command=self.open_calibration_dialog, bg="#f39c12", fg="white", font=("Arial", 8, "bold"))
        self.btn_calibrate.pack(pady=10, padx=5, fill=tk.X)

        self.canvas_frame = tk.Frame(self.main_frame)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.h_scroll = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.v_scroll = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.canvas = tk.Canvas(self.canvas_frame, bg="#bdc3c7", xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.config(command=self.canvas.yview)

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        
        if platform.system() in ['Windows', 'Darwin']:
            self.canvas.bind("<MouseWheel>", self.on_mousewheel)
            self.canvas.bind("<Shift-MouseWheel>", self.on_shift_mousewheel)
        else:
            self.canvas.bind("<Button-4>", self.on_mousewheel_up)
            self.canvas.bind("<Button-5>", self.on_mousewheel_down)
            self.canvas.bind("<Shift-Button-4>", self.on_shift_mousewheel_up)
            self.canvas.bind("<Shift-Button-5>", self.on_shift_mousewheel_down)

        self.set_tool('select')

    def on_mousewheel(self, event): self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    def on_shift_mousewheel(self, event): self.canvas.xview_scroll(int(-1*(event.delta/120)), "units")
    def on_mousewheel_up(self, event): self.canvas.yview_scroll(-1, "units")
    def on_mousewheel_down(self, event): self.canvas.yview_scroll(1, "units")
    def on_shift_mousewheel_up(self, event): self.canvas.xview_scroll(-1, "units")
    def on_shift_mousewheel_down(self, event): self.canvas.xview_scroll(1, "units")

    def on_key_press(self, event):
        if isinstance(event.widget, tk.Entry): return
        char = event.char.lower()
        keysym = event.keysym.lower()
        if char == self.shortcuts['disegna']: self.set_tool('draw')
        elif char == self.shortcuts['seleziona']: self.set_tool('select')
        elif char == self.shortcuts['pan']: self.set_tool('pan')
        elif char == self.shortcuts['calibra']: self.open_calibration_dialog()
        elif keysym in ['delete', 'backspace']: self.delete_selected_box()

    def delete_selected_box(self):
        if self.selected_box and self.selected_box in self.calibrations:
            data = self.calibrations[self.selected_box]
            self.canvas.delete(self.selected_box)
            self.canvas.delete(data["label_id"])
            del self.calibrations[self.selected_box]
            self.select_box(None)

    def open_settings(self):
        dialog = SettingsDialog(self, self.shortcuts)
        self.wait_window(dialog)
        if dialog.result:
            self.shortcuts = dialog.result
            self.btn_select.config(text=f"^\nSeleziona\n({self.shortcuts['seleziona'].upper()})")
            self.btn_draw.config(text=f"[ ]\nDisegna\n({self.shortcuts['disegna'].upper()})")
            self.btn_pan.config(text=f"<>\nPan\n({self.shortcuts['pan'].upper()})")
            self.btn_calibrate.config(text=f"⚙️\nCalibra\n({self.shortcuts['calibra'].upper()})")

    def set_tool(self, tool_name):
        self.current_tool = tool_name
        self.btn_draw.config(bg="lightgray")
        self.btn_select.config(bg="lightgray")
        self.btn_pan.config(bg="lightgray")
        if tool_name == 'draw':
            self.btn_draw.config(bg="yellow")
            self.canvas.config(cursor="cross")
            self.select_box(None) 
        elif tool_name == 'select':
            self.btn_select.config(bg="yellow")
            self.canvas.config(cursor="arrow")
        elif tool_name == 'pan':
            self.btn_pan.config(bg="yellow")
            self.canvas.config(cursor="hand2")
            self.select_box(None)

    def start_app(self):
        self.welcome_frame.destroy()
        self.main_frame.place(relwidth=1, relheight=1)

    def load_pdf(self):
        filepath = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not filepath: return
        self.pdf_doc = fitz.open(filepath)
        self.pdf_page = self.pdf_doc[0]
        self.rotation_angle = 0.0
        
        self.update_idletasks() 
        canvas_height = self.canvas.winfo_height()
        if canvas_height < 100: canvas_height = 800
        pdf_height = self.pdf_page.rect.height
        self.scale_factor = canvas_height / pdf_height
        self.render_pdf()

    def zoom(self, factor):
        if not self.pdf_page: return
        self.scale_factor *= factor
        self.render_pdf()

    def rotate_pdf(self):
        if not self.pdf_page: return
        angle = simpledialog.askfloat("Ruota PDF", "Inserisci l'angolo di rotazione:", initialvalue=90.0)
        if angle is not None:
            self.rotation_angle += angle
            self.render_pdf()

    def toggle_grid(self):
        self.grid_visible = not self.grid_visible
        self.draw_grid()

    def draw_grid(self):
        for line in self.grid_lines: self.canvas.delete(line)
        self.grid_lines.clear()
        if self.grid_visible:
            bbox = self.canvas.bbox("pdf_img")
            if not bbox: return
            w, h = bbox[2], bbox[3]
            for x in range(0, int(w), 50): self.grid_lines.append(self.canvas.create_line(x, 0, x, h, fill="green", dash=(2, 2)))
            for y in range(0, int(h), 50): self.grid_lines.append(self.canvas.create_line(0, y, w, y, fill="green", dash=(2, 2)))

    def render_pdf(self):
        if not self.pdf_page: return
        self.canvas.delete("all")
        self.grid_lines.clear()
        
        base_matrix = fitz.Matrix(self.scale_factor, self.scale_factor).prerotate(self.rotation_angle)
        bbox = self.pdf_page.rect * base_matrix
        self.matrix = base_matrix * fitz.Matrix(1, 0, 0, 1, -bbox.x0, -bbox.y0)
        
        pix = self.pdf_page.get_pixmap(matrix=self.matrix)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img, tags="pdf_img")
        
        self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))
        self.generate_snap_points()
        self.redraw_boxes()
        self.draw_grid()

    def redraw_boxes(self):
        for item_id, data in list(self.calibrations.items()):
            pdf_rect = data["pdf_rect"]
            pts = [fitz.Point(x, y) * self.matrix for x, y in [
                (pdf_rect.x0, pdf_rect.y0), (pdf_rect.x1, pdf_rect.y0),
                (pdf_rect.x0, pdf_rect.y1), (pdf_rect.x1, pdf_rect.y1)
            ]]
            xs, ys = [p.x for p in pts], [p.y for p in pts]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)

            color = "blue" if data.get("calibrated") else "red"
            text_str = data.get("param", "Da calibrare")
            
            new_rect = self.canvas.create_rectangle(
                x0, y0, x1, y1, outline="red", width=2, fill="yellow", stipple="gray25", tags="box"
            )
            new_label = self.canvas.create_text(
                x0 + 5, y0 + 5, text=text_str, fill=color, font=("Arial", max(10, int(14*self.scale_factor)), "bold"), anchor=tk.NW
            )
            
            data["label_id"] = new_label
            self.calibrations[new_rect] = data
            if item_id == self.selected_box: self.select_box(new_rect)
            del self.calibrations[item_id]

    def generate_snap_points(self):
        self.snap_points = []
        for d in self.pdf_page.get_drawings():
            for item in d["items"]:
                if item[0] in ("l", "c"): 
                    p1 = item[1] * self.matrix
                    self.snap_points.append((p1.x, p1.y))
                    if item[0] == "l":
                        p2 = item[2] * self.matrix
                        self.snap_points.append((p2.x, p2.y))

    def snap_coordinate(self, x, y):
        best_dist = 10.0
        snapped_x, snapped_y = x, y
        for sx, sy in self.snap_points:
            dist = ((sx - x)**2 + (sy - y)**2)**0.5
            if dist < best_dist:
                best_dist = dist
                snapped_x, snapped_y = sx, sy
        if self.grid_visible and best_dist == 10.0:
            gx, gy = round(x / 50) * 50, round(y / 50) * 50
            if ((gx - x)**2 + (gy - y)**2)**0.5 < 15.0: snapped_x, snapped_y = gx, gy
        return snapped_x, snapped_y

    def select_box(self, box_id):
        if self.selected_box: self.canvas.itemconfig(self.selected_box, outline="red", width=2)
        self.selected_box = box_id
        if self.selected_box:
            self.canvas.itemconfig(self.selected_box, outline="blue", width=3)
            self.canvas.tag_raise(self.selected_box)
            self.canvas.tag_raise(self.calibrations[self.selected_box]["label_id"])

    def on_press(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if self.current_tool == 'pan': self.canvas.scan_mark(event.x, event.y)
        elif self.current_tool == 'draw':
            sx, sy = self.snap_coordinate(x, y)
            self.rect_start_x, self.rect_start_y = sx, sy
            self.current_rect = self.canvas.create_rectangle(sx, sy, sx, sy, outline="red", width=2, fill="yellow", stipple="gray25", tags="box")
        elif self.current_tool == 'select':
            sx, sy = self.snap_coordinate(x, y)
            self.drag_mode = None
            if self.selected_box:
                coords = self.canvas.coords(self.selected_box)
                if coords:
                    x1, y1, x2, y2 = coords
                    T = 15
                    if abs(x - x1) < T and abs(y - y1) < T: self.drag_mode = 'nw'
                    elif abs(x - x2) < T and abs(y - y2) < T: self.drag_mode = 'se'
                    elif abs(x - x1) < T and abs(y - y2) < T: self.drag_mode = 'sw'
                    elif abs(x - x2) < T and abs(y - y1) < T: self.drag_mode = 'ne'
                    elif x1 <= x <= x2 and y1 <= y <= y2: self.drag_mode = 'move'

            if not self.drag_mode:
                items = self.canvas.find_overlapping(x, y, x, y)
                boxes = [i for i in items if "box" in self.canvas.gettags(i)]
                if boxes:
                    self.select_box(boxes[-1])
                    self.drag_mode = 'move'
                else: self.select_box(None)
            self.drag_start_x, self.drag_start_y = sx, sy

    def on_drag(self, event):
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if self.current_tool == 'pan': self.canvas.scan_dragto(event.x, event.y, gain=1)
        elif self.current_tool == 'draw' and self.current_rect:
            sx, sy = self.snap_coordinate(x, y)
            self.canvas.coords(self.current_rect, self.rect_start_x, self.rect_start_y, sx, sy)
        elif self.current_tool == 'select' and self.selected_box and self.drag_mode:
            sx, sy = self.snap_coordinate(x, y)
            dx, dy = sx - self.drag_start_x, sy - self.drag_start_y
            x1, y1, x2, y2 = self.canvas.coords(self.selected_box)

            if self.drag_mode == 'move':
                self.canvas.move(self.selected_box, dx, dy)
                self.canvas.move(self.calibrations[self.selected_box]["label_id"], dx, dy)
            elif self.drag_mode == 'nw': self.canvas.coords(self.selected_box, sx, sy, x2, y2)
            elif self.drag_mode == 'se': self.canvas.coords(self.selected_box, x1, y1, sx, sy)
            elif self.drag_mode == 'sw': self.canvas.coords(self.selected_box, sx, y1, x2, sy)
            elif self.drag_mode == 'ne': self.canvas.coords(self.selected_box, x1, sy, sx, y2)
            self.drag_start_x, self.drag_start_y = sx, sy

    def on_release(self, event):
        if self.current_tool == 'draw' and self.current_rect:
            x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            ex, ey = self.snap_coordinate(x, y)
            if abs(ex - self.rect_start_x) < 15 or abs(ey - self.rect_start_y) < 15:
                self.canvas.delete(self.current_rect)
                self.current_rect = None
                return

            inv_matrix = ~self.matrix
            p_start = fitz.Point(self.rect_start_x, self.rect_start_y) * inv_matrix
            p_end = fitz.Point(ex, ey) * inv_matrix
            txt_id = self.canvas.create_text(min(self.rect_start_x, ex) + 5, min(self.rect_start_y, ey) + 5, text="Da calibrare", fill="red", font=("Arial", max(10, int(14*self.scale_factor)), "bold"), anchor=tk.NW)
            
            self.calibrations[self.current_rect] = {"calibrated": False, "pdf_rect": fitz.Rect(p_start, p_end), "label_id": txt_id}
            self.set_tool('select')
            self.select_box(self.current_rect)
            self.current_rect = None
            
        elif self.current_tool == 'select' and self.selected_box and self.drag_mode:
            x1, y1, x2, y2 = self.canvas.coords(self.selected_box)
            inv_matrix = ~self.matrix
            self.calibrations[self.selected_box]["pdf_rect"] = fitz.Rect(fitz.Point(x1, y1) * inv_matrix, fitz.Point(x2, y2) * inv_matrix)
            if self.drag_mode != 'move': self.canvas.coords(self.calibrations[self.selected_box]["label_id"], min(x1,x2)+5, min(y1,y2)+5)
            self.drag_mode = None

    def on_double_click(self, event):
        if self.current_tool == 'select' and self.selected_box: self.open_calibration_dialog()

    def open_calibration_dialog(self):
        if not self.selected_box: return messagebox.showinfo("Info", "Seleziona prima un rettangolo usando lo strumento 'Seleziona'.")
            
        data = self.calibrations[self.selected_box]
        dialog = CalibrationDialog(self, existing_data=data)
        self.wait_window(dialog)
        
        if dialog.delete_flag: self.delete_selected_box()
        elif dialog.result:
            dialog.result["pdf_rect"] = data["pdf_rect"]
            dialog.result["label_id"] = data["label_id"]
            self.calibrations[self.selected_box] = dialog.result
            self.canvas.itemconfig(data["label_id"], text=dialog.result["param"], fill="blue")

    # --- MOTORE DI ESTRAZIONE ASSOLUTO (V3) ---
    def process_and_export(self):
        calibrated_boxes = [cal for cal in self.calibrations.values() if cal.get("calibrated", False)]
        if not self.pdf_page or not calibrated_boxes:
            return messagebox.showwarning("Attenzione", "Devi calibrare almeno un rettangolo prima di esportare.")
            
        drawings = self.pdf_page.get_drawings()
        target_depths = np.arange(0, 40.01, 0.01)
        df_final = pd.DataFrame({"Profondità (m)": target_depths})
        
        for cal in calibrated_boxes:
            pts = [fitz.Point(x, y) * self.matrix for x, y in [
                (cal["pdf_rect"].x0, cal["pdf_rect"].y0), (cal["pdf_rect"].x1, cal["pdf_rect"].y0),
                (cal["pdf_rect"].x0, cal["pdf_rect"].y1), (cal["pdf_rect"].x1, cal["pdf_rect"].y1)
            ]]
            xs, ys = [p.x for p in pts], [p.y for p in pts]
            cx0, cx1, cy0, cy1 = min(xs), max(xs), min(ys), max(ys)
            
            box_width = cx1 - cx0
            box_height = cy1 - cy0
            
            points = []
            conversion = CONVERSION_FACTORS.get((cal["source_unit"], cal["target_unit"]), 1.0)
            chosen_color = cal.get("color_filter", "Tutti")
            
            for d in drawings:
                # 1. IGNORA I RETTANGOLI: le cornici e gli sfondi sono quasi sempre operazioni "re" (rectangle)
                # questo ripulisce istantaneamente il 90% del rumore di fondo.
                
                # 2. COLORE INFALLIBILE
                line_color = "Altro"
                c = d.get("color")
                if c is None or len(c) < 3:
                    line_color = "Nero/Grigio"
                else:
                    r, g, b = c[0], c[1], c[2]
                    # Se i valori RGB sono vicinissimi tra loro, è una sfumatura di grigio/nero
                    if max(r,g,b) - min(r,g,b) < 0.15:
                        line_color = "Nero/Grigio"
                    else:
                        if r > g + 0.2 and r > b + 0.2: line_color = "Rosso"
                        elif b > r + 0.2 and b > g + 0.2: line_color = "Blu"
                        elif g > r + 0.2 and g > b + 0.2: line_color = "Verde"
                
                if chosen_color != "Tutti" and line_color != chosen_color:
                    continue

                for item in d["items"]:
                    if item[0] == "re": continue # Ignora sempre i rettangoli
                    
                    pts_raw = []
                    # 3. ESTRAZIONE ENDPOINT (Niente maniglie di bezier che sballano)
                    if item[0] == "l":
                        pts_raw = [item[1], item[2]]
                        
                    if not pts_raw: continue

                    p1 = pts_raw[0] * self.matrix
                    p2 = pts_raw[1] * self.matrix

                    # 4. FILTRO ANTI-CORNICE (Senza uccidere i valori sullo zero!)
                    # Se una linea attraversa il grafico per quasi tutta la sua lunghezza/altezza, la scartiamo.
                    dx = abs(p1.x - p2.x)
                    dy = abs(p1.y - p2.y)
                    if dy < 1.0: continue # Regola 1: Veto Orizzontale (ignora i ritorni allo zero)
                    if dy >= box_height * 0.95: continue # Cornice verticale
                    if dx >= box_width * 0.95: continue  # Cornice o griglia orizzontale
                    
                    # 5. ESTRAZIONE PRECISA DEI PUNTI (Nessun bleed, tolleranza fissa a soli 2 pixel)
                    margin = 2
                    for p in (p1, p2):
                        if (cx0 - margin) <= p.x <= (cx1 + margin) and (cy0 - margin) <= p.y <= (cy1 + margin):
                            # Mappa i pixel in valori matematici reali
                            px_cl = max(cx0, min(cx1, p.x))
                            py_cl = max(cy0, min(cy1, p.y))
                            
                            val_x = np.interp(px_cl, [cx0, cx1], cal["x_range"]) * conversion
                            val_y = np.interp(py_cl, [cy0, cy1], cal["y_range"])
                            points.append((val_y, val_x))
            
            if points:
                # Arrotondo a 1cm per aggregare i punti sdoppiati in un profilo pulito
                df_pts = pd.DataFrame(points, columns=['depth', 'val'])
                df_pts['depth_round'] = df_pts['depth'].round(3)
                df_pts = df_pts.groupby('depth_round')['val'].max().reset_index().sort_values('depth_round')
                
                f_interp = interp1d(df_pts['depth_round'], df_pts['val'], bounds_error=False, fill_value=np.nan)
                col_name = f'{cal["param"]} ({cal["target_unit"]})'
                df_final[col_name] = f_interp(target_depths)
        
        if len(df_final.columns) == 1:
            messagebox.showerror("Errore", "Nessun dato estratto. Assicurati che i colori corrispondano e che le maschere coprano le curve.")
        else:
            PreviewWindow(self, df_final)

if __name__ == "__main__":
    app = CPTUApp()
    app.mainloop()