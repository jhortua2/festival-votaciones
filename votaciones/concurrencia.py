"""Prueba de concurrencia (Entrega 3 · CP-09).

Lanza varios hilos que intentan votar *al mismo tiempo* en la misma categoría con el mismo
usuario. Cada hilo usa su propia conexión a la base de datos, como dos solicitudes web
simultáneas. Gracias a la restricción única (usuario, categoría, edición) solo una gana.
"""
import threading

from django.db import connection

from .servicios import VotoRechazado, emitir_voto


def votar_en_paralelo(usuario, opciones):
    """Cada opción se envía desde un hilo distinto, todos arrancan juntos. Devuelve la lista de resultados."""
    barrera = threading.Barrier(len(opciones))
    resultados = [None] * len(opciones)

    def trabajo(i, opcion):
        try:
            barrera.wait(timeout=10)
            voto = emitir_voto(usuario, opcion.pk)
            resultados[i] = ("aceptado", voto.codigo)
        except VotoRechazado as e:
            resultados[i] = ("rechazado", e.mensaje)
        except Exception as e:  # cualquier otro error queda visible en el resultado
            resultados[i] = ("error", f"{type(e).__name__}: {e}")
        finally:
            connection.close()

    hilos = [threading.Thread(target=trabajo, args=(i, o)) for i, o in enumerate(opciones)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    return resultados
