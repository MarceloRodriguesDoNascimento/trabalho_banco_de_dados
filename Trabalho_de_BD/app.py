"""
Dashboard ISA por sub-bacia — interativo.   Executar:  streamlit run app.py
Requisitos: pip install -r requirements.txt
"""
import io
import warnings

import numpy as np
import pandas as pd
import streamlit as st

import dados_isa
import graficos as G
import isa_lib as L
import mapa as M
import padronizacao as P

warnings.filterwarnings("ignore")
st.set_page_config(page_title="ISA por sub-bacia", page_icon="💧", layout="wide")


# ------------------------------- dados / cache -------------------------------
@st.cache_data(show_spinner=False)
def ler_csv(conteudo: bytes):
    return L.carregar_bruto(io.BytesIO(conteudo))


@st.cache_data(show_spinner=False)
def tratar(raw, **kw):
    return P.padronizar(raw, **kw)


@st.cache_data(show_spinner=False)
def base_embutida():
    return dados_isa.carregar()


@st.cache_data(show_spinner=False)
def geojson(raw):
    """Geometrias do próprio CSV; se ele não tiver GEOMETRIA (ex.: o CSV padronizado), usa as da base embutida."""
    gj = M.construir_geojson(raw)
    if gj is not None:
        return gj, "csv"
    return M.construir_geojson(dados_isa.carregar()), "embutida"


@st.cache_data(show_spinner=False)
def validar(df, col, metodos, frac, reps, seed, ordem):
    return L.validar_interpolacao(df, col, list(metodos), frac, reps, seed, ordem)


def tabela(df, nd=4):
    st.dataframe(df.round(nd))


# ------------------------------- barra lateral -------------------------------
sb = st.sidebar
sb.header("1 · Dados")
sb.caption("Base do ISA já embutida no app (255 sub-bacias, com geometrias). Não precisa enviar nada.")
up = sb.file_uploader("Usar outro CSV (opcional)", type="csv")
raw = ler_csv(up.getvalue()) if up is not None else base_embutida()

sb.header("2 · Tratamento")
sb.caption("Vale para o dashboard inteiro e para a base exportada.")
ausentes = sb.selectbox("Dados ausentes", P.MET_AUSENTES, 0,
                        help="Interpolar percorre as linhas por cod_sub_bacia. Veja a aba Interpolação antes de confiar nesse método.")
dups = sb.checkbox("Remover duplicidades", True)
modo_out = sb.radio("Outliers", P.MET_OUTLIER, 0, help="Sinalizar mantém os valores e cria colunas outlier_*. Winsorizar limita aos limites. Remover apaga linhas.")
cols_out = sb.multiselect("Detectar outliers em", L.VARS, default=["isa"], format_func=L.rotulo)
met_out = sb.radio("Método de detecção", ["iqr", "z"], format_func=lambda m: "IQR (Tukey)" if m == "iqr" else "Z-score")
k = sb.slider("Sensibilidade k", 1.0, 5.0, 1.5, 0.5, help="IQR: 1,5 é o usual. Z-score: 3 é o usual.")
escala = sb.selectbox("Colunas em escala estatística", ["nenhuma", "zscore", "minmax"])
if modo_out != "sinalizar":
    sb.warning("Atenção: no ISA os valores baixos são casos reais (ex.: sub-bacias sem rede de esgoto). Winsorizar/remover esconde justamente o problema.")

try:
    kw = dict(ausentes=ausentes, remover_duplicados=dups, outliers=modo_out, colunas_outliers=tuple(cols_out),
              metodo_outlier=met_out, k=k, escala=escala)
    base, log = tratar(raw, **kw)
    ref, _ = tratar(raw, ausentes="interpolar", remover_duplicados=True, outliers="sinalizar",
                    colunas_outliers=tuple(cols_out), metodo_outlier=met_out, k=k, escala="nenhuma")
except ValueError as e:
    st.error(str(e))
    st.stop()

sb.header("3 · Filtros")
dfr = L.com_rotulo(base)
sel = sb.multiselect("Bacias", sorted(dfr["bacia"].unique()))
isa_a, isa_b = sb.slider("Faixa de ISA", 0.0, 1.0, (0.0, 1.0), 0.01)
pop_min = sb.number_input("População mínima", 0, int(dfr["populacao"].max()), 0, step=500)
faixas = sb.multiselect("Faixa de ISA (classe)", list(G.COR_FAIXA), default=list(G.COR_FAIXA))
sem_pop = sb.checkbox("Excluir sub-bacias sem população", False)

