"""
app.py
Aplicación web: cómo reaccionan 14 bancos europeos a los anuncios de tipos del BCE.

En local:   python3 app.py   ->  abrir http://127.0.0.1:8050
En Render:  gunicorn app:server --workers 1 --timeout 120
"""
import plotly.graph_objects as go
from dash import Dash, Input, Output, ctx, dash_table, dcc, html

import modelo

# --------------------------------------------------------------------------
# 1. DATOS Y MODELOS (se calculan una sola vez, al arrancar la app)
# --------------------------------------------------------------------------
print("Cargando datos y entrenando modelos...")
anormal = modelo.cargar_rentabilidad_anormal()
decisiones = modelo.cargar_decisiones(anormal)
tipos = modelo.cargar_tipos()

# Para cada número de días: tabla de eventos, resultados y modelos
eventos, resultados, modelos = {}, {}, {}
for dias in modelo.DIAS_POSIBLES:
    eventos[dias] = modelo.tabla_eventos(anormal, decisiones, dias)
    resultados[dias], modelos[dias] = modelo.entrenar(eventos[dias])
print("Modelos listos.")

TIPO_ACTUAL = tipos["tipo_dfr"].iloc[-1]  # último tipo del BCE (2,50 %)

AZUL = "#2a78d6"     # el banco sube / subidas de tipos
ROJO = "#d0473b"     # el banco baja
NARANJA = "#e08a1e"  # bajadas de tipos
GRIS = "#9a9893"


def num(x, decimales=2, signo=False):
    """Escribe un número con coma decimal: 2.5 -> '2,50'  |  signo=True -> '+2,50'."""
    texto = f"{x:+.{decimales}f}" if signo else f"{x:.{decimales}f}"
    return texto.replace(".", ",")


def texto_dias(dias):
    return "el mismo día del anuncio" if dias == 0 else f"del anuncio a {dias} días después"

# --------------------------------------------------------------------------
# 2. GRÁFICOS
# --------------------------------------------------------------------------
def grafico_impacto(tabla, ticker_elegido, cambio_pb, mostrar_intervalo):
    """Barras horizontales con la reacción esperada de cada banco."""
    colores = [AZUL if v >= 0 else ROJO for v in tabla["impacto"]]
    opacidad = [1 if t == ticker_elegido else 0.35 for t in tabla.index]  # resalta el banco elegido

    fig = go.Figure(go.Bar(
        x=tabla["impacto"],
        y=tabla["banco"],
        orientation="h",
        marker=dict(color=colores, opacity=opacidad),
        error_x=dict(array=tabla["ic95"], visible=mostrar_intervalo, color=GRIS),
        hovertemplate="%{y}: %{x:+.2f} %<extra></extra>",
    ))
    fig.update_layout(
        height=520, margin=dict(l=10, r=20, t=10, b=40), plot_bgcolor="white", separators=",.",
        xaxis_title=f"Reacción esperada frente al mercado ante {num(cambio_pb, 0, True)} pb (%)",
    )
    fig.add_vline(x=0, line_color="black", line_width=1)
    return fig


def grafico_dia_a_dia(ticker):
    """Cómo se va ajustando el precio del banco en los 10 días siguientes al anuncio."""
    caminos = modelo.reaccion_dia_a_dia(anormal, decisiones, ticker)
    colores = {"Subidas de tipos": AZUL, "Bajadas de tipos": NARANJA}

    fig = go.Figure()
    for nombre, valores in caminos.items():
        fig.add_trace(go.Scatter(x=list(range(len(valores))), y=valores, mode="lines+markers",
                                 name=nombre, line=dict(color=colores[nombre], width=2),
                                 hovertemplate="Día %{x}: %{y:+.2f} %<extra></extra>"))
    fig.add_hline(y=0, line_color="black", line_width=1)
    fig.update_layout(
        height=440, margin=dict(l=10, r=20, t=40, b=40), plot_bgcolor="white", separators=",.",
        xaxis_title="Días de bolsa después del anuncio (0 = día del anuncio)",
        yaxis_title="Reacción acumulada media frente al mercado (%)",
        legend=dict(orientation="h", y=1.1),
    )
    return fig


