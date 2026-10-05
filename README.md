# Sensibilidad bancaria a los tipos del BCE

Aplicación interactiva que estima cómo reaccionan en bolsa los bancos europeos a una subida o bajada de los tipos de interés del BCE.

## Descripción

El usuario escribe un tipo de interés (por ejemplo, un 4 %) y la aplicación lo compara con el tipo actual de la facilidad de depósito del BCE (2,50 %). Con esa diferencia (4 % − 2,50 % = +150 puntos básicos) calcula cuánto se espera que suba o baje la acción de cada banco, según la sensibilidad que ese banco ha mostrado en el pasado.

La aplicación muestra:

1. **Gráfica comparativa de los 14 bancos**, con barras ordenadas de mayor ganador a mayor perdedor, que marcan los bancos en los que el modelo no es fiable.
2. **Gráfica del banco elegido**: relación entre el cambio de tipos y su rentabilidad mensual, con la recta de ajuste.
3. **Tabla de fiabilidad**: error del modelo y R² de cada banco, comparados con una estimación básica (suponer que cada mes el banco rinde lo mismo que su media).

El resultado es una **estimación de sensibilidad**, no una predicción exacta de precios ni asesoramiento financiero.

## Objetivos

- Medir con datos reales la sensibilidad de cada banco a los cambios de tipos del BCE, en vez de suponerla.
- Permitir probar escenarios (por ejemplo, «¿y si el BCE sube los tipos hasta el 4 %?») y ver al instante qué bancos ganan y cuáles pierden.
- Mostrar con honestidad la fiabilidad de cada resultado, comparando el modelo con una referencia básica.
- Practicar el ciclo completo de la asignatura: tratamiento de datos, modelo, aplicación con Dash y publicación en Render.

## Datos

| Fuente | Contenido | Uso |
|---|---|---|
| BCE | Tipo de la facilidad de depósito, con 20 cambios desde 2016. Se añade el nivel previo (−0,50 %) para incluir el primer cambio. | Variable explicativa |
| Yahoo Finance (biblioteca `yfinance`) | Precios de cierre mensuales desde junio de 2022 de 14 bancos de la zona euro | Variable a explicar (rentabilidad mensual) |

Ambas fuentes se descargan una vez y se guardan como CSV en `data/`, de modo que la aplicación publicada no depende de conexiones externas.

**Bancos incluidos**

| País | Bancos (código en Yahoo Finance) |
|---|---|
| España | Banco Santander (SAN), BBVA (BBVA), CaixaBank (CABK), Banco Sabadell (SAB), Bankinter (BKT) |
| Francia | BNP Paribas (BNP), Société Générale (GLE), Crédit Agricole (ACA) |
| Alemania | Deutsche Bank (DBK), Commerzbank (CBK) |
| Italia | UniCredit (UCG), Intesa Sanpaolo (ISP) |
| Países Bajos | ING Groep (INGA) |
| Bélgica | KBC Group (KBC) |

## Método

1. **Tratamiento de los datos.** El tipo vigente a fin de cada mes se convierte en un cambio mensual en puntos básicos (0 en los meses sin reunión). Los precios pasan a rentabilidades mensuales. Ambas tablas se unen por fecha y se revisan los huecos y las columnas vacías.
2. **Modelo.** Para cada banco: `rentabilidad mensual = a + b · cambio del tipo + error`. El coeficiente `b` es la sensibilidad del banco. Se comparan tres modelos de scikit-learn: regresión lineal, regresión con penalización (Ridge) y bosque aleatorio (Random Forest).
3. **Validación.** Solo unos 20 de los ~50 meses tienen cambio de tipos, y un único corte 75/25 dejaría en la prueba solo dos subidas (junio y septiembre de 2026). Por eso se valida con ventanas temporales crecientes (se entrena con el pasado y se prueba con los meses siguientes, sin mezclar al azar). Se miden el error medio (RMSE) y el R², y se comparan con la referencia básica de predecir la media.
4. **Escenarios.** El modelo elegido por banco se reentrena con todos los datos. Se calcula el impacto usando la diferencia con el tipo actual y la multiplica por la sensibilidad de cada banco.

## Limitaciones

- El precio de un banco depende de muchos factores además de los tipos (economía, bolsa en general, resultados, inflación, energía, política). El modelo solo usa uno y unos 50 meses, por lo que el R² será modesto.
- El mercado anticipa las decisiones del BCE.
- Las subidas de tipos coincidieron con subidas de la inflación, así que no se puede demostrar que los tipos sean la causa.
- El modelo se ajusta con cambios mensuales. Un salto como el de 2,50 % a 4 % ocurriría en varias reuniones, y se supone que los efectos se suman. Por eso la aplicación solo admite tipos entre 0 % y 4 %, los niveles vistos desde 2022.
- Se usa el precio de cierre, sin contar los dividendos.

## Plan de trabajo inicial

Se subirán versiones al repositorio.

| Fechas | | Evolución |
|---|---|---|
| 5-11 oct | Entrega de la propuesta; repositorio Github; descarga y guardado de los datos; tratamiento de los datos |
| 12-25 oct | Modelos y validación temporal; tabla de fiabilidad.| [ ] |
| 26 oct-8 nov | Primera versión de la aplicación con el campo para escribir el tipo y la gráfica comparativa de bancos; publicación en Render | 
| 9-22 nov | Resto de gráficos, diseño y mejoras (segunda variable, retardo); limpieza y orden del código | 
| 23-30 nov | Pruebas finales y ensayo de la exposición (5 min + 2 de preguntas); presentaciones el 26 y 30 de noviembre | 

## Mejora continua prevista

- Añadir la rentabilidad del índice bancario europeo como segunda variable, para separar lo que afecta a todos los bancos de lo que depende de los tipos.
- Ampliar el número de bancos o añadir el efecto sobre una hipoteca.

## Estructura del repositorio (prevista)

```
sensibilidad-bancos-bce/
├── data/              # CSV del BCE y de precios de los bancos
├── src/               # tratamiento de datos y modelos
├── app.py             # aplicación Dash
├── requirements.txt   # dependencias (para Render)
└── README.md
```

## Tecnologías

Python · pandas · scikit-learn · Plotly · Dash · Render · GitHub