df = dfr[dfr["isa"].between(isa_a, isa_b) & (dfr["populacao"] >= pop_min) & dfr["faixa_isa"].isin(faixas)]
if sel:
    df = df[df["bacia"].isin(sel)]
if sem_pop:
    df = df[~df["sem_populacao"]]
if len(df) < 3:
    st.warning("Poucos registros com esses filtros (mínimo 3).")
    st.stop()

# --------------------------------- cabeçalho ---------------------------------
st.title("💧 Salubridade ambiental por sub-bacia")
pop = df["populacao"].sum()
isa_pond = (df["isa"] * df["populacao"]).sum() / pop if pop else np.nan
c = st.columns(6)
c[0].metric("Sub-bacias", len(df))
c[1].metric("Bacias (por id)", df["id_bacia"].nunique())
c[2].metric("População", L.br(pop, 0))
c[3].metric("ISA médio", L.br(df["isa"].mean()))
c[4].metric("ISA mediano", L.br(df["isa"].median()))
c[5].metric("ISA ponderado (pop.)", L.br(isa_pond))

abas = st.tabs(["📖 Visão geral", "📊 Estatísticas", "📉 Regressão", "🧩 Interpolação", "🚨 Outliers",
                "🗺️ Mapa", "📋 Bacias", "🧹 Padronização & MySQL"])

# ------------------------------- Visão geral ---------------------------------
with abas[0]:
    esq, dir_ = st.columns(2)
    esq.plotly_chart(G.hist_medidas(df["isa"], "ISA"))
    dir_.plotly_chart(G.barras_faixas(df))
    st.plotly_chart(G.pop_vs_isa(df))
    st.info("A base é uma fotografia (sem coluna de data): **não há tendência temporal nem sazonalidade** a medir. "
            "Os padrões aqui são espaciais e estruturais. Use os filtros e o tratamento na barra lateral e veja tudo se atualizar.")

# ------------------------------- Estatísticas --------------------------------
with abas[1]:
    var = st.selectbox("Variável", L.VARS, index=L.VARS.index("isa"), format_func=L.rotulo, key="var_stat")
    s = df[var].astype(float)
    m = st.columns(6)
    m[0].metric("Média", L.br(s.mean(), 4)); m[1].metric("Mediana", L.br(s.median(), 4))
    m[2].metric("Moda", L.br(s.mode().iloc[0], 4)); m[3].metric("Desvio padrão", L.br(s.std(), 4))
    m[4].metric("Variância", f"{s.var():.4g}".replace(".", ",")); m[5].metric("CV", L.br(100 * s.std() / s.mean(), 1) + "%")
    forma = ("assimétrica à esquerda (cauda de valores baixos)" if s.skew() < -.5 else
             "assimétrica à direita (cauda de valores altos)" if s.skew() > .5 else "aproximadamente simétrica")
    st.write(f"Distribuição **{forma}** (assimetria {L.br(s.skew(), 2)}, curtose {L.br(s.kurt(), 2)}). "
             f"Média {'<' if s.mean() < s.median() else '>'} mediana: "
             f"{'a cauda puxa a média para baixo' if s.mean() < s.median() else 'a cauda puxa a média para cima'}. "
             "Variância depende da unidade; compare dispersões pelo CV.")
    e1, e2 = st.columns(2)
    e1.plotly_chart(G.hist_medidas(s, L.rotulo(var)))
    e2.plotly_chart(G.qq(s, L.rotulo(var)))
    st.subheader("Tabela completa")
    todas = L.descritivas(df, L.VARS)
    todas.index = [L.rotulo(i) for i in todas.index]
    tabela(todas)
    st.download_button("⬇️ Baixar estatísticas (CSV)", todas.to_csv().encode("utf-8"), "estatisticas_descritivas.csv", "text/csv")
    st.subheader("Correlação")
    metodo_c = st.radio("Coeficiente", ["spearman", "pearson"], horizontal=True,
                        help="Spearman é robusto a outliers e assimetria (recomendado aqui).")
    sel_c = st.multiselect("Variáveis", L.VARS, default=["isa", "ice", "iie", "icl", "idr", "densidade_hab_ha", "populacao",
                                                         "pop_sem_rede_coletora", "pop_mancha_inundacao"], format_func=L.rotulo)
    if len(sel_c) >= 2:
        st.plotly_chart(G.heatmap_corr(df[sel_c].corr(method=metodo_c), f"Correlação de {metodo_c.capitalize()}"))

