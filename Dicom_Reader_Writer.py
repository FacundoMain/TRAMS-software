__author__ = 'Alejo Chacon and Facundo Main'
import SimpleITK as sitk
import os
import time
import uuid
import tkinter as tk
from tkinter import filedialog
import numpy as np
import math

def get_dicom(dicom_path):
    """
    Esta funcion permite al usuario explorar el disco y seleccionar una carpeta desde la cual cargar archivos DICOM (pensada para estudios de RMN 
    con múltiples cortes). La funcion toma todos los archivos de la carpeta y los divide en dos variables: una imagen 3D de SimpleITK que contiene 
    todos los cortes del estudio y una lista de metadataos asociados a cada corte. La funcion esta basada en un código ejemplo presentado en la página de 
    SimpleITK, el cual modifica el funcionamiento normal del método ImageSeriesReader para que no descarte los metadatos asociados a las imágenes que lee.

    :param dicom_path: string con la dirección de los elementos que se desean cargar
    Returns:
    :param image_3D: imagen 3D de SimpleITK con las imagenes asociadas a todos los archivos DICOM del directorio de carga
    :param metadatos: lista de diccionarios 'dict' que contienen una clave (key: str) y un valor (value: str)
    """
    
    carpeta = dicom_path

    # Leer las series DICOM de la carpeta seleccionada
    series_IDs = sitk.ImageSeriesReader.GetGDCMSeriesIDs(carpeta)
    if not series_IDs:
        raise ValueError(f"La carpeta '{carpeta}' no contiene una serie DICOM.")
    
    series_file_names = sitk.ImageSeriesReader.GetGDCMSeriesFileNames(carpeta, series_IDs[0])
    
    series_reader = sitk.ImageSeriesReader()
    series_reader.SetFileNames(series_file_names)
    series_reader.MetaDataDictionaryArrayUpdateOn()
    series_reader.LoadPrivateTagsOn()
    image3D = series_reader.Execute()
    image_3D = sitk.Cast(image3D, sitk.sitkInt16)
    #image_3D = sitk.Cast(image3D, sitk.sitkFloat32)     #prueba de lectura en float 32

    # Extraer metadatos
    #imagenes = [image3D[:,:,i] for i in range(image3D.GetDepth())] /// Segmenta la imagen 3D en una lista de cortes, no se usa
    metadatos = [{key: series_reader.GetMetaData(i, key) for key in series_reader.GetMetaDataKeys(i)} for i in range(image3D.GetDepth())]
    
    return image_3D, metadatos



def generate_uid():
    """Genera un UID de DICOM basándose en un UUID (Identificador Unico Universal)"""
    return "2.25." + str(uuid.uuid4().int)



