"""Gráficos interativos (Plotly): zoom, hover, legenda clicável."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

import isa_lib as L
import mapa as MP

AZUL, LARANJA, VERMELHO, VERDE, CINZA = "#1f77b4", "#ff7f0e", "#d62728", "#2ca02c", "#7f7f7f"
COR_FAIXA = {"Crítico": VERMELHO, "Baixo": LARANJA, "Médio": "#e6c200", "Alto": VERDE}


def _base(fig, titulo=None, altura=440):
    fig.update_layout(template="plotly_white", title=titulo, height=altura, separators=",.",
                      margin=dict(l=10, r=10, t=60 if titulo else 20, b=10), legend=dict(orientation="h", y=-0.2))
    return fig


def hist_medidas(s, nome, bins=30):
    s = s.dropna().astype(float)
    cont = np.histogram(s, bins=bins)[0]
    fig = go.Figure(go.Histogram(x=s, nbinsx=bins, marker_color=AZUL, opacity=.8, name="frequência"))
    moda = s.mode().iloc[0]
    for rot, v, cor, dash in [("Média", s.mean(), VERMELHO, "dash"), ("Mediana", s.median(), LARANJA, "solid"),
                              ("Moda", moda, VERDE, "dot")]:
        fig.add_trace(go.Scatter(x=[v, v], y=[0, cont.max() * 1.05], mode="lines",
                                 name=f"{rot} = {L.br(v, 3)}", line=dict(color=cor, dash=dash, width=3)))
    fig.update_xaxes(title=nome); fig.update_yaxes(title="Nº de sub-bacias")
    return _base(fig, f"Distribuição de {nome}")


def box_variaveis(df, cols, titulo="Boxplot (passe o mouse nos pontos)"):
    d = df[["cod_sub_bacia", "nome_bacia"] + list(cols)].melt(id_vars=["cod_sub_bacia", "nome_bacia"],
                                                                var_name="índice", value_name="valor")
    d["índice"] = d["índice"].map(L.rotulo)
    fig = px.box(d, x="valor", y="índice", points="outliers", hover_data=["cod_sub_bacia", "nome_bacia"],
                 color_discrete_sequence=[AZUL])
    fig.update_yaxes(title=None)
    return _base(fig, titulo, 420)


def barras_faixas(df):
    c = df["faixa_isa"].value_counts().reindex(list(COR_FAIXA)).fillna(0).astype(int)
    fig = go.Figure(go.Bar(x=c.index, y=c.values, marker_color=[COR_FAIXA[k] for k in c.index],
                           text=[f"{v} ({100 * v / max(c.sum(), 1):.1f}%)".replace(".", ",") for v in c.values],
                           textposition="outside"))
    fig.update_yaxes(title="Nº de sub-bacias")
    return _base(fig, "Sub-bacias por faixa de ISA (<0,5 | 0,5–0,7 | 0,7–0,9 | ≥0,9)", 380)


def heatmap_corr(corr, titulo):
    nomes = [L.rotulo(c) for c in corr.columns]
    fig = go.Figure(go.Heatmap(z=corr.values, x=nomes, y=nomes, zmin=-1, zmax=1, colorscale="RdBu_r",
                               texttemplate="%{z:.2f}", textfont=dict(size=9)))
    fig.update_yaxes(autorange="reversed")
    return _base(fig, titulo, 620)


def scatter_regressao(df, x, y, mod, cor=None, log_x=False):
    """Dispersão + reta + banda de IC95% da média + banda de predição 95%."""
    d = df.dropna(subset=[x, y])
    fig = px.scatter(d, x=x, y=y, color=cor, hover_data=["cod_sub_bacia", "nome_bacia"], opacity=.7,
                     color_discrete_map=COR_FAIXA, category_orders={"faixa_isa": list(COR_FAIXA)})
    xs = np.linspace(mod["x"].min(), mod["x"].max(), 100)
    yh, lo, hi, plo, phi = L.prever(mod, xs)
    for nome, a, b, cor_f in [("Predição 95%", plo, phi, "rgba(214,39,40,.08)"), ("IC 95% da reta", lo, hi, "rgba(214,39,40,.25)")]:
        fig.add_trace(go.Scatter(x=np.r_[xs, xs[::-1]], y=np.r_[b, a[::-1]], fill="toself", fillcolor=cor_f,
                                 line=dict(width=0), hoverinfo="skip", name=nome))
    sinal = "+" if mod["slope"] >= 0 else "−"
    fig.add_trace(go.Scatter(x=xs, y=yh, mode="lines", line=dict(color=VERMELHO, width=3),
                             name=f"ŷ = {L.br(mod['intercept'], 3)} {sinal} {L.br(abs(mod['slope']), 4)}·x"))
    fig.update_xaxes(title=L.rotulo(x), type="log" if log_x else "linear"); fig.update_yaxes(title=L.rotulo(y))
    return _base(fig, f"Regressão linear: {L.rotulo(y)} × {L.rotulo(x)} (R² = {L.br(mod['r2'], 3)})", 520)


def residuos(pred, resid):
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Resíduos × valores previstos", "Distribuição dos resíduos"))
    fig.add_trace(go.Scatter(x=pred, y=resid, mode="markers", marker=dict(color=AZUL, opacity=.6), name="resíduo"), 1, 1)
    fig.add_hline(y=0, line_dash="dash", line_color=VERMELHO, row=1, col=1)
    fig.add_trace(go.Histogram(x=resid, nbinsx=30, marker_color=LARANJA, name="resíduos"), 1, 2)
    fig.update_layout(showlegend=False)
    return _base(fig, None, 360)


def qq(s, nome):
    (osm, osr), (slope, inter, r) = stats.probplot(pd.Series(s).dropna(), dist="norm")
    fig = go.Figure(go.Scatter(x=osm, y=osr, mode="markers", marker=dict(color=AZUL, opacity=.6), name="dados"))
    fig.add_trace(go.Scatter(x=[osm.min(), osm.max()], y=[inter + slope * osm.min(), inter + slope * osm.max()],
                             mode="lines", line=dict(color=VERMELHO), name="normal"))
    fig.update_xaxes(title="Quantis teóricos (normal)"); fig.update_yaxes(title="Quantis observados")
    return _base(fig, f"Q-Q plot de {nome} (R² = {L.br(r ** 2, 3)})", 380)


def pop_vs_isa(df):
    d = df[df["populacao"] > 0]
    fig = px.scatter(d, x="populacao", y="isa", color="pop_mancha_inundacao", size="area_ha", log_x=True,
                     hover_data=["cod_sub_bacia", "nome_bacia"], color_continuous_scale="YlOrRd")
    fig.update_xaxes(title="População (escala log)"); fig.update_yaxes(title="ISA")
    return _base(fig, "População × ISA (cor = pop. em mancha de inundação, tamanho = área)", 480)


def ranking_bacias(b, n):
    b = b.dropna(subset=["isa_ponderado"]).head(n).iloc[::-1]
    fig = go.Figure(go.Bar(x=b["isa_ponderado"], y=b["bacia"], orientation="h",
                           marker_color=[VERMELHO if v < .8 else LARANJA for v in b["isa_ponderado"]],
                           customdata=np.c_[b["populacao"], b["sub_bacias"]],
                           hovertemplate="%{y}<br>ISA ponderado: %{x:.3f}<br>População: %{customdata[0]:,}<br>Sub-bacias: %{customdata[1]}<extra></extra>"))
    fig.update_xaxes(title="ISA ponderado pela população", range=[0, 1.02])
    return _base(fig, f"As {n} bacias com pior ISA (chave = id_bacia)", 120 + 28 * len(b))


def comparar_interpolacao(res, sd):
    fig = go.Figure(go.Bar(x=res.index, y=res["RMSE"], error_y=dict(type="data", array=res["RMSE (desvio entre repetições)"]),
                           marker_color=AZUL, name="RMSE"))
    fig.add_hline(y=sd, line_dash="dash", line_color=VERMELHO, annotation_text=f"desvio padrão = {L.br(sd, 4)}")
    fig.update_yaxes(title="RMSE (menor = melhor)")
    return _base(fig, "Erro ao reconstruir valores escondidos, por método", 400)


def real_vs_imputado(real, imp, nome, eixo_y="imputado", titulo="Real × imputado (uma rodada)"):
    real, imp = pd.Series(real).astype(float), pd.Series(imp).astype(float)
    lim = [min(real.min(), imp.min()), max(real.max(), imp.max())]
    fig = go.Figure(go.Scatter(x=real, y=imp, mode="markers", marker=dict(color=AZUL, opacity=.7), name="observações"))
    fig.add_trace(go.Scatter(x=lim, y=lim, mode="lines", line=dict(color=VERMELHO, dash="dash"), name="acerto perfeito"))
    fig.update_xaxes(title=f"{nome} real"); fig.update_yaxes(title=f"{nome} {eixo_y}")
    return _base(fig, titulo, 400)


def outliers_scatter(df, y, flag):
    d = df.assign(situação=np.where(df[flag], "outlier", "normal"))
    fig = px.scatter(d, x="cod_sub_bacia", y=y, color="situação", hover_data=["nome_bacia", "populacao"],
                     color_discrete_map={"outlier": VERMELHO, "normal": "#aec7e8"})
    fig.update_xaxes(title="cod_sub_bacia"); fig.update_yaxes(title=L.rotulo(y))
    return _base(fig, f"Outliers de {L.rotulo(y)} (clique na legenda para ocultar)", 420)


def mapa_coropletico(df, gj, coluna, rotulo_cor, escala="RdYlGn", faixa=None, estilo="carto-positron", opacidade=.75):
    """Mapa das sub-bacias coloridas por `coluna` (df precisa de cod_sub_bacia e bacia). Passe o mouse para ver os dados."""
    centro, zoom = MP.centro_zoom(gj)
    hover = {"cod_sub_bacia": True, "id_bacia": True, "populacao": ":,", "isa": ":.3f", "faixa_isa": True}
    args = dict(data_frame=df, geojson=gj, locations="cod_sub_bacia", featureidkey="properties.cod_sub_bacia",
                color=coluna, hover_name="bacia", hover_data=hover, center=centro, zoom=zoom, opacity=opacidade,
                labels={coluna: rotulo_cor, "cod_sub_bacia": "código", "id_bacia": "id da bacia",
                        "populacao": "população", "isa": "ISA", "faixa_isa": "faixa"})
    if coluna == "faixa_isa":
        args.update(color_discrete_map=COR_FAIXA, category_orders={"faixa_isa": list(COR_FAIXA)})
    else:
        args.update(color_continuous_scale=escala, range_color=faixa)
    if hasattr(px, "choropleth_map"):                      # plotly >= 5.24 (MapLibre)
        fig = px.choropleth_map(map_style=estilo, **args)
    else:                                                  # plotly mais antigo (Mapbox, sem token nos estilos abaixo)
        fig = px.choropleth_mapbox(mapbox_style=estilo, **args)
    fig.update_traces(marker_line_width=.6, marker_line_color="#555555")
    return _base(fig, None, 640)