# --------------------------------- Regressão ---------------------------------
with abas[2]:
    modo = st.radio("Tipo", ["Simples", "Múltipla"], horizontal=True)
    if modo == "Simples":
        a, b_, c_ = st.columns(3)
        y = a.selectbox("Y (resposta)", L.VARS, index=L.VARS.index("isa"), format_func=L.rotulo)
        opc_x = [v for v in L.VARS if v != y]
        x = b_.selectbox("X (explicativa)", opc_x, index=opc_x.index("ies") if "ies" in opc_x else 0, format_func=L.rotulo)
        colorir = c_.checkbox("Colorir por faixa de ISA", True)
        o1, o2 = st.columns(2)
        sem_out = o1.checkbox("Ignorar outliers (IQR) de X e Y na regressão", False)
        log_x = o2.checkbox("Eixo X em escala log", False) if (df[x] > 0).all() else False
        d = df
        if sem_out:
            for v in (x, y):
                lo, hi = P.limites(d[v], "iqr", 1.5)
                d = d[d[v].between(lo, hi)]
            st.caption(f"{len(df) - len(d)} sub-bacias ignoradas.")
        try:
            mod = L.regressao_simples(d[x], d[y])
        except ValueError as e:
            st.warning(str(e)); mod = None
        if mod:
            q = st.columns(6)
            q[0].metric("n", mod["n"]); q[1].metric("Inclinação", L.br(mod["slope"], 4))
            q[2].metric("Intercepto", L.br(mod["intercept"], 4)); q[3].metric("R²", L.br(mod["r2"], 3))
            q[4].metric("r (Pearson)", L.br(mod["r"], 3)); q[5].metric("ρ (Spearman)", L.br(mod["spearman"], 3))
            st.write(f"IC 95% da inclinação: [{L.br(mod['ic_slope'][0], 4)}; {L.br(mod['ic_slope'][1], 4)}] · "
                     f"p-valor: {'< 0,001' if mod['p'] < .001 else L.br(mod['p'], 3)} · RMSE: {L.br(mod['rmse'], 4)} · MAE: {L.br(mod['mae'], 4)}")
            passo = .1 if d[x].max() <= 1 else 1
            st.success(f"Interpretação: a cada +{L.br(passo, 1 if passo < 1 else 0)} em **{L.rotulo(x)}**, "
                       f"**{L.rotulo(y)}** varia em média {L.br(mod['slope'] * passo, 4)} (associação, não causa).")
            if y == "isa" and x in ("ice", "iie", "ies", "icl", "icl_cf", "idr"):
                st.warning("Circularidade: esse índice é um componente do ISA (ISA = 0,05·IAB + 0,35·IES + 0,20·ICL + 0,40·IDR). "
                           "O R² alto é parcialmente mecânico.")
            st.plotly_chart(G.scatter_regressao(d, x, y, mod, "faixa_isa" if colorir else None, log_x))
            st.plotly_chart(G.residuos(mod["pred"], mod["resid"]))
            st.subheader("Prever / interpolar na reta")
            x0 = st.number_input(f"Valor de {L.rotulo(x)}", value=float(np.round(d[x].median(), 4)), format="%.4f")
            yh, lo, hi, plo, phi = L.prever(mod, x0)
            r = st.columns(3)
            r[0].metric(f"{L.rotulo(y)} previsto", L.br(float(yh), 4))
            r[1].metric("IC 95% da média", f"{L.br(float(lo), 3)} – {L.br(float(hi), 3)}")
            r[2].metric("Intervalo de predição 95%", f"{L.br(float(plo), 3)} – {L.br(float(phi), 3)}")
            if not (mod["x"].min() <= x0 <= mod["x"].max()):
                st.warning("Valor fora do intervalo observado: isso é extrapolação, o resultado é pouco confiável.")
    else:
        y = st.selectbox("Y (resposta)", L.VARS, index=L.VARS.index("isa"), format_func=L.rotulo, key="y_multi")
        padrao = [v for v in ["densidade_hab_ha", "pop_mancha_inundacao", "pop_sem_rede_coletora"] if v != y]
        xs = st.multiselect("X (explicativas)", [v for v in L.VARS if v != y], default=padrao, format_func=L.rotulo)
        if xs:
            try:
                mm = L.regressao_multipla(df, y, xs)
                q = st.columns(4)
                q[0].metric("n", mm["n"]); q[1].metric("R²", L.br(mm["r2"], 3))
                q[2].metric("R² ajustado", L.br(mm["r2_aj"], 3)); q[3].metric("RMSE", L.br(mm["rmse"], 4))
                tab = mm["tabela"].copy(); tab.index = [L.rotulo(i) for i in tab.index]
                tabela(tab, 5)
                st.caption(f"Teste F global: p {'< 0,001' if mm['p_f'] < .001 else '= ' + L.br(mm['p_f'], 3)}.")
                if y == "isa" and {"ies", "icl", "idr"} & set(xs):
                    st.warning("Incluir componentes do ISA como X recupera a fórmula do índice (R² ≈ 1): é identidade, não descoberta.")
                st.plotly_chart(G.real_vs_imputado(mm["y"], mm["pred"], L.rotulo(y), "previsto", "Real × previsto"))
                st.plotly_chart(G.residuos(mm["pred"], mm["resid"]))
            except ValueError as e:
                st.warning(str(e))
        else:
            st.info("Escolha ao menos uma variável X.")

