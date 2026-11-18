"""
Dashboard executivo do ISA (Indice de Salubridade Ambiental) por sub-bacia - Belo Horizonte.
Para rodar:  streamlit run dashboard.py
(precisa do arquivo base_isa_padronizada.csv na mesma pasta)
"""
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Dashboard ISA", page_icon="💧", layout="wide")

# ---------------------------------------------------------------
# 1. LER OS DADOS
# ---------------------------------------------------------------
df = pd.read_csv("base_isa_padronizada.csv")

DATA_BASE = "02/05/2023"  # data da base (foto unica, sem atualizacao automatica)

# Regras de negocio (sempre as mesmas no dashboard inteiro)
# Faixas do ISA: Critico < 0,5 | Baixo 0,5-0,7 | Medio 0,7-0,9 | Alto >= 0,9
# "Sub-bacia em atencao" = faixa Critico ou Baixo
df["em_atencao"] = df["faixa_isa"].isin(["Crítico", "Baixo"])

# ---------------------------------------------------------------
# 2. FILTRO (so um, para nao poluir)
# ---------------------------------------------------------------
st.sidebar.header("Filtro")
bacias = sorted(df["nome_bacia"].unique())
escolhidas = st.sidebar.multiselect("Bacia", bacias)
if escolhidas:
    df = df[df["nome_bacia"].isin(escolhidas)]

# ---------------------------------------------------------------
# 3. CABECALHO: publico, pergunta e data
# ---------------------------------------------------------------
st.title("💧 Salubridade ambiental das sub-bacias de BH")
st.caption(
    "Público: gestor de saneamento da prefeitura  |  "
    f"Dados de {DATA_BASE} (base fixa, sem atualização automática)"
)
st.markdown("**Pergunta central:** quais sub-bacias precisam de investimento primeiro?")

# ---------------------------------------------------------------
# 4. TOPO: KPIs (numeros grandes)
# ---------------------------------------------------------------
populacao = df["populacao"].sum()
isa_ponderado = (df["isa"] * df["populacao"]).sum() / populacao
qtd_atencao = int(df["em_atencao"].sum())
pop_atencao = df.loc[df["em_atencao"], "populacao"].sum()
sem_rede = df["pop_sem_rede_coletora"].sum()
inundacao = df["pop_mancha_inundacao"].sum()

# Semaforo do ISA geral
if isa_ponderado >= 0.9:
    semaforo = "🟢"
elif isa_ponderado >= 0.7:
    semaforo = "🟡"
else:
    semaforo = "🔴"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("ISA geral (ponderado)", f"{semaforo} {isa_ponderado:.3f}".replace(".", ","))
c2.metric("Sub-bacias em atenção", f"{'🔴' if qtd_atencao > 0 else '🟢'} {qtd_atencao} de {len(df)}")
c3.metric("Pessoas nessas sub-bacias", f"{pop_atencao:,}".replace(",", "."))
c4.metric("Pessoas sem rede de esgoto", f"{sem_rede:,}".replace(",", "."))
c5.metric("Pessoas em área de inundação", f"{inundacao:,}".replace(",", "."))

# Acao ligada ao indicador (se o numero esta vermelho, o que fazer?)
if qtd_atencao > 0:
    st.error(
        f"🔴 **Ação:** {qtd_atencao} sub-bacia(s) com ISA abaixo de 0,7. "
        "Priorizar obras de esgoto e drenagem nelas (veja a tabela no final)."
    )
else:
    st.success("🟢 **Ação:** nenhuma sub-bacia em atenção neste filtro. Manter a manutenção de rotina.")

st.divider()

# ---------------------------------------------------------------
# 5. MEIO: graficos
# (a base e uma "foto" sem data, entao nao ha grafico de tendencia no tempo;
#  o comparativo entre indices mostra onde esta o ponto mais fraco)
# ---------------------------------------------------------------
esq, dir_ = st.columns(2)

# Grafico 1: media de cada indice
indices = {
    "ICE (esgoto)": "ice",
    "IIE (interceptação)": "iie",
    "ICL (lixo)": "icl",
    "IDR (drenagem)": "idr",
}
medias = pd.DataFrame({
    "Índice": list(indices.keys()),
    "Média": [df[col].mean() for col in indices.values()],
})
fig1 = px.bar(medias, x="Índice", y="Média", range_y=[0, 1], text_auto=".3f",
              title="Qual serviço está mais fraco? (média, 0 a 1)")
esq.plotly_chart(fig1)

# Grafico 2: populacao por faixa
cores = {"Crítico": "#c0392b", "Baixo": "#e67e22", "Médio": "#f1c40f", "Alto": "#27ae60"}
por_faixa = df.groupby("faixa_isa")["populacao"].sum().reset_index()
fig2 = px.bar(por_faixa, x="faixa_isa", y="populacao", color="faixa_isa",
              color_discrete_map=cores,
              category_orders={"faixa_isa": ["Crítico", "Baixo", "Médio", "Alto"]},
              title="Quantas pessoas vivem em cada faixa de ISA?",
              labels={"faixa_isa": "Faixa", "populacao": "População"})
fig2.update_layout(showlegend=False)
dir_.plotly_chart(fig2)

st.divider()

# ---------------------------------------------------------------
# 6. BASE: tabela detalhada
# ---------------------------------------------------------------
st.subheader("Sub-bacias prioritárias (menor ISA primeiro)")
tabela = df[df["populacao"] > 0].sort_values("isa").head(15)
tabela = tabela[["cod_sub_bacia", "nome_bacia", "populacao", "isa", "faixa_isa", "ice", "idr"]]
tabela.columns = ["Código", "Bacia", "População", "ISA", "Faixa", "ICE (esgoto)", "IDR (drenagem)"]
st.dataframe(tabela, hide_index=True)

# ---------------------------------------------------------------
# 7. RODAPE: definicoes (consistencia das metricas)
# ---------------------------------------------------------------
with st.expander("Como os números são calculados"):
    st.write("- **ISA geral (ponderado):** média do ISA de cada sub-bacia, com peso na população.")
    st.write("- **Faixas do ISA:** Crítico < 0,5 | Baixo 0,5 a 0,7 | Médio 0,7 a 0,9 | Alto ≥ 0,9.")
    st.write("- **Sub-bacia em atenção:** faixa Crítico ou Baixo.")
    st.write("- **Dados:** base padronizada (sem duplicados nem valores ausentes), 255 sub-bacias.")
    st.write(f"- **Última atualização:** {DATA_BASE}.")