def rgb_to_dicom(imagenes, metadatos, imagen3D, tipo_registro = 3):
    """
    Crea elementos DICOM RGB a partir de una lista de imágenes. Copia los metadatos específicos del paciente de una lista de metadatos recibida por parámetro y 
    genera los específicos del estudio.
    :param imagenes: lista de imágenes SimpleITK RGB (imagenes bidimensionales con pixeles vectoriales)
    :param metadatos: lista de diccionarios (dict) con los metadatos de una de las resonancias utulizadas para generar el TRAM
    """
    TIPOS_REGISTRO = {
        1: "Deformable Registration",
        2: "RigidExternal Registration",
        3: "RigidInternal Basic Registration",
        4: "RigidInternal ROI Registration"
    }   

    # Abrir un cuadro de diálogo para que el usuario seleccione la carpeta donde se guardarán los archivos DICOM
    root = tk.Tk()
    root.withdraw()  # Ocultar la ventana principal de Tkinter
    output_folder = filedialog.askdirectory(title="Selecciona la carpeta donde guardar los archivos DICOM")

    if not output_folder:
        raise ValueError("No se seleccionó ninguna carpeta de salida")

    # Obtener el nombre del paciente de los metadatos
    paciente_nombre = metadatos[0]["0010|0010"].rstrip() if "0010|0010" in metadatos[0] else "Desconocido"
    output_folder = os.path.join(output_folder, f"TRAMs_RGB_{paciente_nombre}")

    # Crear la carpeta si no existe
    os.makedirs(output_folder, exist_ok=True)

    # Inicializar el escritor de archivos DICOM
    writer = sitk.ImageFileWriter()
    writer.KeepOriginalImageUIDOn()

    # Parametros de la imagen 3D
    origen_3D = np.array(imagen3D.GetOrigin())      # es la coordenada fisica en mm del voxel (0,0,0), vector con 3 valores.
    spacing_3D = np.array(imagen3D.GetSpacing())    # es cuanto mide en mm cada lado del voxel. En Z responde a la separacion entre slices
    direction_3D = np.array(imagen3D.GetDirection()).reshape(3,3)   # indica la direccion exacta de los vectores unitarios

    row = direction_3D[:, 0]   # componentes del vector direccion de X 
    col = direction_3D[:, 1]   # componentes del vector direecion de Y 
    #normal = np.cross(row, col)     # componente del vector dirrecion de Z, corresponde hacia donde avanza el estudio
    normal = direction_3D[:, 2] 
    
    orientation = list(row) + list(col)     # orientacion del paciente

    # Tags que se van a copiar
    # se agrega el Tag de Image Orientation Patient
    tags_to_copy = [
        "0010|0010", # Patient Name
        "0010|0020", # Patient ID
        "0010|0030", # Patient Birth Date
        "0008|0050", # Accession Number
        "0008|0060", # Modality
        "0020|1040", # Position Reference Indicator
        "0018|0081", # Echo Time
        "0018|0020", # Scanning Sequence
        "0018|0021", # Sequence Variant
        "0018|0022", # Scan Options
        "0020|1041", # Slice Location
        "0018|5100"  # Patient Position
    ]

    modification_time = time.strftime("%H%M%S")
    modification_date = time.strftime("%Y%m%d")

    # Generar nuevos valores para Study Instance UID y Study ID
    new_study_instance_uid = generate_uid()
    new_study_id = time.strftime("%Y%m%d%H%M%S")
    new_frame_of_reference_uid = generate_uid()


    for i, img in enumerate(imagenes):
        # Convertir la imagen a SimpleITK si es necesario
        if not isinstance(img, sitk.Image):
            img_array = sitk.GetArrayFromImage(img)
            img = sitk.GetImageFromArray(img_array, isVector=True)

        # Verificar que la imagen sea RGB (con 3 componentes por píxel)
        if img.GetNumberOfComponentsPerPixel() != 3:
            raise ValueError("La imagen no es RGB. Asegúrese de que la imagen tenga 3 componentes por píxel.")

        position = origen_3D + i * spacing_3D[2] * normal   # se calcula la posicion fisica del slice en el sistema de coorednadas del paciente
        # origen_3D es la posicion fisica del voxel inicial
        # i es el slice, i va de 0 a la cantidad de cortes - 1
        # spacing_3D[2] corresponde a la distancia entre slices en mm
        # normal es un vector de 3 dimensiones que tiene la direccion de avance de los cortes
        
        series_tag_values = [
            (k, metadatos[i].get(k, '')) for k in tags_to_copy if k in metadatos[i]
        ] + [
            ("0008|0031", modification_time),           # Series Time
            ("0008|0021", modification_date),           # Series Date
            ("0008|0008", "DERIVED\\SECONDARY"),        # Image Type
            ("0020|000E", f"1.2.826.0.1.3680043.2.1125.{modification_date} .1{modification_time}"),  # Series Instance UID
            ("0020|0037", '\\'.join(map(str, orientation))),  # Image Orientation (Patient)
            ("0020|0032", '\\'.join(map(str, position))), # Image Position
            ("0028|0030", f"{spacing_3D[0]}\\{spacing_3D[1]}"), # Pixel spacing
            ("0018|0050", str(spacing_3D[2])),  # Slice Thickness
            ("0008|103E", metadatos[i].get("0008|103E", "") + " Processed-TRAM-RGB-" + TIPOS_REGISTRO[tipo_registro]),  # Series Description
            ("0028|0002", "3"),                         # Samples per Pixel
            ("0028|0004", "RGB"),                       # Photometric Interpretation
            ("0028|0006", "0"),                         # Planar Configuration
            ("0028|0100", "8"),                         # Bits Allocated
            ("0028|0101", "8"),                         # Bits Stored
            ("0028|0102", "7"),                         # High Bit
            ("0028|0103", "0"),                         # Pixel Representation
            ("0008|0020", modification_date),           # Study Date
            ("0008|0030", modification_time),           # Study Time
            ("0020|000D", new_study_instance_uid),      # New Study Instance UID
            ("0020|0010", new_study_id),                # New Study ID
            ("0020|0052", new_frame_of_reference_uid),  # Frame of Reference UID
            ("0008|0070", "Facundo Main"),              # Manufacturer
            ("0018|0023", ""),                          # MR Acquisition Type
            ("0008|0080", "CEMENER"),                   # Institution Name
            ("0008|1030", "TRAM")                       # Study Description
        ]

        # Añadir metadatos específicos a la imagen
        for tag, value in series_tag_values:
            img.SetMetaData(tag, value)

        # Crea los metadatos específicos de cada corte
        img.SetMetaData("0008|0012", time.strftime("%Y%m%d"))  # Instance Creation Date
        img.SetMetaData("0008|0013", time.strftime("%H%M%S"))  # Instance Creation Time
        img.SetMetaData("0020|0013", str(i))  # Instance Number


        # Generar el nombre del archivo con el formato especificado
        image_uid = img.GetMetaData("0020|000E")
        file_name = f"TRAM.{image_uid}.Image.{i:04d}.dcm"

        # Escribir la imagen en el directorio de salida con el nombre especificado
        writer.SetFileName(os.path.join(output_folder, file_name))
        writer.Execute(img)

    print(f"Archivos DICOM guardados en: {output_folder}")