# -------------------------------- Interpolação -------------------------------
with abas[3]:
    st.write("A interpolação só é útil se **valores vizinhos se parecem**. Aqui você testa isso: o app esconde parte dos valores "
             "conhecidos, tenta reconstruí-los e mede o erro de cada método.")
    a, b_, c_, d_ = st.columns(4)
    v = a.selectbox("Variável", L.VARS, index=L.VARS.index("isa"), format_func=L.rotulo, key="v_interp")
    ordem = b_.selectbox("Ordenar linhas por", ["cod_sub_bacia", "id_sub_bacia", "id_bacia"])
    frac = c_.slider("% escondido", 5, 40, 10, 5) / 100
    reps = d_.slider("Repetições", 5, 50, 20, 5)
    mets = st.multiselect("Métodos", L.METODOS_INTERP, default=L.METODOS_INTERP)
    seed = st.number_input("Semente aleatória", 0, 9999, 0)
    if mets:
        res, sd = validar(ref, v, tuple(mets), frac, reps, int(seed), ordem)
        st.plotly_chart(G.comparar_interpolacao(res, sd))
        tabela(res)
        melhor = res.index[0]
        ganho = 1 - res.iloc[0]["RMSE"] / sd
        if ganho < .15:
            st.warning(f"O melhor método ({melhor}) reduz o erro em apenas {L.br(100 * ganho, 0)}% em relação a "
                       "'chutar a média' (desvio padrão). Sem estrutura útil na ordem escolhida, **não confie em interpolação** para esta variável.")
        else:
            st.success(f"O método **{melhor}** reduz o erro em {L.br(100 * ganho, 0)}% em relação ao desvio padrão: há estrutura aproveitável.")
        rng = np.random.default_rng(int(seed))
        conh = ref.dropna(subset=[v]).reset_index(drop=True)
        mask = rng.random(len(conh)) < frac
        if mask.sum() > 1:
            t = conh.copy(); t.loc[mask, v] = np.nan
            met1 = st.selectbox("Ver uma rodada do método", mets, index=mets.index(melhor))
            imp = L.preencher(t, v, met1, ordem)
            st.plotly_chart(G.real_vs_imputado(conh.loc[mask, v], imp[mask], L.rotulo(v)))
    nulos = raw.isna().sum()
    nulos = nulos[(nulos > 0) & (nulos < len(raw))]
    st.caption("Colunas do CSV original com ausentes parciais: " + (", ".join(f"{i} ({n})" for i, n in nulos.items()) or "nenhuma")
               + ". (NOME_SUB_BACIA é 100% vazia e foi descartada.)")

