__author__ = 'Alejo Chacon and Facundo Main'

import itk
import SimpleITK as sitk
import time
from load_registration import load_registration_dicom
from RegisterImages.WithDicomReg import registerDicom
import tkinter as tk
from tkinter import filedialog
from back_to_slices import convert_3d_image_to_slices

# Constantes
DEFORMABLE = 1
REXTERNAL = 2
RINTERNAL = 3

# Variable de la transformacion, se utilizara para la validacion
FINAL_TRANSFORM = None
RIGID_TRANSFORM = None
DEFORMABLE_TRANSFORM = None


def recast_itk(image):
    # Convertir la imagen sitkImage a un array NumPy
    np_array = sitk.GetArrayFromImage(image)

    # Convertir el array NumPy a una imagen ITK
    itk_image = itk.GetImageFromArray(np_array)

    # Asegurarse de que sea de tipo itk.Image[itk.F, 3]
    itk_image = itk.cast_image_filter(itk_image, ttype=(type(itk_image), itk.Image[itk.F, 3]))

    return itk_image

def recast_sitk(image):
    # Convertir la imagen ITK a un array NumPy
    np_array = itk.array_view_from_image(image)

    # Convertir el array NumPy a una imagen SimpleITK
    sitk_image = sitk.GetImageFromArray(np_array)   

    # Asegurarse de que sea de tipo sitkFloat32
    sitk_image = sitk.Cast(sitk_image, sitk.sitkFloat32)

    return sitk_image


def fast_registration(fixed_image, moving_image):
    # Transformación inicial (centrar imágenes)
    initial_transform = sitk.CenteredTransformInitializer(
        sitk.Cast(fixed_image, moving_image.GetPixelID()), 
        moving_image, 
        sitk.Euler3DTransform(), 
        sitk.CenteredTransformInitializerFilter.MOMENTS
    )
    
    global RIGID_TRANSFORM

    registration_method = sitk.ImageRegistrationMethod()

    # Métrica de información mutua con más bins
    registration_method.SetMetricAsMattesMutualInformation(numberOfHistogramBins=100)

    # Estrategia de muestreo: NONE (Denso, toma todos los pixeles), REGULAR (Regular, pixeles distribuidos uniformemente),
    # RANDOM (Aleatorio, toma puntos al azar pero puede dar resultados inconsistentes)
    registration_method.SetMetricSamplingStrategy(registration_method.RANDOM)
    # Porcentaje de pixeles tomados para el muestreo (Comentar si uso muestreo denso)
    registration_method.SetMetricSamplingPercentage(0.25)

    # Interpolador lineal para precisión
    registration_method.SetInterpolator(sitk.sitkLinear)

    # Optimizador con más iteraciones y criterios de convergencia ajustados
    total_iterations = 100
    registration_method.SetOptimizerAsGradientDescent(
        learningRate=1.0, 
        numberOfIterations=total_iterations, 
        convergenceMinimumValue=1e-6, 
        convergenceWindowSize=10
    )
    
    registration_method.SetOptimizerScalesFromPhysicalShift() 

    # Transformación rígida final
    final_transform = sitk.Euler3DTransform(initial_transform)
    registration_method.SetInitialTransform(final_transform)

    # Factores de reducción de resolución y suavizado por niveles
    registration_method.SetShrinkFactorsPerLevel(shrinkFactors=[6, 3, 1])
    registration_method.SetSmoothingSigmasPerLevel(smoothingSigmas=[3, 1, 0])
    registration_method.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()

    # Ejecutar registración
    final_transform = registration_method.Execute(sitk.Cast(fixed_image, sitk.sitkFloat32), 
                                                  sitk.Cast(moving_image, sitk.sitkFloat32))

    RIGID_TRANSFORM = final_transform

    # Aplicar la transformación resultante
    resampled_image = sitk.Resample(
        moving_image, 
        fixed_image, 
        final_transform, 
        sitk.sitkLinear, 
        0.0, 
        moving_image.GetPixelID()
    )

    return resampled_image


