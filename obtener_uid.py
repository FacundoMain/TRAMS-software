import pydicom
import os
import random

def get_series_instance_uid(directorio):
    """
    Extrae el valor del metadato "SOP Instance UID" de una imagen DICOM.

    Parameters:
    dicom_image (pydicom.dataset.FileDataset): Imagen DICOM cargada con pydicom.

    Returns:
    str: Valor del "Series Instance UID" o None si no se encuentra.
    """

    # Verificar si el directorio existe
    if not os.path.isdir(directorio):
        raise ValueError(f"El directorio {directorio} no existe")

    # Listar todos los archivos en el directorio
    archivos = os.listdir(directorio)

    # Filtrar solo los archivos DICOM
    archivos_dicom = [f for f in archivos if f.endswith('.dcm')]

    # Verificar si hay archivos DICOM en el directorio
    if not archivos_dicom:
        raise ValueError("No se encontraron archivos DICOM en el directorio proporcionado")

    # Seleccionar el primer archivo
    archivo_primero = archivos_dicom[0]

    # Construir la ruta completa del archivo
    ruta_archivo = os.path.join(directorio, archivo_primero)

    # Cargar el archivo DICOM
    dicom = pydicom.dcmread(ruta_archivo)

    try:
        # Extrae el valor del metadato "Series Instance UID"
        series_instance_uid = dicom.SeriesInstanceUID
        return series_instance_uid
    except Exception as e:
        print(f"Error al obtener el Series Instance UID: {e}")
        return None