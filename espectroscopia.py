"""Funciones para relacionar capturas de MRS con cortes de una T1 3D."""

import tkinter as tk
from tkinter import filedialog

import cv2
import numpy as np

def cargar_capturas_mrs():
    """Permite seleccionar varias capturas MRS y las devuelve en una lista."""
    root = tk.Tk()
    root.withdraw()
    rutas = filedialog.askopenfilenames(
        title="Seleccionar capturas de espectroscopia",
        filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.bmp"), ("Todos", "*.*")],
    )
    root.destroy()

    capturas = []
    for ruta in rutas:
        imagen = cv2.imread(ruta, cv2.IMREAD_COLOR)
        if imagen is None:
            raise ValueError(f"No se pudo abrir la imagen: {ruta}")
        capturas.append(imagen)

    return capturas

def _gris_uint8(imagen):
    """Convierte una imagen 2D/3D a escala de grises de 8 bits."""
    imagen = np.asarray(imagen)
    if imagen.ndim == 3:
        if imagen.shape[2] == 3:
            imagen = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
        elif imagen.shape[2] == 4:
            imagen = cv2.cvtColor(imagen, cv2.COLOR_BGRA2GRAY)
        else:
            raise ValueError("La imagen debe tener 1, 3 o 4 canales.")
    elif imagen.ndim != 2:
        raise ValueError("Cada corte o captura debe ser una imagen 2D o en color.")

    imagen = np.nan_to_num(imagen.astype(np.float32))
    pixeles = imagen[imagen != 0]
    if pixeles.size < 10:
        pixeles = imagen.ravel()
    if pixeles.size == 0:
        raise ValueError("La imagen no contiene píxeles válidos.")

    p1, p99 = np.percentile(pixeles, [1, 99])
    if p99 <= p1:
        p1, p99 = float(pixeles.min()), float(pixeles.max())
    if p99 <= p1:
        return np.zeros(imagen.shape, dtype=np.uint8)
    imagen = np.clip((imagen - p1) / (p99 - p1), 0, 1)
    return (imagen * 255).astype(np.uint8)


def _coincidencia(fuente, plantilla, escalas):
    """Busca plantilla dentro de fuente para varias escalas.

    Las dos imágenes deben ser matrices float32 en escala de grises.
    Devuelve (mejor_puntaje, mejor_escala, mejor_posicion).
    """
    alto, ancho = fuente.shape
    alto_t, ancho_t = plantilla.shape
    mejor_puntaje = -1.0
    mejor_escala = None
    mejor_posicion = None

    for escala in escalas:
        nuevo_ancho = int(round(ancho_t * escala))
        nuevo_alto = int(round(alto_t * escala))
        if nuevo_ancho < 20 or nuevo_alto < 20:
            continue
        if nuevo_ancho > ancho or nuevo_alto > alto:
            continue

        interpolacion = cv2.INTER_AREA if escala < 1 else cv2.INTER_CUBIC
        plantilla_escalada = cv2.resize(
            plantilla, (nuevo_ancho, nuevo_alto), interpolation=interpolacion
        )
        resultado = cv2.matchTemplate(
            fuente, plantilla_escalada, cv2.TM_CCOEFF_NORMED
        )
        _, puntaje, _, posicion = cv2.minMaxLoc(resultado)

        if np.isfinite(puntaje) and puntaje > mejor_puntaje:
            mejor_puntaje = float(puntaje)
            mejor_escala = float(escala)
            mejor_posicion = posicion

    return mejor_puntaje, mejor_escala, mejor_posicion