def grafico_banco(ticker, dias):
    """Barras: qué hizo el banco frente al mercado después de cada decisión del BCE."""
    tabla = eventos[dias]
    colores = [AZUL if c > 0 else NARANJA for c in tabla["cambio_pb"]]  # azul = subida, naranja = bajada
    etiquetas = [f"{c:+.0f} pb" for c in tabla["cambio_pb"]]

    fig = go.Figure(go.Bar(
        x=tabla["fecha_anuncio"].dt.strftime("%d/%m/%Y"),
        y=tabla[ticker],
        marker_color=colores,
        text=etiquetas,
        textposition="outside",
        hovertemplate="%{x} (%{text})<br>Reacción: %{y:+.2f} %<extra></extra>",
    ))
    fig.add_hline(y=0, line_color="black", line_width=1)
    fig.update_layout(
        height=460, margin=dict(l=10, r=20, t=20, b=80), plot_bgcolor="white", separators=",.",
        xaxis_title="Fecha del anuncio del BCE",
        yaxis_title="Reacción frente al mercado (%)",
    )
    return fig


def grafico_tipos():
    """Evolución del tipo de depósito del BCE."""
    fig = go.Figure(go.Scatter(x=tipos["fecha"], y=tipos["tipo_dfr"], mode="lines+markers",
                               line=dict(color=AZUL, shape="hv")))
    fig.update_layout(height=380, margin=dict(l=10, r=20, t=10, b=40), plot_bgcolor="white",
                      yaxis_title="Facilidad de depósito (%)", separators=",.")
    return fig


# --------------------------------------------------------------------------
# 3. DISEÑO DE LA PÁGINA
# --------------------------------------------------------------------------
app = Dash(__name__, title="Sensibilidad bancaria al BCE")
server = app.server  # lo usa gunicorn en Render

opciones_bancos = [{"label": banco, "value": ticker} for ticker, (banco, pais) in modelo.BANCOS.items()]
opciones_dias = [{"label": "Mismo día" if d == 0 else f"{d} días", "value": d} for d in modelo.DIAS_POSIBLES]

# Panel de controles (izquierda)
panel = html.Aside(className="panel", children=[
    html.Div(className="marca", children=[html.Span("BCE"), "Sensibilidad bancaria"]),

    html.Label("Tipo al que podría llegar el BCE"),
    html.Div(id="texto-tipo", className="tipo-valor"),
    dcc.Slider(id="tipo", min=1.0, max=4.0, step=0.25, value=TIPO_ACTUAL + 0.25,
               marks={1: "1", 2: "2", 3: "3", 4: "4"}),

    html.Div(className="escenarios", children=[
        html.Button("−50 pb", id="boton-m50", className="boton"),
        html.Button("−25 pb", id="boton-m25", className="boton"),
        html.Button("Sin cambio", id="boton-0", className="boton"),
        html.Button("+25 pb", id="boton-p25", className="boton"),
        html.Button("+50 pb", id="boton-p50", className="boton"),
    ]),

    html.Label("Banco"),
    dcc.Dropdown(id="banco", options=opciones_bancos, value="SAN.MC", clearable=False),

    html.Label("Días después del anuncio"),
    dcc.RadioItems(id="dias", options=opciones_dias, value=1, className="radios"),

    html.Label("Modelo"),
    dcc.RadioItems(id="modelo", options=modelo.MODELOS, value="Regresión lineal", className="radios"),

    html.P(f"Estudio de {len(decisiones)} decisiones del BCE con precios diarios. "
           "No es asesoramiento financiero.", className="aviso"),
])

