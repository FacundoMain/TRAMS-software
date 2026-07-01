import numpy as np
import matplotlib.pyplot as plt
import SimpleITK as sitk

from matplotlib.widgets import TextBox
from matplotlib.widgets import RectangleSelector


def select_roi_mask(fixed_image):

    pixel_array = sitk.GetArrayViewFromImage(fixed_image)

    num_slices = pixel_array.shape[0]
    current_slice = num_slices // 2

    roi = None

    fig, ax = plt.subplots(figsize=(6,6))
    fig.subplots_adjust(bottom=0.18)
    fig.canvas.manager.set_window_title("Seleccione ROI")

    # Crear la imagen UNA sola vez
    img = ax.imshow(pixel_array[current_slice], cmap="gray")

    ax.set_title(
    f"Slice {current_slice+1}/{num_slices}\n"
    "← → cambiar slice | Dibuje la ROI con el mouse | Enter: confirmar"
    )

    ax.axis("off")

    # -----------------------------
    # Mostrar slice
    # -----------------------------

    def show_slice(index):

        nonlocal current_slice

        current_slice = index

        img.set_data(pixel_array[current_slice])

        ax.set_title(
            f"Slice {current_slice+1}/{num_slices}\n"
            "← → cambiar slice | Dibuje la ROI con el mouse | Enter: confirmar"
        )

        fig.canvas.draw_idle()

    # -----------------------------
    # Callback del RectangleSelector
    # -----------------------------

    def on_select(eclick, erelease):

        nonlocal roi

        x1 = int(round(eclick.xdata))
        y1 = int(round(eclick.ydata))

        x2 = int(round(erelease.xdata))
        y2 = int(round(erelease.ydata))

        roi = (
            min(x1,x2),
            min(y1,y2),
            max(x1,x2),
            max(y1,y2)
        )

        print("ROI seleccionada:", roi)

    # -----------------------------
    # Teclado
    # -----------------------------

    def on_key(event):

        nonlocal current_slice
        
        if event.key == "right":

            current_slice = (current_slice+1)%num_slices

            show_slice(current_slice)

        elif event.key == "left":

            current_slice = (current_slice-1)%num_slices

            show_slice(current_slice)

        
        elif event.key=="enter":

            if roi is None:

                print("Primero debe seleccionar una ROI.")

                return

            plt.close(fig)

    # -----------------------------
    # Ir a un slice
    # -----------------------------

    def submit(text):

        nonlocal current_slice

        try:

            idx = int(text)-1

            if 0 <= idx < num_slices:

                current_slice = idx

                show_slice(current_slice)

        except:

            pass

    axbox = plt.axes([0.30,0.05,0.40,0.06])

    text_box = TextBox(axbox,"Slice",initial="")

    text_box.on_submit(submit)

    selector = RectangleSelector(
        ax,
        on_select,
        useblit=True,
        button=[1],
        minspanx=5,
        minspany=5,
        interactive=True
    )

    fig.canvas.mpl_connect("key_press_event",on_key)

    show_slice(current_slice)

    plt.show()

    if roi is None:

        return None

    # ======================================================
    # Crear máscara 3D
    # ======================================================

    x0,y0,x1,y1 = roi

    mask_array = np.zeros(pixel_array.shape,dtype=np.uint8)

    mask_array[:,y0:y1,x0:x1] = 1

    mask = sitk.GetImageFromArray(mask_array)

    mask.CopyInformation(fixed_image)

    return mask