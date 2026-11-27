"""
descargar_diarios.py
Descarga los precios DIARIOS de los 14 bancos y del Euro Stoxx 50.
Se ejecuta una sola vez en tu ordenador:  python3 descargar_diarios.py
"""
import yfinance as yf

BANCOS = ["SAN.MC", "BBVA.MC", "CABK.MC", "SAB.MC", "BKT.MC",
          "BNP.PA", "GLE.PA", "ACA.PA", "DBK.DE", "CBK.DE",
          "UCG.MI", "ISP.MI", "INGA.AS", "KBC.BR"]

INDICE = "^STOXX50E"  # Euro Stoxx 50: lo que hace el mercado en general

# Precios de cierre diarios, ajustados por dividendos
precios = yf.download(BANCOS + [INDICE], start="2016-01-01", interval="1d", auto_adjust=True)["Close"]

# Quitar días sin ningún dato
precios = precios.dropna(how="all")

precios.to_csv("data/precios_diarios.csv")
print(precios.tail())
print("Días descargados:", len(precios))