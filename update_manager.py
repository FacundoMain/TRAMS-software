__author__ = 'Alejo Chacon'
# Update Manager

import os
import subprocess
import sys
import pkg_resources
import ast 

def instalar_faltantes_desde_requerimientos():
    """
    Lee el archivo requirements.txt, verifica si las dependencias están instaladas
    y si no lo están, las instala automáticamente.
    """
    requirements_file = 'requirements.txt'
    
    try:
        # Leer el archivo requirements.txt
        with open(requirements_file, 'r') as f:
            requerimientos = f.read().splitlines()
        
        # Verificar e instalar los paquetes que faltan
        for requerimiento in requerimientos:
            paquete = requerimiento.split('==')[0]  # Obtiene el nombre del paquete
            try:
                # Verifica si el paquete está instalado
                pkg_resources.require(requerimiento)
            except pkg_resources.DistributionNotFound:
                # El paquete no está instalado, entonces lo instala
                print(f"El paquete {paquete} no está instalado. Instalando...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", requerimiento])
            except pkg_resources.VersionConflict:
                # Si hay un conflicto de versiones, también lo instala
                print(f"Conflicto de versión encontrado para {paquete}. Actualizando...")
                subprocess.check_call([sys.executable, "-m", "pip", "install", requerimiento])
    
    except FileNotFoundError:
        print(f"No se encontró el archivo {requirements_file}. Asegúrate de que exista en el directorio.")
    except Exception as e:
        print(f"Error al procesar los requerimientos: {e}")