# Contenido (derecha)
contenido = html.Main(className="contenido", children=[
    html.H1("¿Cómo reaccionan los bancos europeos a los anuncios del BCE?"),
    html.Div(id="kpis", className="kpis"),

    dcc.Tabs([
        dcc.Tab(label="Impacto", children=[
            html.Div(className="dos-col", children=[
                html.Div(className="tarjeta", children=[
                    html.H3(id="titulo-impacto"),
                    html.P("Reacción = rentabilidad del banco menos la del Euro Stoxx 50. "
                           "Azul: sube · Rojo: baja · Líneas grises: intervalo del 95 % "
                           "(solo regresión lineal). Si cruza el 0, el efecto no es significativo.",
                           className="nota"),
                    dcc.Graph(id="grafico-impacto"),
                ]),
                html.Div(id="ficha", className="tarjeta ficha"),
            ]),
        ]),
        dcc.Tab(label="Día a día", children=[
            html.Div(className="tarjeta", children=[
                html.H3(id="titulo-dia-a-dia"),
                html.P("Media de todas las subidas y de todas las bajadas. Muestra si el precio "
                       "reacciona de golpe el día del anuncio o se va ajustando en los días siguientes.",
                       className="nota"),
                dcc.Graph(id="grafico-dia-a-dia"),
            ]),
        ]),
        dcc.Tab(label="Banco", children=[
            html.Div(className="tarjeta", children=[
                html.H3(id="titulo-banco"),
                html.P("Cada barra es una decisión del BCE. Azul: subida de tipos · Naranja: bajada. "
                       "Encima de cada barra, el cambio del tipo.",
                       className="nota"),
                dcc.Graph(id="grafico-banco"),
            ]),
        ]),
        dcc.Tab(label="Fiabilidad", children=[
            html.Div(className="tarjeta", children=[
                html.H3("Error fuera de muestra (validación temporal)"),
                html.P("RMSE en puntos de rentabilidad. Si el modelo no mejora el RMSE de "
                       "predecir la media, el cambio de tipos explica poco de la reacción.",
                       className="nota"),
                dash_table.DataTable(id="tabla-fiabilidad", sort_action="native",
                                     style_cell={"textAlign": "left", "padding": "8px"}),
            ]),
        ]),
        dcc.Tab(label="Tipos BCE", children=[
            html.Div(className="tarjeta", children=[
                html.H3("Tipo de la facilidad de depósito del BCE"),
                dcc.Graph(figure=grafico_tipos()),
            ]),
        ]),
    ]),
])

app.layout = html.Div(className="pagina", children=[panel, contenido])

# --------------------------------------------------------------------------
# 4. INTERACTIVIDAD (callbacks)
# --------------------------------------------------------------------------
@app.callback(
    Output("tipo", "value"),
    Input("boton-m50", "n_clicks"), Input("boton-m25", "n_clicks"), Input("boton-0", "n_clicks"),
    Input("boton-p25", "n_clicks"), Input("boton-p50", "n_clicks"),
    prevent_initial_call=True,
)
def pulsar_boton(*clics):
    """Los botones mueven el deslizador a tipo actual ± X pb."""
    saltos = {"boton-m50": -0.50, "boton-m25": -0.25, "boton-0": 0,
              "boton-p25": 0.25, "boton-p50": 0.50}
    return TIPO_ACTUAL + saltos[ctx.triggered_id]


