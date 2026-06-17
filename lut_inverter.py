__author__ = 'Alejo Chacon'
# Inversor de LUT para PET-CT

import SimpleITK as sitk


def invert_image_list(image_list):
    inverted_images = []

    for img in image_list:
        # Convertir la imagen a un array NumPy
        img_array = sitk.GetArrayFromImage(img)
        
        # Multiplicar los valores de los píxeles por -1
        inverted_array = -img_array
        
        # Convertir el array invertido de vuelta a una imagen SimpleITK
        inverted_img = sitk.GetImageFromArray(inverted_array)
        inverted_img.CopyInformation(img)
        
        inverted_images.append(inverted_img)

    return inverted_images 