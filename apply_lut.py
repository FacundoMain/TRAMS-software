__author__ = 'Alejo Chacon'

import SimpleITK as sitk
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm

def apply_lut(image_list, exclude_percent, lut):
    """
    Aplica una LUT a una lista de imágenes SimpleITK y ajusta el rango dinámico de la LUT según el histograma de la imagen.

    Parameters:
    image_list (list of sitk.Image): Lista de imágenes SimpleITK.
    exclude_percent (float): Porcentaje de los extremos del histograma a excluir (0-100).

    Returns:
    list of sitk.Image: Lista de imágenes con la LUT aplicada.
    """
    processed_images = []

    # Obtener el colormap rainbow e invertirlo
    LUT = plt.get_cmap(lut)
    #inverted_LUT = LUT.reversed()

    for image in image_list:
        # Convertir la imagen SimpleITK a un numpy array
        img_array = sitk.GetArrayFromImage(image)

        # Calcular el histograma y los percentiles
        hist, bin_edges = np.histogram(img_array, bins=256, range=(np.min(img_array), np.max(img_array)))
        cdf = np.cumsum(hist) / np.sum(hist) * 100  # CDF en porcentaje
        lower_bound = np.interp(exclude_percent, cdf, bin_edges[:-1])
        upper_bound = np.interp(100 - exclude_percent, cdf, bin_edges[:-1])

        # Ajustar los valores de intensidad al rango [0, 1] basado en los percentiles calculados
        img_scaled = np.clip((img_array - lower_bound) / (upper_bound - lower_bound), 0, 1)

        # Aplicar la LUT invertida a los valores escalados
        img_colored = LUT(img_scaled)

        # Convertir el array con LUT aplicada de vuelta a una imagen SimpleITK
        # Excluir el canal alfa (transparencia) retornado por el cmap de matplotlib
        img_colored = img_colored[..., :3]

        # Convertir la imagen original en escala de grises a RGB
        if image.GetNumberOfComponentsPerPixel() == 1:
            img_gray_to_rgb = sitk.Compose([image]*3)
        else:
            img_gray_to_rgb = image

        # Crear una imagen SimpleITK a partir del array coloreado
        img_colored_sitk = sitk.GetImageFromArray((img_colored * 255).astype(np.uint8))

        # Establecer el espaciado de la imagen procesada
        if img_gray_to_rgb.GetSpacing() is not None and len(img_gray_to_rgb.GetSpacing()) == 3:
            img_colored_sitk.SetSpacing(img_gray_to_rgb.GetSpacing())

        # Verificar y establecer la dirección de la imagen procesada
        direction = img_gray_to_rgb.GetDirection()
        if len(direction) == 9:  # Verificar si la dirección es una matriz de 3x3
            img_colored_sitk.SetDirection(direction)

        # Verificar y establecer el origen de la imagen procesada
        origin = img_gray_to_rgb.GetOrigin()
        if len(origin) == 3:
            img_colored_sitk.SetOrigin(origin)

        processed_images.append(img_colored_sitk)

    return processed_images




def apply_histogram(image_list, percentile):
    """
    Recorta los extremos del histograma de una lista de imágenes, permite que la LUT se distribuya entre los pixeles representativos y que no se pierdan valores de color
    en valores de intensidad que se repiten poco
    :param image_list: lista de imágenes que seran recortadas
    :param percentile: percentil que será eliminado en cada extremo
    Returns:
    :param saturated_images: lista de imágenes ya recortadas
    """
    saturated_images = []

    for idx, image in enumerate(image_list):
        # Obtener el array de la imagen
        image_array = sitk.GetArrayFromImage(image)
        
        # Calcular el histograma
        histogram, bin_edges = np.histogram(image_array, bins=256, range=(image_array.min(), image_array.max()))
        
        # Calcular los límites inferior y superior del percentil
        cdf = np.cumsum(histogram) / np.sum(histogram)
        lower_bound = np.searchsorted(cdf, percentile / 100.0)
        upper_bound = np.searchsorted(cdf, 1 - percentile / 100.0)
        
        # Obtener los valores de los límites
        lower_bound_value = bin_edges[lower_bound]
        upper_bound_value = bin_edges[upper_bound]
        
        # Evitar la división por cero
        if upper_bound_value == lower_bound_value:
            print(f"Warning: upper_bound_value ({upper_bound_value}) is equal to lower_bound_value ({lower_bound_value}) for image index {idx}. Skipping this image.")
            saturated_images.append(image)
            continue
        
        # Aplicar saturación a los valores fuera del percentil
        image_array_saturated = np.clip(image_array, lower_bound_value, upper_bound_value)
        
        # Escalar la imagen para que ocupe todo el rango original de valores
        try:
            image_array_saturated = (image_array_saturated - lower_bound_value) / (upper_bound_value - lower_bound_value) * (image_array.max() - image_array.min()) + image_array.min()
        except RuntimeWarning as e:
            print(f"RuntimeWarning encountered in image index {idx}: {e}")
            continue
        
        # Asegurar que la imagen esté en 16 bits enteros
        image_array_saturated = np.round(image_array_saturated).astype(np.int16)
        
        # Convertir de vuelta a una imagen SimpleITK
        try:
            saturated_image = sitk.GetImageFromArray(image_array_saturated)
        except RuntimeWarning as e:
            print(f"RuntimeWarning encountered in image index {idx} during type casting: {e}")
            continue

        saturated_image.CopyInformation(image)
        
        saturated_images.append(saturated_image)

    return saturated_images




