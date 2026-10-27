__author__ = "Facundo Main"

import itk
import SimpleITK as sitk
import numpy as np
from mri_registration_tool import get_transform

# esto es cuanto esta trasladado. Ir cambiando para cada caso. Ver paper TG132
# caso traslacion y rotacion
GROUND_TRUTH_TRASLATION = [-5.07, 17.29, -18.06] # caso 2. BAD1 - BAD4
VOXEL_DIMENSIONS = [0.7, 0.7, 3.0] 
GROUND_TRUTH_ROTATION = [-5, 8, 10] 

def compute_translation_errors(ground_truth_translation, estimated_translation):
    """
    Calcula errores de registración entre la transformación
    verdadera y la estimada.

    Parameters
    ----------
    ground_truth_translation : array-like
        Traslación real aplicada [tx, ty, tz] en mm.

    estimated_translation : array-like
        Traslación obtenida por el algoritmo [tx, ty, tz] en mm.

    Returns
    -------
    dict
        Diccionario con:
        - error_x
        - error_y
        - error_z
        - euclidean_error
        - maximum_cardinal_direction_error
    """

    gt = np.array(ground_truth_translation, dtype=float)
    est = np.array(estimated_translation, dtype=float)

    errors = np.abs(gt - est)

    error_x = errors[0]
    error_y = errors[1]
    error_z = errors[2]

    euclidean_error = np.linalg.norm(errors)

    maximum_cardinal_direction_error = np.max(errors)

    return {
        "error_x": error_x,
        "error_y": error_y,
        "error_z": error_z,
        "euclidean_error": euclidean_error,
        "maximum_cardinal_direction_error":
            maximum_cardinal_direction_error
    }


def check_directional_tolerance(errors, voxel_dimensions):
    """
    Verifica tolerancias TG-132 por eje.

    Parameters
    ----------
    errors : dict
        Resultado de compute_translation_errors()

    voxel_dimensions : tuple
        (vx, vy, vz) en mm

    Returns
    -------
    dict
    """

    vx, vy, vz = voxel_dimensions

    tolerances = {
        "x": 0.5 * vx,
        "y": 0.5 * vy,
        "z": 0.5 * vz
    }

    passed = {
        "x": errors["error_x"] < tolerances["x"],
        "y": errors["error_y"] < tolerances["y"],
        "z": errors["error_z"] < tolerances["z"]
    }

    overall_pass = all(passed.values())

    return {
        "tolerances": tolerances,
        "passed": passed,
        "overall_pass": overall_pass
    }

def compute_rotation_errors(ground_truth_rotation, estimated_rotation):

    errors = np.abs(np.array(ground_truth_rotation) - np.array(estimated_rotation))
   
    return {
        "error_rx": errors[0],
        "error_ry": errors[1],
        "error_rz": errors[2],
        "maximum_rotation_error":
            np.max(errors)
    }

def check_rotation_tolerance(rotation_errors, rotation_tolerance_deg = 1.0):

    passed = {
        "rx":
            rotation_errors["error_rx"]
            <= rotation_tolerance_deg,
        "ry":
            rotation_errors["error_ry"]
            <= rotation_tolerance_deg,
        "rz":
            rotation_errors["error_rz"]
            <= rotation_tolerance_deg
    }
    overall_pass = all(
        passed.values()
    )
    return {
        "tolerance_deg":
            rotation_tolerance_deg,
        "passed":
            passed,
        "overall_pass":
            overall_pass
    }

def load_landmarks(txt_path):

    points = []

    with open(txt_path, "r") as f:

        for line in f:

            values = line.split()

            if len(values) >= 3:

                x = float(values[0])
                y = float(values[1])
                z = float(values[2])

                points.append([x,y,z])

    return np.array(points)


def transform_landmarks(points, transform):

    transformed_points = []

    for point in points:

        p = tuple(point)
        transformed = transform.TransformPoint(p)
        transformed_points.append(transformed)

    return np.array(transformed_points)

def compute_tre(transformed_points, reference_points):

    errors = np.linalg.norm(transformed_points - reference_points, axis=1)

    return errors


