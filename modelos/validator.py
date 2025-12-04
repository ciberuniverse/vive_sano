def json_retorno(codigo: int, mensaje_retorno: dict | str | int | list) -> dict:

    return {"codigo": codigo, "mensaje": mensaje_retorno}



def validar_caracteres(formulario_a_validar: dict, name_len_chars: dict) -> dict:
    """
    name_len_chars = {
        "nombre_en_formulario": [100, "12345@"]
    }
    """

    for key, value in formulario_a_validar:
        
        if key not in name_len_chars:
            return json_retorno(402, "Estas enviando un formulario incompleto o corrupto.")
        
        if len(value) > name_len_chars[key][0]:
            return  json_retorno(402, f"La longitud de {key} supera el maximo establecido.")
        
        if any(x not in name_len_chars[key][1] for x in value.lower()):
            return json_retorno(402, f"Estas enviando caracteres no permitidos en {key}.")
    
    return json_retorno(200, "Formulario parcialmente bien formateado.")