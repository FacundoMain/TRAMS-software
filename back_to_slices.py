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

#prueba de plano sagital
def convert_3d_image_to_sagital(sitk_image_3d):
    
    sitk_slices_sagital = []
    
     # Recorre eje Y
    for x in range(sitk_image_3d.GetSize()[0]):

        # Extrae plano coronal
        slice_2d = sitk_image_3d[x, :, :]

        sitk_slices_sagital.append(slice_2d)


    return sitk_slices_sagital