def monochrome_to_dicom(imagenes, metadatos):
    """
    Crea elementos DICOM en escala de grises a partir de una lista de imágenes. Copia los metadatos específicos del paciente de una lista de metadatos recibida 
    por parámetro y genera los específicos del estudio.
    :param imagenes: lista de imágenes SimpleITK en escala de grises
    :param metadatos: lista de diccionarios (dict) con los metadatos de una de las resonancias utulizadas para generar el TRAM
    """
    # Abrir un cuadro de diálogo para que el usuario seleccione la carpeta donde se guardarán los archivos DICOM
    root = tk.Tk()
    root.withdraw()  # Ocultar la ventana principal de Tkinter
    output_folder = filedialog.askdirectory(title="Selecciona la carpeta donde guardar los archivos DICOM")

    if not output_folder:
        raise ValueError("No se seleccionó ninguna carpeta de salida")

    # Obtener el nombre del paciente de los metadatos
    paciente_nombre = metadatos[0]["0010|0010"].rstrip() if "0010|0010" in metadatos[0] else "Desconocido"
    output_folder = os.path.join(output_folder, f"TRAMs_Mono_{paciente_nombre}")

    # Crear la carpeta si no existe
    os.makedirs(output_folder, exist_ok=True)

    # Inicializar el escritor de archivos DICOM
    writer = sitk.ImageFileWriter()
    writer.KeepOriginalImageUIDOn()

    # Tags que se van a copiar
    tags_to_copy = [
        "0010|0010",  # Patient Name
        "0010|0020",  # Patient ID
        "0010|0030",  # Patient Birth Date
        "0008|0050",  # Accession Number
        "0008|0060",  # Modality
        "0020|1040",  # Position Reference Indicator
        "0018|0081",  # Echo Time
        "0018|0020",  # Scanning Sequence
        "0018|0021",  # Sequence Variant
        "0018|0022",  # Scan Options
        "0018|0050",  # Slice Thickness
        "0020|1041",  # Slice Location
        "0018|5100",  # Patient Position
        "0020|0032"   # Image Position Patient
    ]

    modification_time = time.strftime("%H%M%S")
    modification_date = time.strftime("%Y%m%d")

    # Generar nuevos valores para Study Instance UID y Study ID
    new_study_instance_uid = generate_uid()
    new_study_id = time.strftime("%Y%m%d%H%M%S")
    new_frame_of_reference_uid = generate_uid()

    for i, img in enumerate(imagenes):
        # Convertir la imagen a SimpleITK si es necesario
        if not isinstance(img, sitk.Image):
            img_array = sitk.GetArrayFromImage(img)
            img = sitk.GetImageFromArray(img_array)

        # Verificar que la imagen sea monocromática (con 1 componente por píxel)
        if img.GetNumberOfComponentsPerPixel() != 1:
            raise ValueError("La imagen no es monocromática. Asegúrese de que la imagen tenga 1 componente por píxel.")

        # Configurar la dirección de la imagen
        direction = img.GetDirection()
        series_tag_values = [
            (k, metadatos[i].get(k, '')) for k in tags_to_copy if k in metadatos[i]
        ] + [
            ("0008|0031", modification_time),           # Series Time
            ("0008|0021", modification_date),           # Series Date
            ("0008|0008", "DERIVED\\SECONDARY"),        # Image Type
            ("0020|000E", f"1.2.826.0.1.3680043.2.1125.{modification_date}.1{modification_time}"),  # Series Instance UID
            ("0020|0037", '\\'.join(map(str, (direction[0], direction[2], 0, direction[1], direction[3], 0)))), # Image Orientation (Patient)
            ("0008|103E", metadatos[i].get("0008|103E", "") + " Processed-TRAM-Monochrome"),  # Series Description
            ("0008|0020", modification_date),           # Study Date
            ("0008|0030", modification_time),           # Study Time
            ("0020|000D", new_study_instance_uid),      # New Study Instance UID
            ("0020|0010", new_study_id),                # New Study ID
            ("0020|0052", new_frame_of_reference_uid),  # Frame of Reference UID
            ("0008|0070", "Alejo Chacon"),              # Manufacturer
            ("0018|0023", ""),                          # MR Acquisition Type
            ("0008|0080", "CEMENER"),                   # Institution Name
            ("0008|1030", "TRAM")                       # Study Description
        ]

        # Añadir metadatos específicos a la imagen
        for tag, value in series_tag_values:
            img.SetMetaData(tag, value)

        # Crea los metadatos específicos de cada corte
        img.SetMetaData("0008|0012", time.strftime("%Y%m%d"))  # Instance Creation Date
        img.SetMetaData("0008|0013", time.strftime("%H%M%S"))  # Instance Creation Time
        img.SetMetaData("0020|0013", str(i))  # Instance Number

        # Generar el nombre del archivo con el formato especificado
        image_uid = img.GetMetaData("0020|000E")
        file_name = f"TRAM.{image_uid}.Image.{i:04d}.dcm"

        # Escribir la imagen en el directorio de salida con el nombre especificado
        writer.SetFileName(os.path.join(output_folder, file_name))
        writer.Execute(img)

    print(f"Archivos DICOM guardados en: {output_folder}")



