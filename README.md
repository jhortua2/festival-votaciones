# Tu Voto Vallenato · Sistema Web de Votaciones

Proyecto de la asignatura **Desarrollo Web**. Es una propuesta de sistema de votaciones para el **Festival de la Leyenda Vallenata 2027**, construido con **Python + Django + MySQL + Bootstrap** (Django MVT).

> Todas las categorías, votaciones y opciones que trae el proyecto son **ejemplos ilustrativos**. El cliente no las ha aprobado. Las reglas que siguen pendientes de validación (frecuencia de voto, visibilidad de resultados, identificación del votante) quedaron **configurables**, no fijas en el código.

---

## 1. Qué necesita instalar (una sola vez)

| Programa | Versión | Dónde |
|---|---|---|
| Python | 3.11 o superior | https://www.python.org/downloads/ (en Windows marque **"Add python.exe to PATH"**) |
| MySQL Server | **8.0 o superior** | https://dev.mysql.com/downloads/installer/ (MySQL Installer). También sirve **Laragon**, que ya trae MySQL 8 |
| Un editor | — | Visual Studio Code, por ejemplo |

> **⚠️ Ojo con XAMPP:** XAMPP trae MariaDB 10.4, y Django 5.2 necesita **MySQL 8.0.11+** o **MariaDB 10.5+**. Con XAMPP las migraciones fallan con el error *"MariaDB 10.5 or later is required"*. En ese caso instale MySQL 8 o Laragon, o use el modo SQLite de la sección 6 para ir probando.

## 2. Crear la base de datos

Abra **MySQL Workbench** (o la consola de MySQL) con el usuario `root` y ejecute el archivo **`crear_bd.sql`** que viene en el proyecto. Ese archivo crea:

- la base `festival_votaciones` (con tildes y eñes: `utf8mb4`);
- el usuario `festival` con contraseña `festival2027`.

Por consola sería: `mysql -u root -p < crear_bd.sql`

## 3. Preparar el proyecto

Abra una terminal **dentro de la carpeta del proyecto** (donde está `manage.py`).

