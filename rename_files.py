__author__ = 'Alejo Chacon'

import os
from tkinter import Tk
from tkinter.filedialog import askdirectory
"""
Es un script para cambiar el nombre de los archivos de una carpeta. Viene bien para cuando la numeracion de los archivos
hace que se lean en el orden equivocado (1,2,...,10 se lee en el orden 1,10,2,3,4...)
Cuando se ejecuta va a aparecer una ventana que te permite buscar la carpeta donde estan los archivos objetivo, luego
hay que ingresar en la terminal el formato base del nombre nuevo y el código lo repite para todas las imágenes 
agregándoles el número en formato de 4 dígitos (0001 hasta 9999)
"""

def rename_files(directory, base_name):
    files = os.listdir(directory)
    # Asegurar que los archivos estén ordenados de alguna manera
    files.sort()  
    for i, filename in enumerate(files):
        file_extension = os.path.splitext(filename)[1]  # Obtener la extensión del archivo
        #base_name = filename
        #file_extension = ".dcm"
        new_name = f"{base_name}{i+1:04d}{file_extension}"
        #new_name = f"{base_name}{file_extension}"
        os.rename(os.path.join(directory, filename), os.path.join(directory, new_name))


#Ejecuta la funcion
def main():
    # Ocultar la ventana principal de Tkinter
    Tk().withdraw()
    # Abrir un cuadro de diálogo para seleccionar la carpeta
    directory = askdirectory(title="Selecciona la carpeta con los archivos a renombrar")
    if directory:
        base_name = input("Ingrese el nombre base para los archivos: ")
        rename_files(directory, base_name)
        print("Archivos renombrados con éxito.")
    else:
        print("No se seleccionó ninguna carpeta.")

if __name__ == "__main__":
    main()