def monochrome_to_PET_dicom(imagenes, metadatos):
    # Abrir un cuadro de diálogo para que el usuario seleccione la carpeta donde se guardarán los archivos DICOM
    root = tk.Tk()
    root.withdraw()  # Ocultar la ventana principal de Tkinter
    output_folder = filedialog.askdirectory(title="Selecciona la carpeta donde guardar los archivos DICOM")

    if not output_folder:
        raise ValueError("No se seleccionó ninguna carpeta de salida")

    # Obtener el nombre del paciente de los metadatos
    paciente_nombre = metadatos[0]["0010|0010"].rstrip() if "0010|0010" in metadatos[0] else "Desconocido"
    output_folder = os.path.join(output_folder, f"TRAMs_Mono_PET.Format_{paciente_nombre}")

    # Crear la carpeta si no existe
    os.makedirs(output_folder, exist_ok=True)

    # Inicializar el escritor de archivos DICOM
    writer = sitk.ImageFileWriter()
    writer.KeepOriginalImageUIDOn()

    # Tags que se van a copiar
    tags_to_copy = [
        "0010|0010",  # Patient Name
        "0010|0020",  # Patient ID
        "0010|0030",  # Patient Birth Date
        "0008|0050",  # Accession Number
        "0020|1040",  # Position Reference Indicator
        "0018|0050",  # Slice Thickness
        "0020|1041",  # Slice Location
        "0018|5100",  # Patient Position
        "0020|0032"   # Image Position Patient
    ]

    modification_time = time.strftime("%H%M%S")
    modification_date = time.strftime("%Y%m%d")

    # Generar nuevos valores para Study Instance UID y Study ID
    new_study_instance_uid = generate_uid()
    new_study_id = time.strftime("%Y%m%d%H%M%S")
    new_frame_of_reference_uid = generate_uid()

    for i, img in enumerate(imagenes):
        # Convertir la imagen a SimpleITK si es necesario
        #if not isinstance(img, sitk.Image):
        #    img_array = sitk.GetArrayFromImage(img)
        #    img = sitk.GetImageFromArray(img_array)

        # Verificar que la imagen sea monocromática (con 1 componente por píxel)
        if img.GetNumberOfComponentsPerPixel() != 1:
            raise ValueError("La imagen no es monocromática. Asegúrese de que la imagen tenga 1 componente por píxel.")

        # Configurar la dirección de la imagen
        # se cambia la Image orientation del paciente
        direction = img.GetDirection()
        
        row = direction[0:3]
        col = direction[3:6]

        series_tag_values = [
            (k, metadatos[i].get(k, '')) for k in tags_to_copy if k in metadatos[i]
        ] + [
            ("0008|0031", modification_time),           # Series Time
            ("0008|0021", modification_date),           # Series Date
            ("0008|0008", "DERIVED\\SECONDARY"),        # Image Type
            ("0020|000E", f"1.2.826.0.1.3680043.2.1125.{modification_date}.1{modification_time}"),  # Series Instance UID
            ("0020|0037", '\\'.join(map(str, list(row) + list(col)))), # Image Orientation (Patient)
            #Se deja comentado y se reemplaza por vectores fijos para evitar errores por no ortogonalidad como consecuencia de redondeos
            #("0020|0037", '\\'.join(map(str, (1, 0, 0, 0, 1, 0)))), # Image Orientation (Patient)
            ("0008|103E", metadatos[i].get("0008|103E", "") + " Processed-TRAM-PET"),  # Series Description
            ("0008|0020", modification_date),           # Study Date
            ("0008|0030", modification_time),           # Study Time
            ("0020|000D", new_study_instance_uid),      # New Study Instance UID
            ("0020|0010", new_study_id),                # New Study ID
            ("0020|0052", new_frame_of_reference_uid),  # Frame of Reference UID
            ("0008|0070", "Alejo Chacon"),              # Manufacturer
            ("0008|0080", "CEMENER"),                   # Institution Name
            ("0008|1030", "TRAM"),                      # Study Description
            ("0008|0060", "PT"),                        # Modality set to PET
            ("0018|1030", "TRAM (PET format)"),         # Protocol Name
            ("0054|1000", "PET"),                       # Series Type
            ("0054|0400", "SUVR"),                      # Reconstruction Method
            ("0054|0016", " "),                         # Radiopharmaceutical Information Sequence
            ("0054|0020", "ACQUIRED"),                  # Image Type
            ("0054|0100", "SUVbw"),                     # Units
            ("0054|0081", "ECAT"),                      # Units
            ("0054|1001", "Dynamic"),                   # Series Type
            ("0018|1181", "NONE"),                      # Collimator Type
            ("0028|0051", "DECY\\RADL\\ATTN\\SCAT\\DTIM\\RAN\\NORM"),   # Corrected Image 
            ("0054|1002", "EMISSION"),                  # Counts Source
            ("0054|1102", "START"),                     # Decay Correction
            ("0054|0414", "FOWARD"),                    # Patient Gantry Relationship Code Sequence
            ("0054|0410", "HFS"),                       # Patient Orientation Code Sequence
            #("0018|1100",       ),                      # Reconstruction Diameter
            ("0054|1000", "WHOLE BODY\\IMAGE"),         # Series Type
            ("0008|0022", modification_date),           # Acquisition Date
            ("0008|0032", modification_time),           # Acquisition Time
            ("0018|1242", "89900"),                     # Actual Frame Duration
            ("0054|1300", "1137981"),                   # Frame Reference Time
            ("0054|1330", str(i)),                      # Image Index
            ("0054|1001", "BQML")                       # Units
        ]

        # Añadir metadatos específicos a la imagen
        for tag, value in series_tag_values:
            img.SetMetaData(tag, value)

        # Crea los metadatos específicos de cada corte
        img.SetMetaData("0008|0012", time.strftime("%Y%m%d"))  # Instance Creation Date
        img.SetMetaData("0008|0013", time.strftime("%H%M%S"))  # Instance Creation Time
        img.SetMetaData("0020|0013", str(i))  # Instance Number

        # Generar el nombre del archivo con el formato especificado
        image_uid = img.GetMetaData("0020|000E")
        file_name = f"TRAM.{image_uid}.Image.{i:04d}.dcm"

        # Escribir la imagen en el directorio de salida con el nombre especificado
        writer.SetFileName(os.path.join(output_folder, file_name))
        writer.Execute(img)

    print(f"Archivos DICOM guardados en: {output_folder}")


