"""
NERV_GUI.py - Interfaz gráfica general de NERV
(Neuroimaging Evaluator for Response Verification)

Reemplaza el flujo por consola de Looped_NERV.py por una única ventana con
los pasos del protocolo:

    1. Cargar estudios (RM temprana y tardía)
    2. Registración (rígida / deformable) y verificación visual
    3. TRAM: histograma, LUT y recorte
    4. Exportar (RGB y PET-CT en DICOM)
    +  Botón "Agregar estudio de espectroscopia" (todavía sin función)

Uso (desde la carpeta del proyecto, junto a los demás .py):
    python NERV_GUI.py            -> usa los módulos reales de NERV
    python NERV_GUI.py --demo     -> datos sintéticos, para probar la interfaz

Toda la comunicación con el código existente está en la clase RealBackend.
Si alguna firma no coincide con tus módulos, es el único lugar a tocar.
"""

__author__ = "Interfaz basada en el flujo de Alejo Chacon y Facundo Main"

import sys
import time
import traceback
from types import SimpleNamespace

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import SimpleITK as sitk
import matplotlib

matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --------------------------------------------------------------------------
# Apariencia
# --------------------------------------------------------------------------
BG = "#14161b"
PANEL = "#1b1e25"
PANEL_HI = "#262a33"
ACCENT = "#4f8cff"
FG = "#e6e8ec"
FG_DIM = "#8b919c"
OK = "#4cc38a"
VIEW_BG = "#0d0e12"

_FAIL = object()  # marca de error en operaciones largas

# Opciones de registración (mismas ramas que mri_registration_tool.registration_tool)
REG_OPTIONS = [
    ("deformable", "Deformable"),
    ("externa", "Rígida externa (archivo DICOM)"),
    ("interna", "Rígida interna básica"),
    ("roi", "Rígida interna con ROI"),
]
REG_HINTS = {
    "deformable": "Aplica primero una rígida y luego una B-spline. Puede tardar varios minutos.",
    "externa": "Pide el archivo DICOM de registro. Indicá cuál resonancia es la fija.",
    "interna": "Registro rígido por información mutua (validado).",
    "roi": "Se abrirá una ventana para seleccionar la ROI y luego se registra. Falta validar.",
}
REG_NAMES = {1: "Deformable", 2: "Rígida externa", 3: "Rígida interna básica", 4: "Rígida interna con ROI"}


# --------------------------------------------------------------------------
# Utilidades de imagen
# --------------------------------------------------------------------------
def slice_to_array(s):
    """Convierte un corte (sitk.Image, lista [R,G,B] de sitk.Image o ndarray)
    a un ndarray HxW (escala de grises) o HxWx3 (color)."""
    if isinstance(s, (list, tuple)):
        chans = [sitk.GetArrayFromImage(c) if isinstance(c, sitk.Image) else np.asarray(c) for c in s]
        if len(chans) in (3, 4) and chans[0].ndim == 2:
            return np.stack(chans[:3], axis=-1)
        return chans[0]
    if isinstance(s, sitk.Image):
        a = sitk.GetArrayFromImage(s)
        if s.GetNumberOfComponentsPerPixel() > 1:
            return a
        if a.ndim == 3 and a.shape[0] in (3, 4):
            return np.moveaxis(a, 0, -1)[..., :3]
        if a.ndim == 3 and a.shape[0] == 1:
            return a[0]
        return a
    return np.asarray(s)


def is_rgb(a):
    return a.ndim == 3 and a.shape[-1] in (3, 4)