def _preparar_captura_mrs(captura_mrs):
    """Extrae automáticamente el panel anatómico y reduce overlays de la MRS.

    No solicita ROI manual. Detecta el componente de mayor tamaño de la imagen,
    elimina píxeles coloreados (texto/espectro) y líneas rectas brillantes
    (marco de la cuadrícula) mediante inpainting.
    """
    imagen = np.asarray(captura_mrs)

    if imagen.ndim == 2:
        gris = imagen
        imagen_color = cv2.cvtColor(_gris_uint8(imagen), cv2.COLOR_GRAY2BGR)
    elif imagen.ndim == 3 and imagen.shape[2] == 3:
        imagen_color = imagen
        gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    elif imagen.ndim == 3 and imagen.shape[2] == 4:
        imagen_color = cv2.cvtColor(imagen, cv2.COLOR_BGRA2BGR)
        gris = cv2.cvtColor(imagen_color, cv2.COLOR_BGR2GRAY)
    else:
        raise ValueError("La captura MRS debe ser una imagen 2D, BGR o BGRA.")

    gris = _gris_uint8(gris)
    alto_total, ancho_total = gris.shape

    # Detectar el área principal de la imagen anatómica, descartando en lo
    # posible los paneles negros y textos externos de la interfaz.
    _, binaria = cv2.threshold(gris, 12, 255, cv2.THRESH_BINARY)
    cantidad, etiquetas, estadisticas, _ = cv2.connectedComponentsWithStats(
        binaria, connectivity=8
    )

    x, y, ancho, alto = 0, 0, ancho_total, alto_total
    if cantidad > 1:
        areas = estadisticas[1:, cv2.CC_STAT_AREA]
        componente = 1 + int(np.argmax(areas))
        area = int(estadisticas[componente, cv2.CC_STAT_AREA])
        bx = int(estadisticas[componente, cv2.CC_STAT_LEFT])
        by = int(estadisticas[componente, cv2.CC_STAT_TOP])
        bw = int(estadisticas[componente, cv2.CC_STAT_WIDTH])
        bh = int(estadisticas[componente, cv2.CC_STAT_HEIGHT])

        # Aceptar el recorte solo si el componente parece corresponder al panel
        # anatómico y no a un texto u objeto pequeño.
        if area > 0.10 * gris.size and bw > 0.35 * ancho_total and bh > 0.35 * alto_total:
            margen = max(2, int(round(0.01 * min(bw, bh))))
            x = max(0, bx - margen)
            y = max(0, by - margen)
            x2 = min(ancho_total, bx + bw + margen)
            y2 = min(alto_total, by + bh + margen)
            ancho, alto = x2 - x, y2 - y

    panel_color = imagen_color[y:y + alto, x:x + ancho].copy()
    panel_gris = gris[y:y + alto, x:x + ancho].copy()
    alto, ancho = panel_gris.shape

    # 1) Detectar texto/elementos de colores (por ejemplo, espectro verde y
    # parámetros amarillos). La anatomía de la captura es esencialmente gris.
    hsv = cv2.cvtColor(panel_color, cv2.COLOR_BGR2HSV)
    mascara_color = np.uint8(
        (hsv[:, :, 1] > 55) & (hsv[:, :, 2] > 45)
    ) * 255

    # 2) Detectar líneas horizontales y verticales largas, como el rectángulo
    # blanco que delimita la región multivoxel. Se restringe la búsqueda a la
    # zona interior para evitar eliminar el contorno del cráneo.
    brillante = np.uint8(panel_gris >= 220) * 255
    largo_h = max(20, int(round(ancho * 0.20)))
    largo_v = max(20, int(round(alto * 0.20)))
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (largo_h, 1))
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, largo_v))
    lineas_h = cv2.morphologyEx(brillante, cv2.MORPH_OPEN, kernel_h)
    lineas_v = cv2.morphologyEx(brillante, cv2.MORPH_OPEN, kernel_v)
    mascara_lineas = cv2.bitwise_or(lineas_h, lineas_v)

    zona_interior = np.zeros_like(mascara_lineas)
    y0, y1 = int(0.06 * alto), int(0.94 * alto)
    x0, x1 = int(0.06 * ancho), int(0.94 * ancho)
    zona_interior[y0:y1, x0:x1] = 255
    mascara_lineas = cv2.bitwise_and(mascara_lineas, zona_interior)
    mascara_lineas = cv2.dilate(
        mascara_lineas, np.ones((3, 3), dtype=np.uint8), iterations=1
    )

    mascara = cv2.bitwise_or(mascara_color, mascara_lineas)

    # Evitar aplicar inpainting si la máscara accidentalmente cubre demasiada
    # anatomía; en ese caso se eliminan solo los elementos coloreados.
    if np.count_nonzero(mascara) > 0.25 * mascara.size:
        mascara = mascara_color

    if np.count_nonzero(mascara) > 0:
        panel_gris = cv2.inpaint(panel_gris, mascara, 3, cv2.INPAINT_TELEA)

    return panel_gris


