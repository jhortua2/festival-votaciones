# Despliegue en Vercel con MySQL en TiDB Cloud (servidor público)

Guía paso a paso para publicar **Tu Voto Vallenato** en internet:

- **Vercel** ejecuta la aplicación Django, con HTTPS incluido.
- **TiDB Cloud Starter** guarda los datos: es una base de datos **compatible con MySQL**, en la nube y con conexión cifrada.

Los dos tienen plan gratis sin tarjeta de crédito y sin vencimiento. La aplicación queda en una dirección como `https://festival-votaciones.vercel.app`.

> **Seguridad:** la `DJANGO_SECRET_KEY`, la contraseña de la base y las claves de los usuarios de prueba del servidor son **nuevas** y solo se escriben en las variables de Vercel. Nunca se suben a GitHub ni se ponen en documentos. Las claves del README son públicas y **no** se usan en el servidor.

El proyecto ya trae lo necesario:

| Archivo | Para qué |
|---|---|
| `vercel.json` | Al construir corre `preparar_servidor`: migraciones, tabla de caché y datos de prueba |
| `.python-version` | Usa Python 3.12 |
| `requirements.txt` | Incluye `whitenoise` (archivos estáticos) y `certifi` (conexión cifrada a la base) |
| `config/settings.py` | Agrega solo el dominio de Vercel, cifra la conexión a MySQL con `DB_SSL=1` y guarda el bloqueo de intentos en la base con `DJANGO_CACHE_DB=1` |

---

## 1. Crear la base de datos en TiDB Cloud
1. Entra a <https://tidbcloud.com> → **Sign up** → **Continue with GitHub** (cuenta **jhortua2**).
2. Crea una instancia **Starter** (gratis). Región: la más cercana que ofrezca, por ejemplo **AWS us-east-1**.
3. Cuando esté lista, clic en **Connect**:
   - **Connect With:** General.
   - Dale **Generate Password** (o **Reset Password**). **Cópiala en un lugar seguro**: no se vuelve a mostrar.
   - Anota el **Host**, el **Port** (4000) y el **User** (algo como `xxxxxxx.root`).
4. Abre **SQL Editor** (o **Chat2Query**) y ejecuta:

   ```sql
   CREATE DATABASE festival_votaciones CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

## 2. Crear el proyecto en Vercel
1. Entra a <https://vercel.com> → **Sign Up** → **Continue with GitHub** (cuenta **jhortua2**) → plan **Hobby** (gratis).
2. **Add New… → Project** → **Import** el repositorio **jhortua2/festival-votaciones**. Si no aparece, dale permiso a Vercel sobre ese repositorio en GitHub.
3. Vercel detecta Django solo. **Todavía no le des Deploy**: primero abre **Environment Variables** (paso 3).

## 3. Variables de entorno
En la pantalla de importación, en **Environment Variables**, pega esto (Vercel acepta pegar varias líneas de una vez), cambiando lo que está en MAYÚSCULAS:

```
DB_ENGINE=mysql
DB_HOST=HOST_DE_TIDB
DB_PORT=4000
DB_USER=USUARIO_DE_TIDB
DB_PASSWORD=CONTRASEÑA_DE_TIDB
DB_NAME=festival_votaciones
DB_SSL=1

DJANGO_DEBUG=0
DJANGO_HTTPS=1
DJANGO_CACHE_DB=1
DJANGO_SECRET_KEY=PEGA_AQUI_UNA_CLAVE_LARGA_Y_ALEATORIA

