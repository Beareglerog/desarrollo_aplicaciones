# Sensibilidad bancaria a los tipos del BCE

Aplicación web (Dash + Plotly) que estima cómo reaccionan en bolsa 14 bancos de la zona euro
a los cambios del tipo de la facilidad de depósito del BCE.

## Estructura

```
app.py              Aplicación Dash (controles, gráficos y tablas)
modelo.py           Datos y modelos (lineal, Ridge, Random Forest + validación temporal)
preparar_tipos.py   Convierte el Excel del BCE en data/tipos_bce.csv (solo local)
data/
  tipos_bce.csv       Decisiones del BCE (fecha de entrada en vigor, tipo de depósito)
  precios_bancos.csv  Cierres mensuales ajustados de los 14 bancos (Yahoo Finance)
assets/estilo.css   Estilos (Dash los carga solo)
requirements.txt    Dependencias
render.yaml         Configuración de Render
```

## Ejecutar en local

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                      # abre http://127.0.0.1:8050
```

Para ver solo los resultados del modelo en la terminal: `python modelo.py`

## Desplegar en Render

1. Sube la carpeta a un repositorio de GitHub:
   ```bash
   git init && git add . && git commit -m "Primera versión de la app"
   git branch -M main
   git remote add origin https://github.com/<usuario>/<repo>.git
   git push -u origin main
   ```
2. En render.com: **New → Web Service** → conecta el repositorio.
3. Configuración (si no la toma de `render.yaml`):
   - Runtime: **Python**
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:server --workers 1 --timeout 120`
   - Plan: Free
4. Cada `git push` vuelve a desplegar la app.

El plan gratuito "duerme" el servicio si nadie lo visita: el primer acceso tarda en
torno a un minuto. Ábrela unos minutos antes de presentar.

## Método

- El tipo vigente a fin de cada mes se convierte en un cambio mensual en puntos básicos
  (0 en los meses sin reunión). Los precios se convierten en rentabilidades mensuales (%).
- Para cada banco: `rentabilidad = a + b · cambio_pb + error`. `b` es la sensibilidad.
- Validación con ventanas crecientes (`TimeSeriesSplit`, 5 cortes): se entrena con el
  pasado y se prueba con los meses siguientes. Se compara el RMSE con el de predecir la media.
- El impacto de un escenario es `predicción(cambio) − predicción(0)`, que en la regresión
  lineal equivale a `b · cambio` y también funciona con Random Forest.

Estimación de sensibilidad con fines académicos; no es asesoramiento financiero.