# --------------------------------------------------------------------------
# Visor de cortes (con deslizador y rueda del mouse)
# --------------------------------------------------------------------------
class SliceViewer(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        self.fig = Figure(figsize=(5, 3), dpi=100, facecolor=VIEW_BG)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        w = self.canvas.get_tk_widget()
        w.configure(bg=VIEW_BG, highlightthickness=0, width=300, height=200)
        w.pack(side="top", fill="both", expand=True)

        ttk.Button(bar, text="◀", width=3, command=lambda: self.step(-1)).pack(side="left")
        self.slider = ttk.Scale(bar, from_=0, to=1, orient="horizontal", command=self._on_slider)
        self.slider.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(bar, text="▶", width=3, command=lambda: self.step(1)).pack(side="left")
        self.label = ttk.Label(bar, text="—", width=16, anchor="e")
        self.label.pack(side="left", padx=(8, 0))

        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            w.bind(ev, self._on_wheel)
        w.bind("<Enter>", lambda e: w.focus_set())
        w.bind("<Left>", lambda e: self.step(-1))
        w.bind("<Right>", lambda e: self.step(1))
        w.bind("<Up>", lambda e: self.step(1))
        w.bind("<Down>", lambda e: self.step(-1))

        self.n = 0
        self.idx = 0
        self._panels = []
        self._updating = False
        self.on_change = None  # callback(idx) al cambiar de corte
        self.unit = "Corte"    # texto de la etiqueta ("Corte", "Captura", ...)

    # -- API --------------------------------------------------------------
    def clear(self):
        self.fig.clear()
        self._panels = []
        self.n = 0
        self.label.config(text="—")
        self.canvas.draw_idle()

    def set_images(self, lists, titles):
        """lists: una o más listas de cortes (se muestran lado a lado)."""
        self.fig.clear()
        self._panels = []
        lists = [l for l in lists if l]
        if not lists:
            self.canvas.draw_idle()
            return
        self.n = min(len(l) for l in lists)
        for k, (lst, title) in enumerate(zip(lists, titles)):
            arrs = [slice_to_array(s) for s in lst[: self.n]]
            ax = self.fig.add_subplot(1, len(lists), k + 1)
            ax.set_facecolor(VIEW_BG)
            ax.set_title(title, color=FG, fontsize=10, pad=6)
            ax.axis("off")
            rgb = is_rgb(arrs[0])
            if rgb:
                lo, hi = 0, 1
                im = ax.imshow(self._norm_rgb(arrs[0]))
            else:
                sample = np.concatenate([a[::4, ::4].ravel() for a in arrs]).astype(float)
                lo, hi = np.percentile(sample, (0.5, 99.5))
                if hi <= lo:
                    hi = lo + 1.0
                im = ax.imshow(arrs[0], cmap="gray", vmin=lo, vmax=hi)
            self._panels.append(SimpleNamespace(im=im, arrs=arrs, rgb=rgb))
        self.fig.subplots_adjust(left=0.01, right=0.99, bottom=0.01, top=0.93, wspace=0.03)
        self.slider.config(to=max(self.n - 1, 1))
        self.goto(self.n // 2)

    def goto(self, i):
        if not self._panels:
            return
        self.idx = int(max(0, min(self.n - 1, i)))
        for p in self._panels:
            a = p.arrs[self.idx]
            p.im.set_data(self._norm_rgb(a) if p.rgb else a)
        self.label.config(text=f"{self.unit} {self.idx + 1} / {self.n}")
        self._updating = True
        self.slider.set(self.idx)
        self._updating = False
        self.canvas.draw_idle()
        if self.on_change:
            self.on_change(self.idx)

    def step(self, d):
        self.goto(self.idx + d)

    # -- internos ---------------------------------------------------------
    @staticmethod
    def _norm_rgb(a):
        a = a[..., :3].astype(float)
        if a.max() > 1.0:
            a = a / 255.0
        return np.clip(a, 0, 1)

    def _on_slider(self, v):
        if not self._updating:
            self.goto(int(round(float(v))))

    def _on_wheel(self, e):
        up = (getattr(e, "num", 0) == 4) or (getattr(e, "delta", 0) > 0)
        self.step(-1 if up else 1)


# --------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------
class RealBackend:
    """Puente hacia los módulos existentes de NERV (mismas llamadas que
    Looped_NERV.py). Si alguna firma cambia, se corrige acá."""

    demo = False

    def __init__(self):
        from Dicom_Reader_Writer import get_dicom, rgb_to_dicom, monochrome_to_PET_dicom, export_registration_txt
        from back_to_slices import convert_3d_image_to_slices, convert_3d_image_to_arrslices
        import mri_registration_tool as mrt
        from subtract_mri import subtract_mri
        from apply_lut import lut_and_clipping_manager

        self._get_dicom = get_dicom
        self._rgb_to_dicom = rgb_to_dicom
        self._pet_to_dicom = monochrome_to_PET_dicom
        self._to_slices = convert_3d_image_to_slices
        self._to_arrays = convert_3d_image_to_arrslices
        self._export_txt = export_registration_txt
        self._mrt = mrt
        self._subtract = subtract_mri
        self._lut = lut_and_clipping_manager

    def load_study(self, path, which):
        return self._get_dicom(path)  # -> (img, metadata)

    def to_slices(self, img):
        return self._to_slices(img)

    def to_arrays(self, img):
        return self._to_arrays(img)  # lista de ndarrays 2D (lo que usa espectroscopia.py)

    def register(self, t1_img, t1_md, t2_img, t2_md, mode, fixed="t1"):
        """Replica las ramas de mri_registration_tool.registration_tool sin usar input().
        mode: 'deformable' | 'externa' | 'interna' | 'roi'.  fixed: 't1' | 't2' (solo externa).
        -> (t1_list, t2_list, t1_img, resampled_img3D, tipo_registro)"""
        m = self._mrt
        to_slices = m.convert_3d_image_to_slices
        # Cada intento parte limpio: evita que una transformada vieja (p. ej. de una
        # deformable previa) se componga con la de este intento en get_transform().
        m.RIGID_TRANSFORM = None
        m.DEFORMABLE_TRANSFORM = None

        if mode == "deformable":
            res3d = m.nonrigid_registration(t1_img, t2_img)
            return to_slices(t1_img), to_slices(res3d), t1_img, res3d, m.DEFORMABLE

        if mode == "externa":
            dicom_reg = m.load_registration_dicom()
            if dicom_reg is None:
                raise RuntimeError("No se seleccionó el archivo de registro.")
            if fixed == "t1":
                res3d = m.registerDicom(t1_img, t2_img, t2_md[0].get("0020|000e"), dicom_reg)
                return to_slices(t1_img), to_slices(res3d), t1_img, res3d, m.REXTERNAL
            res3d = m.registerDicom(t2_img, t1_img, t1_md[0].get("0020|000e"), dicom_reg)
            return to_slices(res3d), to_slices(t2_img), t1_img, res3d, m.REXTERNAL

        if mode == "interna":
            res3d = m.rigid_registration(t1_img, t2_img)
            return to_slices(t1_img), to_slices(res3d), t1_img, res3d, m.RINTERNALBASIC

        if mode == "roi":
            mask = m.select_roi_mask(t1_img)
            res3d = m.rigid_registration_withMask(t1_img, t2_img, mask)
            return to_slices(t1_img), to_slices(res3d), t1_img, res3d, m.RINTERNALROI

        raise ValueError(f"Tipo de registración desconocido: {mode}")

    def subtract(self, t1_list, t2_list):
        return self._subtract(t1_list, t2_list)

    def make_tram(self, subtraction, clip):
        if clip:
            return self._lut(subtraction, clip, lut="jet")
        return self._lut(subtraction, lut="jet")

    def export_registration(self):
        self._export_txt(self._mrt.get_transform())

    def export_rgb(self, tram, t1_md, resampled, tipo):
        rgb_tram = []
        for img in tram:
            R = sitk.GetArrayFromImage(img[0])
            G = sitk.GetArrayFromImage(img[1])
            B = sitk.GetArrayFromImage(img[2])
            rgb = sitk.GetImageFromArray(np.stack((R, G, B), axis=-1), isVector=True)
            rgb_tram.append(rgb)
        self._rgb_to_dicom(rgb_tram, t1_md, resampled, tipo)

    def export_pet(self, tram_pet, t1_md, resampled, tipo):
        self._pet_to_dicom(tram_pet, t1_md, resampled, tipo)


class DemoBackend:
    """Datos sintéticos para probar la interfaz sin DICOM reales."""

    demo = True

    def load_study(self, path, which):
        rng = np.random.default_rng(1 if which == "t1" else 2)
        z, h, w = 24, 128, 128
        zz, yy, xx = np.mgrid[0:z, 0:h, 0:w]
        brain = (((yy - 64) / 52) ** 2 + ((xx - 64) / 44) ** 2 + ((zz - 12) / 14) ** 2) < 1
        vol = np.where(brain, 400.0, 0.0)
        tumor = ((yy - 58) ** 2 + (xx - 72) ** 2 + ((zz - 12) * 2.2) ** 2) < 14 ** 2
        if which == "t1":
            vol += tumor * 120
        else:
            vol += tumor * (120 + 220 * np.exp(-(((yy - 58) ** 2 + (xx - 72) ** 2) / 120.0)))
            vol -= (((yy - 60) ** 2 + (xx - 70) ** 2 + ((zz - 12) * 2.2) ** 2) < 5 ** 2) * 150
        vol += rng.normal(0, 8, vol.shape) * brain
        return sitk.GetImageFromArray(vol.astype(np.float32)), {"demo": True}

    def to_slices(self, img):
        arr = sitk.GetArrayFromImage(img)
        return [sitk.GetImageFromArray(arr[i]) for i in range(arr.shape[0])]

    def to_arrays(self, img):
        return list(sitk.GetArrayFromImage(img))

    def export_registration(self):
        messagebox.showinfo("Demo", "En modo demo no se escribe ningún archivo de registración.")

    def register(self, t1_img, t1_md, t2_img, t2_md, mode, fixed="t1"):
        time.sleep(0.6)
        tipo = {"deformable": 1, "externa": 2, "interna": 3, "roi": 4}[mode]
        return self.to_slices(t1_img), self.to_slices(t2_img), t1_img, t2_img, tipo

    def subtract(self, t1_list, t2_list):
        return [sitk.Subtract(sitk.Cast(b, sitk.sitkFloat32), sitk.Cast(a, sitk.sitkFloat32))
                for a, b in zip(t1_list, t2_list)]

    def make_tram(self, subtraction, clip):
        arrs = [sitk.GetArrayFromImage(s) for s in subtraction]
        allv = np.concatenate([a.ravel() for a in arrs])
        m = float(np.abs(allv).max())
        if clip:
            c = clip.strip().lower()
            m = float(np.percentile(np.abs(allv), 100 - float(c[:-1]))) if c.endswith("%") else float(c)
        m = max(m, 1e-6)
        cmap = matplotlib.colormaps["jet"]
        out = []
        for a in arrs:
            rgba = cmap(np.clip((a + m) / (2 * m), 0, 1))
            out.append((rgba[..., :3] * 255).astype(np.uint8))
        return out

    def export_rgb(self, tram, t1_md, resampled, tipo):
        messagebox.showinfo("Demo", "En modo demo no se escribe ningún DICOM.")

    def export_pet(self, tram_pet, t1_md, resampled, tipo):
        messagebox.showinfo("Demo", "En modo demo no se escribe ningún DICOM.")


# --------------------------------------------------------------------------
# Aplicación
# --------------------------------------------------------------------------
STEPS = ["Cargar estudios", "Registración", "TRAM y LUT", "Exportar"]
MRS_BTN_TEXT = "＋  Agregar estudio de espectroscopia"


class NervApp(tk.Tk):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self.title("NERV — Neuroimaging Evaluator for Response Verification")
        self.geometry("1320x800")
        self.minsize(1050, 660)
        self.configure(bg=BG)
        self._style()
        self._menu()
        self._reset_state()
        self._layout()
        self.show_page(0)

    # -- estado -----------------------------------------------------------
    def _reset_state(self):
        self.s = SimpleNamespace(
            t1_img=None, t1_md=None, t2_img=None, t2_md=None,
            t1_slices=None, t2_slices=None,
            t1_list=None, t2_list=None, resampled=None, tipo=None,
            subtraction=None, tram=None, tram_prev=None, clip=None,
        )
        self.done = set()
        self._tram_cache = {}
        self._reset_mrs()

    # -- estilo / menú ----------------------------------------------------
    def _style(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, font=("Segoe UI", 10))
        st.configure("TFrame", background=BG)
        st.configure("TLabel", background=BG, foreground=FG)
        st.configure("Dim.TLabel", foreground=FG_DIM)
        st.configure("H.TLabel", font=("Segoe UI", 17, "bold"))
        st.configure("Sub.TLabel", foreground=FG_DIM, font=("Segoe UI", 10))
        st.configure("Ok.TLabel", foreground=OK)
        st.configure("TButton", background=PANEL_HI, foreground=FG, padding=(12, 6), borderwidth=0)
        st.map("TButton", background=[("active", "#323744"), ("disabled", PANEL)],
               foreground=[("disabled", FG_DIM)])
        st.configure("Accent.TButton", background=ACCENT, foreground="white", font=("Segoe UI", 10, "bold"))
        st.map("Accent.TButton", background=[("active", "#6a9eff"), ("disabled", PANEL)],
               foreground=[("disabled", FG_DIM)])
        st.configure("TRadiobutton", background=BG, foreground=FG)
        st.map("TRadiobutton", background=[("active", BG)])
        st.configure("TEntry", insertcolor=FG, padding=5)
        st.configure("Horizontal.TScale", background=BG, troughcolor=PANEL_HI)
        st.configure("Card.TFrame", background=PANEL)
        st.configure("Card.TRadiobutton", background=PANEL, foreground=FG)
        st.map("Card.TRadiobutton", background=[("active", PANEL)])
        st.configure("Card.TLabel", background=PANEL)
        st.configure("CardDim.TLabel", background=PANEL, foreground=FG_DIM)

    def _menu(self):
        m = tk.Menu(self)
        f = tk.Menu(m, tearoff=0)
        f.add_command(label="Nuevo análisis", command=self.new_analysis)
        f.add_separator()
        f.add_command(label="Salir", command=self.destroy)
        m.add_cascade(label="Archivo", menu=f)
        self.config(menu=m)

    # -- layout -----------------------------------------------------------
    def _layout(self):
        side = tk.Frame(self, bg=PANEL, width=240)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="NERV", bg=PANEL, fg=FG, font=("Segoe UI", 24, "bold")).pack(anchor="w", padx=20, pady=(22, 0))
        tk.Label(side, text="Neuroimaging Evaluator\nfor Response Verification", bg=PANEL, fg=FG_DIM,
                 justify="left", font=("Segoe UI", 9)).pack(anchor="w", padx=20, pady=(0, 24))

        self.step_btns = []
        for i, name in enumerate(STEPS):
            b = tk.Button(side, text=f"  {i + 1}   {name}", anchor="w", relief="flat", bd=0,
                          font=("Segoe UI", 11), padx=14, pady=10, cursor="hand2",
                          command=lambda i=i: self.show_page(i))
            b.pack(fill="x", padx=10, pady=2)
            self.step_btns.append(b)

        tk.Frame(side, bg=PANEL).pack(fill="both", expand=True)
        tk.Frame(side, bg=PANEL_HI, height=1).pack(fill="x", padx=16, pady=8)
        self.btn_spectro = tk.Button(side, text=MRS_BTN_TEXT, relief="flat", bd=0,
                                     wraplength=190, justify="left", anchor="w", bg=PANEL_HI, fg=FG,
                                     activebackground="#323744", activeforeground=FG, font=("Segoe UI", 10),
                                     padx=14, pady=10, cursor="hand2", command=self.open_mrs)
        self.btn_spectro.pack(fill="x", padx=10, pady=(0, 18))

        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)
        self.status = tk.StringVar(value="Listo")
        sb = tk.Frame(right, bg=PANEL)
        sb.pack(side="bottom", fill="x")
        tk.Label(sb, textvariable=self.status, bg=PANEL, fg=FG_DIM, anchor="w", padx=14, pady=5).pack(side="left")
        if self.backend.demo:
            tk.Label(sb, text="MODO DEMO — datos sintéticos", bg=PANEL, fg="#e0a030", padx=14).pack(side="right")

        self.container = ttk.Frame(right)
        self.container.pack(fill="both", expand=True, padx=24, pady=18)
        self.pages = [self._page_load(), self._page_reg(), self._page_tram(), self._page_export(), self._page_mrs()]

    @staticmethod
    def _header(parent, title, subtitle):
        ttk.Label(parent, text=title, style="H.TLabel").pack(anchor="w")
        ttk.Label(parent, text=subtitle, style="Sub.TLabel", wraplength=900, justify="left").pack(anchor="w", pady=(2, 14))

    # -- navegación -------------------------------------------------------
    def allowed(self, i):
        if i == 4:  # espectroscopia: solo requiere la T1 cargada
            return bool(self.s.t1_slices)
        return i == 0 or (i - 1) in self.done

    def show_page(self, i):
        if not self.allowed(i):
            return
        for p in self.pages:
            p.pack_forget()
        self.pages[i].pack(fill="both", expand=True)
        self.cur = i
        if i == 2:
            self._enter_tram()
        elif i == 3:
            self._enter_export()
        elif i == 4:
            self._enter_mrs()
        self._refresh_mrs_buttons()
        self._refresh_steps()

    def _refresh_steps(self):
        for i, b in enumerate(self.step_btns):
            ok = self.allowed(i)
            mark = "✓" if i in self.done else str(i + 1)
            b.config(text=f"  {mark}   {STEPS[i]}", state="normal" if ok else "disabled")
            if i == getattr(self, "cur", 0):
                b.config(bg=ACCENT, fg="white", activebackground=ACCENT, activeforeground="white")
            else:
                b.config(bg=PANEL, fg=FG if ok else "#555a66", activebackground=PANEL_HI,
                         activeforeground=FG, disabledforeground="#555a66")
        on_mrs = getattr(self, "cur", 0) == 4
        self.btn_spectro.config(bg=ACCENT if on_mrs else PANEL_HI, fg="white" if on_mrs else FG,
                                activebackground=ACCENT if on_mrs else "#323744")

    def busy(self, msg, fn, *a, **k):
        """Ejecuta fn en el hilo principal mostrando cursor de espera y
        capturando errores (los módulos de NERV abren ventanas propias)."""
        self.status.set(msg)
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            return fn(*a, **k)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            messagebox.showerror("Error", f"{msg}\n\n{type(e).__name__}: {e}")
            return _FAIL
        finally:
            self.config(cursor="")
            self.status.set("Listo")

    def new_analysis(self):
        if messagebox.askyesno("Nuevo análisis", "Se descartará el trabajo actual. ¿Continuar?"):
            self._reset_state()
            self.lbl_t1.config(text="Sin cargar", style="Dim.TLabel")
            self.lbl_t2.config(text="Sin cargar", style="Dim.TLabel")
            for v in (self.view_load, self.view_reg, self.view_tram, self.view_exp):
                v.clear()
            self.btn_accept_reg.config(state="disabled")
            self.btn_export_reg.config(state="disabled")
            self.show_page(0)

    # ---------------------------------------------------------------- 1
    def _page_load(self):
        f = ttk.Frame(self.container)
        self._header(f, "Cargar estudios",
                     "Seleccioná la carpeta DICOM de la resonancia temprana y la de la tardía.")
        card = ttk.Frame(f, style="Card.TFrame")
        card.pack(fill="x", pady=(0, 14))
        rows = [("Resonancia temprana (T1)", "t1"), ("Resonancia tardía (T2)", "t2")]
        for r, (txt, which) in enumerate(rows):
            ttk.Label(card, text=txt, style="Card.TLabel", font=("Segoe UI", 10, "bold")).grid(
                row=r, column=0, sticky="w", padx=16, pady=12)
            lbl = ttk.Label(card, text="Sin cargar", style="CardDim.TLabel")
            lbl.grid(row=r, column=1, sticky="w", padx=8)
            setattr(self, f"lbl_{which}", lbl)
            ttk.Button(card, text="Seleccionar carpeta…", command=lambda w=which: self.pick_study(w)).grid(
                row=r, column=2, padx=16, pady=12)
            card.columnconfigure(1, weight=1)
        self.view_load = SliceViewer(f)
        foot = ttk.Frame(f)
        foot.pack(side="bottom", fill="x", pady=(10, 0))
        self.btn_next_load = ttk.Button(foot, text="Continuar a registración  →", style="Accent.TButton",
                                        state="disabled", command=lambda: self.show_page(1))
        self.btn_next_load.pack(side="right")
        self.view_load.pack(side="top", fill="both", expand=True)
        return f

    def pick_study(self, which):
        name = "temprana" if which == "t1" else "tardía"
        if self.backend.demo:
            path = "demo"
        else:
            path = filedialog.askdirectory(title=f"Seleccione la carpeta de la resonancia {name}")
            if not path:
                return
        res = self.busy(f"Cargando resonancia {name}…", self._load_study, which, path)
        if res is _FAIL:
            return
        lbl = getattr(self, f"lbl_{which}")
        lbl.config(text=path, style="Ok.TLabel")
        if which == "t1":
            self._reset_mrs()  # el corte de MRS elegido sobre la T1 anterior ya no vale
        self.done -= {0, 1, 2, 3}
        self.s.tram = self.s.subtraction = None
        self.btn_accept_reg.config(state="disabled")
        self.btn_export_reg.config(state="disabled")
        self._show_loaded()

    def _load_study(self, which, path):
        img, md = self.backend.load_study(path, which)
        slices = self.backend.to_slices(img)
        setattr(self.s, f"{which}_img", img)
        setattr(self.s, f"{which}_md", md)
        setattr(self.s, f"{which}_slices", slices)

    def _show_loaded(self):
        s = self.s
        lists, titles = [], []
        if s.t1_slices:
            lists.append(s.t1_slices); titles.append("RM temprana (T1) — original")
        if s.t2_slices:
            lists.append(s.t2_slices); titles.append("RM tardía (T2) — original")
        self.view_load.set_images(lists, titles)
        if s.t1_slices and s.t2_slices:
            self.done.add(0)
            self.btn_next_load.config(state="normal")
        self._refresh_steps()

    # ---------------------------------------------------------------- 2
    def _page_reg(self):
        f = ttk.Frame(self.container)
        self._header(f, "Registración",
                     "Elegí el tipo de registración, ejecutala y verificá visualmente que las imágenes "
                     "coincidan. Podés repetir con otro método hasta quedar conforme.")
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 6))
        self.reg_mode = tk.StringVar(value="interna")
        for val, txt in REG_OPTIONS:
            ttk.Radiobutton(top, text=txt, value=val, variable=self.reg_mode,
                            command=self._reg_mode_changed).pack(side="left", padx=(0, 18))

        row2 = ttk.Frame(f)
        row2.pack(fill="x", pady=(2, 4))
        self.btn_run_reg = ttk.Button(row2, text="Ejecutar registración", style="Accent.TButton",
                                      command=self.run_registration)
        self.btn_run_reg.pack(side="left")
        self.fixed_var = tk.StringVar(value="t1")
        self.fixed_box = ttk.Frame(row2)
        ttk.Label(self.fixed_box, text="Resonancia fija:").pack(side="left", padx=(0, 8))
        ttk.Radiobutton(self.fixed_box, text="Temprana (T1)", value="t1", variable=self.fixed_var).pack(side="left", padx=(0, 10))
        ttk.Radiobutton(self.fixed_box, text="Tardía (T2)", value="t2", variable=self.fixed_var).pack(side="left")
        self.lbl_reg = ttk.Label(row2, text="", style="Ok.TLabel")
        self.lbl_reg.pack(side="left", padx=14)

        self.lbl_hint = ttk.Label(f, text="", style="Dim.TLabel")
        self.lbl_hint.pack(anchor="w", pady=(0, 10))
        self.view_reg = SliceViewer(f)
        foot = ttk.Frame(f)
        foot.pack(side="bottom", fill="x", pady=(10, 0))
        self.btn_accept_reg = ttk.Button(foot, text="Aceptar registración  →", style="Accent.TButton",
                                         state="disabled", command=self.accept_registration)
        self.btn_accept_reg.pack(side="right")
        self.btn_export_reg = ttk.Button(foot, text="Exportar registración (.txt)", state="disabled",
                                         command=self.export_registration)
        self.btn_export_reg.pack(side="right", padx=8)
        ttk.Label(foot, text="¿No quedó bien? Cambiá el método y ejecutá de nuevo.", style="Dim.TLabel").pack(side="left")
        self._reg_mode_changed()
        self.view_reg.pack(side="top", fill="both", expand=True)
        return f

    def _reg_mode_changed(self):
        mode = self.reg_mode.get()
        self.lbl_hint.config(text=REG_HINTS[mode])
        if mode == "externa":
            self.fixed_box.pack(side="left", padx=(18, 0), after=self.btn_run_reg)
        else:
            self.fixed_box.pack_forget()

    def run_registration(self):
        s = self.s
        mode, fixed = self.reg_mode.get(), self.fixed_var.get()
        res = self.busy("Registrando imágenes… (puede tardar varios minutos)", self.backend.register,
                        s.t1_img, s.t1_md, s.t2_img, s.t2_md, mode, fixed)
        if res is _FAIL:
            return
        # Se parte siempre de los volúmenes originales: cada intento es independiente.
        s.t1_list, s.t2_list, _t1_reg, s.resampled, s.tipo = res
        self.done -= {1, 2, 3}
        s.tram = s.subtraction = None
        self.lbl_reg.config(text=f"Registración aplicada: {REG_NAMES.get(s.tipo, s.tipo)}")
        if mode == "externa" and fixed == "t2":
            titles = ["T1 (registrada)", "T2 (fija)"]
        else:
            titles = ["T1 (fija)", "T2 (registrada)"]
        self.view_reg.set_images([s.t1_list, s.t2_list], titles)
        self.btn_accept_reg.config(state="normal")
        self.btn_export_reg.config(state="normal")
        self._refresh_steps()

    def export_registration(self):
        self.busy("Exportando archivo de registración…", self.backend.export_registration)

    def accept_registration(self):
        s = self.s
        res = self.busy("Restando resonancias…", self._compute_subtraction)
        if res is _FAIL:
            return
        self.done.add(1)
        self.show_page(2)

    def _compute_subtraction(self):
        s = self.s
        s.subtraction = self.backend.subtract(s.t1_list, s.t2_list)
        s.clip, s.tram_prev = None, None
        s.tram = self.backend.make_tram(s.subtraction, None)
        self._tram_cache = {None: s.tram}
        self.m.tram = None  # la vista TRAM+MRS debe tomar el TRAM nuevo
        self._sub_arrays = [slice_to_array(x).astype(float) for x in s.subtraction]
        self._hist_data = np.concatenate([a[::2, ::2].ravel() for a in self._sub_arrays])
        lo, hi = float(self._hist_data.min()), float(self._hist_data.max())
        self._hist_bins = np.linspace(lo, hi if hi > lo else lo + 1.0, 161)  # mismo eje en todos los cortes

    # ---------------------------------------------------------------- 3
    def _page_tram(self):
        f = ttk.Frame(self.container)
        self._header(f, "TRAM y LUT",
                     "Revisá el histograma de la resta y, si hace falta, recortá los valores extremos para "
                     "mejorar la interpretación. Rojo = necrosis · Azul = tumor activo.")
        body = ttk.Frame(f)
        body.pack(fill="both", expand=True)
        right = ttk.Frame(body, style="Card.TFrame", width=330)
        right.pack(side="right", fill="y", padx=(16, 0))
        right.pack_propagate(False)
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        self.view_tram = SliceViewer(left)
        self.view_tram.pack(fill="both", expand=True)
        self.view_tram.on_change = lambda i: self._draw_hist()
        ttk.Label(right, text="Histograma de la resta", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        self.hist_scope = tk.StringVar(value="slice")
        hrow = ttk.Frame(right, style="Card.TFrame")
        hrow.pack(fill="x", padx=14)
        for val, txt in (("slice", "Corte actual"), ("volume", "Todo el volumen")):
            ttk.Radiobutton(hrow, text=txt, value=val, variable=self.hist_scope,
                            style="Card.TRadiobutton", command=self._draw_hist).pack(side="left", padx=(0, 12))
        self.hfig = Figure(figsize=(3.2, 2.4), dpi=100, facecolor=PANEL)
        self.hcanvas = FigureCanvasTkAgg(self.hfig, master=right)
        self.hcanvas.get_tk_widget().configure(bg=PANEL, highlightthickness=0)
        self.hcanvas.get_tk_widget().pack(fill="x", padx=8)

        ttk.Label(right, text="Recorte de valores", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(14, 2))
        ttk.Label(right, text="Intensidad máxima (ej. 300) o percentil de cola con % (ej. 5%).",
                  style="CardDim.TLabel", wraplength=290, justify="left").pack(anchor="w", padx=14)
        self.clip_var = tk.StringVar()
        e = ttk.Entry(right, textvariable=self.clip_var)
        e.pack(fill="x", padx=14, pady=8)
        e.bind("<Return>", lambda ev: self.apply_clip())
        row = ttk.Frame(right, style="Card.TFrame")
        row.pack(fill="x", padx=14)
        for c, (txt, cmd) in enumerate([("Aplicar", self.apply_clip), ("Deshacer", self.undo_clip),
                                        ("Quitar", self.reset_clip)]):
            ttk.Button(row, text=txt, command=cmd, padding=(4, 6)).grid(
                row=0, column=c, sticky="ew", padx=(0 if c == 0 else 4, 0))
            row.columnconfigure(c, weight=1, uniform="b")
        self.lbl_clip = ttk.Label(right, text="Sin recorte", style="CardDim.TLabel")
        self.lbl_clip.pack(anchor="w", padx=14, pady=10)

        tk.Frame(right, bg=PANEL).pack(fill="both", expand=True)
        self.btn_tram_mrs = ttk.Button(right, text="Ver con MRS", state="disabled", command=self.open_tram_mrs)
        self.btn_tram_mrs.pack(fill="x", padx=14)
        ttk.Button(right, text="Aceptar TRAM  →", style="Accent.TButton", command=self.accept_tram).pack(
            fill="x", padx=14, pady=14)
        return f

    def _enter_tram(self):
        s = self.s
        if s.tram is None and s.subtraction is None:
            return
        self._draw_hist()
        self.view_tram.set_images([s.t1_list, s.tram], ["RM temprana (T1)", "TRAM"])

    def _draw_hist(self):
        if self.s.subtraction is None or not hasattr(self, "_sub_arrays"):
            return
        per_slice = self.hist_scope.get() == "slice"
        idx = min(self.view_tram.idx, len(self._sub_arrays) - 1)
        data = self._sub_arrays[idx].ravel() if per_slice else self._hist_data
        title = f"Corte {idx + 1} / {len(self._sub_arrays)}" if per_slice else "Todo el volumen"
        self.hfig.clear()
        ax = self.hfig.add_subplot(111)
        ax.set_facecolor(VIEW_BG)
        ax.hist(data, bins=self._hist_bins, color=ACCENT, log=True)
        ax.set_xlim(self._hist_bins[0], self._hist_bins[-1])
        ax.set_title(title, color=FG_DIM, fontsize=8, pad=4)
        ax.tick_params(colors=FG_DIM, labelsize=7)
        for sp in ax.spines.values():
            sp.set_color(PANEL_HI)
        self.hfig.subplots_adjust(left=0.14, right=0.97, bottom=0.14, top=0.91)
        self.hcanvas.draw_idle()

    def _set_tram(self, clip):
        s = self.s
        new = self.backend.make_tram(s.subtraction, clip)
        s.tram_prev, s.tram, s.clip = (s.tram, s.clip), new, clip
        self.lbl_clip.config(text=f"Recorte actual: {clip}" if clip else "Sin recorte")
        idx = self.view_tram.idx
        self.view_tram.set_images([s.t1_list, s.tram], ["RM temprana (T1)", "TRAM"])
        self.view_tram.goto(idx)

    def apply_clip(self):
        txt = self.clip_var.get().strip().lower()
        if not txt:
            return
        try:
            float(txt[:-1] if txt.endswith("%") else txt)
        except ValueError:
            messagebox.showwarning("Recorte inválido", "Ingresá un número (ej. 300) o un porcentaje (ej. 5%).")
            return
        self.busy("Aplicando recorte…", self._set_tram, txt)

    def undo_clip(self):
        s = self.s
        if not s.tram_prev:
            return
        s.tram, s.clip = s.tram_prev
        s.tram_prev = None
        self.lbl_clip.config(text=f"Recorte actual: {s.clip}" if s.clip else "Sin recorte")
        idx = self.view_tram.idx
        self.view_tram.set_images([s.t1_list, s.tram], ["RM temprana (T1)", "TRAM"])
        self.view_tram.goto(idx)

    def reset_clip(self):
        self.clip_var.set("")
        self.busy("Quitando recorte…", self._set_tram, None)

    def accept_tram(self):
        self.done.add(2)
        self.show_page(3)

    # ---------------------------------------------------------------- 4
    def _page_export(self):
        f = ttk.Frame(self.container)
        self._header(f, "Exportar resultados",
                     "El TRAM PET-CT no se recorta: la LUT se puede ajustar luego dentro de ARIA.")
        self.view_exp = SliceViewer(f)
        foot = ttk.Frame(f)
        foot.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(foot, text="← Volver al TRAM", command=lambda: self.show_page(2)).pack(side="left")
        self.btn_exp_mrs = ttk.Button(foot, text="Ver con MRS", state="disabled", command=self.open_tram_mrs)
        self.btn_exp_mrs.pack(side="left", padx=8)
        ttk.Button(foot, text="Guardar TRAM PET-CT (DICOM)", style="Accent.TButton",
                   command=self.save_pet).pack(side="right")
        ttk.Button(foot, text="Guardar TRAM RGB (DICOM)", style="Accent.TButton",
                   command=self.save_rgb).pack(side="right", padx=8)
        self.view_exp.pack(side="top", fill="both", expand=True)
        return f

    def _enter_export(self):
        s = self.s
        if s.subtraction is None:
            return
        self.tram_pet = [sitk.Cast(x, sitk.sitkInt16) for x in s.subtraction]
        self.view_exp.set_images([s.tram, self.tram_pet], ["TRAM RGB", "TRAM adaptado a PET-CT"])

    def save_rgb(self):
        s = self.s
        self.busy("Guardando TRAM RGB…", self.backend.export_rgb, s.tram, s.t1_md, s.resampled, s.tipo)

    def save_pet(self):
        s = self.s
        self.busy("Guardando TRAM PET-CT…", self.backend.export_pet, self.tram_pet, s.t1_md, s.resampled, s.tipo)

    # ---------------------------------------------------------------- MRS
    def _page_mrs(self):
        f = ttk.Frame(self.container)
        self._header(f, "Espectroscopia (MRS)",
                     "Cargá las capturas de MRS, buscá el corte de la T1 que les corresponde y confirmalo. "
                     "El índice queda guardado para ver luego el mismo corte del TRAM junto a la MRS.")
        top = ttk.Frame(f)
        top.pack(fill="x", pady=(0, 8))
        ttk.Button(top, text="1 · Cargar capturas…", command=self.mrs_load).pack(side="left")
        self.lbl_mrs_caps = ttk.Label(top, text="Sin capturas", style="Dim.TLabel")
        self.lbl_mrs_caps.pack(side="left", padx=12)
        self.btn_mrs_find = ttk.Button(top, text="2 · Buscar corte en la T1", style="Accent.TButton",
                                       state="disabled", command=self.mrs_find)
        self.btn_mrs_find.pack(side="left")

        foot = ttk.Frame(f)
        foot.pack(side="bottom", fill="x", pady=(10, 0))
        self.btn_mrs_confirm = ttk.Button(foot, text="Confirmar corte", style="Accent.TButton",
                                          state="disabled", command=self.mrs_confirm)
        self.btn_mrs_confirm.pack(side="right")
        self.btn_mrs_reselect = ttk.Button(foot, text="Reelegir corte", state="disabled",
                                           command=self._mrs_start_selection)
        self.btn_mrs_reselect.pack(side="right", padx=8)
        self.lbl_mrs_status = ttk.Label(foot, text="", style="Ok.TLabel")
        self.lbl_mrs_status.pack(side="left")

        body = ttk.Frame(f)
        body.pack(side="top", fill="both", expand=True)
        card = ttk.Frame(body, style="Card.TFrame", width=330)
        card.pack(side="right", fill="y", padx=(16, 0))
        card.pack_propagate(False)
        self.view_mrs = SliceViewer(body)
        self.view_mrs.pack(side="left", fill="both", expand=True)
        self.view_mrs.on_change = self._mrs_on_change

        ttk.Label(card, text="Corte de la MRS", style="Card.TLabel",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=14, pady=(14, 4))
        self.lbl_mrs_info = ttk.Label(card, text="", style="CardDim.TLabel", wraplength=295, justify="left")
        self.lbl_mrs_info.pack(anchor="w", padx=14)

        # selector de imagen izquierda (T1 / TRAM) y controles del TRAM; se muestran solo al comparar
        self.mrs_base = tk.StringVar(value="t1")
        self.mrs_base_row = ttk.Frame(card, style="Card.TFrame")
        ttk.Label(self.mrs_base_row, text="Izquierda:", style="CardDim.TLabel").pack(side="left", padx=(0, 10))
        ttk.Radiobutton(self.mrs_base_row, text="T1", value="t1", variable=self.mrs_base,
                        style="Card.TRadiobutton", command=self._mrs_refresh_compare).pack(side="left", padx=(0, 10))
        self.rb_mrs_tram = ttk.Radiobutton(self.mrs_base_row, text="TRAM", value="tram", variable=self.mrs_base,
                                           style="Card.TRadiobutton", command=self._mrs_refresh_compare)
        self.rb_mrs_tram.pack(side="left")

        self.mrs_tram_box = ttk.Frame(card, style="Card.TFrame")
        ttk.Label(self.mrs_tram_box, text="Histograma del corte (resta)", style="Card.TLabel",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 2))
        self.mfig = Figure(figsize=(3.1, 1.6), dpi=100, facecolor=PANEL)
        self.mcanvas = FigureCanvasTkAgg(self.mfig, master=self.mrs_tram_box)
        self.mcanvas.get_tk_widget().configure(bg=PANEL, highlightthickness=0)
        self.mcanvas.get_tk_widget().pack(fill="x")
        ttk.Label(self.mrs_tram_box, text="Recorte: intensidad (ej. 300) o percentil (ej. 5%)",
                  style="CardDim.TLabel", wraplength=295, justify="left").pack(anchor="w", pady=(6, 2))
        row = ttk.Frame(self.mrs_tram_box, style="Card.TFrame")
        row.pack(fill="x")
        self.mrs_clip_var = tk.StringVar()
        e = ttk.Entry(row, textvariable=self.mrs_clip_var, width=10)
        e.pack(side="left", fill="x", expand=True)
        e.bind("<Return>", lambda ev: self.mrs_apply_clip())
        ttk.Button(row, text="Aplicar", padding=(8, 5), command=self.mrs_apply_clip).pack(side="left", padx=(6, 0))
        ttk.Button(row, text="Quitar", padding=(8, 5),
                   command=lambda: self.mrs_apply_clip(reset=True)).pack(side="left", padx=(4, 0))
        self.lbl_mrs_clip = ttk.Label(self.mrs_tram_box, text="Sin recorte", style="CardDim.TLabel")
        self.lbl_mrs_clip.pack(anchor="w", pady=(6, 0))
        ttk.Button(self.mrs_tram_box, text="Usar como TRAM final", command=self.mrs_adopt_clip).pack(fill="x", pady=(6, 0))
        self._mrs_set_idle_ui()
        return f

    # -- estado -------------------------------------------------------------
    def _reset_mrs(self):
        """Descarta capturas, índice y cortes de la T1 (al cargar una T1 nueva o empezar de cero)."""
        self.m = SimpleNamespace(captures=None, arrays=None, candidates=None, start=None, index=None,
                                 score=None, note="", mode="idle", tram=None, clip=None)
        if hasattr(self, "view_mrs"):
            self.mrs_base.set("t1")
            self.view_mrs.clear()
            self.lbl_mrs_caps.config(text="Sin capturas", style="Dim.TLabel")
            self.btn_mrs_find.config(state="disabled")
            self.lbl_mrs_status.config(text="")
            self._mrs_set_idle_ui()
        if hasattr(self, "btn_spectro"):
            self.btn_spectro.config(text=MRS_BTN_TEXT)
            self._refresh_mrs_buttons()

    def _mrs_set_idle_ui(self):
        self.m.mode = "idle"
        self.btn_mrs_confirm.config(state="disabled")
        self.btn_mrs_reselect.config(state="disabled")
        self.mrs_base_row.pack_forget()
        self.mrs_tram_box.pack_forget()
        self.lbl_mrs_info.config(text="Cargá las capturas y buscá el corte para empezar.")

    def _mrs_module(self):
        try:
            import espectroscopia
            return espectroscopia
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            messagebox.showerror(
                "Espectroscopia",
                "No se pudo cargar espectroscopia.py. Verificá que esté en la carpeta del proyecto y "
                f"que OpenCV esté instalado (pip install opencv-python).\n\n{type(e).__name__}: {e}")
            return None

    @staticmethod
    def _rgb(captura):
        """Las capturas vienen de cv2.imread (BGR): se pasan a RGB para mostrarlas."""
        c = np.asarray(captura)
        return np.ascontiguousarray(c[..., ::-1]) if c.ndim == 3 else c

    def _tram_ready(self):
        s, m = self.s, self.m
        return (s.tram is not None and s.subtraction is not None and m.index is not None
                and m.index < len(s.tram))

    def _refresh_mrs_buttons(self):
        st = "normal" if (self.m.index is not None and self.s.tram is not None) else "disabled"
        for b in (getattr(self, "btn_tram_mrs", None), getattr(self, "btn_exp_mrs", None)):
            if b is not None:
                b.config(state=st)

    # -- flujo --------------------------------------------------------------
    def open_mrs(self):
        if not self.s.t1_slices:
            messagebox.showinfo("Espectroscopia", "Primero cargá la resonancia T1 (paso 1).")
            return
        self.show_page(4)

    def open_tram_mrs(self):
        if self.m.index is None or self.s.tram is None:
            return
        self.mrs_base.set("tram")
        self.show_page(4)

    def _enter_mrs(self):
        if self.m.mode == "compare":
            self._mrs_refresh_compare()

    def mrs_load(self):
        mrs = self._mrs_module()
        if mrs is None:
            return
        caps = self.busy("Cargando capturas de MRS…", mrs.cargar_capturas_mrs)
        if caps is _FAIL or not caps:
            return
        self._reset_mrs()
        self.m.captures = caps
        self.lbl_mrs_caps.config(text=f"{len(caps)} captura(s)", style="Ok.TLabel")
        self.btn_mrs_find.config(state="normal")
        self.view_mrs.unit = "Captura"
        self.view_mrs.set_images([[self._rgb(c) for c in caps]], ["Capturas de MRS"])

    def mrs_find(self):
        mrs = self._mrs_module()
        if mrs is None or not self.m.captures:
            return
        m = self.m
        if m.arrays is None:
            arr = self.busy("Preparando los cortes de la T1…", self.backend.to_arrays, self.s.t1_img)
            if arr is _FAIL:
                return
            m.arrays = arr
        res = self.busy("Buscando el corte de la T1 que coincide con la MRS…",
                        mrs.buscar_corte_t1, m.arrays, m.captures[0])
        if res is _FAIL:
            return
        idx, score = res
        n = len(m.arrays)
        m.score = score
        if idx is not None:
            m.candidates = mrs.generar_candidatos_t1(idx, n, 7)
            m.start = idx
            m.note = (f"Corte sugerido: {idx + 1} (correlación {score:.2f}). Revisá los candidatos con ◀ ▶ "
                      "y confirmá el que corresponda.")
        else:
            m.candidates = list(range(n))
            m.start = n // 2
            m.note = (f"No hay una coincidencia suficiente con la T1 (mejor correlación {score:.2f}). "
                      "Planificación sobre otra secuencia (p. ej. T2-FLAIR): elegí el corte manualmente.")
        m.index = None
        self._mrs_start_selection()

    def _mrs_start_selection(self):
        m = self.m
        if m.arrays is None or not m.candidates:
            return
        start = m.index if m.index in m.candidates else m.start
        m.mode = "select"
        cap = self._rgb(m.captures[0])
        self.view_mrs.unit = "Candidato"
        self.view_mrs.set_images([[m.arrays[i] for i in m.candidates], [cap] * len(m.candidates)],
                                 ["T1 — corte candidato", "MRS — captura de referencia"])
        self.view_mrs.goto(m.candidates.index(start))
        self._mrs_mode_ui()

    def mrs_confirm(self):
        m = self.m
        if m.mode != "select":
            return
        m.index = m.candidates[self.view_mrs.idx]
        self.lbl_mrs_status.config(text=f"✓ Corte {m.index + 1} confirmado")
        self.btn_spectro.config(text=f"✓  Espectroscopia — corte {m.index + 1}")
        self.status.set(f"Espectroscopia: corte {m.index + 1} de la T1 guardado")
        self._refresh_mrs_buttons()
        m.mode = "compare"
        self._mrs_refresh_compare()

    # -- comparación (T1 o TRAM, fijo, junto a las capturas) ----------------
    def _mrs_refresh_compare(self, keep=False):
        s, m = self.s, self.m
        if m.index is None:
            return
        use_tram = self.mrs_base.get() == "tram" and self._tram_ready()
        if use_tram:
            if m.tram is None:  # primera vez: parte del TRAM vigente
                m.tram, m.clip = s.tram, s.clip
                self.mrs_clip_var.set(s.clip or "")
                self.lbl_mrs_clip.config(text=f"Recorte en esta vista: {m.clip}" if m.clip else "Sin recorte")
            base, title = m.tram[m.index], f"TRAM — corte {m.index + 1}"
        else:
            base, title = m.arrays[m.index], f"T1 — corte {m.index + 1}"
        caps = [self._rgb(c) for c in m.captures]
        idx = self.view_mrs.idx if keep else 0
        m.mode = "compare"
        self.view_mrs.unit = "Captura"
        self.view_mrs.set_images([[base] * len(caps), caps], [title, "MRS — capturas"])
        self.view_mrs.goto(idx)
        self._mrs_mode_ui()
        if use_tram:
            self._mrs_draw_hist()

    def _mrs_mode_ui(self):
        m = self.m
        self.mrs_base_row.pack_forget()
        self.mrs_tram_box.pack_forget()
        self.btn_mrs_confirm.config(state="normal" if m.mode == "select" else "disabled")
        self.btn_mrs_reselect.config(state="normal" if (m.mode == "compare" and m.candidates) else "disabled")
        if m.mode == "compare":
            ready = self._tram_ready()
            self.rb_mrs_tram.config(state="normal" if ready else "disabled")
            if not ready:
                self.mrs_base.set("t1")
            self.mrs_base_row.pack(fill="x", padx=14, pady=(14, 0))
            if self.mrs_base.get() == "tram":
                self.mrs_tram_box.pack(fill="x", padx=14, pady=(10, 0))
        self._mrs_on_change(self.view_mrs.idx)

    def _mrs_on_change(self, idx):
        m = self.m
        n = len(m.arrays) if m.arrays else 0
        if m.mode == "select":
            self.lbl_mrs_info.config(
                text=f"Candidato {idx + 1} de {len(m.candidates)}  ·  corte {m.candidates[idx] + 1} de {n}\n\n{m.note}")
        elif m.mode == "compare":
            extra = "\nTRAM en el mismo índice que la T1." if self.mrs_base.get() == "tram" else ""
            self.lbl_mrs_info.config(
                text=f"Corte confirmado: {m.index + 1} de {n}\nCaptura {idx + 1} de {len(m.captures)}{extra}")

    # -- histograma y recorte del TRAM en esta vista --------------------------
    def _mrs_draw_hist(self):
        m = self.m
        if self.s.subtraction is None or not hasattr(self, "_sub_arrays") or m.index is None \
                or m.index >= len(self._sub_arrays):
            return
        self.mfig.clear()
        ax = self.mfig.add_subplot(111)
        ax.set_facecolor(VIEW_BG)
        ax.hist(self._sub_arrays[m.index].ravel(), bins=self._hist_bins, color=ACCENT, log=True)
        ax.set_xlim(self._hist_bins[0], self._hist_bins[-1])
        ax.set_title(f"Corte {m.index + 1}", color=FG_DIM, fontsize=8, pad=3)
        ax.tick_params(colors=FG_DIM, labelsize=7)
        for sp in ax.spines.values():
            sp.set_color(PANEL_HI)
        self.mfig.subplots_adjust(left=0.14, right=0.97, bottom=0.16, top=0.88)
        self.mcanvas.draw_idle()

    def mrs_apply_clip(self, reset=False):
        txt = None
        if reset:
            self.mrs_clip_var.set("")
        else:
            txt = self.mrs_clip_var.get().strip().lower()
            if not txt:
                return
            try:
                float(txt[:-1] if txt.endswith("%") else txt)
            except ValueError:
                messagebox.showwarning("Recorte inválido", "Ingresá un número (ej. 300) o un porcentaje (ej. 5%).")
                return
        self.busy("Aplicando recorte…", self._mrs_set_clip, txt)

    def _mrs_set_clip(self, clip):
        if clip not in self._tram_cache:
            self._tram_cache[clip] = self.backend.make_tram(self.s.subtraction, clip)
        self.m.tram, self.m.clip = self._tram_cache[clip], clip
        self.lbl_mrs_clip.config(text=f"Recorte en esta vista: {clip}" if clip else "Sin recorte")
        self._mrs_refresh_compare(keep=True)

    def mrs_adopt_clip(self):
        """El recorte de esta vista es exploratorio; con este botón pasa a ser el TRAM que se exporta."""
        s, m = self.s, self.m
        if m.tram is None:
            return
        s.tram, s.clip, s.tram_prev = m.tram, m.clip, None
        self.lbl_clip.config(text=f"Recorte actual: {m.clip}" if m.clip else "Sin recorte")
        self.status.set("El TRAM de esta vista se usará para exportar")


# --------------------------------------------------------------------------
def main():
    demo = "--demo" in sys.argv
    if demo:
        backend = DemoBackend()
    else:
        # Los módulos de NERV pueden crear ventanas Tk al importarse: se prepara una raíz oculta primero.
        probe = tk.Tk()
        probe.withdraw()
        try:
            backend = RealBackend()
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            use_demo = messagebox.askyesno(
                "No se pudieron cargar los módulos de NERV",
                f"{type(e).__name__}: {e}\n\n¿Querés abrir la interfaz en modo demo (datos sintéticos)?")
            probe.destroy()
            if not use_demo:
                return
            backend = DemoBackend()
        else:
            probe.destroy()
    NervApp(backend).mainloop()


if __name__ == "__main__":
    main()