"""
Dashboard Streamlit — Índice de Salubridade Ambiental (ISA) por sub-bacia.
Executar:  streamlit run app.py
Requisitos: pip install streamlit pandas numpy scipy matplotlib seaborn
"""
import warnings
import pandas as pd
import streamlit as st
import isa_lib as L

warnings.filterwarnings("ignore")
st.set_page_config(page_title="ISA por sub-bacia", page_icon="💧", layout="wide")

ARQ_PADRAO = "20230502_indice_-salubridade_-ambiental_-subbacia.csv"


@st.cache_data
def ler(arquivo):
    return L.carregar(arquivo)


# ------------------------------ barra lateral --------------------------------
st.sidebar.header("Dados")
up = st.sidebar.file_uploader("CSV do ISA (opcional)", type="csv")
try:
    df_full = ler(up if up is not None else ARQ_PADRAO)
except FileNotFoundError:
    st.error(f"Coloque o arquivo '{ARQ_PADRAO}' na mesma pasta do app ou use o upload na barra lateral.")
    st.stop()

st.sidebar.header("Filtros")
bacias = sorted(df_full.NOME_BACIA.dropna().unique())
sel = st.sidebar.multiselect("Bacias", bacias, default=[])
isa_min, isa_max = st.sidebar.slider("Faixa de ISA", 0.0, 1.0, (0.0, 1.0), 0.01)
excluir_vazias = st.sidebar.checkbox("Excluir sub-bacias sem população", value=False)

df = df_full[df_full.ISA_SUB_BACIA.between(isa_min, isa_max)]
if sel:
    df = df[df.NOME_BACIA.isin(sel)]
if excluir_vazias:
    df = df[df.POPULACAO_SUB_BACIA > 0]
if df.empty:
    st.warning("Nenhum registro com esses filtros.")
    st.stop()

# --------------------------------- cabeçalho ---------------------------------
st.title("💧 Salubridade ambiental por sub-bacia")
st.caption("Cada linha da base é uma sub-bacia. Os índices vão de 0 (pior) a 1 (melhor).")

pop_total = df.POPULACAO_SUB_BACIA.sum()
isa_pond = (df.ISA_SUB_BACIA * df.POPULACAO_SUB_BACIA).sum() / pop_total if pop_total else float("nan")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Sub-bacias", len(df))
c2.metric("Bacias", df.NOME_BACIA.nunique())
c3.metric("População", f"{pop_total:,.0f}".replace(",", "."))
c4.metric("ISA médio", f"{df.ISA_SUB_BACIA.mean():.3f}")
c5.metric("ISA ponderado (pop.)", f"{isa_pond:.3f}")

abas = st.tabs(["📖 Resumo", "📊 Estatística descritiva", "📈 Distribuições", "🔗 Correlações",
                "🚨 Anomalias e outliers", "🗺️ Bacias e ranking", "🧪 Qualidade dos dados"])

# --------------------------------- Resumo ------------------------------------
with abas[0]:
    st.subheader("A história em cinco frases")
    st.markdown(
        """
1. **A maior parte das sub-bacias vai bem**: ~81% têm ISA ≥ 0,9 e a mediana é 0,972.
2. **A média (0,943) engana**: a moda é 1,0 e a mediana é maior que a média — sinal de uma cauda de casos ruins puxando tudo para baixo.
3. **O problema está no esgoto**: o esgotamento sanitário (IES, sobretudo a *interceptação*) é o componente que mais explica o ISA (ρ ≈ 0,82).
4. **Há dois tipos de sub-bacia ruim**: as que *não têm rede de esgoto* (Macacos, Terra Vermelha) e as que sofrem com *drenagem/inundação* (Nado, Ribeirão da Onça).
5. **Densidade e tamanho quase não importam**: a desigualdade é de infraestrutura, não de adensamento.
"""
    )
    st.info("A base é uma **fotografia** (um único momento, sem coluna de data). "
            "Por isso **não existe tendência temporal nem sazonalidade** a medir — "
            "os 'padrões' aqui são espaciais e estruturais.")
    st.pyplot(L.fig_hist_isa(df))
    st.pyplot(L.fig_faixas(df))