def clip_histogram(image_list, max_intensity):
    """
    Recorta los valores del histograma de una lista de imágenes según un valor máximo de intensidad. 
    Los valores mayores a max_intensity se saturan a max_intensity, y los menores a -max_intensity se saturan a -max_intensity.
    
    :param image_list: lista de imágenes que serán recortadas.
    :param max_intensity: valor máximo de intensidad que se tomará como saturación para valores positivos y negativos.
    
    :returns: lista de imágenes ya recortadas.
    """
    saturated_images = []

    for idx, image in enumerate(image_list):
        # Obtener el array de la imagen
        image_array = sitk.GetArrayFromImage(image)
        
        # Aplicar saturación a los valores fuera del rango [-max_intensity, max_intensity]
        image_array_saturated = np.clip(image_array, -max_intensity, max_intensity)
        
        # Asegurar que la imagen esté en 16 bits enteros
        image_array_saturated = np.round(image_array_saturated).astype(np.int16)
        
        # Convertir de vuelta a una imagen SimpleITK
        try:
            saturated_image = sitk.GetImageFromArray(image_array_saturated)
        except RuntimeWarning as e:
            print(f"RuntimeWarning encountered in image index {idx} during type casting: {e}")
            continue
        
        # Copiar la información espacial de la imagen original
        saturated_image.CopyInformation(image)
        
        saturated_images.append(saturated_image)

    return saturated_images




def apply_lut_2(image_list, intensity_max, lut):
    """
    Aplica una LUT a una lista de imágenes SimpleITK, ajustando el rango dinámico de la LUT
    según un valor de intensidad máxima.

    Parameters:
    image_list (list of sitk.Image): Lista de imágenes SimpleITK.
    intensity_max (float): Valor máximo de intensidad. Los valores por arriba y por debajo de este se saturan.
    lut (str): Nombre de la LUT a aplicar.

    Returns:
    list of sitk.Image: Lista de imágenes con la LUT aplicada.
    """
    processed_images = []

    # Obtener el colormap de la LUT
    LUT = plt.get_cmap(lut)

    for image in image_list:
        # Convertir la imagen SimpleITK a un numpy array
        img_array = sitk.GetArrayFromImage(image)

        # Aplicar saturación a los valores de intensidad según intensity_max
        img_array_saturated = np.clip(img_array, -intensity_max, intensity_max)

        # Ajustar los valores de intensidad al rango [0, 1] basado en intensity_max
        img_scaled = (img_array_saturated + intensity_max) / (2 * intensity_max)

        # Aplicar la LUT a los valores escalados
        img_colored = LUT(img_scaled)

        # Excluir el canal alfa (transparencia) retornado por el cmap de matplotlib
        img_colored = img_colored[..., :3]

        # Convertir la imagen original en escala de grises a RGB si es necesario
        if image.GetNumberOfComponentsPerPixel() == 1:
            img_gray_to_rgb = sitk.Compose([image]*3)
        else:
            img_gray_to_rgb = image

        # Crear una imagen SimpleITK a partir del array coloreado
        img_colored_sitk = sitk.GetImageFromArray((img_colored * 255).astype(np.uint8))

        # Establecer el espaciado de la imagen procesada
        if img_gray_to_rgb.GetSpacing() is not None and len(img_gray_to_rgb.GetSpacing()) == 3:
            img_colored_sitk.SetSpacing(img_gray_to_rgb.GetSpacing())

        # Verificar y establecer la dirección de la imagen procesada
        direction = img_gray_to_rgb.GetDirection()
        if len(direction) == 9:  # Verificar si la dirección es una matriz de 3x3
            img_colored_sitk.SetDirection(direction)

        # Verificar y establecer el origen de la imagen procesada
        origin = img_gray_to_rgb.GetOrigin()
        if len(origin) == 3:
            img_colored_sitk.SetOrigin(origin)

        processed_images.append(img_colored_sitk)

    return processed_images