def _coincidencia_cerca_de_posicion(fuente, plantilla, escalas, centro, radio=10):
    """Refina la correlación en una ventana alrededor de una posición común."""
    alto, ancho = fuente.shape
    alto_t, ancho_t = plantilla.shape
    cx, cy = centro
    mejor = (-1.0, None, None)

    for escala in escalas:
        nuevo_ancho = int(round(ancho_t * escala))
        nuevo_alto = int(round(alto_t * escala))
        if nuevo_ancho < 20 or nuevo_alto < 20:
            continue
        if nuevo_ancho > ancho or nuevo_alto > alto:
            continue

        interpolacion = cv2.INTER_AREA if escala < 1 else cv2.INTER_CUBIC
        plantilla_escalada = cv2.resize(
            plantilla, (nuevo_ancho, nuevo_alto), interpolation=interpolacion
        )

        x0 = max(0, int(round(cx)) - radio)
        y0 = max(0, int(round(cy)) - radio)
        x1 = min(ancho, int(round(cx)) + radio + nuevo_ancho + 1)
        y1 = min(alto, int(round(cy)) + radio + nuevo_alto + 1)
        region = fuente[y0:y1, x0:x1]

        if region.shape[0] < nuevo_alto or region.shape[1] < nuevo_ancho:
            continue

        resultado = cv2.matchTemplate(
            region, plantilla_escalada, cv2.TM_CCOEFF_NORMED
        )
        _, valor, _, posicion_local = cv2.minMaxLoc(resultado)

        if np.isfinite(valor) and valor > mejor[0]:
            posicion_global = (x0 + posicion_local[0], y0 + posicion_local[1])
            mejor = (float(valor), float(escala), posicion_global)

    return mejor

