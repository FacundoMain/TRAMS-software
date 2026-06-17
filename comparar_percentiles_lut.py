__author__ = 'Alejo Chacon'
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import TextBox
import SimpleITK as sitk

def comparar_percentiles(img1, img2, title1, title2, window_title):
    """
    Visualiza dos listas de imágenes a las cuales se les ha modificado el rango de intensidad de pixeles
    """
    # Extraer matrices de píxeles
    img1_array = [np.squeeze(sitk.GetArrayViewFromImage(img)) for img in img1]
    img2_arrays = [np.squeeze(sitk.GetArrayViewFromImage(img)) for img in img2]

    # Asegurarse de que ambas imágenes tengan la misma cantidad de cortes
    num_images = min(len(img1_array), len(img2_arrays))
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
        
        axs[0].imshow(img1_array[current_index])
        if (title1 == "0") or (title1 == 0):
            axs[0].set_title(f"TRAM con recorte nulo {current_index + 1}/{num_images}")   
        else:
            axs[0].set_title(f"TRAM con recorte {title1} {current_index + 1}/{num_images}")
        
        axs[0].axis('off')

        axs[1].imshow(img2_arrays[current_index])
        axs[1].set_title(f"TRAM con recorte del {title2} {current_index + 1}/{num_images}")
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