def lut_and_clipping_manager(image_list, intensity_max=None, lut='jet'):
    """
    Aplica una LUT a una lista de imágenes SimpleITK, ajustando el rango dinámico de la LUT
    según un valor de intensidad máxima o porcentaje.

    Parameters:
    image_list (list of sitk.Image): Lista de imágenes SimpleITK.
    intensity_max (str or None): Valor máximo de intensidad o porcentaje. 
                                 Si es None, no se recorta.
                                 Si es un valor porcentual (por ejemplo, '5%'), se recortan las colas
                                 del histograma en ese porcentaje para valores positivos y negativos.
                                 Si es un valor numérico, se usa como límite superior y -valor como límite inferior.
    lut (str): Nombre de la LUT a aplicar. Default: 'jet'.

    Returns:
    list of sitk.Image: Lista de imágenes con la LUT aplicada.
    """
    processed_images = []

    # Obtener el colormap de la LUT
    LUT = plt.get_cmap(lut)

    for image in image_list:
        # Convertir la imagen SimpleITK a un numpy array
        img_array = sitk.GetArrayFromImage(image)

        # Si se ingresa un porcentaje
        if intensity_max and isinstance(intensity_max, str) and '%' in intensity_max:
            percent = float(intensity_max.strip('%')) / 100.0
            print("entra al if %")
            # Calcular el histograma y los percentiles
            hist, bin_edges = np.histogram(img_array, bins=256, range=(np.min(img_array), np.max(img_array)))
            cdf = np.cumsum(hist) / np.sum(hist) * 100  # CDF en porcentaje
            lower_bound = np.interp(percent, cdf, bin_edges[:-1])
            upper_bound = np.interp(100 - percent, cdf, bin_edges[:-1])

            # Ajustar los valores de intensidad al rango [0, 1] basado en los percentiles calculados
            img_scaled = np.clip((img_array - lower_bound) / (upper_bound - lower_bound), 0, 1)

        # Si se ingresa un valor numérico para intensidad máxima
        elif intensity_max:
            intensity_max = float(intensity_max)
            # Aplicar saturación a los valores de intensidad según intensity_max
            img_array_saturated = np.clip(img_array, -intensity_max, intensity_max)

            # Ajustar los valores de intensidad al rango [0, 1] basado en intensity_max
            img_scaled = (img_array_saturated + intensity_max) / (2 * intensity_max)

        # Si no se ingresa ningún recorte, usar los valores originales de la imagen
        else:
            # Escalar la imagen completa al rango [0, 1]
            min_intensity = np.min(img_array)
            max_intensity = np.max(img_array)
            img_scaled = (img_array - min_intensity) / (max_intensity - min_intensity)

        # Aplicar la LUT a los valores escalados
        img_colored = LUT(img_scaled)

        # Excluir el canal alfa (transparencia) retornado por el cmap de matplotlib
        img_colored = img_colored[..., :3]

        # Convertir la imagen original en escala de grises a RGB si es necesario
        if image.GetNumberOfComponentsPerPixel() == 1:
            img_gray_to_rgb = sitk.Compose([image]*3)
        else:
            img_gray_to_rgb = image

        # Crear una imagen SimpleITK a partir del array coloreado
        img_colored_sitk = sitk.GetImageFromArray((img_colored * 255).astype(np.uint8))

        # Establecer el espaciado de la imagen procesada
        if img_gray_to_rgb.GetSpacing() is not None and len(img_gray_to_rgb.GetSpacing()) == 3:
            img_colored_sitk.SetSpacing(img_gray_to_rgb.GetSpacing())

        # Verificar y establecer la dirección de la imagen procesada
        direction = img_gray_to_rgb.GetDirection()
        if len(direction) == 9:  # Verificar si la dirección es una matriz de 3x3
            img_colored_sitk.SetDirection(direction)

        # Verificar y establecer el origen de la imagen procesada
        origin = img_gray_to_rgb.GetOrigin()
        if len(origin) == 3:
            img_colored_sitk.SetOrigin(origin)

        processed_images.append(img_colored_sitk)

    return processed_images
