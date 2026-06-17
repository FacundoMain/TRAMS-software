__author__ = 'Alejo Chacon and Facundo Main'
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import TextBox
import SimpleITK as sitk

def compare_mri(fixed_img_sitk_list, moving_img_sitk_list, title1, title2, window_title):
    """
    Visualiza las imágenes DICOM lado a lado y permite navegar entre ellas usando las flechas del teclado o ingresando el número de la imagen a la que se desea ir.

    Parameters:
    :param fixed_img_sitk_list (list): Lista de imágenes SimpleITK de la resonancia fija.
    :param moving_img_sitk_list (list): Lista de imágenes SimpleITK de la resonancia móvil registrada.
    :param title1: título de la primera imagen
    :param title2: título de la segunda imagen
    """

    # Extraer matrices de píxeles
    fixed_pixel_arrays = [np.squeeze(sitk.GetArrayViewFromImage(img)) for img in fixed_img_sitk_list]
    moving_pixel_arrays = [np.squeeze(sitk.GetArrayViewFromImage(img)) for img in moving_img_sitk_list]

    # Asegurarse de que ambas imágenes tengan la misma cantidad de cortes
    num_images = min(len(fixed_pixel_arrays), len(moving_pixel_arrays))
    current_index = 0

    fig, axs = plt.subplots(1, 2, figsize=(12, 6))
    fig.subplots_adjust(bottom=0.2)
    fig.canvas.manager.set_window_title(window_title)

    # Define una subfuncion que grafica ambas matrices de pixeles en paralelo
    def show_images(index):
        nonlocal current_index
        current_index = index
        
        for ax in axs:
            ax.clear()
        
        axs[0].imshow(fixed_pixel_arrays[current_index], cmap='gray')
        axs[0].set_title(f"{title1}: {current_index + 1}/{num_images}")
        axs[0].axis('off')

        axs[1].imshow(moving_pixel_arrays[current_index], cmap='gray')
        axs[1].set_title(f"{title2}: {current_index + 1}/{num_images}")
        axs[1].axis('off')
        
        fig.canvas.draw()

    # Configura que pueda recorrer las imagenes con las flechas del teclado
    def on_key_press(event):
        nonlocal current_index
        if event.key == 'right':
            current_index = (current_index + 1) % num_images
        elif event.key == 'left':
            current_index = (current_index - 1) % num_images
        show_images(current_index)
    
    # Configura que pueda dirigirme a un corte específico de la resonancia a partir del nro de la imagen (útil cuando se donde esta lo que quiero ver)
    def submit(text):
        nonlocal current_index
        try:
            index = int(text) - 1
            if 0 <= index < num_images:
                current_index = index
                show_images(current_index)
        except ValueError:
            pass

    axbox = plt.axes([0.3, 0.05, 0.4, 0.075])
    text_box = TextBox(axbox, "Go to image #", initial="")
    text_box.on_submit(submit)
    
    fig.canvas.mpl_connect('key_press_event', on_key_press)
    show_images(current_index)
    plt.show()

#   prueba del corte sagital, despues se puede borrar  
def compare_mri_sagital (fixed_img_sitk_list, moving_img_sitk_list, fixed_spacing, moving_spacing, title1, title2, window_title):
    
    # Extraer matrices de píxeles
    fixed_pixel_arrays = [np.squeeze(sitk.GetArrayViewFromImage(img)) for img in fixed_img_sitk_list]
    moving_pixel_arrays = [np.squeeze(sitk.GetArrayViewFromImage(img)) for img in moving_img_sitk_list]

    # Asegurarse de que ambas imágenes tengan la misma cantidad de cortes
    num_images = min(len(fixed_pixel_arrays), len(moving_pixel_arrays))
    current_index = 0

    fig, axs = plt.subplots(1, 2, figsize=(12, 6))
    fig.subplots_adjust(bottom=0.2)
    fig.canvas.manager.set_window_title(window_title)

    # Define una subfuncion que grafica ambas matrices de pixeles en paralelo
    def show_images(index):
        nonlocal current_index
        current_index = index
        
        for ax in axs:
            ax.clear()
        
        axs[0].imshow(fixed_pixel_arrays[current_index], cmap='gray', aspect=fixed_spacing[2] / fixed_spacing[1])
        axs[0].set_title(f"{title1}: {current_index + 1}/{num_images}")
        axs[0].axis('off')

        axs[1].imshow(moving_pixel_arrays[current_index], cmap='gray',  aspect=moving_spacing[2] / moving_spacing[1])
        axs[1].set_title(f"{title2}: {current_index + 1}/{num_images}")
        axs[1].axis('off')
        
        fig.canvas.draw()

    # Configura que pueda recorrer las imagenes con las flechas del teclado
    def on_key_press(event):
        nonlocal current_index
        if event.key == 'right':
            current_index = (current_index + 1) % num_images
        elif event.key == 'left':
            current_index = (current_index - 1) % num_images
        show_images(current_index)
    
    # Configura que pueda dirigirme a un corte específico de la resonancia a partir del nro de la imagen (útil cuando se donde esta lo que quiero ver)
    def submit(text):
        nonlocal current_index
        try:
            index = int(text) - 1
            if 0 <= index < num_images:
                current_index = index
                show_images(current_index)
        except ValueError:
            pass

    axbox = plt.axes([0.3, 0.05, 0.4, 0.075])
    text_box = TextBox(axbox, "Go to image #", initial="")
    text_box.on_submit(submit)
    
    fig.canvas.mpl_connect('key_press_event', on_key_press)
    show_images(current_index)
    plt.show()

    