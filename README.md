# Fototeca · Cámara de Comercio de Palmira

Archivo fotográfico institucional. Monolito modular en Django con dos roles
(**superadministrador** y **usuario de consulta**), acceso por **enlace mágico**
(Supabase Auth) y almacenamiento de las imágenes en **PostgreSQL**.

---

## 1. Puesta en marcha local

```bash
cd fototeca-ccp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env                    # y completa los valores
python manage.py migrate
python manage.py crear_superadmin       # toma ADMIN_CORREO y ADMIN_CLAVE del .env
python manage.py cargar_demo            # categorías + 12 fotografías de ejemplo
python manage.py runserver
```

> Las credenciales del superadministrador viven en el `.env`
> (`ADMIN_CORREO` / `ADMIN_CLAVE`), que **no** se versiona. Cámbialas después
> del primer ingreso.

| Ruta | Qué es |
|---|---|
| `http://127.0.0.1:8000/` | Galería (requiere sesión) |
| `http://127.0.0.1:8000/cuenta/ingresar/` | Ingreso con enlace mágico |
| `http://127.0.0.1:8000/cuenta/ingresar/clave/` | Ingreso del superadministrador con contraseña |
| `http://127.0.0.1:8000/panel/` | Panel de administración |
| `http://127.0.0.1:8000/salud/` | Health-check para Railway |

> Sin `DATABASE_URL` resuelta el proyecto arranca con SQLite, para que puedas
> trabajar sin credenciales. En Railway detecta Postgres automáticamente.

### Probar el enlace mágico sin depender de Supabase

Pon `MAGIC_LINK_BACKEND=local` en el `.env`. Con `DEBUG=True` el correo se
imprime en la consola del servidor y el enlace se puede copiar y pegar en el
navegador. Es la forma más rápida de probar el flujo completo.

---

## 2. Configurar Supabase (enlace mágico en producción)

El `.env` ya trae `SUPABASE_URL`, `SUPABASE_ANON_PUBLIC` y `SUPABASE_SERVICE_ROLE`.
Falta autorizar la URL de retorno en el panel de Supabase:

1. **Authentication → URL Configuration**
   - *Site URL*: `https://tu-dominio` (o `http://127.0.0.1:8000` en pruebas).
   - *Redirect URLs*: añade `https://tu-dominio/cuenta/supabase/retorno/`
     (y `http://127.0.0.1:8000/cuenta/supabase/retorno/` para local).
     **Sin esto Supabase rechaza el enlace.**
2. **Authentication → Providers → Email**: deja habilitado *Email* y
   *Confirm email* desactivado no es necesario para magic link.
3. *(Opcional pero recomendado)* **Project Settings → Auth → SMTP Settings**:
   configura el SMTP de la Cámara. El SMTP de cortesía de Supabase limita el
   envío a unos pocos correos por hora y solo a direcciones del equipo.

La aplicación acepta las dos variantes de plantilla de correo de Supabase:

- `?token_hash=…&type=magiclink` → se verifica en el servidor (recomendada).
- `#access_token=…` → el fragmento lo reenvía la página de retorno por POST.

### Cómo queda el control de acceso

Supabase solo envía y valida el correo. **Quién puede entrar lo decide la
Fototeca**: si el correo no corresponde a un usuario activo creado por el
superadministrador, no se envía ningún enlace y, si alguien llegara con un token
válido de Supabase, la sesión se rechaza con un 403. El formulario responde
siempre el mismo mensaje exista o no la cuenta, para no revelar el padrón.

---

## 3. Despliegue en Railway

1. Crea el servicio a partir del repositorio; Railway usa `railway.json`.
2. Añade el plugin **PostgreSQL** en el mismo proyecto.
3. Variables del servicio web (`Variables`):

   ```
   DATABASE_URL = ${{Postgres.DATABASE_URL}}
   SECRET_KEY   = <cadena larga y aleatoria>
   DEBUG        = False
   SITE_URL     = https://<tu-dominio>
   ALLOWED_HOSTS = <tu-dominio>
   CSRF_TRUSTED_ORIGINS = https://<tu-dominio>
   DB_SSL_REQUIRE = True
   SUPABASE_URL / SUPABASE_ANON_PUBLIC / SUPABASE_SERVICE_ROLE
   MAGIC_LINK_BACKEND = supabase
   ```

4. El `startCommand` corre `migrate` antes de `gunicorn`. Tras el primer
   despliegue, crea el superadministrador desde la consola de Railway:

   ```bash
   python manage.py crear_superadmin --correo admin@ccpalmira.org.co
   ```

   (Si omites `--clave` se genera una y se imprime una sola vez.)