# ------------------------- Estatística descritiva ---------------------------
with abas[1]:
    st.subheader("Média, mediana, moda, desvio padrão e variância")
    desc = L.descritivas(df, L.NUM)
    st.dataframe(desc.style.format("{:,.4f}"), use_container_width=True)
    st.markdown(
        """
**Como ler:**
- **Média < mediana < moda (=1,0)** nos índices → distribuição assimétrica à esquerda (assimetria negativa).
- **Variância** depende da unidade: a de população (≈ 84 milhões) e a do ISA (≈ 0,006) não são comparáveis.
  Use o **CV (%)** para comparar dispersões: população ≈ 94%, área ≈ 92%, densidade ≈ 53%, ISA ≈ 8,5%.
- **Curtose alta** (ICL ≈ 44, ICE ≈ 31) = caudas pesadas: poucos valores extremos pesam muito.
- **Nº de modas > 1** (população e densidade) significa que a moda é pouco informativa nessas variáveis contínuas.
"""
    )
    var = st.selectbox("Detalhar uma variável", L.NUM, index=len(L.NUM) - 1)
    s = df[var]
    a, b, c, d = st.columns(4)
    a.metric("Média", f"{s.mean():.4f}"); b.metric("Mediana", f"{s.median():.4f}")
    c.metric("Moda", f"{s.mode().iloc[0]:.4f}"); d.metric("Desvio padrão", f"{s.std():.4f}")
    st.write(f"Variância: **{s.var():.6g}** · Q1: {s.quantile(.25):.4f} · Q3: {s.quantile(.75):.4f} · "
             f"IQR: {s.quantile(.75) - s.quantile(.25):.4f}")

# ------------------------------ Distribuições -------------------------------
with abas[2]:
    st.subheader("Como os índices se distribuem")
    st.pyplot(L.fig_box_indices(df))
    st.markdown(
        "**Leitura:** a caixa de quase todos os índices está comprimida perto de 1,0 e os pontos isolados "
        "ficam só à esquerda. O **IDR** (drenagem) é o que tem a maior fração de sub-bacias fora do padrão (~14%)."
    )
    col1, col2 = st.columns(2)
    with col1:
        st.pyplot(L.fig_dist_populacao(df))
    with col2:
        st.pyplot(L.fig_qq(df))
    st.markdown(
        "**Leitura:** a população é muito assimétrica à direita (assimetria ≈ 2,8); a escala log a simetriza. "
        "O Q-Q plot do ISA se afasta fortemente da reta (Shapiro-Wilk p < 0,001): **não é normal**. "
        "Prefira mediana, quartis e testes não paramétricos (Spearman, Mann-Whitney, Kruskal-Wallis)."
    )

# ------------------------------- Correlações --------------------------------
with abas[3]:
    st.subheader("O que se move junto com o ISA?")
    st.pyplot(L.fig_corr(df))
    st.pyplot(L.fig_componentes_vs_isa(df))
    st.markdown(
        """
**Leitura:**
- Correlação positiva forte: **IES (0,82)**, **IIE (0,82)**, **ICE (0,73)**, **ICL (0,59)**. Esses índices *compõem* o ISA, então a
  correlação é em parte mecânica (veja a aba de qualidade dos dados).
- Correlação negativa: **população sem interceptação (−0,80)**, **sem rede coletora (−0,73)**, **em mancha de inundação (−0,53)**.
- **Densidade × ISA ≈ −0,08 (Spearman)**: praticamente nula. Cuidado com conclusões como 'quanto mais adensado, pior'.
- Contagens absolutas (população total, área) são correlacionadas entre si por tamanho; use **proporções** ao comparar sub-bacias.
"""
    )
    st.pyplot(L.fig_densidade_faixas(df))
    st.pyplot(L.fig_pop_vs_isa(df))