def buscar_corte_t1(cortes_t1, captura_mrs, top_k=15, factor_reduccion=0.30):
    """Busca el corte T1 más parecido a la anatomía de una captura MRS.

    No requiere selección manual de ROI. La captura MRS se recorta y se limpian
    automáticamente algunos elementos gráficos. La primera etapa preselecciona
    cortes; la segunda los compara a resolución completa usando una escala y
    posición inicial comunes para reducir variaciones entre ejecuciones.

    Devuelve (indice_mejor_corte, correlacion_final).
    """
    if len(cortes_t1) == 0:
        raise ValueError("El vector de cortes T1 está vacío.")
    if not 0 < factor_reduccion <= 1:
        raise ValueError("factor_reduccion debe estar entre 0 y 1.")
    if top_k < 1:
        raise ValueError("top_k debe ser mayor o igual a 1.")

    # Captura MRS preparada automáticamente; no hay cv2.selectROI().
    plantilla_u8 = _preparar_captura_mrs(captura_mrs)
    plantilla = plantilla_u8.astype(np.float32) / 255.0
    alto_t, ancho_t = plantilla.shape

    # La geometría de los cortes debe ser consistente dentro del volumen.
    primer_corte = _gris_uint8(cortes_t1[0])
    alto, ancho = primer_corte.shape
    escala_max = min(ancho / ancho_t, alto / alto_t)
    if escala_max <= 0:
        raise ValueError("No se pudo determinar una escala válida de comparación.")

    # -------------------- ETAPA 1: PRESELECCIÓN RÁPIDA --------------------
    plantilla_reducida = cv2.resize(
        plantilla, None, fx=factor_reduccion, fy=factor_reduccion,
        interpolation=cv2.INTER_AREA
    )
    plantilla_reducida = cv2.GaussianBlur(plantilla_reducida, (5, 5), 0)

    escalas_gruesas = np.linspace(escala_max * 0.55, escala_max, 12)
    resultados_iniciales = []

    for indice, corte in enumerate(cortes_t1):
        fuente_u8 = _gris_uint8(corte)
        if fuente_u8.shape != (alto, ancho):
            raise ValueError("Todos los cortes T1 deben tener las mismas dimensiones.")

        fuente = fuente_u8.astype(np.float32) / 255.0
        fuente_reducida = cv2.resize(
            fuente, None, fx=factor_reduccion, fy=factor_reduccion,
            interpolation=cv2.INTER_AREA
        )
        fuente_reducida = cv2.GaussianBlur(fuente_reducida, (5, 5), 0)

        puntaje, escala, posicion = _coincidencia(
            fuente_reducida, plantilla_reducida, escalas_gruesas
        )
        if escala is not None and posicion is not None:
            # Convertir la posición de la imagen reducida a píxeles originales.
            posicion_original = (
                posicion[0] / factor_reduccion,
                posicion[1] / factor_reduccion
            )
            resultados_iniciales.append(
                (puntaje, indice, escala, posicion_original)
            )

    if not resultados_iniciales:
        raise ValueError("No se pudo comparar la captura MRS con los cortes T1.")

    resultados_iniciales.sort(key=lambda r: r[0], reverse=True)
    candidatos = resultados_iniciales[:min(top_k, len(resultados_iniciales))]

    print("\n--- Preselección rápida ---")
    for puntaje, indice, escala, posicion in candidatos:
        print(
            f"Corte {indice}: correlación inicial = {puntaje:.4f}, "
            f"escala = {escala:.4f}, posición = ({posicion[0]:.1f}, {posicion[1]:.1f})"
        )
     # Estimar una única transformación inicial a partir de los candidatos.
    escala_comun = float(np.median([r[2] for r in candidatos]))
    centro_comun = (
        float(np.median([r[3][0] for r in candidatos])),
        float(np.median([r[3][1] for r in candidatos]))
    )

    # -------------------- ETAPA 2: REFINAMIENTO --------------------
    # Todos los candidatos se comparan en la misma ventana espacial y con un
    # rango estrecho de escalas alrededor de la estimación común.
    escala_min = max(0.01, escala_comun * 0.97)
    escala_max_fina = min(escala_max, escala_comun * 1.03)
    escalas_finas = np.linspace(escala_min, escala_max_fina, 13)

    resultados_finales = []
    for puntaje_inicial, indice, _, _ in candidatos:
        fuente = _gris_uint8(cortes_t1[indice]).astype(np.float32) / 255.0
        puntaje, escala, posicion = _coincidencia_cerca_de_posicion(
            fuente, plantilla, escalas_finas, centro_comun, radio=10
        )
        if escala is not None:
            resultados_finales.append(
                (puntaje, indice, escala, posicion, puntaje_inicial)
            )

    if not resultados_finales:
        raise ValueError("No se pudo refinar la coincidencia de los cortes candidatos.")

    resultados_finales.sort(key=lambda r: r[0], reverse=True)
    print("\n--- Resultados después del refinamiento ---")
    for puntaje, indice, escala, posicion, inicial in resultados_finales:
        print(
            f"Corte {indice}: correlación final = {puntaje:.4f} "
            f"(inicial = {inicial:.4f}), escala = {escala:.4f}, "
            f"posición = {posicion}"
        )

    mejor_puntaje, mejor_indice, mejor_escala, mejor_posicion, _ = resultados_finales[0]
    print(
        f"\nMejor corte: {mejor_indice} | correlación final: {mejor_puntaje:.4f} | "
        f"escala: {mejor_escala:.4f} | posición: {mejor_posicion}"
    )

    return mejor_indice, mejor_puntaje

