"""Gráficos interativos (Plotly): zoom, hover, legenda clicável."""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

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


def barras_faixas(df):
    c = df["faixa_isa"].value_counts().reindex(list(COR_FAIXA)).fillna(0).astype(int)
    fig = go.Figure(go.Bar(x=c.index, y=c.values, marker_color=[COR_FAIXA[k] for k in c.index],
                           text=[f"{v} ({100 * v / max(c.sum(), 1):.1f}%)".replace(".", ",") for v in c.values],
                           textposition="outside"))
    fig.update_yaxes(title="Nº de sub-bacias")
    return _base(fig, "Sub-bacias por faixa de ISA (<0,5 | 0,5–0,7 | 0,7–0,9 | ≥0,9)", 380)


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


# ----------------------- gráficos simples (Outliers e Regressão) -----------------------
def _rotulos(d):
    return d["nome_bacia"].astype(str) + " (" + d["cod_sub_bacia"].astype(str) + ")"


def _linhas_limite(fig, limites, a, b):
    for valor, rot in limites:
        if np.isfinite(valor) and a <= valor <= b:
            fig.add_vline(x=valor, line_dash="dash", line_color="#444444", annotation_text=f"{rot}: {L.br(valor, 3)}",
                          annotation_position="top")


def outliers_histograma(s, flag, lo, hi, nome, bins=30):
    """Histograma simples: azul = normal, vermelho = fora do normal; linhas tracejadas = limites do normal."""
    s = np.asarray(s, float)
    flag = np.asarray(flag, bool)
    ok_ = ~np.isnan(s)
    bordas = np.histogram_bin_edges(s[ok_], bins=bins)
    normal, _ = np.histogram(s[ok_ & ~flag], bins=bordas)
    fora, _ = np.histogram(s[ok_ & flag], bins=bordas)
    fig = go.Figure()
    for nome_t, cont, cor in (("Normal", normal, AZUL), ("Fora do normal (outlier)", fora, VERMELHO)):
        fig.add_trace(go.Bar(x=(bordas[:-1] + bordas[1:]) / 2, y=cont, width=np.diff(bordas) * .95, name=nome_t, marker_color=cor))
    fig.update_layout(barmode="stack")
    _linhas_limite(fig, ((lo, "limite inferior"), (hi, "limite superior")), bordas[0], bordas[-1])
    fig.update_xaxes(title=nome)
    fig.update_yaxes(title="Nº de sub-bacias")
    return _base(fig, f"Quantas sub-bacias estão fora do normal em {nome}?", 400)


def outliers_ranking(df, y, lo, hi, nome, n=15):
    """Barras com as sub-bacias mais distantes do normal (vermelho = abaixo do limite, laranja = acima). None se não há outliers."""
    fora = df[(df[y] < lo) | (df[y] > hi)].copy()
    if fora.empty:
        return None
    fora["distancia"] = np.where(fora[y] < lo, lo - fora[y], fora[y] - hi)
    fora = fora.nlargest(n, "distancia").iloc[::-1]
    cores = np.where((fora[y] < lo).to_numpy(), VERMELHO, LARANJA)
    topo = float(fora[y].max()) * 1.2
    fig = go.Figure(go.Bar(x=fora[y], y=_rotulos(fora), orientation="h", marker_color=cores, showlegend=False,
                           text=[L.br(v, 3) for v in fora[y]], textposition="outside", cliponaxis=False))
    fig.update_xaxes(title=nome, range=[0, topo])
    _linhas_limite(fig, ((lo, "limite inferior"), (hi, "limite superior")), 0, topo)
    return _base(fig, "Quais são as sub-bacias mais fora do normal", 130 + 28 * len(fora))


def scatter_regressao(df, x, y, mod, cor=None, log_x=False):
    """Dispersão simples: cada ponto é uma sub-bacia; a linha vermelha é a tendência."""
    d = df.dropna(subset=[x, y])
    fig = px.scatter(d, x=x, y=y, color=cor, hover_data=["cod_sub_bacia", "nome_bacia"], opacity=.7,
                     color_discrete_map=COR_FAIXA, category_orders={"faixa_isa": list(COR_FAIXA)})
    xs = np.linspace(mod["x"].min(), mod["x"].max(), 50)
    fig.add_trace(go.Scatter(x=xs, y=mod["intercept"] + mod["slope"] * xs, mode="lines",
                             line=dict(color=VERMELHO, width=3), name="Tendência (reta)"))
    fig.update_xaxes(title=L.rotulo(x), type="log" if log_x else "linear")
    fig.update_yaxes(title=L.rotulo(y))
    return _base(fig, f"{L.rotulo(y)} × {L.rotulo(x)}: cada ponto é uma sub-bacia", 480)


def maiores_erros(d, resid, nome_y, n=10):
    """Barras com as sub-bacias que mais fogem da tendência (real − esperado). `d` alinhado com `resid`."""
    resid = np.asarray(resid, float)
    if len(d) != len(resid) or len(d) == 0:
        return None
    t = d[["nome_bacia", "cod_sub_bacia"]].copy()
    t["erro"] = resid
    t = t.iloc[np.argsort(-np.abs(resid))[:n]].iloc[::-1]
    fig = go.Figure(go.Bar(x=t["erro"], y=_rotulos(t), orientation="h", showlegend=False,
                           marker_color=np.where(t["erro"] < 0, VERMELHO, AZUL), cliponaxis=False,
                           text=[("+" if v >= 0 else "−") + L.br(abs(v), 3) for v in t["erro"]], textposition="outside"))
    fig.add_vline(x=0, line_color="#444444")
    fig.update_xaxes(title=f"{nome_y}: real − esperado pela reta")
    return _base(fig, "Sub-bacias que mais fogem da tendência", 130 + 28 * len(t))


def pesos_variaveis(beta, nome_y):
    """Barras com o peso de cada variável no resultado (efeito padronizado: comparável entre variáveis)."""
    b = beta.dropna()
    if b.empty:
        return None
    b = b.iloc[np.argsort(np.abs(b.to_numpy()))]
    fig = go.Figure(go.Bar(x=b.to_numpy(), y=[L.rotulo(i) for i in b.index], orientation="h", showlegend=False,
                           marker_color=np.where(b.to_numpy() >= 0, AZUL, VERMELHO), cliponaxis=False,
                           text=[L.br(v, 2) for v in b.to_numpy()], textposition="outside"))
    fig.add_vline(x=0, line_color="#444444")
    fig.update_xaxes(title=f"← diminui {nome_y}   |   aumenta {nome_y} →")
    return _base(fig, "Quais variáveis mais pesam no resultado", 150 + 60 * len(b))