def run_validation(tipo_registro):      # el ripo de registro definido en mri_registration_tool #defomable 1, rigida 2
    
    if tipo_registro == 1:
        print("Validacion para la registracion deformable")
        transform = get_transform()

        moving_points = load_landmarks(r"..\TG 132\DIR Lab Data - Case 8 Part 2 of 2\case8_T50.txt") 
        fixed_points = load_landmarks(r"..\TG 132\DIR Lab Data - Case 8 Part 2 of 2\case8_T00.txt")

        transformed_points = transform_landmarks(moving_points, transform)

        errors = compute_tre(transformed_points, fixed_points)
        
        print("----- TRE RESULTS -----")
        print(f"Mean TRE: {np.mean(errors):.3f} mm")
        print(f"Std TRE: {np.std(errors):.3f} mm")
        print(f"Max TRE: {np.max(errors):.3f} mm")
        print(f"Min TRE: {np.min(errors):.3f} mm")

    else:

        transform = get_transform()

        if transform is None:
            print("No existe transformacion")
            return
        
        if isinstance(transform, sitk.CompositeTransform):
            transform = transform.GetNthTransform(0)

        estimated_translation = np.array(transform.GetTranslation())
        estimated_rotation = np.array([
            transform.GetAngleX(),
            transform.GetAngleY(),
            transform.GetAngleZ()                           
        ])

        estimated_rotation_deg = np.degrees(estimated_rotation)

        #chequeo de los datos
        print("GT: ", GROUND_TRUTH_TRASLATION)
        print("EST: ", estimated_translation)
        print("rotation")
        print("GT ", GROUND_TRUTH_ROTATION)
        print("EST: ", estimated_rotation_deg)

        traslation_errors = compute_translation_errors(GROUND_TRUTH_TRASLATION, estimated_translation)
        rotation_errors = compute_rotation_errors(GROUND_TRUTH_ROTATION, estimated_rotation_deg)

        traslation_tolerance_results = check_directional_tolerance(traslation_errors, VOXEL_DIMENSIONS)
        rotation_tolerance_results = check_rotation_tolerance(rotation_errors, rotation_tolerance_deg = 1.0)
        # ==================================
        # PRINT RESULTADOS
        # ==================================
        print("\n----- RESULTADOS -----")
        print(f"Error X: {traslation_errors['error_x']:.3f} mm")
        print(f"Error Y: {traslation_errors['error_y']:.3f} mm")
        print(f"Error Z: {traslation_errors['error_z']:.3f} mm")
        print("Maximum cardinal direction error:", f"{traslation_errors['maximum_cardinal_direction_error']:.3f} mm" )
        print("Euclidean error:", f"{traslation_errors['euclidean_error']:.3f} mm")
        print(f"Error X: {rotation_errors['error_rx']:.3f} °")
        print(f"Error Y: {rotation_errors['error_ry']:.3f} °")
        print(f"Error Z: {rotation_errors['error_rz']:.3f} °")    
        print("\n----- TOLERANCIAS -----")
        print(f"X PASS: {traslation_tolerance_results['passed']['x']}")
        print(f"Y PASS: {traslation_tolerance_results['passed']['y']}")
        print(f"Z PASS: {traslation_tolerance_results['passed']['z']}")
        print("\nOVERALL PASS:", traslation_tolerance_results["overall_pass"])
        print("\n--- Rotation ---")
        print("RX PASS:", rotation_tolerance_results["passed"]["rx"])
        print("RY PASS:", rotation_tolerance_results["passed"]["ry"])
        print("RZ PASS:", rotation_tolerance_results["passed"]["rz"])
        print("\nOVERALL PASS:", rotation_tolerance_results["overall_pass"])

