

import pandas as pd

import yfinance as yf

tickers = [
    "SAN.MC", "BBVA.MC", "CABK.MC", "SAB.MC", "BKT.MC",   # España
    "BNP.PA", "GLE.PA", "ACA.PA",                          # Francia
    "DBK.DE", "CBK.DE",                                    # Alemania
    "UCG.MI", "ISP.MI",                                    # Italia
    "INGA.AS", "KBC.BR",                                   # Países Bajos / Bélgica
]
precios = yf.download(tickers, start="2016-03-16", interval="1mo")["Close"]
precios.to_csv("data/precios_bancos.csv")