def precise_registration(fixed_image, moving_image):
    # Transformación inicial (centrar imágenes)
    initial_transform = sitk.CenteredTransformInitializer(
        sitk.Cast(fixed_image, moving_image.GetPixelID()), 
        moving_image, 
        sitk.Euler3DTransform(), 
        sitk.CenteredTransformInitializerFilter.MOMENTS
    )
    
    registration_method = sitk.ImageRegistrationMethod()

    # Métrica de información mutua con más bins
    registration_method.SetMetricAsMattesMutualInformation(numberOfHistogramBins=300)

    # Estrategia de muestreo: NONE (Denso, toma todos los pixeles), REGULAR (Regular, pixeles distribuidos uniformemente),
    # RANDOM (Aleatorio, toma puntos al azar pero puede dar resultados inconsistentes)
    registration_method.SetMetricSamplingStrategy(registration_method.NONE)
    # Porcentaje de pixeles tomados para el muestreo (Comentar si uso muestreo denso)
    # registration_method.SetMetricSamplingPercentage(0.25)

    # Interpolador lineal para precisión
    registration_method.SetInterpolator(sitk.sitkBSpline)

    # Optimizador con más iteraciones y criterios de convergencia ajustados
    total_iterations = 600

    #registration_method.SetOptimizerAsGradientDescent(
    #    learningRate=1.0, 
    #    numberOfIterations=total_iterations, 
    #    convergenceMinimumValue=1e-10, 
    #    convergenceWindowSize=10
    #)

    registration_method.SetOptimizerAsRegularStepGradientDescent(
    learningRate=1.0, 
    minStep=1e-6, 
    numberOfIterations=total_iterations, 
    relaxationFactor=0.5,
    gradientMagnitudeTolerance=1e-4
)


    registration_method.SetOptimizerScalesFromPhysicalShift() 

    # Transformación rígida final
    final_transform = sitk.AffineTransform(fixed_image.GetDimension())
    registration_method.SetInitialTransform(final_transform)

    # Factores de reducción de resolución y suavizado por niveles
    registration_method.SetShrinkFactorsPerLevel(shrinkFactors=[4, 2, 1])
    registration_method.SetSmoothingSigmasPerLevel(smoothingSigmas=[2, 1, 0])
    registration_method.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()

    # Ejecutar registración
    final_transform = registration_method.Execute(sitk.Cast(fixed_image, sitk.sitkFloat32), 
                                                  sitk.Cast(moving_image, sitk.sitkFloat32))

    # Aplicar la transformación resultante
    resampled_image = sitk.Resample(
        moving_image, 
        fixed_image, 
        final_transform, 
        sitk.sitkLinear, 
        0.0, 
        moving_image.GetPixelID()
    )

    return resampled_image

