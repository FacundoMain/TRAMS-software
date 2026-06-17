__author__ = 'Alejo Chacon'
import pydicom
import tkinter as tk
from tkinter import filedialog

def load_registration_dicom():
    """
    Permite al usuario explorar su ordenador para seleccionar un archivo DICOM de registración y carga la información de registración entre dos resonancias.

    Returns:
    pydicom.dataset.FileDataset: Dataset DICOM que contiene la información de registro, o None si hubo un error.
    """
    # Crear una ventana oculta para usar el explorador de archivos
    root = tk.Tk()
    root.withdraw()  # Ocultar la ventana principal

    # Abrir cuadro de diálogo para seleccionar archivo
    file_path = filedialog.askopenfilename(title="Seleccionar archivo DICOM de registro",
                                           filetypes=[("DICOM files", "*.dcm")])
    
    if not file_path:
        print("No se seleccionó ningún archivo.")
        return None

    try:
        # Cargar el archivo DICOM
        ds = pydicom.dcmread(file_path)
        
        # Verificar que contiene los atributos necesarios para la registración
        if not hasattr(ds, 'RegistrationSequence'):
            raise AttributeError("El archivo DICOM no contiene la secuencia de registración necesaria.")
        
        with open("registro_completo.txt", "w", encoding="utf-8") as f:
            f.write(str(ds))

        print("Se guardó registro_completo.txt")
        #print("Archivo dicom de registracion")
        #print(ds)
        return ds

    except Exception as e:
        print(f"Error al cargar el archivo DICOM de registración: {e}")
        return None