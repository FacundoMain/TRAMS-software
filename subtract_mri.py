import SimpleITK as sitk

def subtract_mri(mri_t1, mri_t2):
    """
    Resta cada imagen en list1 a la imagen correspondiente en list2
    
    Parameters:
    list1 (list of sitk.Image): Lista de imágenes a restar de list2
    list2 (list of sitk.Image): Lista de imágenes
    
    Returns:
    list of sitk.Image: Lista con las imágenes resultantes de la resta
    """
    if len(mri_t1) != len(mri_t2):
        raise ValueError("Las listas deben tener la misma longitud")
    
    result_list = []
    for img1, img2 in zip(mri_t1, mri_t2):
        result_img = sitk.Subtract(img2, img1)
        result_list.append(result_img)
    
    return result_list

def subtract_mri_3d(fixed_image, moving_image):
    
    return sitk.Subtract(moving_image, fixed_image)