**Windows (PowerShell o CMD):**
```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Si en el paso 2 usó otro usuario o contraseña, ábralo y edítelo en el archivo `.env`.

> Si PowerShell no deja activar el entorno, ejecute una vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 4. Crear las tablas y cargar datos de ejemplo

```bash
python manage.py migrate
python manage.py cargar_demo
```

`migrate` crea todas las tablas en MySQL. `cargar_demo` crea la edición 2027, 3 categorías, 5 votaciones (abiertas, próximas, cerrada y un borrador), sus opciones, 60 votantes de prueba y unos 150 votos.

## 5. Arrancar el servidor

```bash
python manage.py runserver
```

Abra **http://127.0.0.1:8000/** en el navegador.

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | `admin@festival.test` | `Festival2027!` |
| Votante | `ana@festival.test` | `Vallenato2027!` |

- Sitio público: http://127.0.0.1:8000/
- Panel de administración de la Fundación: http://127.0.0.1:8000/panel/
- Admin técnico de Django (solo superusuario): http://127.0.0.1:8000/django-admin/

Para detener el servidor: `Ctrl + C`. Cada vez que vuelva a trabajar, active el entorno (`venv\Scripts\activate`) y ejecute `python manage.py runserver`.

Para empezar desde cero con los datos de ejemplo: `python manage.py cargar_demo --reiniciar`

## 6. Modo rápido sin MySQL (opcional)

Si todavía no tiene MySQL, en el archivo `.env` cambie `DB_ENGINE=mysql` por `DB_ENGINE=sqlite` y repita el paso 4. Los datos quedan en el archivo `db.sqlite3`. **La entrega oficial debe usar MySQL.**

## 7. Pruebas automáticas

```bash
python manage.py test
```

Son 19 pruebas de las reglas del voto: un voto por persona, voto diario, votación cerrada, opción inactiva, restricción única en la base de datos, publicar solo con 2 opciones o más, permisos del panel, registro, inicio de sesión y exportación CSV.

---

## 8. Cómo está organizado

```
festival-votaciones/
├── config/            Configuración (settings.py lee el archivo .env)
├── cuentas/           Usuario, registro e inicio de sesión          → CU-01, CU-02
├── votaciones/
│   ├── models.py      Edición, Categoría, Votación, Opción, Voto    → modelo conceptual
│   ├── servicios.py   Reglas del voto (emitir_voto)                 → CU-04, RN-02…RN-06
│   ├── views.py       Pantallas públicas                            → CU-03, CU-04
│   ├── views_panel.py Panel de administración                       → CU-05…CU-08
│   ├── management/commands/cargar_demo.py   Datos de ejemplo
│   └── tests/         Pruebas automáticas
├── auditoria/         Bitácora de acciones                          → RF-13, RNF-09
├── templates/         HTML (Bootstrap + estilo vallenato)
├── static/            CSS y Bootstrap local (funciona sin internet)
├── crear_bd.sql       Script para crear la base y el usuario
└── requirements.txt
```

### Pantallas del prototipo → URL real

| # | Pantalla | URL |
|---|---|---|
| 1 | Inicio | `/` |
| 2 | Registro | `/cuentas/registro/` |
| 3 | Inicio de sesión | `/cuentas/ingresar/` |
| 4 | Categorías | `/categorias/` |
| 5 | Votaciones disponibles | `/categorias/<id>/` |
| 6 | Detalle de la votación | `/votaciones/<id>/` |
| 7 | Opciones | `/votaciones/<id>/opciones/` |
| 8 | Confirmación | `/votaciones/<id>/confirmar/?opcion=<id>` |
| 9 | Comprobante / rechazo | `/comprobante/<código>/` |
| 10 | Panel | `/panel/` |
| 11 | Gestión de categorías | `/panel/categorias/` |
| 12 | Gestión de votaciones | `/panel/votaciones/` |
| 13 | Gestión de opciones | `/panel/votaciones/<id>/opciones/` |
| 14 | Resultados | `/panel/resultados/` |
| + | Mis votos | `/cuentas/mis-votos/` |
| + | Auditoría | `/panel/auditoria/` |

### Reglas de negocio en el código

| Regla | Dónde se cumple |
|---|---|
| RN-01 Votación → Categoría → Edición | `ForeignKey` en `votaciones/models.py` |
| RN-02 Solo se vota con la votación abierta | `Votacion.estado` se calcula con las fechas; `servicios.emitir_voto` |
| RN-04 Solo usuarios registrados votan | `@login_required` en la confirmación |
| RN-05 El voto no se modifica | No hay vista de edición; el admin de Django lo bloquea |
| RN-06 Frecuencia de voto *(pendiente)* | Campo `frecuencia` por votación + restricción única `(usuario, votación, clave_frecuencia)` en MySQL |
| RN-07 Mínimo 2 opciones para publicar | `Votacion.puede_publicarse()` |
| RN-08 Opción con votos no se elimina | `views_panel.opcion_eliminar` / inactivar con justificación |
| RN-10 Visibilidad de resultados *(pendiente)* | Campo `visibilidad` por votación |
| CHECK cierre > apertura | Restricción `cierre_posterior_apertura` en la base de datos |

## 9. Problemas comunes

| Error | Solución |
|---|---|
| `Access denied for user 'festival'` | Revise usuario y contraseña en `.env`, o ejecute de nuevo `crear_bd.sql` |
| `Unknown database 'festival_votaciones'` | No se ejecutó `crear_bd.sql` |
| `Can't connect to MySQL server on '127.0.0.1'` | El servicio de MySQL no está encendido (Laragon: "Iniciar todo"; Windows: Servicios → MySQL80) |
| `MariaDB 10.5 or later is required` | Está usando XAMPP. Vea la advertencia de la sección 1 |
| `'python' no se reconoce como un comando` | Reinstale Python marcando "Add python.exe to PATH" |
| `No module named 'django'` | Falta activar el entorno: `venv\Scripts\activate` |
| Se ve sin estilos | Revise que abrió `http://127.0.0.1:8000` y no el archivo HTML directamente |

## 10. Pendiente para las próximas entregas

- Confirmar con el cliente las reglas marcadas como *Pendiente de validación* y ajustar los valores por defecto.
- Recuperación de contraseña por correo (requiere configurar un servidor SMTP).
- Verificación de la cuenta por código (P-02) y CAPTCHA contra bots (R-01).
- Exportación a PDF y certificación de resultados (P-12).
- Despliegue en un servidor con HTTPS y `DJANGO_DEBUG=0`.
