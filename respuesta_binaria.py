def solicitar_respuesta_binaria(pregunta):
    while True:
        respuesta = input(f"{pregunta} (sí/no): ").strip().lower()
        if respuesta in ['sí', 'si', 's', 'yes', 'y', '1']:
            return True
        elif respuesta in ['no', 'n', '0']:
            return False
        else:
            print("Por favor, ingrese una respuesta válida (sí/no).")