@app.callback(
    Output("texto-tipo", "children"),
    Output("kpis", "children"),
    Output("titulo-impacto", "children"),
    Output("grafico-impacto", "figure"),
    Output("ficha", "children"),
    Output("titulo-dia-a-dia", "children"),
    Output("grafico-dia-a-dia", "figure"),
    Output("titulo-banco", "children"),
    Output("grafico-banco", "figure"),
    Output("tabla-fiabilidad", "data"),
    Input("tipo", "value"),
    Input("banco", "value"),
    Input("dias", "value"),
    Input("modelo", "value"),
)
def actualizar(tipo, ticker, dias, nombre_modelo):
    # --- Escenario
    cambio_pb = round((tipo - TIPO_ACTUAL) * 100)
    tabla = modelo.calcular_impacto(resultados[dias], modelos[dias], cambio_pb, nombre_modelo)
    fila = resultados[dias].loc[ticker]

    texto_tipo = [html.Strong(f"{num(tipo)} %"),
                  html.Span(f"{num(cambio_pb, 0, True)} pb frente al {num(TIPO_ACTUAL)} % actual")]

    # --- Indicadores de arriba
    def kpi(titulo, valor):
        return html.Div(className="kpi", children=[html.Span(titulo), html.Strong(valor)])

    mas_sube, mas_baja = tabla.iloc[-1], tabla.iloc[0]
    kpis = [
        kpi("Cambio de tipos", f"{num(cambio_pb, 0, True)} pb"),
        kpi("Bancos que suben", str((tabla["impacto"] > 0).sum())),
        kpi("Bancos que bajan", str((tabla["impacto"] < 0).sum())),
        kpi("Más beneficiado", f"{mas_sube['banco']} ({num(mas_sube['impacto'], 2, True)} %)"),
        kpi("Más perjudicado", f"{mas_baja['banco']} ({num(mas_baja['impacto'], 2, True)} %)"),
    ]

    # --- Ficha del banco elegido
    impacto_banco = tabla.loc[ticker, "impacto"]
    significativo = "Sí" if fila["p_valor"] < 0.05 else "No"
    ficha = [
        html.H3(f"{fila['banco']} · {fila['pais']}"),
        html.Div(className="dato-grande", children=[
            html.Span("Reacción esperada en el escenario"),
            html.Strong(f"{num(impacto_banco, 2, True)} %",
                        style={"color": AZUL if impacto_banco >= 0 else ROJO}),
        ]),
        html.Dl([
            html.Dt("Sensibilidad por +25 pb"), html.Dd(f"{num(fila['b'] * 25, 2, True)} %"),
            html.Dt("p-valor"), html.Dd(num(fila["p_valor"])),
            html.Dt("¿Significativo al 5 %?"), html.Dd(significativo),
            html.Dt("R² dentro de muestra"), html.Dd(f"{num(fila['r2'] * 100, 1)} %"),
            html.Dt("R² fuera de muestra"), html.Dd(f"{num(fila['R2 fuera ' + nombre_modelo] * 100, 1)} %"),
            html.Dt("Decisiones analizadas"), html.Dd(str(fila["decisiones"])),
        ]),
    ]

    # --- Tabla de fiabilidad
    tabla_fiabilidad = []
    for t, r in resultados[dias].iterrows():
        tabla_fiabilidad.append({
            "Banco": r["banco"],
            "RMSE media": round(r["RMSE media"], 2),
            "RMSE lineal": round(r["RMSE Regresión lineal"], 2),
            "RMSE Ridge": round(r["RMSE Ridge"], 2),
            "RMSE Random Forest": round(r["RMSE Random Forest"], 2),
            f"¿{nombre_modelo} mejora a la media?": "Sí" if r["R2 fuera " + nombre_modelo] > 0 else "No",
        })

    return (
        texto_tipo,
        kpis,
        f"Reacción esperada de cada banco ({texto_dias(dias)})",
        grafico_impacto(tabla, ticker, cambio_pb, nombre_modelo == "Regresión lineal"),
        ficha,
        f"{fila['banco']}: reacción en los días siguientes al anuncio",
        grafico_dia_a_dia(ticker),
        f"{fila['banco']}: reacción tras cada decisión del BCE ({texto_dias(dias)})",
        grafico_banco(ticker, dias),
        tabla_fiabilidad,
    )

    # --------------------------------------------------------------------------
# 5. main
# --------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)