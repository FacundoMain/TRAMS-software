__author__ = 'Alejo Chacon and Facundo Main'

from compare_registered_mri import compare_mri, compare_mri_sagital
from apply_lut import lut_and_clipping_manager
from plot_histogram import plot_histograms_with_lut
import tkinter as tk
from tkinter import filedialog
from subtract_mri import subtract_mri, subtract_mri_3d
from visualize_sitk import show_sitk_image
from Dicom_Reader_Writer import get_dicom, rgb_to_dicom, monochrome_to_PET_dicom, export_registration_txt
import SimpleITK as sitk
import numpy as np 
from comparar_percentiles_lut import comparar_percentiles
import time
from respuesta_binaria import solicitar_respuesta_binaria
from mri_registration_tool import registration_tool, get_transform
from validation import run_validation, validate_subtraction_2d, validate_subtraction_3d, insert_cube, apply_translation, apply_rotation

# No borrar, son las funciones que se usan para descargar los paquetes necesarios para que el codigo funcione (Es la sección comentada al inicio del programa)
from lut_inverter import invert_image_list
#from update_manager import instalar_faltantes_desde_requerimientos

from back_to_slices import convert_3d_image_to_slices, convert_3d_image_to_sagital

# Habilito el uso de ventanas
root = tk.Tk()
root.withdraw()  # Ocultar la ventana principal

#Bienvenida
print("Bienvenido a NERV: Neuroimaging Evaluator for Response Verification")
print("")
print("")

time.sleep(3)

#Verificación de paquetes instalados:
#print("Aguarde mientras se verifica que los paquetes necesarios esten instalados")
#print("Esta función solo es necesaria al trabajar con el script. Si ve este mensaje en el ejecutable comente la siguiente sección del código y vuelva a crearlo")
# Descarga los paquetes de python necesarios para correr el programa. Utilizar cuando se hace un pull desde el repositorio a 
# partir de un .txt que se encuentra en la carpeta del main
#instalar_faltantes_desde_requerimientos()



# Cargo las imágenes que se utilizan para el protocolo
print("Seleccione la carpeta en la que se encuentra la resonancia temprana.")
time.sleep(2)
t1_path = filedialog.askdirectory(title=f"Seleccione la carpeta que contiene la resonancia temprana")
t1_img, t1_metadata = get_dicom(t1_path)
print(f"Se cargó la imagen temprana desde la carpeta: {t1_path}")

print("Seleccione la carpeta donde se encuentra la resonancia tardía")
time.sleep(2)
t2_path = filedialog.askdirectory(title=f"Seleccione la carpeta que contiene la resonancia tardía")
t2_img, t2_metadata = get_dicom(t2_path)
print(f"Se cargó la imagen tardía desde la carpeta: {t2_path}")

asd1 = convert_3d_image_to_slices(t1_img)
asd2 = convert_3d_image_to_slices(t2_img)
compare_mri(asd1, asd2, "Resonancia t1 original", "Resonancia t2 original", "Imágenes crudas")

print("T1")
print(t1_img.GetOrigin())
print(t1_img.GetSpacing())
print(t1_img.GetDirection())

print("T2")
print(t2_img.GetOrigin())
print(t2_img.GetSpacing())
print(t2_img.GetDirection())

# PRUEBA MODIFICACION DE MISMA IMAGEN ANTES DE REGISTRAR
#intensity = int(input("ingrese intensidad del cuadrado: "))
#t2_img = insert_cube(t2_img, intensity=intensity)
#t2_img = apply_rotation(t2_img)
#t2_img = apply_translation(t2_img)      
#aux1 = convert_3d_image_to_slices(t2_img)

#compare_mri(asd1, aux1, "t1 cruda", "t2 modificada", "Prueba de modificacion")