DEMO_CLAVE_ADMIN=CLAVE_NUEVA_DEL_ADMINISTRADOR
DEMO_CLAVE_JURADO=CLAVE_NUEVA_DEL_JURADO
DEMO_CLAVE_VOTANTE=CLAVE_NUEVA_DEL_VOTANTE
```

- Para la clave secreta, en tu PC ejecuta `py -c "import secrets; print(secrets.token_urlsafe(50))"` y pega lo que salga.
- Las tres `DEMO_CLAVE_*` son las contraseñas de los usuarios de prueba **en el servidor**. Usa claves largas y distintas a las del README, y compártelas solo dentro del equipo. Sin ellas el servidor **no** crea los usuarios de prueba.

Ahora sí, dale **Deploy**.

## 4. Revisar el despliegue
En el proyecto → **Deployments** → el último → **Building** (registros de la construcción). Deben aparecer:
- Las migraciones aplicadas (`Applying votaciones.0004_voto_por_categoria… OK`, etc.).
- `Datos de ejemplo cargados: 1 edición, 4 categorías, 6 votaciones…`
- `Usuarios de prueba creados con las claves de las variables DEMO_CLAVE_*` (las claves **no** se imprimen).

Al terminar, Vercel muestra la dirección pública (**Visit**).

## 5. Verificar que funciona y es seguro

| Comprobación | Cómo | Resultado esperado |
|---|---|---|
| El sitio abre | `https://TU_PROYECTO.vercel.app` | Página de inicio con las categorías |
| Datos desde MySQL (TiDB) | `/api/categorias/` | JSON con las categorías |
| HTTPS obligatorio | Abrir la dirección con `http://` | Redirige a `https://` |
| Sin modo de depuración | Abrir `/no-existe/` | Página de error simple, sin código ni rutas internas |
| Panel protegido | Abrir `/panel/` sin sesión | Pide iniciar sesión |
| Claves públicas no sirven | Entrar con `admin@festival.test` y la clave del README | **No** deja entrar |
| Bloqueo de intentos | Equivocarse 5 veces con la contraseña | «Demasiados intentos fallidos…» |
| Voto completo | Registrar un votante y votar | Comprobante, y el voto aparece en **Votos registrados** |
| Datos en la base | En el SQL Editor de TiDB: `SELECT codigo, categoria_id FROM festival_votaciones.votaciones_voto;` | El voto recién hecho |
| Cabeceras de seguridad | En la terminal de tu PC: `curl -sI https://TU_PROYECTO.vercel.app` | `Strict-Transport-Security`, `X-Frame-Options: DENY` y `X-Content-Type-Options: nosniff` |

Probado antes de publicar, simulando el servidor con las mismas variables (`DJANGO_DEBUG=0`, `DJANGO_HTTPS=1`, `DJANGO_CACHE_DB=1`) y MySQL/MariaDB: `preparar_servidor` crea las tablas y la caché, el dominio de Vercel se agrega solo, el bloqueo tras 5 intentos funciona con la caché en la base, `http` redirige a `https` y salen las cabeceras de seguridad.

## 6. Actualizar después de un cambio
Cada `git push` a la rama `main` hace que Vercel vuelva a construir y publicar solo, y al construir aplica las migraciones nuevas. No hay que entrar a ningún servidor.

## 7. Datos frescos el día de la sustentación
`preparar_servidor` carga los datos de prueba **solo la primera vez**. Para dejar las votaciones abiertas con fechas nuevas:
- **Lo más fácil:** en **Panel → Votaciones → Editar**, cambiar la fecha de cierre.
- **Desde cero:** en tu PC, crea un archivo `.env.tidb` (no se sube a GitHub, porque `.env*` no se sube) con las mismas variables `DB_*` y `DEMO_CLAVE_*` del paso 3 y ejecuta en PowerShell:

  ```powershell
  Get-Content .env.tidb | ForEach-Object { if ($_ -match '^(\w+)=(.*)$') { Set-Item "env:$($matches[1])" $matches[2] } }
  py manage.py cargar_demo --reiniciar
  ```

  Esto borra votos y usuarios creados en TiDB y recrea los datos con las claves del servidor. Cierra esa terminal al terminar.

## Si la construcción falla en Vercel
- **`Access denied` o `SSL` en la conexión:** revisa `DB_HOST`, `DB_USER`, `DB_PASSWORD`, que `DB_PORT=4000` y que `DB_SSL=1`.
- **`Unknown database`:** falta el `CREATE DATABASE` del paso 1.4.
- **Error en una migración:** copia el mensaje del registro de construcción; TiDB es compatible con MySQL pero no idéntico.

## Limitaciones
- **Imágenes subidas:** las imágenes de opciones que suba el administrador no se guardan, porque Vercel no guarda archivos. Las opciones sin imagen muestran su inicial y no se ven afectadas.
- **Primera visita lenta:** si nadie entra por un rato, la primera visita tarda unos segundos mientras Vercel enciende la aplicación.
- **Prueba de carga:** el comando `prueba_carga` se corre contra MySQL en el PC; no se ejecuta en Vercel.
- **Plan gratis de TiDB:** 5 GiB de datos y un cupo mensual de consumo, más que suficiente para el proyecto.
