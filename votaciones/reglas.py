"""Origen de cada regla de negocio (observación de la Entrega 1).

Separa lo que definió el cliente en el enunciado del proyecto de lo que propuso el equipo.
Las propuestas siguen pendientes de validación con la Fundación hasta que respondan las
preguntas de la sección 9 del documento. Cuando el cliente apruebe una regla, se cambia aquí
a APROBADA y todas las pantallas lo muestran solas.
"""
ENUNCIADO = "enunciado"   # La pide el enunciado del proyecto
APROBADA = "aprobada"     # La aprobó la Fundación después (todavía ninguna)
PROPUESTA = "propuesta"   # La propuso el equipo; pendiente de validación

REGLAS = {
    "RN-01": (ENUNCIADO, "Toda votación pertenece a una categoría y toda categoría a una edición."),
    "RN-02": (PROPUESTA, "Solo se vota con la votación abierta y dentro de sus fechas."),
    "RN-03": (PROPUESTA, "Cada voto corresponde a una sola opción de la votación."),
    "RN-04": (PROPUESTA, "Solo usuarios registrados pueden votar."),
    "RN-05": (PROPUESTA, "Un voto emitido no se puede cambiar ni anular."),
    "RN-06": (PROPUESTA, "La frecuencia de voto se configura en cada votación."),
    "RN-07": (PROPUESTA, "Una votación necesita mínimo dos opciones activas para publicarse."),
    "RN-08": (PROPUESTA, "Las opciones con votos no se eliminan, solo se inactivan con justificación."),
    "RN-09": (PROPUESTA, "Edad mínima para votar y manejo de menores de edad."),
    "RN-10": (PROPUESTA, "Visibilidad de los resultados para el público."),
    "RN-11": (PROPUESTA, "Cómo se define el resultado: voto del público independiente o combinado con el jurado."),
    "RN-12": (PROPUESTA, "Criterio de desempate."),
    "RN-13": (PROPUESTA, "Solo califican los jurados asignados a la votación."),
    "RN-14": (PROPUESTA, "Cada jurado califica una vez cada opción y no puede cambiarlo."),
    "RN-15": (PROPUESTA, "Un jurado no vota como público en la votación que califica."),
}

ETIQUETA = {ENUNCIADO: "Enunciado", APROBADA: "Aprobada", PROPUESTA: "Propuesta"}
DESCRIPCION = {
    ENUNCIADO: "Definida por el cliente en el enunciado del proyecto.",
    APROBADA: "Aprobada por la Fundación.",
    PROPUESTA: "Propuesta del equipo, pendiente de validación con la Fundación.",
}


def origen(codigo):
    """Las preguntas (P-xx) siempre están pendientes; las reglas desconocidas se tratan como propuesta."""
    if codigo.startswith("P-"):
        return PROPUESTA
    return REGLAS.get(codigo, (PROPUESTA, ""))[0]