def generar_candidatos_t1(indice_detectado, total_cortes, cantidad=7):
    """Genera índices candidatos alrededor del índice automático.

    Por defecto devuelve siete índices (índice detectado +/- 3). Si el índice
    está cerca de un extremo, desplaza la ventana para conservar siete cortes
    válidos. Si el volumen tiene menos de siete cortes, devuelve todos.
    """
    if total_cortes <= 0:
        raise ValueError("El volumen T1 no contiene cortes.")
    if not 0 <= indice_detectado < total_cortes:
        raise ValueError("El índice detectado está fuera del volumen T1.")
    if cantidad < 1:
        raise ValueError("La cantidad de candidatos debe ser mayor que cero.")

    cantidad_real = min(cantidad, total_cortes)
    mitad = cantidad_real // 2
    inicio = indice_detectado - mitad
    inicio = max(0, min(inicio, total_cortes - cantidad_real))
    return list(range(inicio, inicio + cantidad_real))

def seleccionar_corte_t1(cortes_t1, captura_mrs, indices_candidatos,
                          indice_inicial=None):
    """Permite revisar secuencialmente cortes T1 y confirmar uno.

    Muestra solamente dos imágenes: el corte T1 seleccionado a la izquierda,
    que puede cambiarse entre los índices candidatos, y la captura MRS fija a
    la derecha. El usuario navega con las flechas izquierda/derecha o A/D y
    confirma el índice con ENTER.

    Devuelve el índice definitivo dentro de cortes_t1. Devuelve None si se
    cancela con Q o ESC.
    """
    if len(cortes_t1) == 0:
        raise ValueError("El vector de cortes T1 está vacío.")
    if captura_mrs is None:
        raise ValueError("No se recibió una captura MRS.")

    indices = list(indices_candidatos)
    if not indices:
        raise ValueError("No se recibieron índices candidatos.")
    if len(set(indices)) != len(indices):
        raise ValueError("Los índices candidatos no deben estar repetidos.")
    if any(not isinstance(i, (int, np.integer)) or i < 0 or i >= len(cortes_t1)
           for i in indices):
        raise ValueError("Uno o más índices candidatos están fuera del volumen.")

    # Dimensiones de los dos paneles. La captura MRS permanece fija.
    ancho_panel, alto_panel = 550, 550
    alto_titulo = 55
    margen = 12

    panel_mrs = _ajustar_a_panel(captura_mrs, ancho_panel, alto_panel)
    if indice_inicial in indices:
        posicion_actual = indices.index(indice_inicial)
    else:
        posicion_actual = 0

    nombre_ventana = "Seleccion manual del corte T1. Presione ENTER para guardar ese corte"

    try:
        while True:
            indice_actual = indices[posicion_actual]
            panel_t1 = _ajustar_a_panel(
                cortes_t1[indice_actual], ancho_panel, alto_panel
            )

            ventana = np.zeros(
                (alto_panel + alto_titulo, ancho_panel * 2, 3),
                dtype=np.uint8
            )
            ventana[alto_titulo:, :ancho_panel] = panel_t1
            ventana[alto_titulo:, ancho_panel:] = panel_mrs

            titulo_t1 = (
                f"T1 - candidato {posicion_actual + 1}/{len(indices)} "
                f"(corte {indice_actual})"
            )
            titulo_mrs = "MRS - captura de referencia"
            cv2.putText(
                ventana, titulo_t1, (margen, 35), cv2.FONT_HERSHEY_SIMPLEX,
                0.65, (255, 255, 255), 2, cv2.LINE_AA
            )
            cv2.putText(
                ventana, titulo_mrs, (ancho_panel + margen, 35),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2,
                cv2.LINE_AA
            )

            cv2.imshow(nombre_ventana, ventana)
            tecla = cv2.waitKeyEx(0)
            tecla_ascii = tecla & 0xFF

            # Flechas de navegación en OpenCV/Windows y códigos habituales
            # de otros sistemas. A/D quedan como alternativa sencilla.
            teclas_izquierda = {2424832, 65361, 81}
            teclas_derecha = {2555904, 65363, 83}

            if tecla_ascii in (ord("a"), ord("A")) or tecla in teclas_izquierda:
                posicion_actual = (posicion_actual - 1) % len(indices)
            elif tecla_ascii in (ord("d"), ord("D")) or tecla in teclas_derecha:
                posicion_actual = (posicion_actual + 1) % len(indices)
            elif tecla_ascii in (13, 10):  # ENTER
                indice_final = int(indices[posicion_actual])
                print(f"Corte T1 confirmado por el usuario: {indice_final}")
                return indice_final
            elif tecla_ascii in (ord("q"), ord("Q"), 27):  # Q o ESC
                print("Selección manual cancelada.")
                return None
    finally:
        cv2.destroyWindow(nombre_ventana)


