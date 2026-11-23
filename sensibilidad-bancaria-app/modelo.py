"""Datos y modelos: sensibilidad de 14 bancos europeos a los cambios de tipos del BCE.

Para cada banco:  rentabilidad mensual (%) = a + b · cambio del tipo (pb) + error
Se comparan regresión lineal, Ridge y Random Forest con validación temporal de
ventanas crecientes, frente a la referencia de predecir la media.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

DATA = Path(__file__).parent / "data"

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

PERIODOS = {
    "ciclo": ("Ciclo de tipos (2022-2026)", "2022-01-01"),
    "completo": ("Muestra completa (2016-2026)", "2016-05-01"),
}

NOMBRES_MODELO = {"lineal": "Regresión lineal", "ridge": "Ridge", "rf": "Random Forest"}


# ---------------------------------------------------------------- datos
def cargar_tipos() -> pd.DataFrame:
    tipos = pd.read_csv(DATA / "tipos_bce.csv", parse_dates=["fecha"])
    return tipos.sort_values("fecha").reset_index(drop=True)


def cargar_datos() -> pd.DataFrame:
    """Tabla mensual: cambio del tipo (pb) y rentabilidad (%) de cada banco.

    yfinance fecha las velas mensuales el día 1: la fila 2026-09-01 es el cierre
    de septiembre. Por eso el tipo de esa fila es el vigente a fin de ese mes.
    """
    precios = pd.read_csv(DATA / "precios_bancos.csv", parse_dates=["Date"])
    precios = precios.rename(columns={"Date": "fecha"}).set_index("fecha").sort_index()
    rent = precios.pct_change() * 100  # rentabilidad mensual en %

    tipos = cargar_tipos()
    fin_mes = rent.index + pd.offsets.MonthEnd(0)
    tipo_fin_mes = pd.merge_asof(
        pd.DataFrame({"fin_mes": fin_mes}), tipos,
        left_on="fin_mes", right_on="fecha", direction="backward",
    )["tipo_dfr"].to_numpy()

    tabla = rent.copy()
    tabla.insert(0, "tipo", tipo_fin_mes)
    # Cambio respecto al mes anterior en pb (0 en los meses sin reunión)
    tabla.insert(1, "cambio_pb", (tabla["tipo"].diff() * 100).round(0))
    return tabla.dropna(subset=["cambio_pb"]).dropna(axis=1, how="all")


def tipo_actual() -> float:
    return float(cargar_tipos()["tipo_dfr"].iloc[-1])


# ---------------------------------------------------------------- modelos
def _crear(nombre: str):
    if nombre == "lineal":
        return LinearRegression()
    if nombre == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=5.0))
    return RandomForestRegressor(n_estimators=100, min_samples_leaf=5,
                                 max_depth=3, random_state=0)


def _validar(x: np.ndarray, y: np.ndarray, nombre: str, n_splits: int = 5) -> dict:
    """Ventanas crecientes: entrena con el pasado, prueba con los meses siguientes."""
    real, pred, media = [], [], []
    for tr, te in TimeSeriesSplit(n_splits=n_splits).split(x):
        m = _crear(nombre).fit(x[tr], y[tr])
        real.append(y[te])
        pred.append(m.predict(x[te]))
        media.append(np.full(len(te), y[tr].mean()))  # referencia: la media del pasado
    real, pred, media = map(np.concatenate, (real, pred, media))
    sse, sse_ref = ((real - pred) ** 2).sum(), ((real - media) ** 2).sum()
    return {
        "rmse": float(np.sqrt(((real - pred) ** 2).mean())),
        "rmse_media": float(np.sqrt(((real - media) ** 2).mean())),
        "r2_oos": float(1 - sse / sse_ref),  # >0: mejora a predecir la media
    }


def _ols(x: np.ndarray, y: np.ndarray) -> dict:
    """Regresión lineal con error estándar, p-valor y R² dentro de muestra."""
    r = stats.linregress(x.ravel(), y)
    return {"a": r.intercept, "b": r.slope, "se_b": r.stderr,
            "p_valor": r.pvalue, "r2": r.rvalue ** 2}


def estimar(periodo: str = "ciclo") -> dict:
    """Estima los tres modelos para cada banco.

    Devuelve un dict con:
      resumen: DataFrame (una fila por banco) con coeficientes y errores
      modelos: {ticker: {nombre_modelo: modelo entrenado con toda la muestra}}
      datos:   tabla mensual usada
    """
    tabla = cargar_datos()
    tabla = tabla[tabla.index >= PERIODOS[periodo][1]]
    filas, modelos = [], {}
    for ticker, (nombre, pais) in BANCOS.items():
        if ticker not in tabla:
            continue
        d = tabla[["cambio_pb", ticker]].dropna()
        x, y = d[["cambio_pb"]].to_numpy(), d[ticker].to_numpy()

        fila = {"ticker": ticker, "banco": nombre, "pais": pais, "meses": len(d)}
        fila.update(_ols(x, y))
        for m in NOMBRES_MODELO:
            v = _validar(x, y, m)
            fila[f"rmse_{m}"], fila[f"r2oos_{m}"] = v["rmse"], v["r2_oos"]
            fila["rmse_media"] = v["rmse_media"]
        fila["mejor"] = min(NOMBRES_MODELO, key=lambda m: fila[f"rmse_{m}"])
        filas.append(fila)
        # Reentrenar con todos los datos
        modelos[ticker] = {m: _crear(m).fit(x, y) for m in NOMBRES_MODELO}

    return {"resumen": pd.DataFrame(filas).set_index("ticker"),
            "modelos": modelos, "datos": tabla}


def impacto(est: dict, cambio_pb: float, modelo: str = "lineal") -> pd.DataFrame:
    """Impacto esperado (%) de un cambio de tipos en cada banco.

    impacto = predicción(cambio) − predicción(0). En la regresión lineal es b · cambio;
    así el cálculo sirve también para Random Forest, que no tiene coeficiente b.
    modelo: 'lineal', 'ridge', 'rf' o 'mejor' (el de menor RMSE en validación).
    """
    res = est["resumen"].copy()
    valores = []
    for ticker, fila in res.iterrows():
        m = fila["mejor"] if modelo == "mejor" else modelo
        mod = est["modelos"][ticker][m]
        p = mod.predict(np.array([[cambio_pb], [0.0]]))
        valores.append((p[0] - p[1], NOMBRES_MODELO[m]))
    res["impacto"] = [v[0] for v in valores]
    res["modelo_usado"] = [v[1] for v in valores]
    # Intervalo del 95 % (solo con sentido para la regresión lineal)
    res["ic95"] = 1.96 * res["se_b"] * abs(cambio_pb)
    return res.sort_values("impacto", ascending=False)


if __name__ == "__main__":
    est = estimar("ciclo")
    cols = ["banco", "meses", "b", "p_valor", "r2", "r2oos_lineal", "r2oos_ridge", "r2oos_rf", "mejor"]
    with pd.option_context("display.width", 160, "display.float_format", "{:.3f}".format):
        print(est["resumen"][cols])
        print(impacto(est, 25)[["banco", "impacto", "ic95"]])