# ---------------------------------- Outliers ---------------------------------
with abas[4]:
    var_o = st.selectbox("Variável", L.VARS, index=L.VARS.index(cols_out[0]) if cols_out else L.VARS.index("isa"),
                         format_func=L.rotulo, key="var_out")
    lo, hi = P.limites(ref[var_o], met_out, k)
    flag = f"outlier_{var_o}"
    d = ref.copy()
    d[flag] = (d[var_o] < lo) | (d[var_o] > hi)
    d = d[d["cod_sub_bacia"].isin(df["cod_sub_bacia"])]
    if np.isfinite(lo):
        st.write(f"Limites ({'IQR' if met_out == 'iqr' else 'z-score'}, k = {k}): **[{L.br(lo, 3)}; {L.br(hi, 3)}]** · "
                 f"**{int(d[flag].sum())}** de {len(d)} sub-bacias fora.")
    else:
        st.warning("IQR = 0 nesta variável (valores colados em um mesmo número): o método não detecta outliers aqui.")
    x1, x2 = st.columns(2)
    x1.plotly_chart(G.outliers_scatter(d, var_o, flag))
    x2.plotly_chart(G.box_variaveis(d, [var_o], "Boxplot"))
    cols_show = ["cod_sub_bacia", "nome_bacia", "populacao", "ice", "iie", "icl", "idr", "isa"]
    st.subheader("Sub-bacias fora dos limites")
    tabela(d[d[flag]].sort_values(var_o)[cols_show], 3)
    st.subheader("Antes × depois do tratamento")
    if modo_out == "sinalizar" and ausentes in ("interpolar", "nenhum") and escala == "nenhuma":
        st.caption("O tratamento atual não altera valores (apenas sinaliza); escolha 'winsorizar' ou 'remover' na barra lateral para ver o impacto.")
    tabela(L.comparar_antes_depois(ref, base, [v for v in (cols_out or ["isa"])]), 4)
    st.subheader("Casos especiais")
    st.write("Sub-bacias sem população (índices = 1,0 por ausência de moradores, não por mérito):")
    tabela(base[base["sem_populacao"]][["cod_sub_bacia", "nome_bacia", "area_ha", "populacao", "isa"]], 3)

# ------------------------------------ Mapa -----------------------------------
with abas[5]:
    gj_all, origem_geo = geojson(raw)
    if gj_all is None:
        st.info("Não foi possível ler as geometrias das sub-bacias.")
    else:
        if origem_geo == "embutida":
            st.caption("O CSV enviado não tem geometrias: usando as da base embutida (ligação por cod_sub_bacia).")
        INDICES = ["isa", "ice", "iie", "ies", "icl", "idr"]
        opcoes = {"Faixa de ISA (categorias)": "faixa_isa", "ISA ponderado da bacia": "isa_bacia"}
        opcoes.update({L.rotulo(v): v for v in INDICES + ["populacao", "densidade_hab_ha", "pop_sem_rede_coletora",
                                                         "pop_sem_interceptacao", "pop_mancha_inundacao"]})
        m1, m2, m3, m4 = st.columns(4)
        nome_cor = m1.selectbox("Colorir por", list(opcoes), 0)
        escala_cor = m2.radio("Escala (índices)", ["Ajustada aos dados", "Fixa 0–1"],
                              help="Quase tudo é > 0,9; a escala ajustada mostra melhor as diferenças.")
        fundo = m3.selectbox("Mapa de fundo", ["carto-positron", "open-street-map", "carto-darkmatter", "white-bg"],
                             help="'white-bg' funciona sem internet (só os polígonos).")
        opac = m4.slider("Opacidade", 0.3, 1.0, 0.75, 0.05)
        col_cor = opcoes[nome_cor]
        bb_m = L.por_bacia(df)
        dm = df.assign(isa_bacia=df["id_bacia"].map(bb_m["isa_ponderado"]).fillna(df["id_bacia"].map(bb_m["isa_medio"])))
        gj = M.filtrar_geojson(gj_all, dm["cod_sub_bacia"])
        dm = dm[dm["cod_sub_bacia"].isin({f["properties"]["cod_sub_bacia"] for f in gj["features"]})]
        if dm.empty:
            st.warning("Nenhuma sub-bacia com geometria para os filtros atuais.")
        else:
            faixa_cor, paleta = None, "Blues"
            if col_cor in INDICES + ["isa_bacia"]:
                paleta = "RdYlGn"
                if escala_cor.startswith("Fixa"):
                    faixa_cor = (0.0, 1.0)
                else:
                    vmin, vmax = float(dm[col_cor].quantile(.02)), float(dm[col_cor].max())
                    faixa_cor = (vmin, vmax if vmax > vmin else vmin + 1e-3)
            elif col_cor in ("pop_sem_rede_coletora", "pop_sem_interceptacao", "pop_mancha_inundacao"):
                paleta = "YlOrRd"
            st.plotly_chart(G.mapa_coropletico(dm, gj, col_cor, nome_cor, paleta, faixa_cor, fundo, opac))
            st.caption(f"{len(dm)} sub-bacias no mapa. Use o filtro **Bacias** ou a faixa de ISA na barra lateral para isolar regiões. "
                       "As coordenadas do CSV (UTM, zona 23 Sul, inferida) são convertidas para latitude/longitude.")
            st.subheader("10 piores sub-bacias visíveis no mapa")
            tabela(dm.nsmallest(10, "isa")[["cod_sub_bacia", "bacia", "populacao", "ice", "iie", "icl", "idr", "isa"]], 3)

