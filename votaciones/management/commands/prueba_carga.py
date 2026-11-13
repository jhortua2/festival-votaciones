"""Prueba de carga: muchos votantes votando al mismo tiempo (Eje 4).

Uso:  py manage.py prueba_carga
      py manage.py prueba_carga --usuarios 500 --hilos 40

Crea votantes temporales y cada uno envía DOS votos casi a la vez en la misma categoría
(como si hiciera doble clic o atacara el formulario). Los votos se envían en paralelo desde
varios hilos, cada uno con su propia conexión a MySQL, como solicitudes web simultáneas.

Mide cuántos votos se aceptan y se rechazan, cuánto tarda cada uno y comprueba que:
  - cada votante quedó con exactamente un voto en la categoría;
  - no hay ninguna combinación usuario-categoría-edición repetida en toda la tabla.

Al final borra los votantes temporales, sus votos y sus registros de auditoría.
Se debe correr con MySQL: SQLite no admite escrituras simultáneas.
"""
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, connections
from django.db.models import Count

from auditoria.models import Registro
from cuentas.models import Usuario
from votaciones.models import Votacion, Voto
from votaciones.servicios import VotoRechazado, emitir_voto

PREFIJO = "carga-"
DOMINIO = "@prueba.test"


def _percentil(valores, p):
    if not valores:
        return 0.0
    orden = sorted(valores)
    k = min(len(orden) - 1, max(0, round(p / 100 * (len(orden) - 1))))
    return orden[k]


class Command(BaseCommand):
    help = "Muchos votantes votando al mismo tiempo: mide tiempos y comprueba que no haya votos duplicados."

    def add_arguments(self, parser):
        parser.add_argument("--usuarios", type=int, default=200, help="Votantes temporales (defecto 200).")
        parser.add_argument("--hilos", type=int, default=25, help="Solicitudes en paralelo (defecto 25).")
        parser.add_argument("--conservar", action="store_true", help="No borrar los votantes temporales al final.")

    def handle(self, *args, usuarios=200, hilos=25, conservar=False, **opts):
        if connection.vendor == "sqlite":
            raise CommandError("La prueba de carga necesita MySQL: SQLite no admite escrituras simultáneas.")
        if usuarios < 1 or hilos < 1:
            raise CommandError("--usuarios y --hilos deben ser mayores que cero.")

        votacion = next((v for v in Votacion.objects.filter(publicada=True, categoria__activa=True,
                                                            categoria__edicion__activa=True)
                         .exclude(modo=Votacion.Modo.JURADO).select_related("categoria")
                         if v.esta_abierta and v.opciones_activas().count() >= 2), None)
        if votacion is None:
            raise CommandError("No hay votaciones abiertas. Corra primero: py manage.py cargar_demo --reiniciar")
        opciones = list(votacion.opciones_activas())

        self._limpiar()
        clave = make_password(None)                      # sin contraseña utilizable: no pueden iniciar sesión
        Usuario.objects.bulk_create([
            Usuario(username=f"{PREFIJO}{i:05d}{DOMINIO}", email=f"{PREFIJO}{i:05d}{DOMINIO}", password=clave,
                    first_name="Carga", last_name=f"{i:05d}")
            for i in range(usuarios)
        ], batch_size=500)
        votantes = list(Usuario.objects.filter(email__startswith=PREFIJO).order_by("email"))

        # Dos solicitudes por votante, una detrás de otra en la cola: llegan prácticamente juntas.
        solicitudes = []
        for i, u in enumerate(votantes):
            solicitudes.append((u, opciones[i % len(opciones)]))
            solicitudes.append((u, opciones[(i + 1) % len(opciones)]))

        self.stdout.write(f"Motor: {connection.vendor} ({connection.settings_dict['NAME']})")
        self.stdout.write(f"Votación: {votacion.categoria.nombre} · {votacion.nombre}")
        self.stdout.write(f"{usuarios} votantes · {len(solicitudes)} solicitudes · {hilos} en paralelo\n")

        def votar(par):
            usuario, opcion = par
            inicio = time.perf_counter()
            try:
                emitir_voto(usuario, opcion.pk)
                estado = "aceptado"
            except VotoRechazado:
                estado = "rechazado"
            except Exception as e:  # noqa: BLE001 - se cuenta como error y se muestra
                estado = f"error: {type(e).__name__}: {e}"
            finally:
                connections.close_all()
            return estado, (time.perf_counter() - inicio) * 1000

        inicio_total = time.perf_counter()
        with ThreadPoolExecutor(max_workers=hilos) as pool:
            resultados = list(pool.map(votar, solicitudes))
        total_s = time.perf_counter() - inicio_total

        tiempos = [ms for _, ms in resultados]
        aceptados = sum(1 for e, _ in resultados if e == "aceptado")
        rechazados = sum(1 for e, _ in resultados if e == "rechazado")
        errores = [e for e, _ in resultados if e.startswith("error")]

        con_un_voto = (Voto.objects.filter(usuario__in=votantes, categoria=votacion.categoria)
                       .values("usuario").annotate(n=Count("id")))
        por_usuario = [f["n"] for f in con_un_voto]
        repetidos = (Voto.objects.values("usuario", "categoria", "edicion").annotate(n=Count("id"))
                     .filter(n__gt=1).count())

        self.stdout.write("Resultados")
        self.stdout.write(f"  Solicitudes aceptadas:  {aceptados}")
        self.stdout.write(f"  Solicitudes rechazadas: {rechazados}  (segundo voto del mismo votante en la categoría)")
        self.stdout.write(f"  Errores:                {len(errores)}")
        for e in sorted(set(errores))[:5]:
            self.stdout.write(f"    · {e}")
        self.stdout.write(f"  Tiempo total:           {total_s:.2f} s  ·  {len(solicitudes) / total_s:.1f} solicitudes por segundo")
        self.stdout.write(f"  Tiempo por solicitud:   promedio {statistics.mean(tiempos):.0f} ms · "
                          f"mediana {_percentil(tiempos, 50):.0f} ms · p95 {_percentil(tiempos, 95):.0f} ms · "
                          f"máximo {max(tiempos):.0f} ms")
        self.stdout.write(f"  Votantes con exactamente 1 voto: {por_usuario.count(1)} de {usuarios}")
        self.stdout.write(f"  Combinaciones repetidas en toda la tabla: {repetidos}\n")

        aprobada = (aceptados == usuarios and por_usuario.count(1) == usuarios and len(por_usuario) == usuarios
                    and repetidos == 0 and not errores)
        if aprobada:
            self.stdout.write(self.style.SUCCESS(
                f"PRUEBA DE CARGA APROBADA: {usuarios} votantes simultáneos, un voto cada uno y cero duplicados."))
        else:
            self.stdout.write(self.style.ERROR("PRUEBA DE CARGA CON FALLAS: revise los errores de arriba."))

        if not conservar:
            self._limpiar()
            self.stdout.write("Votantes temporales, sus votos y su auditoría eliminados.")

    def _limpiar(self):
        temporales = Usuario.objects.filter(email__startswith=PREFIJO, email__endswith=DOMINIO)
        Voto.objects.filter(usuario__in=temporales).delete()
        Registro.objects.filter(usuario__in=temporales).delete()
        temporales.delete()