exit = False
while exit == False: 

    # Registro las imágenes. Se utiliza un loop que permite probar las distintas estrategias disponibles hasta quedar satisfecho
    print("Esta herramienta permite aplicar una registracion rigida o utilizar una herramienta de registración deformable")
    time.sleep(2)

    satisfaction = False
    while (satisfaction == False):

        t1_list, t2_list, t1_img, resampled_img3D, tipo_registro = registration_tool(t1_img, t1_metadata, t2_img, t2_metadata)

        # Compara los resultados de la registracion
        print("Verifique que la registracion haya sido aplicada correctamente")
        time.sleep(2)
        compare_mri(t1_list, t2_list, "t1 MRI", "t2 MRI", "Verifique que la registración se haya aplicado correctamente")

        resp0 = solicitar_respuesta_binaria("¿Está satisfecho con el resultado de la registración?")
        if resp0 == True:
            satisfaction = True
        
        elif resp0 == False:
            print("Intente con otro de los métodos disponibles")
            time.sleep(2)

    #prueba de Graficacion corte sagital
    #t1_list_sagital = convert_3d_image_to_sagital(t1_img)
    #t2_list_sagital = convert_3d_image_to_sagital(resampled_img3D)

    #fixed_spacing = np.array(t1_img.GetSpacing())ri
    #resampled_img3D_spacing = np.array(resampled_img3D.GetSpacing())

    #compare_mri_sagital(t1_list_sagital, t2_list_sagital, fixed_spacing, resampled_img3D_spacing, "t1 sagital", "t2 sagital", "Ver si se deforma")
    
    #prueba de deformacion


    print("------")
    #print("Prueba de validacion")
    #print("Se realiza validacion de la registracion")
    #run_validation(tipo_registro)
    #print("Fin de prueba..")

    print("Prueba de exportacion de archivo")
    transform = get_transform()
    export_registration_txt(transform)

    #print("Aguarde mientras se procesan las resonancias")
    # modifico la imagen moving
    #modified_list = modify_image(t2_list)

    # Se restan las resonancias
    subtraction = subtract_mri(t1_list, t2_list)
    #imagen_3dt2_nula = subtract_mri_3d(t2_img, t2_img)
    #t1_list = convert_3d_image_to_slices(t1_img)
    #t2_list = convert_3d_image_to_slices(t2_img)
    #imagen_2dt2_nula = convert_3d_image_to_slices(imagen_3dt2_nula)
    #compare_mri(t1_list, t2_list, "Lista imagenes temprana", "Lista imagenes tardia", "Comparacion imagenes originales")
    #compare_mri(t1_list, imagen_2dt2_nula, "Lista imagenes temprana", "Resta consigo misma", "Comparacion imagenes original y restada")
    #t2_intensidad_alreves = subtract_mri(t2_list, imagen_2dt2_nula,) # porque se respeta el el flujo de programa original
    #tram = lut_and_clipping_manager(t2_intensidad_alreves, lut='jet')
    #compare_mri(t2_list, tram, "Imagen tardia negativa", "tram", "Comparacion")

    # guardado PET
    # Convertir la resta de resonancias en una imagen SimpleITK y recastearla como un entero de 16 bits
    #subtraction_sitk = []
    #for s_img in subtraction:
    #    sub = sitk.Cast(s_img, sitk.sitkInt16)
    #    subtraction_sitk.append(sub)

    #tram_pet = subtraction_sitk
    #compare_mri(tram, tram_pet, "RGB", "PET format", "TRAM RGB y TRAM adaptado para PET-CT")    

    #resp7 = solicitar_respuesta_binaria("¿Desea guardar el resultado como PET?")
    #if(resp7 == True):    
    #    monochrome_to_PET_dicom(tram_pet, t1_metadata, t2_img)
    
    #compare_mri(t2_list, subtraction, "Imagen modificada", "Subtraction", "Comparacion imagen modificada y sustraccion")
    #break
    #print("validacion de sustraccion")
    #validate_subtraction_2d(t1_list, t2_list, subtraction)

    #validate_subtraction_3d(t1_img, resampled_img3D, subtraction_3d)
    
    # Ver resta en escala de grises
    #show_sitk_image(subtraction, "gray")

    # Se aplica la LUT
    print("A continuación se muestran el TRAM crudo y el histograma de la resta en escala de grises")
    print("Utilice la información del histograma para decidir si quiere recortarlo y mejorar la interpretacion de la imagen")
    tram = lut_and_clipping_manager(subtraction, lut='jet')

    # Comprobar histograma
    plot_histograms_with_lut(subtraction, tram)

    # Ajuste manual de los percentiles de la LUT
    resp1 = solicitar_respuesta_binaria("¿Desea ajustar el recorte de valores en la LUT a color?")
    p1=0
    if(resp1 == True):
        print("")
        print("Ingrese el parámetro de recorte deseado. Puede utilizar el valor de intensidad máxima permitida o el percentil de cola que desea eliminar")
        print("Recuerde incluir el caracter '%' si desea realizar un recorte del percentil de cola del histograma")
        time.sleep(3)
        aux1 = tram
        control = False
        while(control!=True):
            p2 = input(f"Ingrese el recorte que desea aplicar(intensidad o percentil): ").strip().lower()        
            aux2 = lut_and_clipping_manager(subtraction,p2, lut='jet')
            print("Se grafican el tram con el recorte anterior y el actual")
            comparar_percentiles(aux1, aux2, p1, p2, "Comparar recorte de percentiles RGB")
            resp2 = solicitar_respuesta_binaria("¿Desea probar otro valor?")
            if(resp2 == True):
                p1=p2
                aux1 = aux2
            else:
                control = True
        resp3 = solicitar_respuesta_binaria("¿Desea utilizar último valor ingresado?")
        if(resp3==True):
            tram = aux2

        else:
            resp4 = solicitar_respuesta_binaria("¿Desea conservar el anterior? En negativo se conserva el original")
            if(resp4 == True):
                tram = aux1

    print("Se muestra la versión final del TRAM: ")
    show_sitk_image(tram, lut='jet', window_title='Rojo=Necrosis ; Azul=Tumor Activo')

    resp5 = solicitar_respuesta_binaria("¿Está conforme con el TRAM obtenido? En caso de ingresar 'NO' el proceso volverá a la etapa de registración. ")
    if resp5 == True:
        exit = True