def monochrome_to_PET_dicom(imagenes, metadatos, imagen3D, tipo_registro = 3):
    # registrarion method, guarda la forma de registracion para ponerlo en la descripcion en la imagen Dicom
    # 1 = Registracion deformable
    # 2 = Registracion Rigida Externa
    # 3 = Registracion Rigida Interna
    TIPOS_REGISTRO = {
        1: "Deformable Registration",
        2: "RigidExternal Registration",
        3: "RigidInternal Basic Registration",
        4: "RigidInternal ROI Registration"
    }    
    # Abrir un cuadro de diálogo para que el usuario seleccione la carpeta donde se guardarán los archivos DICOM
    root = tk.Tk()
    root.withdraw()  # Ocultar la ventana principal de Tkinter
    output_folder = filedialog.askdirectory(title="Selecciona la carpeta donde guardar los archivos DICOM")

    if not output_folder:
        raise ValueError("No se seleccionó ninguna carpeta de salida")

    # Obtener el nombre del paciente de los metadatos
    paciente_nombre = metadatos[0]["0010|0010"].rstrip() if "0010|0010" in metadatos[0] else "Desconocido"
    output_folder = os.path.join(output_folder, f"TRAMs_Mono_PET.Format_{paciente_nombre}")

    # Crear la carpeta si no existe
    os.makedirs(output_folder, exist_ok=True)

    # Inicializar el escritor de archivos DICOM
    writer = sitk.ImageFileWriter()
    writer.KeepOriginalImageUIDOn()

    # Parametros de la imagen 3D
    origen_3D = np.array(imagen3D.GetOrigin())      # es la coordenada fisica en mm del voxel (0,0,0), vector con 3 valores.
    spacing_3D = np.array(imagen3D.GetSpacing())    # es cuanto mide en mm cada lado del voxel. En Z responde a la separacion entre slices
    direction_3D = np.array(imagen3D.GetDirection()).reshape(3,3)   # indica la direccion exacta de los vectores unitarios

    row = direction_3D[:, 0]   # componentes del vector direccion de X 
    col = direction_3D[:, 1]   # componentes del vector direecion de Y 
    #normal = np.cross(row, col)     # componente del vector dirrecion de Z, corresponde hacia donde avanza el estudio
    normal = direction_3D[:, 2] 
    
    orientation = list(row) + list(col)     # orientacion del paciente

    # Tags que se van a copiar
    tags_to_copy = [
        "0010|0010", # Patient Name
        "0010|0020", # Patient ID
        "0010|0030", # Patient Birth Date
        "0008|0050", # Accession Number
        "0020|1040", # Position Reference Indicator
        "0018|0081", # Echo Time
        "0018|0020", # Scanning Sequence
        "0018|0021", # Sequence Variant
        "0018|0022", # Scan Options
        "0020|1041", # Slice Location
        "0018|5100"  # Patient Position
    ]

    modification_time = time.strftime("%H%M%S")
    modification_date = time.strftime("%Y%m%d")

    # Generar nuevos valores para Study Instance UID y Study ID
    new_study_instance_uid = generate_uid()
    new_study_id = time.strftime("%Y%m%d%H%M%S")
    new_frame_of_reference_uid = generate_uid()

    for i, img in enumerate(imagenes):  # este i correspoinde a cada slice
        # Convertir la imagen a SimpleITK si es necesario
        if not isinstance(img, sitk.Image):
            raise ValueError("Se esperaba imagen SimpleITK")
        #img_array = sitk.GetArrayFromImage(img)
        #img = sitk.GetImageFromArray(img_array)

        # se recastea a int16 para la escritura
        sitk.Cast(img, sitk.sitkInt16)

        # Verificar que la imagen sea monocromática (con 1 componente por píxel)
        if img.GetNumberOfComponentsPerPixel() != 1:
            raise ValueError("La imagen no es monocromática. Asegúrese de que la imagen tenga 1 componente por píxel.")

        # se cambia la Image orientation del paciente
        position = origen_3D + i * spacing_3D[2] * normal   # se calcula la posicion fisica del slice en el sistema de coorednadas del paciente
        # origen_3D es la posicion fisica del voxel inicial
        # i es el slice, i va de 0 a la cantidad de cortes - 1
        # spacing_3D[2] corresponde a la distancia entre slices en mm
        # normal es un vector de 3 dimensiones que tiene la direccion de avance de los cortes

        series_tag_values = [
            (k, metadatos[i].get(k, '')) for k in tags_to_copy if k in metadatos[i]
        ] + [
            ("0008|0031", modification_time),           # Series Time
            ("0008|0021", modification_date),           # Series Date
            ("0008|0008", "DERIVED\\SECONDARY"),        # Image Type
            ("0020|000E", f"1.2.826.0.1.3680043.2.1125.{modification_date}.1{modification_time}"),  # Series Instance UID
            ("0020|0037", '\\'.join(map(str, orientation))), # Image Orientation (Patient)
            ("0020|0032", '\\'.join(map(str, position))), # Image Position
            ("0028|0030", f"{spacing_3D[0]}\\{spacing_3D[1]}"), # Pixel spacing
            ("0018|0050", str(spacing_3D[2])),  # Slice Thickness
            ("0008|103E", metadatos[i].get("0008|103E", "") + " Processed-TRAM-PET-" + TIPOS_REGISTRO[tipo_registro]),  # Series Description
            ("0008|0020", modification_date),           # Study Date
            ("0008|0030", modification_time),           # Study Time
            ("0020|000D", new_study_instance_uid),      # New Study Instance UID
            ("0020|0010", new_study_id),                # New Study ID
            ("0020|0052", new_frame_of_reference_uid),  # Frame of Reference UID
            ("0008|0070", "Facundo Main"),              # Manufacturer
            ("0008|0080", "CEMENER"),                   # Institution Name
            ("0008|1030", "TRAM"),                      # Study Description
            ("0008|0060", "PT"),                        # Modality set to PET
            ("0018|1030", "TRAM (PET format)"),         # Protocol Name
            ("0054|1000", "PET"),                       # Series Type
            ("0054|0400", "SUVR"),                      # Reconstruction Method
            ("0054|0016", " "),                         # Radiopharmaceutical Information Sequence
            ("0054|0020", "ACQUIRED"),                  # Image Type
            ("0054|0100", "SUVbw"),                     # Units
            ("0054|0081", "ECAT"),                      # Units
            ("0054|1001", "Dynamic"),                   # Series Type
            ("0018|1181", "NONE"),                      # Collimator Type
            ("0028|0051", "DECY\\RADL\\ATTN\\SCAT\\DTIM\\RAN\\NORM"),   # Corrected Image 
            ("0054|1002", "EMISSION"),                  # Counts Source
            ("0054|1102", "START"),                     # Decay Correction
            ("0054|0414", "FOWARD"),                    # Patient Gantry Relationship Code Sequence
            ("0054|0410", "HFS"),                       # Patient Orientation Code Sequence
            #("0018|1100",       ),                      # Reconstruction Diameter
            ("0054|1000", "WHOLE BODY\\IMAGE"),         # Series Type
            ("0008|0022", modification_date),           # Acquisition Date
            ("0008|0032", modification_time),           # Acquisition Time
            ("0018|1242", "89900"),                     # Actual Frame Duration
            ("0054|1300", "1137981"),                   # Frame Reference Time
            ("0054|1330", str(i)),                      # Image Index
            ("0054|1001", "BQML")                       # Units
        ]

        # Añadir metadatos específicos a la imagen
        for tag, value in series_tag_values:
            img.SetMetaData(tag, value)

        # Crea los metadatos específicos de cada corte
        img.SetMetaData("0008|0012", time.strftime("%Y%m%d"))  # Instance Creation Date
        img.SetMetaData("0008|0013", time.strftime("%H%M%S"))  # Instance Creation Time
        img.SetMetaData("0020|0013", str(i))  # Instance Number

        # Generar el nombre del archivo con el formato especificado
        image_uid = img.GetMetaData("0020|000E")
        file_name = f"TRAM.{image_uid}.Image.{i:04d}.dcm"

        # Escribir la imagen en el directorio de salida con el nombre especificado
        writer.SetFileName(os.path.join(output_folder, file_name))
        writer.Execute(img)

    print(f"Archivos DICOM guardados en: {output_folder}")