#se agrega funcion de registracion rigida propia
def rigid_registration (fixed_image, moving_image):

    fixed_float = sitk.Cast(fixed_image, sitk.sitkFloat32)
    moving_float = sitk.Cast(moving_image, sitk.sitkFloat32)
    
    print("Iniciando transformacion rigida...")
    initial_transform = sitk.CenteredTransformInitializer(
        fixed_float,
        moving_float,
        sitk.Euler3DTransform(),
        sitk.CenteredTransformInitializerFilter.GEOMETRY
    )

    global RIGID_TRANSFORM

    # Configuracion metodo de registracion
    registration_method = sitk.ImageRegistrationMethod()
    
    # metrica
    registration_method.SetMetricAsMattesMutualInformation(numberOfHistogramBins=100)   #de 50 a 100
    registration_method.SetMetricSamplingStrategy(registration_method.RANDOM)
    registration_method.SetMetricSamplingPercentage(0.5)  # se cambia 0.2 a 0.5

    # interpolador
    registration_method.SetInterpolator(sitk.sitkLinear)

    # optimizador
    registration_method.SetOptimizerAsGradientDescent(
        learningRate = 0.5, #  ANTES ERA 1.0
        numberOfIterations = 150,   # se cambia de 100 a 150
        convergenceMinimumValue = 1e-6,
        convergenceWindowSize = 10
    )
    registration_method.SetOptimizerScalesFromPhysicalShift()

    # multi-resolution
    registration_method.SetShrinkFactorsPerLevel([4, 2, 1])
    registration_method.SetSmoothingSigmasPerLevel(smoothingSigmas=[2, 1, 0])
    registration_method.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()

    # transform inicial
    registration_method.SetInitialTransform(
        initial_transform,
        inPlace=False
    )
    before = registration_method.MetricEvaluate(fixed_float, moving_float)

    # registracion
    final_transform = registration_method.Execute(
        fixed_float,
        moving_float
    )

    RIGID_TRANSFORM = final_transform
    #print("Print de la final transform")
    #print(final_transform)
    after = registration_method.GetMetricValue()

    print("Metric before:", before)
    print("Metric after :", after)

    print(
    registration_method.GetOptimizerStopConditionDescription()
    )

    if isinstance(final_transform, sitk.CompositeTransform):
        print(
            final_transform.GetNumberOfTransforms()
        )

    #euler = final_transform.GetNthTransform(0)

    #print(euler)

    # aplicacion de registracion
    resampled_image = sitk.Resample(
        moving_image,
        fixed_image,
        final_transform,
        sitk.sitkBSpline,   # aca estaba Affine y se poone Bspline interpolador final del resampleo
        0.0,
        moving_image.GetPixelID()
    )
    return resampled_image

# registracion deformable, tipo B spline
def nonrigid_registration (fixed_image, moving_image):

    # registracion rigida inicial
    resampled_image = rigid_registration (fixed_image, moving_image)
    
    global DEFORMABLE_TRANSFORM

    # conversion a float
    fixed_float = sitk.Cast(fixed_image, sitk.sitkFloat32)
    moving_float = sitk.Cast(resampled_image, sitk.sitkFloat32)

    # transformacion B spline
    print("Iniciando transformacion deformable...")
    # esto define cada cuanto quiero un punto de control muy Importante, define la grilla
    grid_physical_spacing = [40.0, 40.0, 40.0]  # 40 , 40 , 40 se cambio

    # tamano real del volumen en milimetros
    image_physical_size = [
        size * spacing
        for size, spacing in zip(
            fixed_float.GetSize(),
            fixed_float.GetSpacing()
        )
    ]

    # define la grilla en la que todo el volumen de la imagen estara divido, cuantas divisiones por dimension
    mesh_size = [
        int(image_size / grid_spacing + 0.5)
        for image_size, grid_spacing in zip(
            image_physical_size,
            grid_physical_spacing
        )
    ]

    initial_transform = sitk.BSplineTransformInitializer(
        fixed_float,
        transformDomainMeshSize = mesh_size,
        order = 3
    )

    # configuracion del metodo de registracion
    registration_method = sitk.ImageRegistrationMethod()

    # metrica
    registration_method.SetMetricAsMattesMutualInformation(numberOfHistogramBins= 50)   # 50
    registration_method.SetMetricSamplingStrategy(registration_method.RANDOM)
    registration_method.SetMetricSamplingPercentage(0.002)  #   0.001

    # interpolador
    registration_method.SetInterpolator(sitk.sitkLinear)

    # optimizador
    registration_method.SetOptimizerAsLBFGSB(
        gradientConvergenceTolerance=1e-4,  # 1e-5
        numberOfIterations = 100,  # 100
        maximumNumberOfCorrections = 4, # 5
        maximumNumberOfFunctionEvaluations = 200, # puede ir 1000 o 200
        costFunctionConvergenceFactor = 1e+6  # 1e+7
    )

    # Transformada inicial
    registration_method.SetInitialTransform(
        initial_transform,
        inPlace=False
    )

    # Multi-resolution
    registration_method.SetShrinkFactorsPerLevel([4,2,1])  # 4, 2, 1
    registration_method.SetSmoothingSigmasPerLevel([2,1,0]) # 2, 1, 0
    registration_method.SmoothingSigmasAreSpecifiedInPhysicalUnitsOn()

    before = registration_method.MetricEvaluate(fixed_float, moving_float)

    # ejecutar registracion
    final_transform = registration_method.Execute(
        fixed_float,
        moving_float
    )

    DEFORMABLE_TRANSFORM = final_transform
    
    after = registration_method.GetMetricValue()

    print("Metric before:", before)
    print("Metric after :", after)

    print(
    registration_method.GetOptimizerStopConditionDescription()
    )

    print(
    registration_method.GetOptimizerStopConditionDescription()
    )

    if isinstance(final_transform, sitk.CompositeTransform):
        print(
            final_transform.GetNumberOfTransforms()
        )


    # resample final
    resampled_image = sitk.Resample(
        resampled_image,
        fixed_image,
        final_transform,
        sitk.sitkLinear,
        0.0,
        moving_image.GetPixelID()
    )

    return resampled_image

