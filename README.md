# Tu Voto Vallenato · Sistema Web de Votaciones

[![Pruebas](https://github.com/jhortua2/festival-votaciones/actions/workflows/pruebas.yml/badge.svg)](https://github.com/jhortua2/festival-votaciones/actions/workflows/pruebas.yml)

Proyecto de la asignatura **Desarrollo Web** (Fundación Universitaria del Área Andina). Es una propuesta de sistema de votaciones para el **Festival de la Leyenda Vallenata 2027**, construido con **Python 3.12 + Django 5.2 (patrón MVT) + MySQL 8 + Bootstrap 5**.

> **Datos de ejemplo.** Las ediciones, categorías, votaciones y opciones que trae el proyecto son **ilustrativas**; el cliente no las ha aprobado.
>
> **Reglas: enunciado vs. propuesta.** Cada regla aparece en las pantallas con su origen: **Enunciado** (la pidió el cliente en el enunciado) o **Propuesta** (la sugirió el equipo y sigue pendiente de validación con la Fundación). La lista está en [`votaciones/reglas.py`](votaciones/reglas.py).
>
> **Voto del público y jurado.** La Fundación todavía no decide si el voto del público es **independiente** del fallo del jurado o se **combina** con él (pregunta P-06). Por eso cada votación tiene un *modo de resultado* configurable. El 70 % jurado / 30 % público del modo combinado es solo una **propuesta del equipo**, no una decisión oficial.

---

## 1. Qué hay que instalar (una sola vez)

| Programa | Versión | Dónde |
|---|---|---|
| Python | 3.11 o superior | https://www.python.org/downloads/ (en Windows marque **"Add python.exe to PATH"**) o `winget install -e --id Python.Python.3.12` |
| MySQL Server | **8.0 o superior** | https://dev.mysql.com/downloads/installer/ |
| Git | cualquiera | https://git-scm.com/ |

> En Windows el comando de Python suele ser `py`; en macOS y Linux, `python3`. En esta guía se escribe `py`.
>
> **Ojo con XAMPP:** trae MariaDB 10.4 y Django 5.2 necesita MySQL 8.0.11+ o MariaDB 10.5+.

## 2. Descargar el proyecto y crear el entorno virtual

```bash
git clone https://github.com/jhortua2/festival-votaciones.git
cd festival-votaciones
py -m venv venv
```

Activar el entorno (hay que hacerlo **cada vez** que se abre una terminal nueva):

| Sistema | Comando |
|---|---|
| Windows (PowerShell) | `.\venv\Scripts\Activate.ps1` |
| Windows (CMD) | `venv\Scripts\activate` |
| macOS / Linux | `source venv/bin/activate` |

Con el entorno activo, la terminal muestra `(venv)` al inicio. Luego se instalan las librerías:

```bash
py -m pip install -r requirements.txt
```

> Si PowerShell no deja activar el entorno, ejecute una vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
> La carpeta `venv/` está en `.gitignore`: cada integrante crea la suya y no se sube a GitHub.

## 3. Crear la base de datos en MySQL

1. Abra el archivo **`crear_bd.sql`** y cambie `CAMBIE_ESTA_CLAVE` por una clave suya.
2. Ejecútelo como `root` en **MySQL Workbench** (o `mysql -u root -p < crear_bd.sql`). Crea la base `festival_votaciones` (`utf8mb4`) y el usuario `festival`.
3. Copie `.env.example` como `.env` (`copy .env.example .env` en Windows, `cp` en macOS/Linux) y escriba en `DB_PASSWORD` la misma clave del paso 1.

> **La clave real solo va en `.env`**, que está en `.gitignore` y nunca se sube al repositorio.

## 4. Crear las tablas y cargar los datos de prueba

```bash
py manage.py migrate
py manage.py cargar_demo
```

`migrate` crea todas las tablas en MySQL. `cargar_demo` carga:

- **1 edición**: 2027 (número 60, la activa). Las demás ediciones se registran desde Django Admin o el panel;
- 3 categorías y 5 votaciones (abiertas, próxima, cerrada y un borrador), con sus opciones;
- tres usuarios de prueba, uno por rol (administrador, jurado y votante), con un voto y las calificaciones del jurado en la votación cerrada;
- los dos modos de resultado: **combinado** en «Mejor canción inédita» e **independiente** en «Grupo de piloneras favorito».

Para volver a empezar desde cero: `py manage.py cargar_demo --reiniciar`

## 5. Arrancar el servidor

```bash
py manage.py runserver 8888
```

Para apagar: `Ctrl + C`.

| | URL |
|---|---|
| Sitio público | http://localhost:8888 |
| Ediciones del Festival | http://localhost:8888/ediciones/ |
| Panel de la Fundación | http://localhost:8888/panel/ |
| Panel del jurado | http://localhost:8888/jurado/ |
| Django Admin | http://localhost:8888/django-admin/ |

### Usuarios de prueba

Los crea `cargar_demo`. Son **datos de prueba** sin información real; no sirven en ningún otro sistema.

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | `admin@festival.test` | `Festival2027!` |
| Votante | `votante@festival.test` | `Vallenato2027!` |
| Jurado | `jurado@festival.test` | `Jurado2027!` |

## 6. Pruebas automáticas

```bash
py manage.py test
```

Son **47 pruebas**. Deben terminar en `OK`.

| Grupo | Qué prueban |
|---|---|
| Voto del público | Un voto por persona, voto diario, votación cerrada, opción inactiva, restricción única en la base de datos |
| Panel | Permisos, publicar solo con 2 opciones o más, exportación CSV |
| Cuentas | Registro, validaciones e inicio de sesión |
| Jurado | Calificar todas las opciones, no calificar dos veces, solo jurados asignados, escala, el jurado no vota como público |
| Modo de resultado | Independiente (no mezcla jurado y público) y combinado (aplica el peso); el 70/30 se muestra como propuesta |
| Origen de las reglas | Enunciado vs. propuesta en las etiquetas |
| Ediciones | Página pública con varias ediciones, crear y activar en el panel, año repetido, permisos |

### Evidencia reproducible en GitHub

Cada vez que alguien sube un commit, GitHub corre las pruebas solo, contra un **MySQL 8 real** ([`.github/workflows/pruebas.yml`](.github/workflows/pruebas.yml)): instala las librerías, crea las tablas, carga los datos de prueba y corre las 47 pruebas. El resultado se ve en la pestaña **Actions** del repositorio y en la insignia de arriba de este README.

## 7. Modo rápido sin MySQL (opcional)

En el archivo `.env` cambie `DB_ENGINE=mysql` por `DB_ENGINE=sqlite` y repita el paso 4. Los datos quedan en `db.sqlite3` (también ignorado por Git). **La entrega oficial usa MySQL.**

---

## 8. Cómo está organizado (patrón MVT)

```
festival-votaciones/
├── config/              Configuración: settings.py lee el archivo .env; urls.py reúne las rutas
├── cuentas/             Usuario propio con rol, registro, inicio y cierre de sesión
├── votaciones/
│   ├── models.py        Modelos: Edición → Categoría → Votación → Opción → Voto / Calificación
│   ├── reglas.py        Origen de cada regla (enunciado o propuesta)
│   ├── servicios.py     Reglas del voto y de la calificación (lógica de negocio)
│   ├── views.py         Vistas públicas          urls.py
│   ├── views_panel.py   Panel de la Fundación    urls_panel.py
│   ├── views_jurado.py  Panel del jurado         urls_jurado.py
│   ├── migrations/      Migraciones de la base de datos
│   ├── management/commands/cargar_demo.py   Datos de prueba
│   └── tests/           Pruebas automáticas
├── auditoria/           Bitácora de acciones
├── templates/           Plantillas HTML (la "T" de MVT)
├── static/              CSS y Bootstrap local
├── .github/workflows/   Pruebas automáticas en GitHub
├── crear_bd.sql         Script para crear la base y el usuario (sin clave real)
└── requirements.txt
```

### Pantallas → URL

| Pantalla | URL |
|---|---|
| Inicio | `/` |
| Ediciones del Festival | `/ediciones/` |
| Registro / Inicio de sesión | `/cuentas/registro/` · `/cuentas/ingresar/` |
| Categorías / Votaciones de una categoría | `/categorias/` · `/categorias/<id>/` |
| Detalle, opciones y confirmación | `/votaciones/<id>/` · `/votaciones/<id>/opciones/` · `/votaciones/<id>/confirmar/` |
| Comprobante / Mis votos | `/comprobante/<código>/` · `/cuentas/mis-votos/` |
| Panel | `/panel/` |
| Ediciones, categorías, votaciones y opciones | `/panel/ediciones/` · `/panel/categorias/` · `/panel/votaciones/` · `/panel/votaciones/<id>/opciones/` |
| Jurados / Resultados / Auditoría | `/panel/jurados/` · `/panel/resultados/` · `/panel/auditoria/` |
| Panel del jurado / Calificar | `/jurado/` · `/jurado/votaciones/<id>/` |

### Reglas de negocio en el código

| Regla | Origen | Dónde se cumple |
|---|---|---|
| RN-01 Votación → Categoría → Edición | Enunciado | `ForeignKey` en `votaciones/models.py` |
| RN-02 Solo se vota con la votación abierta | Propuesta | `Votacion.estado` (calculado con las fechas) y `servicios.emitir_voto` |
| RN-04 Solo usuarios registrados votan | Propuesta | `@login_required` en la confirmación |
| RN-05 El voto no se modifica | Propuesta | No hay vista de edición; Django Admin lo bloquea |
| RN-06 Frecuencia de voto | Propuesta | Campo `frecuencia` + restricción única `(usuario, votación, clave_frecuencia)` en MySQL |
| RN-07 Mínimo 2 opciones para publicar | Propuesta | `Votacion.puede_publicarse()` |
| RN-08 Opción con votos no se elimina | Propuesta | `views_panel.opcion_eliminar`; se inactiva con justificación |
| RN-10 Visibilidad de resultados | Propuesta | Campo `visibilidad` por votación |
| RN-11 Cómo se define el resultado | Propuesta | Campo `modo` (solo público, solo jurado, independiente, combinado) y `Votacion.resultados_ponderados()` |
| RN-13 Solo califican los jurados asignados | Propuesta | Campo `jurados` (asignación) y `servicios.calificar` |
| RN-14 Una calificación por jurado y opción | Propuesta | Restricción única `(jurado, opcion)` en MySQL |
| RN-15 El jurado no vota como público | Propuesta | `servicios.emitir_voto` |

Cuando la Fundación apruebe una regla, se cambia a `APROBADA` en `votaciones/reglas.py` y todas las pantallas lo muestran solas.

## 9. Atención a las observaciones de la Entrega 1

| Observación del docente | Qué se hizo |
|---|---|
| Validar si el voto del público es independiente o combinado; el 70/30 no es oficial | Modo de resultado configurable por votación (por defecto **independiente**). El 70/30 aparece como «Propuesta, no decisión oficial». Sigue la pregunta P-06 para la Fundación |
| Modelo conceptual con asignación de jurados y auditoría | Diagrama actualizado con las entidades *Asignación de jurado* y *Auditoría* |
| Diferenciar reglas del cliente de las propuestas | Etiquetas **Enunciado / Propuesta** en las pantallas y columna *Origen* en el documento y en este README |
| Acceso al repositorio y evidencias reproducibles | Repositorio público, sin inicio de sesión; pasos de instalación, datos de prueba y pruebas automáticas en GitHub Actions con MySQL |
| Interfaces que pedían credenciales | Prototipo y mockups publicados en un enlace abierto, sin inicio de sesión |

## 10. Problemas comunes

| Error | Solución |
|---|---|
| `Access denied for user 'festival'` | La clave de `.env` no coincide con la de `crear_bd.sql` |
| `Unknown database 'festival_votaciones'` | No se ejecutó `crear_bd.sql` |
| `Can't connect to MySQL server` | El servicio MySQL80 está apagado: `Start-Service MySQL80` (PowerShell como administrador) |
| `'py' no se reconoce` | Instale Python y abra una terminal nueva |
| `No module named 'django'` | Falta activar el entorno virtual (paso 2) |
| Se ve sin estilos | Abra `http://localhost:8888`, no el archivo HTML directamente |

## 11. Pendiente para las próximas entregas

- Confirmar con la Fundación las reglas marcadas como *Propuesta*, en especial el modo de resultado (P-06).
- Recuperación de contraseña por correo (requiere un servidor SMTP).
- Verificación de la cuenta por código (P-02) y CAPTCHA contra bots (R-01).
- Exportación a PDF y certificación de resultados (P-12).
- Despliegue con HTTPS y `DJANGO_DEBUG=0`.