# --------------------------- Anomalias e outliers ---------------------------
with abas[4]:
    st.subheader("Valores discrepantes")
    st.dataframe(L.outliers_iqr(df, L.NUM).style.format("{:,.3f}"), use_container_width=True)
    st.caption("Nos índices limitados a 1,0, o limite superior do IQR passa de 1 — só o lado inferior é relevante.")
    st.pyplot(L.fig_pior_subbacias(df))
    st.markdown(
        """
**Anomalias que merecem atenção:**
- 🔴 **Córrego dos Macacos (4140900)** — ISA 0,458; ICE, IIE e ICL ≈ 0,01–0,02: 7.533 de 7.639 moradores sem rede de esgoto nem interceptação,
  e quase ninguém com coleta de lixo. É o outlier mais extremo. **Terra Vermelha (4140803)** tem o mesmo padrão (ISA 0,482).
- 🟠 **Córrego do Nado (4140211)** e **Ribeirão da Onça (4130002/3/5)** — falha mista: IDR de 0,35–0,54 (muitos moradores em mancha de inundação) e/ou IIE baixo.
- ⚪ **Sub-bacia 4120200** (Córrego Sem Nome) — **população = 0** e todos os índices = 1,0. É 'perfeita' por ausência de moradores, não por mérito.
- 🔵 **Cachoeirinha 4131303** — maior população (74.062), ISA 0,844: um 'outlier' de **tamanho**, não de qualidade; pesa muito em qualquer média ponderada.
"""
    )
    st.warning("**Impacto em análises futuras:** os 2 outliers extremos (ISA < 0,5) reduzem a média, aumentam o desvio padrão e "
               "podem dominar uma regressão. Teste os resultados com e sem eles (use o filtro de ISA na barra lateral).")
    st.dataframe(df.nsmallest(15, "ISA_SUB_BACIA")[["COD_SUB_BACIA", "NOME_BACIA", "POPULACAO_SUB_BACIA", "ICE_SUB_BACIA",
                 "IIE_SUB_BACIA", "ICL_SUB_BACIA", "IDR_SUB_BACIA", "ISA_SUB_BACIA"]], use_container_width=True)

# ---------------------------- Bacias e ranking ------------------------------
with abas[5]:
    st.subheader("Do nível da sub-bacia ao nível da bacia")
    n = st.slider("Quantas bacias mostrar", 5, 25, 12)
    st.pyplot(L.fig_ranking_bacias(df, n=n))
    st.dataframe(L.por_bacia(df).style.format({"ISA_medio": "{:.3f}", "ISA_ponderado": "{:.3f}", "populacao": "{:,.0f}"}),
                 use_container_width=True)
    st.markdown(
        "**Leitura:** a média simples e a ponderada por população diferem (ex.: Ribeirão da Onça 0,832 vs 0,789) — "
        "ponderar mostra o que a **população** vive, não o que o **mapa** mostra. "
        "29 das 63 bacias têm só 1 sub-bacia: o 'ISA da bacia' ali é um único ponto, com baixa robustez."
    )

# ---------------------------- Qualidade dos dados ---------------------------
with abas[6]:
    st.subheader("Checagens de integridade")
    nulos = df_full.isna().sum()
    st.write("**Colunas com valores ausentes:**")
    st.dataframe(nulos[nulos > 0].rename("nulos"))
    st.markdown(
        """
- `NOME_SUB_BACIA` está **100% vazia** → use `COD_SUB_BACIA` como identificador.
- `IAB_SUB_BACIA` é **constante (=1)** em todas as linhas → variância zero, não discrimina nada (e gera NaN em correlações).
- A fórmula do ISA foi **recuperada por regressão** (erro ≈ 0): `ISA = 0,05·IAB + 0,35·IES + 0,20·ICL + 0,40·IDR`
  e `IES = 0,30·ICE + 0,70·IIE`. ⚠️ Correlacionar ISA com seus próprios componentes é circular.
- Somas de população (com + sem) diferem da total em até **±1 habitante** — arredondamento, sem impacto.
- A coluna `GEOMETRIA` (polígonos) foi descartada da análise; ela permitiria mapas (geopandas) em uma próxima etapa.
- Não há coluna de data: **sem série temporal**.
"""
    )