def validate_subtraction_2d(fixed_list, moving_list, subtraction_list):
    
    print("Prueba de sustraccion 2d..")

    width, height = fixed_list[0].GetSize()
    prof = len(fixed_list)

    test_voxels = [
    (width//2,height//2, prof//2 - 4),
    (width//2,height//2, prof//2 - 1),
    (width//2,height//2, prof//2 + 1),
    (width//2,height//2, prof//2 + 3),
    (width//2,height//2, prof//2 + 5)
    ]
    
    for voxel in test_voxels:
        
        x, y, z = voxel
        
        fixed_slice = fixed_list[z]
        moving_slice = moving_list[z]
        subtraction_slice = subtraction_list[z]

        fixed_value = fixed_slice.GetPixel(x, y)
        moving_value = moving_slice.GetPixel(x, y)

        expected_value = moving_value - fixed_value
        obtained_value = subtraction_slice.GetPixel(x, y)

        print(f"\nVoxel: ({x}, {y}, {z})")
        print(f"Fixed      : {fixed_value}")
        print(f"Moving     : {moving_value}")
        print(f"Esperado   : {expected_value}")
        print(f"Obtenido   : {obtained_value}")

        if np.isclose(expected_value, obtained_value):
            print("Resultado: OK")
        else:
            print("Resultado: ERROR")


def validate_subtraction_3d(fixed_image, moving_image, subtraction_image):

    print("Prueba de sustraccion 3d ..")

    test_voxels = [
    (256,256,95),
    (256,256,98),
    (256,256,100),
    (256,256,102),
    (256,256,105)
    ]
    
    for voxel in test_voxels:
        
        x, y, z = voxel
        fixed_value = fixed_image.GetPixel(x, y, z)
        moving_value = moving_image.GetPixel(x, y, z)

        
        expected_value = moving_value - fixed_value
        obtained_value = subtraction_image.GetPixel(x, y, z)

        print(f"\nVoxel: ({x}, {y}, {z})")
        print(f"Fixed      : {fixed_value}")
        print(f"Moving     : {moving_value}")
        print(f"Esperado   : {expected_value}")
        print(f"Obtenido   : {obtained_value}")

        if np.isclose(expected_value, obtained_value):
            print("Resultado: OK")
        else:
            print("Resultado: ERROR")

# modificacion de la imagen 2d, modifica unos slices agregandole un cuadrado
def insert_square (original_list, intensity = 1000): 

    width, height = original_list[0].GetSize()
    num_slices = len(original_list)

    # copia de la lista origianl
    modified_list = []

    for img in original_list:
        modified_list.append(sitk.Image(img))
    
    # se genera un cuadrado de 20x20 pixeles centrado
    x0 = width // 2 - 25
    x1 = width // 2 + 25

    y0 = height // 2 - 25
    y1 = height // 2 + 25

    center_z = num_slices // 2
    z0 = center_z - 5
    z1 = center_z + 5

    for z in range (z0, z1):

        slice_img = modified_list[z]

        for y in range(y0, y1):
            for x in range(x0, x1):

                value = slice_img.GetPixel(x, y)

                slice_img.SetPixel(x, y, value + intensity)

    return modified_list        

# esta le agrega un cubo de cierta intensidad a la imagen
def insert_cube (original_image, intensity = 1000):

    modified_image = sitk.Image(original_image)

    cube_size_xy = 50
    cube_size_z = 10

    size_x, size_y, size_z = modified_image.GetSize()
    
    center_x = size_x // 2
    center_y = size_y // 2
    center_z = size_z // 2

    half_xy = cube_size_xy // 2
    half_z = cube_size_z // 2

    x0 = center_x - half_xy
    x1 = center_x + half_xy

    y0 = center_y - half_xy
    y1 = center_y + half_xy

    z0 = center_z - half_z
    z1 = center_z + half_z

    for z in range(z0, z1):
        for y in range(y0, y1):
            for x in range(x0, x1):

                value = modified_image.GetPixel(x, y, z)

                modified_image.SetPixel(
                    x,
                    y,
                    z,
                    value + intensity
                )

    return modified_image

#se trabaja con una transformacion de traslacion, paara agregarle una traslacion
def apply_translation(original_image):

    translation = sitk.TranslationTransform(3) # 3 porque es una traslacion en 3d
    translation.SetOffset([10.0, 5.0, 0.0])  # estos son valores en mm

    translated_image = sitk.Resample(
        original_image,
        original_image,
        translation,
        sitk.sitkLinear,
        0.0,
        original_image.GetPixelID()
    )

    return translated_image    

def apply_rotation(original_image):

    size = original_image.GetSize()

    # el centro de la rotacion sobre el centro fisico del volumen
    center = original_image.TransformContinuousIndexToPhysicalPoint([s/2 for s in size])

    rotation = sitk.Euler3DTransform()
    rotation.SetCenter(center)

    rotation.SetRotation(
        np.deg2rad(5),
        np.deg2rad(0),
        np.deg2rad(0)
    )

    rotated_image = sitk.Resample(
        original_image,
        original_image,
        rotation,
        sitk.sitkLinear,
        0.0,
        original_image.GetPixelID()
    )

    return rotated_image