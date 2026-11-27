"""
modelo.py
Estudio de eventos: cómo reaccionan las acciones de 14 bancos europeos
en los días siguientes a cada anuncio de tipos del BCE.

Idea:
  reacción del banco = lo que se mueve el banco - lo que se mueve el mercado (Euro Stoxx 50),
                       sumado desde el día del anuncio hasta N días después
  reacción = a + b * cambio del tipo (pb)
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

INDICE = "^STOXX50E"  # Euro Stoxx 50: representa al mercado

MODELOS = ["Regresión lineal", "Ridge", "Random Forest"]

DIAS_POSIBLES = [0, 1, 3, 5, 10]  # días después del anuncio que se pueden elegir en la app


# --------------------------------------------------------------------------
# 2. DATOS
# --------------------------------------------------------------------------
def cargar_tipos():
    """Tabla del BCE: fecha de entrada en vigor y tipo de depósito (%)."""
    return pd.read_csv("data/tipos_bce.csv", parse_dates=["fecha"])


def cargar_rentabilidad_anormal():
    """Rentabilidad diaria (%) de cada banco MENOS la del Euro Stoxx 50.

    Así se quita lo que se movió todo el mercado ese día y queda solo lo propio del banco.
    """
    precios = pd.read_csv("data/precios_diarios.csv", parse_dates=["Date"], index_col="Date")
    precios = precios.ffill()  # festivos locales: se repite el precio del día anterior

    rentabilidad = precios.pct_change() * 100
    anormal = rentabilidad[list(BANCOS)].sub(rentabilidad[INDICE], axis=0)
    return anormal.dropna(how="all")


def cargar_decisiones(anormal):
    """Una fila por cada cambio de tipos: fecha del anuncio y cambio en pb."""
    tipos = cargar_tipos()
    tipos["cambio_pb"] = (tipos["tipo_dfr"].diff() * 100).round()

    # El BCE anuncia el jueves y el tipo entra en vigor el miércoles siguiente (6 días después)
    tipos["fecha_anuncio"] = tipos["fecha"] - pd.Timedelta(days=6)

    tipos = tipos.dropna()  # la primera fila no tiene cambio
    # Solo decisiones dentro del periodo con precios
    dentro = (tipos["fecha_anuncio"] >= anormal.index.min()) & (tipos["fecha_anuncio"] <= anormal.index.max())
    return tipos[dentro].reset_index(drop=True)


# --------------------------------------------------------------------------
# 3. REACCIÓN DE LAS ACCIONES A CADA ANUNCIO
# --------------------------------------------------------------------------
def reaccion(anormal, fecha_anuncio, dias):
    """Rentabilidad anormal sumada desde el día del anuncio (día 0) hasta el día `dias`."""
    inicio = anormal.index.searchsorted(fecha_anuncio)  # primer día de bolsa desde el anuncio
    ventana = anormal.iloc[inicio: inicio + dias + 1]
    return ventana.sum()


def tabla_eventos(anormal, decisiones, dias):
    """Una fila por decisión del BCE: fecha, cambio (pb) y reacción de cada banco (%)."""
    filas = []
    for _, decision in decisiones.iterrows():
        fila = reaccion(anormal, decision["fecha_anuncio"], dias)
        fila["fecha_anuncio"] = decision["fecha_anuncio"]
        fila["cambio_pb"] = decision["cambio_pb"]
        filas.append(fila)
    return pd.DataFrame(filas)


def reaccion_dia_a_dia(anormal, decisiones, ticker, dias_max=10):
    """Reacción acumulada media de un banco, día a día, separando subidas y bajadas."""
    resultado = {}
    grupos = {"Subidas de tipos": decisiones[decisiones["cambio_pb"] > 0],
              "Bajadas de tipos": decisiones[decisiones["cambio_pb"] < 0]}

    for nombre, grupo in grupos.items():
        caminos = []
        for fecha in grupo["fecha_anuncio"]:
            inicio = anormal.index.searchsorted(fecha)
            camino = anormal[ticker].iloc[inicio: inicio + dias_max + 1].cumsum()
            if len(camino) == dias_max + 1:  # solo si hay datos de todos los días
                caminos.append(camino.values)
        if caminos:
            resultado[nombre] = np.mean(caminos, axis=0)
    return resultado


# --------------------------------------------------------------------------
# 4. MODELOS
# --------------------------------------------------------------------------
def crear_modelo(nombre):
    if nombre == "Regresión lineal":
        return LinearRegression()
    if nombre == "Ridge":
        return Ridge(alpha=1.0)
    return RandomForestRegressor(n_estimators=50, max_depth=3, min_samples_leaf=3, random_state=0)


def validar(x, y, nombre):
    """Validación temporal: entrena con las decisiones pasadas y prueba con las siguientes.

    Devuelve el RMSE del modelo, el RMSE de predecir la media y el R² fuera de muestra
    (si es > 0, el modelo predice mejor que la media).
    """
    errores_modelo, errores_media = [], []
    for entreno, prueba in TimeSeriesSplit(n_splits=4).split(x):
        modelo = crear_modelo(nombre).fit(x[entreno], y[entreno])
        prediccion = modelo.predict(x[prueba])
        errores_modelo += list((y[prueba] - prediccion) ** 2)
        errores_media += list((y[prueba] - y[entreno].mean()) ** 2)

    rmse = np.sqrt(np.mean(errores_modelo))
    rmse_media = np.sqrt(np.mean(errores_media))
    r2_fuera = 1 - sum(errores_modelo) / sum(errores_media)
    return rmse, rmse_media, r2_fuera


def entrenar(eventos):
    """Entrena los 3 modelos para cada banco.

    Devuelve:
      resultados: tabla con una fila por banco (sensibilidad b, p-valor, errores...)
      modelos:    modelos[ticker][nombre_modelo] = modelo entrenado con todas las decisiones
    """
    x = eventos[["cambio_pb"]].values
    filas = []
    modelos = {}

    for ticker, (banco, pais) in BANCOS.items():
        y = eventos[ticker].values

        # Regresión lineal con estadísticos (b, error estándar, p-valor, R²)
        reg = stats.linregress(eventos["cambio_pb"], y)
        fila = {"ticker": ticker, "banco": banco, "pais": pais, "decisiones": len(y),
                "a": reg.intercept, "b": reg.slope, "error_b": reg.stderr,
                "p_valor": reg.pvalue, "r2": reg.rvalue ** 2}

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
    """Reacción esperada (%) de cada banco ante un cambio de tipos.

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