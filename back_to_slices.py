import SimpleITK as sitk

def convert_3d_image_to_slices(sitk_image_3d):
    """
    Transforma una imagen 3D de SimpleITK en una lista de imágenes
    :param sitk_image_3d: Imagen 3D que será segmentada en cortes
    Returns:
    :param sitk_slices: Lista de imágenes obtenidas al segmentar la imagen 3D
    """
    # Crea una lista vacía para guardar las imagenes
    sitk_slices = []

    # Itera sobre cada corte de la imagen 3D
    for z in range(sitk_image_3d.GetSize()[2]):
        # Extrae el corte 2D sobre el que se está trabajando
        slice_2d = sitk_image_3d[:, :, z]

        # Agrega la imagen 2D a la lista
        sitk_slices.append(slice_2d)
    
    return sitk_slices

def convert_3d_image_to_arrslices(sitk_image_3d, orden_salida="BGR"):
    """
    Transforma una imagen 3D de SimpleITK en una lista de imágenes NumPy.

    Las imágenes RGB se convierten al orden de canales solicitado.
    Las imágenes en escala de grises se mantienen sin modificaciones.

    :param sitk_image_3d: Imagen 3D de SimpleITK.
    :param orden_salida: Orden de canales deseado ('RGB' o 'BGR').
    :return: Lista de imágenes 2D como arrays NumPy.
    """

    sitk_slices = []

    componentes = sitk_image_3d.GetNumberOfComponentsPerPixel()

    if orden_salida.upper() not in ("RGB", "BGR"):
        raise ValueError("El orden de salida debe ser RGB o BGR.")

    for z in range(sitk_image_3d.GetSize()[2]):

        # Extraer corte 2D
        slice_2d = sitk_image_3d[:, :, z]

        # Convertir a NumPy
        slice_array = sitk.GetArrayFromImage(slice_2d)

        # Si es una imagen RGB/BGR
        if componentes == 3:

            # SimpleITK recibe la imagen RGB en el orden original
            if orden_salida.upper() == "BGR":
                slice_array = slice_array[:, :, ::-1].copy()

        # Si es escala de grises, no realizar ninguna conversión
        elif componentes == 1:
            pass

        else:
            raise ValueError(
                f"Cantidad de componentes no soportada: {componentes}"
            )

        sitk_slices.append(slice_array)

    return sitk_slices

#prueba de plano sagital
def convert_3d_image_to_sagital(sitk_image_3d):
    
    sitk_slices_sagital = []
    
     # Recorre eje Y
    for x in range(sitk_image_3d.GetSize()[0]):

        # Extrae plano coronal
        slice_2d = sitk_image_3d[x, :, :]

        sitk_slices_sagital.append(slice_2d)


    return sitk_slices_sagital