print("Se muestran la imagen RM temprana y TRAMS: ")
compare_mri(t1_list, tram, "T1", "TRAM", "Comparacion de T1 y TRAM")
# Convertir la resta de resonancias en una imagen SimpleITK y recastearla como un entero de 16 bits
subtraction_sitk = []
for s_img in subtraction:
    sub = sitk.Cast(s_img, sitk.sitkInt16)
    subtraction_sitk.append(sub)

# Graficar el TRAM RGB y el TRAM PET-CT 
print("Se muestran el TRAM a color y la version PET-CT en escala de grises exportable a ARIA")
print("El TRAM PET-CT no se recorta ya que la LUT puede ser ajustada dentro de ARIA")
time.sleep(5)
tram_pet = subtraction_sitk
compare_mri(tram, tram_pet, "RGB", "PET format", "TRAM RGB y TRAM adaptado para PET-CT")

# Se pregunta si el usuario quiere guardar los TRAMs obtenidos
resp6 = solicitar_respuesta_binaria("¿Desea guardar el resultado RGB?")
if(resp6 == True):
    rgb_tram = []

    for img in tram:
        img_R = img[0]
        img_G = img[1]
        img_B = img[2]
        R = sitk.GetArrayFromImage(img_R)
        G = sitk.GetArrayFromImage(img_G)
        B = sitk.GetArrayFromImage(img_B)

        rgb_array = np.stack((R,G,B), axis=-1)
        rgb = sitk.GetImageFromArray(rgb_array, isVector=True)

        rgb_tram.append(rgb)
    
    rgb_to_dicom(rgb_tram, t1_metadata)

resp7 = solicitar_respuesta_binaria("¿Desea guardar el resultado como PET?")
if(resp7 == True):    
    monochrome_to_PET_dicom(tram_pet, t1_metadata, resampled_img3D, tipo_registro)

print("")
print("Gracias por utilizar NERV")
time.sleep(1)
print("Este programa se autodestruirá en:")
print("5")
time.sleep(1)
print("4")
time.sleep(1)
print("3")
time.sleep(1)
print("2")
time.sleep(1)
print("1")
time.sleep(1)