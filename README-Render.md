# Despliegue en Render – Gestión Talleres

## 1) Prepara el repo
1. Coloca estos archivos en la **raíz** junto a tu `app.py`, carpeta `templates/` y `static/`.
2. Asegúrate de que en `app.py` tu aplicación Flask se llame **`app`** (por ejemplo `app = Flask(__name__)`).
3. (Opcional) Crea un archivo `.env` local a partir de `.env.example`.

Estructura mínima esperada:
```
app.py
templates/
static/
Procfile
requirements.txt
wsgi.py
render.yaml
```

## 2) Sube a GitHub
```bash
git init
git add .
git commit -m "Deploy inicial a Render"
git branch -M main
git remote add origin https://github.com/<tu-usuario>/<tu-repo>.git
git push -u origin main
```

## 3) Crea el servicio en Render
1. Entra a https://render.com → New + → **Web Service**.
2. Conecta tu repositorio.
3. Render detectará `requirements.txt` y usará `render.yaml`.
4. Al finalizar el build, te dará una URL pública.

## 4) Variables de entorno (Settings → Environment)
- `SECRET_KEY`: Render la genera automáticamente gracias al `render.yaml`. Si prefieres un valor propio, edítalo.
- `FLASK_ENV`: `production`

## 5) Consideraciones
- **SQLite**: Si usas `SQLite`, el archivo `.db` se guarda en el sistema de archivos de la instancia. En el plan gratis se resetea al redeploy; para datos persistentes considera PostgreSQL en Render.
- **Archivos estáticos**: Asegúrate de referenciarlos con `url_for('static', filename='...')` en tus templates.
- **Puerto**: Render asigna el puerto vía variable `PORT`. El Procfile ya lo maneja con Gunicorn.
- **Salud** (opcional): agrega una ruta `/health` que devuelva `200` para checks de salud.

## 6) Solución de problemas
- **ImportError: can't find app** → Confirma que tu objeto Flask se llama `app` y existe en `app.py`. Gunicorn usa `wsgi:app`.
- **Plantillas no encontradas** → La carpeta `templates/` debe estar al lado de `app.py` (o configurar `template_folder`).
- **404 en estáticos** → Usa `url_for('static', filename='css/main.css')` y que `static/` exista.
- **Time-out / Crash** → Revisa los logs en Render → pestaña **Logs**.