# ----------------------------------- Bacias ----------------------------------
with abas[6]:
    st.write("**Chave correta: `id_bacia`.** O nome não identifica a bacia (ex.: 'Córrego Sem Nome' reúne várias; 'Ribeirão da Onça' tem 6 ids).")
    n = st.slider("Quantas bacias mostrar", 5, 30, 12)
    bb = L.por_bacia(df)
    st.plotly_chart(G.ranking_bacias(bb, n))
    st.write(f"{(bb['sub_bacias'] == 1).sum()} das {len(bb)} bacias têm apenas 1 sub-bacia: o 'ISA da bacia' ali é um único ponto.")
    tabela(bb[["bacia", "sub_bacias", "populacao", "isa_medio", "isa_ponderado"]], 3)

# ------------------------- Padronização e MySQL ------------------------------
with abas[7]:
    st.subheader("Relatório do tratamento")
    tabela(log, 3)
    with st.expander("De → para dos nomes de colunas"):
        tabela(pd.DataFrame({"original": list(P.RENOMEAR), "padronizado": list(P.RENOMEAR.values())}))
    st.subheader("Nova base")
    st.caption(f"{base.shape[0]} linhas × {base.shape[1]} colunas · inclui area_km2 (m → km: 1 km² = 100 ha), faixa_isa e flags de outlier.")
    st.dataframe(base)
    banco = st.text_input("Nome do banco MySQL", "isa_bh")
    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Baixar CSV padronizado", P.para_csv(base).to_csv(index=False).encode("utf-8"), "base_isa_padronizada.csv", "text/csv")
    d2.download_button("⬇️ Baixar script SQL (MySQL)", P.gerar_script_sql(base, banco).encode("utf-8"), "base_isa_padronizada.sql", "text/plain")
    st.code("mysql -u SEU_USUARIO -p < base_isa_padronizada.sql", language="bash")
    st.subheader("Importar direto para o MySQL")
    with st.form("mysql"):
        f1, f2, f3 = st.columns(3)
        host = f1.text_input("Host", "localhost"); porta = f2.number_input("Porta", 1, 65535, 3306)
        usuario = f3.text_input("Usuário", "root")
        senha = st.text_input("Senha", type="password")
        recriar = st.checkbox("Recriar tabelas (apaga bacia e sub_bacia se já existirem)", True)
        ok = st.form_submit_button("Importar")
    if ok:
        try:
            with st.spinner("Importando..."):
                r = P.importar_mysql(base, host, usuario, senha, banco, porta, recriar)
            st.success(f"Importado em `{r['banco']}`: {r['bacia']} bacias e {r['sub_bacia']} sub-bacias.")
        except ImportError:
            st.error("Instale o driver: pip install pymysql")
        except Exception as e:
            st.error(f"Falha na importação: {e}")
