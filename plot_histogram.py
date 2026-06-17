__author__ = 'Alejo Chacon'
# Graficador de histograma

import SimpleITK as sitk
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import TextBox
import matplotlib.colorbar as cbar

class ImageHistogramNavigator:
    def __init__(self, image_list):
        self.image_list = image_list
        self.total_images = len(image_list)
        self.current_index = 0
        
        # Precalcular histogramas sin restricciones de rango
        self.histograms = [np.histogram(sitk.GetArrayFromImage(img).flatten(), bins=256) for img in image_list]

        # Crear figura y ejes para imagen y histograma
        self.fig, (self.ax_img, self.ax_hist) = plt.subplots(1, 2, figsize=(12, 6))
        plt.subplots_adjust(bottom=0.2)  # Espacio para el cuadro de texto

        # Conectar eventos de teclado
        self.cid_key = self.fig.canvas.mpl_connect('key_press_event', self.on_key)

        # Crear cuadro de entrada de texto para los índices
        self.axbox = plt.axes([0.25, 0.05, 0.5, 0.05])  # Posición del cuadro de texto
        self.text_box = TextBox(self.axbox, 'Ir a la imagen (índice): ')
        self.text_box.on_submit(self.submit_index)

        self.update_display()

    def update_display(self):
        self.update_image()
        self.update_histogram()

    def update_image(self):
        self.ax_img.clear()
        image_array = sitk.GetArrayFromImage(self.image_list[self.current_index])
        self.ax_img.imshow(image_array, cmap='gray')
        self.ax_img.set_title(f'Imagen {self.current_index + 1}/{self.total_images}')
        self.ax_img.axis('off')  # Opcional: desactiva los ejes para una visualización más limpia

    def update_histogram(self):
        self.ax_hist.clear()
        hist, bin_edges = self.histograms[self.current_index]
        self.ax_hist.bar(bin_edges[:-1], hist, width=bin_edges[1] - bin_edges[0], color='blue', alpha=0.7)
        self.ax_hist.set_title('Histograma')
        self.ax_hist.set_xlabel('Intensidad')
        self.ax_hist.set_ylabel('Frecuencia')
        self.ax_hist.grid(True)
        self.fig.canvas.draw()

    def on_key(self, event):
        if event.key == 'right':
            self.current_index = (self.current_index + 1) % self.total_images
        elif event.key == 'left':
            self.current_index = (self.current_index - 1) % self.total_images

        self.update_display()

    def submit_index(self, text):
        try:
            idx = int(text) - 1  # El índice ingresado es 1-based
            if 0 <= idx < self.total_images:
                self.current_index = idx
            else:
                print(f"Índice fuera de rango. Debe estar entre 1 y {self.total_images}.")
        except ValueError:
            print("Por favor ingresa un número válido.")
        
        self.update_display()

def plot_histograms(image_list):
    """
    Grafica las imágenes y sus histogramas para una lista de imágenes SimpleITK,
    permitiendo navegar entre ellas con las flechas del teclado o mediante un cuadro de texto para ingresar el índice.

    Parameters:
    image_list (list of sitk.Image): Lista de imágenes SimpleITK.
    """
    navigator = ImageHistogramNavigator(image_list)
    plt.show()







class TwoImageHistogramNavigator:
    def __init__(self, gray_image_list, color_image_list, lut='jet'):
        self.gray_image_list = gray_image_list
        self.color_image_list = color_image_list
        self.lut = lut
        self.total_images = len(gray_image_list)
        self.current_index = 0

        # Crear la figura con 3 ejes (imagen, histograma y leyenda de LUT)
        self.fig, (self.ax_img, self.ax_hist, self.ax_lut) = plt.subplots(1, 3, figsize=(16, 6),
                                                                          gridspec_kw={'width_ratios': [5, 5, 1]})
        plt.subplots_adjust(bottom=0.2)

        # Conectar eventos de teclado
        self.cid_key = self.fig.canvas.mpl_connect('key_press_event', self.on_key)

        # Crear cuadro de entrada de texto para los índices
        self.axbox = plt.axes([0.25, 0.05, 0.5, 0.05])
        self.text_box = TextBox(self.axbox, 'Ir a la imagen (índice): ')
        self.text_box.on_submit(self.submit_index)

        # Actualizar la visualización inicial
        self.update_display()

        # Crear la leyenda de la LUT una sola vez
        self.update_lut_legend()

    def update_display(self):
        self.update_image()
        self.update_histogram()

    def update_image(self):
        self.ax_img.clear()
        image_array = sitk.GetArrayFromImage(self.color_image_list[self.current_index])
        self.ax_img.imshow(image_array)
        self.ax_img.set_title(f'Imagen {self.current_index + 1}/{self.total_images}')
        self.ax_img.axis('off')

    def update_histogram(self):
        self.ax_hist.clear()
        gray_image_array = sitk.GetArrayFromImage(self.gray_image_list[self.current_index])
        self.ax_hist.hist(gray_image_array.flatten(), bins=256, color='blue', alpha=0.7)
        self.ax_hist.set_title('Histograma')
        self.ax_hist.set_xlabel('Intensidad')
        self.ax_hist.set_ylabel('Frecuencia')
        self.ax_hist.grid(True)

    def update_lut_legend(self):
        self.ax_lut.clear()

        # Crear una barra de colores vertical con la LUT seleccionada
        gradient = np.linspace(0, 1, 256).reshape(-1, 1)
        self.ax_lut.imshow(gradient, aspect='auto', cmap=self.lut, origin='lower')
        self.ax_lut.set_title('LUT')
        self.ax_lut.set_xticks([])
        self.ax_lut.set_yticks([])
        self.ax_lut.axis('off')  # Opcional: ocultar los ejes

    def on_key(self, event):
        if event.key == 'right':
            self.current_index = (self.current_index + 1) % self.total_images
        elif event.key == 'left':
            self.current_index = (self.current_index - 1) % self.total_images

        self.update_display()

    def submit_index(self, text):
        try:
            idx = int(text) - 1  # El índice ingresado es 1-based
            if 0 <= idx < self.total_images:
                self.current_index = idx
            else:
                print(f"Índice fuera de rango. Debe estar entre 1 y {self.total_images}.")
        except ValueError:
            print("Por favor ingresa un número válido.")

        self.update_display()


def plot_histograms_with_lut(gray_image_list, color_image_list, lut='jet'):
    """
    Grafica imágenes a color con LUT y sus histogramas calculados a partir de imágenes en escala de grises.
    Permite navegar entre las imágenes con las flechas del teclado o mediante un cuadro de texto para ingresar el índice.

    Parameters:
    gray_image_list (list of sitk.Image): Lista de imágenes en escala de grises SimpleITK para calcular el histograma.
    color_image_list (list of sitk.Image): Lista de imágenes con LUT aplicada para visualización.
    lut (str): Nombre de la LUT a aplicar. Default: 'jet'.
    """
    navigator = TwoImageHistogramNavigator(gray_image_list, color_image_list, lut)
    plt.show()