5. `healthcheckPath` apunta a `/salud/`, que verifica la conexión a la base.

---

## 4. Arquitectura

```
config/            configuración, urls raíz, wsgi/asgi
apps/
  core/            plantilla base, permisos, procesamiento de imágenes, errores
  accounts/        modelo Usuario, roles, enlaces mágicos, cliente de Supabase
  gallery/         Categoría, Fotografía, galería pública, entrega de binarios
  dashboard/       panel del superadministrador (CRUD + usuarios)
templates/  static/  imagenes-demo/
```

Cada módulo es autónomo (modelos, vistas, urls, formularios) y se comunica con
los demás solo por sus interfaces públicas: `apps.core.imagenes`,
`apps.core.permisos` y `apps.accounts.servicios`.

### Roles

| | Superadministrador | Usuario de consulta |
|---|---|---|
| Ver la galería, buscar y descargar | ✅ | ✅ |
| Ver borradores | ✅ | ❌ |
| Subir / editar / eliminar fotografías | ✅ | ❌ |
| Gestionar categorías | ✅ | ❌ |
| Autorizar y revocar usuarios | ✅ | ❌ |
| Ingreso | Enlace mágico o contraseña | Solo enlace mágico |

Un superadministrador no puede quitarse a sí mismo el rol ni deshabilitarse, y
el sistema impide quedarse sin ningún superadministrador activo.

### Las imágenes viven en Postgres

`Fotografia.imagen` y `Fotografia.miniatura` son columnas `bytea`. El sistema de
archivos de Railway es efímero: guardar el binario en la base evita perder el
archivo en cada despliegue y deja una sola fuente de verdad para los respaldos
(`pg_dump` se lleva las fotografías incluidas).

Al subir una imagen, `apps.core.imagenes.procesar()`:

1. valida que sea JPG/PNG/WEBP real y que no supere `IMAGEN_TAMANIO_MAXIMO_MB`;
2. corrige la orientación según los datos EXIF;
3. limita el ancho a `IMAGEN_ANCHO_MAXIMO` (2400 px) y comprime;
4. genera una miniatura de 640 px para la galería;
5. calcula el SHA-256, que se usa como `ETag`.

Las vistas de listado usan `defer()` sobre las columnas binarias, así que la
grilla nunca carga las imágenes desde la base; se sirven por
`/fotografia/<uuid>/archivo/<variante>/` con `ETag` y respuesta `304`.

### Buscador

`Fotografia.indice_busqueda` guarda título + descripción + categoría + año
normalizados (minúsculas, sin tildes) y se recalcula en cada `save()`. Así
«inauguración» e «inauguracion» devuelven lo mismo sin necesidad de extensiones
de Postgres. La búsqueda exige que aparezcan **todas** las palabras del término.

---

## 5. Comandos útiles

```bash
python manage.py crear_superadmin --correo <correo> [--clave <clave>]
python manage.py cargar_demo [--limpiar] [--carpeta ruta/]
python manage.py collectstatic --noinput
```

---

## 6. Variables de entorno

Ver `.env.example` para la lista completa. Las más relevantes:

| Variable | Por defecto | Para qué |
|---|---|---|
| `SECRET_KEY` | — | Firma de sesiones. **Obligatoria**: con `DEBUG=False` el proyecto no arranca sin ella. |
| `DEBUG` | `True` | Ponlo en `False` al desplegar. |
| `DATABASE_URL` | SQLite | Postgres de Railway. |
| `MAGIC_LINK_BACKEND` | `supabase` si hay credenciales | `supabase` o `local`. |
| `MAGIC_LINK_TTL_MINUTOS` | `20` | Vigencia del enlace propio de Django. |
| `GALERIA_PUBLICA` | `False` | `True` abre la galería sin iniciar sesión. |
| `IMAGEN_TAMANIO_MAXIMO_MB` | `12` | Tamaño máximo de carga. |

---

## 7. Notas de seguridad

- Los tokens de los enlaces propios se guardan **hasheados** (SHA-256); son de
  un solo uso y al usarse invalidan los demás enlaces pendientes de esa persona.
- Límite de 5 solicitudes de enlace por correo cada 15 minutos.
- Los usuarios de consulta se crean sin contraseña utilizable.
- Con `DEBUG=False` se activan HSTS, cookies `Secure` y redirección a HTTPS.
- Las fotografías se sirven con `Cache-Control: private`.

> El `.env` incluido trae credenciales reales de Supabase y Postgres: no lo
> subas al repositorio (ya está en `.gitignore`) y rota las claves si el archivo
> llegó a compartirse.