def _imagen_panel(imagen):
    """Prepara una imagen para mostrar sin truncar intensidades al convertir a uint8."""
    imagen = np.asarray(imagen)
    if imagen.ndim == 2:
        return cv2.cvtColor(_gris_uint8(imagen), cv2.COLOR_GRAY2BGR)
    if imagen.ndim == 3 and imagen.shape[2] == 4:
        imagen = cv2.cvtColor(imagen, cv2.COLOR_BGRA2BGR)
    if imagen.ndim == 3 and imagen.shape[2] == 3:
        if imagen.dtype == np.uint8:
            return imagen.copy()
        return np.clip(imagen, 0, 255).astype(np.uint8)
    raise ValueError("Formato de imagen no válido para visualización.")


def _ajustar_a_panel(imagen, ancho, alto):
    imagen = _imagen_panel(imagen)
    h, w = imagen.shape[:2]
    escala = min(ancho / w, alto / h)
    nw, nh = max(1, int(w * escala)), max(1, int(h * escala))
    interp = cv2.INTER_AREA if escala < 1 else cv2.INTER_LINEAR
    imagen = cv2.resize(imagen, (nw, nh), interpolation=interp)
    panel = np.zeros((alto, ancho, 3), dtype=np.uint8)
    x, y = (ancho - nw) // 2, (alto - nh) // 2
    panel[y:y+nh, x:x+nw] = imagen
    return panel

def mostrar_comparacion(corte_t1, capturas_mrs, indice_corte=None):
    """Muestra el corte T1 fijo a la izquierda y cambia las capturas MRS a la derecha.

    Teclas: A = captura anterior, D = captura siguiente, Q = salir.
    """
    if len(capturas_mrs) == 0:
        raise ValueError("No hay capturas MRS para mostrar.")

    ancho_panel = 550
    alto_panel = 550
    indice_mrs = 0
    panel_t1 = _ajustar_a_panel(corte_t1, ancho_panel, alto_panel)

    while True:
        panel_mrs = _ajustar_a_panel(
            capturas_mrs[indice_mrs], ancho_panel, alto_panel
        )
        ventana = np.zeros((alto_panel + 55, ancho_panel * 2, 3), dtype=np.uint8)
        ventana[55:, :ancho_panel] = panel_t1
        ventana[55:, ancho_panel:] = panel_mrs

        titulo_t1 = "T1 - corte encontrado"
        if indice_corte is not None:
            titulo_t1 += f" ({indice_corte})"
        titulo_mrs = f"MRS - captura {indice_mrs + 1}/{len(capturas_mrs)}"

        cv2.putText(ventana, titulo_t1, (15, 35), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (255, 255, 255), 2)
        cv2.putText(ventana, titulo_mrs, (ancho_panel + 15, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow("Correspondencia T1 - MRS | A: anterior  D: siguiente  Q: salir", ventana)

        tecla = cv2.waitKey(0) & 0xFF
        if tecla == ord("d"):
            indice_mrs = (indice_mrs + 1) % len(capturas_mrs)
        elif tecla == ord("a"):
            indice_mrs = (indice_mrs - 1) % len(capturas_mrs)
        elif tecla == ord("q") or tecla == 27:
            break

    cv2.destroyAllWindows()

# Ejemplo de uso desde el programa principal:
#
# capturas_mrs = cargar_capturas_mrs()
# indice, correlacion = buscar_corte_t1(cortes_t1, capturas_mrs[0])
# mostrar_comparacion(cortes_t1[indice], capturas_mrs, indice)    