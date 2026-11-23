"""Convierte la tabla de tipos del BCE (copiada de su web a Excel) en data/tipos_bce.csv.

Se ejecuta una sola vez en local:  python preparar_tipos.py ECB_rates.xlsx
La app solo lee el CSV resultante, así que no necesita openpyxl en Render.
"""
import re
import sys

import pandas as pd

MESES = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
         "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def convertir(ruta_excel: str, ruta_csv: str = "data/tipos_bce.csv") -> pd.DataFrame:
    bruto = pd.read_excel(ruta_excel, header=None)
    filas = []
    for _, r in bruto.iterrows():
        anio, dia_mes, tipo = r[1], r[2], r[3]
        # Solo filas con un año numérico (descarta cabeceras y la nota de la fuente)
        if not re.fullmatch(r"\d{4}", str(anio).strip()):
            continue
        if isinstance(dia_mes, (pd.Timestamp,)) or hasattr(dia_mes, "month"):
            # Excel convierte "10 May" en una fecha: se toman su día y mes
            fecha = pd.Timestamp(int(anio), dia_mes.month, dia_mes.day)
        else:
            m = re.match(r"(\d{1,2})\s+([A-Za-z]{3})", str(dia_mes).strip())  # "18 Sep.5" -> 18 Sep
            if not m:
                continue
            fecha = pd.Timestamp(int(anio), MESES[m.group(2)], int(m.group(1)))
        valor = float(str(tipo).replace("−", "-").replace(",", ".").strip())
        filas.append({"fecha": fecha.date(), "tipo_dfr": valor})

    tipos = pd.DataFrame(filas).sort_values("fecha").reset_index(drop=True)
    tipos.to_csv(ruta_csv, index=False)
    return tipos


if __name__ == "__main__":
    print(convertir(sys.argv[1] if len(sys.argv) > 1 else "ECB_rates.xlsx"))
