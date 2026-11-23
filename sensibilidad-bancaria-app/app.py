"""
modelo.py
Carga los datos y entrena los modelos de cada banco.

Idea: rentabilidad mensual del banco (%) = a + b * cambio del tipo del BCE (pb)
"""
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import TimeSeriesSplit

# --------------------------------------------------------------------------
# 1. CONFIGURACIÓN
# --------------------------------------------------------------------------
BANCOS = {
    "SAN.MC": ("Banco Santander", "España"),
    "BBVA.MC": ("BBVA", "España"),
    "CABK.MC": ("CaixaBank", "España"),
    "SAB.MC": ("Banco Sabadell", "España"),
    "BKT.MC": ("Bankinter", "España"),
    "BNP.PA": ("BNP Paribas", "Francia"),
    "GLE.PA": ("Société Générale", "Francia"),
    "ACA.PA": ("Crédit Agricole", "Francia"),
    "DBK.DE": ("Deutsche Bank", "Alemania"),
    "CBK.DE": ("Commerzbank", "Alemania"),
    "UCG.MI": ("UniCredit", "Italia"),
    "ISP.MI": ("Intesa Sanpaolo", "Italia"),
    "INGA.AS": ("ING Groep", "Países Bajos"),
    "KBC.BR": ("KBC Group", "Bélgica"),
}

MODELOS = ["Regresión lineal", "Ridge", "Random Forest"]

FECHA_INICIO = "2022-01-01"  # el modelo se estima con el ciclo de tipos 2022-2026


# --------------------------------------------------------------------------
# 2. DATOS
# --------------------------------------------------------------------------
def cargar_tipos():
    """Decisiones del BCE: fecha de entrada en vigor y tipo de depósito (%)."""
    return pd.read_csv("data/tipos_bce.csv", parse_dates=["fecha"])


def cargar_datos():
    """Tabla mensual con el cambio del tipo (pb) y la rentabilidad (%) de cada banco."""
    precios = pd.read_csv("data/precios_bancos.csv", parse_dates=["Date"], index_col="Date")
    tipos = cargar_tipos()

    # Rentabilidad mensual en %
    datos = precios.pct_change() * 100

    # Tipo vigente a final de cada mes (la fila 2026-09-01 es el cierre de septiembre)
    tipo_mes = []
    for fecha in datos.index:
        fin_de_mes = fecha + pd.offsets.MonthEnd(0)
        tipo_mes.append(tipos.loc[tipos["fecha"] <= fin_de_mes, "tipo_dfr"].iloc[-1])
    datos["tipo"] = tipo_mes

    # Cambio del tipo respecto al mes anterior, en puntos básicos (0 si no hubo cambio)
    datos["cambio_pb"] = (datos["tipo"].diff() * 100).round()

    datos = datos.dropna()
    return datos[datos.index >= FECHA_INICIO]


# --------------------------------------------------------------------------
# 3. MODELOS
# --------------------------------------------------------------------------
def crear_modelo(nombre):
    if nombre == "Regresión lineal":
        return LinearRegression()
    if nombre == "Ridge":
        return Ridge(alpha=1.0)
    return RandomForestRegressor(n_estimators=100, max_depth=3, min_samples_leaf=5, random_state=0)


def validar(x, y, nombre):
    """Validación temporal: entrena con el pasado y prueba con los meses siguientes.

    Devuelve el RMSE del modelo, el RMSE de predecir la media y el R² fuera de muestra
    (si es > 0, el modelo predice mejor que la media).
    """
    errores_modelo, errores_media = [], []
    for entreno, prueba in TimeSeriesSplit(n_splits=5).split(x):
        modelo = crear_modelo(nombre).fit(x[entreno], y[entreno])
        prediccion = modelo.predict(x[prueba])
        errores_modelo += list((y[prueba] - prediccion) ** 2)
        errores_media += list((y[prueba] - y[entreno].mean()) ** 2)

    rmse = np.sqrt(np.mean(errores_modelo))
    rmse_media = np.sqrt(np.mean(errores_media))
    r2_fuera = 1 - sum(errores_modelo) / sum(errores_media)
    return rmse, rmse_media, r2_fuera


def entrenar(datos):
    """Entrena los 3 modelos para cada banco.

    Devuelve:
      resultados: tabla con una fila por banco (sensibilidad b, p-valor, errores...)
      modelos:    modelos[ticker][nombre_modelo] = modelo entrenado con todos los meses
    """
    x = datos[["cambio_pb"]].values
    filas = []
    modelos = {}

    for ticker, (banco, pais) in BANCOS.items():
        y = datos[ticker].values

        # Regresión lineal con estadísticos (b, error estándar, p-valor, R²)
        reg = stats.linregress(datos["cambio_pb"], y)
        fila = {"ticker": ticker, "banco": banco, "pais": pais, "meses": len(y),
                "a": reg.intercept, "b": reg.slope, "error_b": reg.stderr, "p_valor": reg.pvalue, "r2": reg.rvalue ** 2}

        # Validación y entrenamiento final de los 3 modelos
        modelos[ticker] = {}
        for nombre in MODELOS:
            rmse, rmse_media, r2_fuera = validar(x, y, nombre)
            fila["RMSE " + nombre] = rmse
            fila["R2 fuera " + nombre] = r2_fuera
            modelos[ticker][nombre] = crear_modelo(nombre).fit(x, y)
        fila["RMSE media"] = rmse_media

        filas.append(fila)

    return pd.DataFrame(filas).set_index("ticker"), modelos


def calcular_impacto(resultados, modelos, cambio_pb, nombre_modelo):
    """Impacto esperado (%) de un cambio de tipos en cada banco.

    impacto = predicción con el cambio - predicción sin cambio
    (en la regresión lineal es exactamente b * cambio_pb)
    """
    tabla = resultados[["banco", "pais", "b", "error_b", "p_valor"]].copy()

    impactos = []
    for ticker in tabla.index:
        modelo = modelos[ticker][nombre_modelo]
        con_cambio = modelo.predict([[cambio_pb]])[0]
        sin_cambio = modelo.predict([[0]])[0]
        impactos.append(con_cambio - sin_cambio)

    tabla["impacto"] = impactos
    tabla["ic95"] = 1.96 * tabla["error_b"] * abs(cambio_pb)  # intervalo del 95 % (lineal)
    return tabla.sort_values("impacto")


# Para probar el modelo sin la app:  python modelo.py
if __name__ == "__main__":
    datos = cargar_datos()
    resultados, modelos = entrenar(datos)
    print(resultados[["banco", "b", "p_valor", "r2", "RMSE media", "RMSE Regresión lineal"]].round(3))
    print(calcular_impacto(resultados, modelos, 25, "Regresión lineal")[["banco", "impacto"]].round(2))