# cambio en la funcion registrarion_tool. Se devuelve la imagen volumentrica 3D resampleada
# esto se hace para despues obtener los parametros asociados al Spacing, Origin y DIrection
# para poder realizar la escritura de los TAGs Dicom de manera correcta

def registration_tool(t1_image, t1_metadata, t2_image, t2_metadata):
    """ 
    Permite al usuario elegir entre todas las opciones de registro disponibles: Externo,  cual requiere de un archivo DICOM 
    con una matriz de transformación; o Interno, el cual aplica uno de los algoritmos de registración disponibles (registro 
    rápido pero poco exacto o registro preciso pero con costo computacional alto). Recibe dos variables con matrices 3D con los
    cortes de las resonancias en t1 y t2, junto con sus metadatos y devuelve dos listas con los cortes de los estudios, uno de los
    cuales ha sido registrado respecto del otro 
    
    Parámeters:
    :param t1_image: variable con una matriz tridimensional de los cortes del estudio obtenida a los 5 minutos de la inyección de contraste
    :param t1_metadata: metadatos de la resonancia t1
    :param t2_image: variable con una matriz tridimensional de los cortes del estudio obtenida a los 70-100 minutos de la inyección de contraste
    :param t2_metadata: metadatos de la resonancia t2
    
    Returns:
    :param t1_list: stack de los cortes de la resonancia t1
    :param t2_list: stack de los cortes de la resonancia t2
    """

    aux = False
    # Creo un bucle que me permita elegir el tipo de registro que deseo aplicar (interna, externa, rápida o precisa)
    while (aux == False):
        resp0 = input("Ingrese el tipo de registracion deseado (RIGIDA/DEFORMABLE): ").strip().lower()

        if resp0 in ['deformable', 'def', 'deform']:
            print("Se aplicara registro deformable a las imagenes")
            resampled3D = nonrigid_registration(t1_image, t2_image)          
            t1_list = convert_3d_image_to_slices(t1_image)
            t2_list = convert_3d_image_to_slices(resampled3D)
            aux = True
            tipo_registro = DEFORMABLE       #deformable

        elif resp0 in ['rigida', 'rigid', 'rig']:

            resp1 = input("Ingrese el tipo de registro deseado (INTERNA/EXTERNA):").strip().lower()

            if resp1 in ['externo', 'externa', 'ext']:
                # Cargo el archivo de registración
                print("Seleccione el archivo de registro")
                dicom_registration = load_registration_dicom()

                # Defino cual es la imagen fija y cual la móvil
                print("Para aplicar la matriz de registro es necesario saber sobre cual de las resonancias se aplicó la transformación.")
                resp2 = input("¿Cuál de las resonancias es la fija? (TEMPRANA/t1 o TARDÍA/t2): ").strip().lower()
                if resp2 in ['temprana', 't1']:
                    print("Aguarde mientras se registran los estudios")
                    # Aplico la matriz de registración
                    resampled3D = registerDicom(t1_image, t2_image, t2_metadata[0].get("0020|000e"), dicom_registration)
                    # Divido los stacks de resonancias en cortes individuales
                    t1_list = convert_3d_image_to_slices(t1_image)
                    t2_list = convert_3d_image_to_slices(resampled3D)
                    # Aplico condicion de salida del bucle
                    aux = True
                    t1_image = t1_image
                    tipo_registro = REXTERNAL   # 2 rigida externa


                elif resp2 in ['tardía', 'tardia', 't2']:       #luego modificar el resto de metodos
                    print("Aguarde mientras se registran los estudios")
                    # Aplico la matriz de registración
                    resampled3D = registerDicom(t2_image, t1_image, t1_metadata[0].get("0020|000e"), dicom_registration)
                    # Divido los stacks de resonancias en cortes individuales
                    t1_list = convert_3d_image_to_slices(resampled3D)
                    t2_list = convert_3d_image_to_slices(t2_image)
                    # Aplico condicion de salida del bucle
                    aux = True
                    tipo_registro = REXTERNAL   # 2 rigida externa

                else:
                    print("Respuesta inválida, intente de nuevo")

            elif resp1 in ["interno", "interna", "int"]:

                # Elijo el método de registración deseado
                print("Este programa cuenta con dos estrategias de registro interno:")
                time.sleep(1)
                print("Registro rápido: se ejecuta a mayor velocidad pero puede tener errores")
                time.sleep(1)
                print("Registro preciso: es más lento pero el resultado tiene un gran grado de exactitúd")

                resp3 = input("Ingrese el método de registro deseado (Preciso/Rápido): ").strip().lower()

                if resp3 in ["rápida", "rapida", "rápido", "rapido"]:
                    print("Aguarde mientras se registran los estudios")
                    #resampled_t2 = fast_registration(t1_image, t2_image)   #la anterior implentada
                    resampled3D = rigid_registration(t1_image, t2_image)    # se cambio por la nueva
                    t1_list = convert_3d_image_to_slices(t1_image)
                    t2_list = convert_3d_image_to_slices(resampled3D)
                    aux = True
                    tipo_registro = RINTERNAL       # 3 rigida interna

                elif resp3 in ["precisa", "preciso"]:
                    print("Aguarde mientras se registran los estudios, esto puede tomar varios minutos dependiendo de la cantidad de cortes y el grado de diferencia")
                    resampled_t2 = precise_registration(t1_image, t2_image)
                    t1_list = convert_3d_image_to_slices(t1_image)
                    t2_list = convert_3d_image_to_slices(resampled_t2)
                    aux = True
                else:
                    print("Respuesta inválida, intente nuevamente")
            else:
                print("Respuesta inválida, intente nuevamente")
        else:
            print("Respuesta inválida, intente nuevamente")

    return t1_list, t2_list, t1_image, resampled3D, tipo_registro

def set_final_transform():

    global FINAL_TRANSFORM

    if (RIGID_TRANSFORM is not None and DEFORMABLE_TRANSFORM is None):
        FINAL_TRANSFORM = RIGID_TRANSFORM
        print("tranformacion rigida")
        #print(FINAL_TRANSFORM)

    elif (RIGID_TRANSFORM is not None and DEFORMABLE_TRANSFORM is not None):

        composite = sitk.CompositeTransform(3)
        composite.AddTransform(RIGID_TRANSFORM)
        composite.AddTransform(DEFORMABLE_TRANSFORM)

        FINAL_TRANSFORM = composite



def get_transform():
    set_final_transform()
    return FINAL_TRANSFORM