def export_registration_txt(transform):
    
    root = tk.Tk()
    root.withdraw()

    print("Seleccione la carpeta para guardar el archivo .txt de registracion")
    output_folder = filedialog.askdirectory(
        title="Seleccione carpeta de destino para el archivo de Registracion"
    )

    if not output_folder:
        print("No se seleccionó ninguna carpeta.")
        return

    filename = os.path.join(
        output_folder,
        input("Escriba el nombre del archivo: ") + ".txt"
    )

    try:
        # Si viene como CompositeTransform
        if isinstance(transform, sitk.CompositeTransform):
            transform = transform.GetNthTransform(0)

        with open(filename, "w", encoding="utf-8") as f:

            f.write("===== REGISTRATION TRANSFORM =====\n\n")
            f.write("Datos directos")
            f.write(f"Transform type: {transform.GetName()}\n\n")

            center = transform.GetCenter()

            f.write("Center of rotation (mm)\n")
            f.write(f"X = {center[0]:.6f}\n")
            f.write(f"Y = {center[1]:.6f}\n")
            f.write(f"Z = {center[2]:.6f}\n\n")
              
            translation = transform.GetTranslation()

            f.write("Translation (mm)\n")
            f.write(f"Tx = {translation[0]:.6f}\n")
            f.write(f"Ty = {translation[1]:.6f}\n")
            f.write(f"Tz = {translation[2]:.6f}\n\n")

            angle_x = math.degrees(transform.GetAngleX())
            angle_y = math.degrees(transform.GetAngleY())
            angle_z = math.degrees(transform.GetAngleZ())

            f.write("Rotation (deg)\n")
            f.write(f"Rx = {angle_x:.6f}\n")
            f.write(f"Ry = {angle_y:.6f}\n")
            f.write(f"Rz = {angle_z:.6f}\n\n")

            matrix = transform.GetMatrix()

            f.write("Rotation Matrix (3x3)\n")

            f.write(f"{matrix[0]:.6f}  {matrix[1]:.6f}  {matrix[2]:.6f}\n")
            f.write(f"{matrix[3]:.6f}  {matrix[4]:.6f}  {matrix[5]:.6f}\n")
            f.write(f"{matrix[6]:.6f}  {matrix[7]:.6f}  {matrix[8]:.6f}\n\n")

            homogeneous = np.array([
            [matrix[0], matrix[1], matrix[2], translation[0]],
            [matrix[3], matrix[4], matrix[5], translation[1]],
            [matrix[6], matrix[7], matrix[8], translation[2]],
            [0.0,       0.0,       0.0,       1.0]
            ])

            f.write("Homogeneous Matrix (4x4)\n")
            for row in homogeneous:
                f.write(f"{row[0]:.6f}  {row[1]:.6f}  {row[2]:.6f}  {row[3]:.6f}\n")

            f.write("\n")

            f.write("Datos de transformación inversa\n")
            homogeneous_inv = np.linalg.inv(homogeneous)
            
            matrix_rotation_inv = homogeneous_inv[:3,:3]

            ry = np.arcsin(-matrix_rotation_inv[2,0])
            rx = np.arctan2(matrix_rotation_inv[2,1], matrix_rotation_inv[2,2])
            rz = np.arctan2(matrix_rotation_inv[1,0], matrix_rotation_inv[0,0])

            rx_deg = np.degrees(rx)
            ry_deg = np.degrees(ry)
            rz_deg = np.degrees(rz)

            f.write("Rotaciones en grados\n")
            f.write(f"Rx = {rx_deg:.6f}\n")
            f.write(f"Ry = {ry_deg:.6f}\n")
            f.write(f"Rz = {rz_deg:.6f}\n\n")

            Tx = homogeneous_inv[0, 3]
            Ty = homogeneous_inv[1, 3]
            Tz = homogeneous_inv[2, 3]

            f.write("Traslaciones en mm\n")
            f.write(f"Tx = {Tx:.6f}\n")
            f.write(f"Ty = {Ty:.6f}\n")
            f.write(f"Tz = {Tz:.6f}\n")
            
            f.write("Inverse Homogeneous Matrix (4x4)\n")
            for row in homogeneous_inv:
                f.write(f"{row[0]:.6f}  {row[1]:.6f}  {row[2]:.6f}  {row[3]:.6f}\n")

            print(f"Transformación exportada a: {filename}")

    except Exception as e:
        print(f"Error exportando transformación: {e}")

