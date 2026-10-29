"""Funções de análise e gráficos (independentes do Streamlit, para poderem ser testadas)."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

sns.set_theme(style="whitegrid", context="notebook")
AZUL, LARANJA, VERMELHO, CINZA = "#1f77b4", "#ff7f0e", "#d62728", "#7f7f7f"

IDX = ["ICE_SUB_BACIA", "IIE_SUB_BACIA", "IES_SUB_BACIA", "ICL_SUB_BACIA", "IDR_SUB_BACIA", "ISA_SUB_BACIA"]
ROT = {"ICE_SUB_BACIA": "ICE (cobertura de esgoto)", "IIE_SUB_BACIA": "IIE (interceptação)",
       "IES_SUB_BACIA": "IES (esgotamento sanitário)", "ICL_SUB_BACIA": "ICL (coleta de lixo)",
       "IDR_SUB_BACIA": "IDR (drenagem/risco)", "ISA_SUB_BACIA": "ISA (índice geral)"}
NUM = ["AREA_SUB_BACIA", "POPULACAO_SUB_BACIA", "DENSIDADE_SUB_BACIA"] + IDX


def carregar(src):
    df = pd.read_csv(src, encoding="utf-8-sig")
    df = df.drop(columns=["GEOMETRIA"], errors="ignore")
    df["NOME_BACIA"] = df["NOME_BACIA"].astype("string")
    df["FAIXA_ISA"] = pd.cut(df["ISA_SUB_BACIA"], [0, .5, .7, .9, 1.0001],
                             labels=["Crítico (<0,5)", "Baixo (0,5–0,7)", "Médio (0,7–0,9)", "Alto (≥0,9)"], right=False)
    return df


def descritivas(df, cols):
    rows = []
    for c in cols:
        s = df[c].dropna()
        moda = s.mode()
        rows.append({
            "variável": c, "n": len(s), "média": s.mean(), "mediana": s.median(),
            "moda": moda.iloc[0], "nº de modas": len(moda), "desvio padrão": s.std(),
            "variância": s.var(), "mín": s.min(), "máx": s.max(),
            "amplitude": s.max() - s.min(), "CV (%)": 100 * s.std() / s.mean() if s.mean() else np.nan,
            "assimetria": s.skew(), "curtose": s.kurt(),
        })
    return pd.DataFrame(rows).set_index("variável")


def outliers_iqr(df, cols):
    rows = []
    for c in cols:
        s = df[c]
        q1, q3 = s.quantile([.25, .75]); i = q3 - q1
        lo, hi = q1 - 1.5 * i, q3 + 1.5 * i
        z = np.abs(stats.zscore(s))
        rows.append({"variável": c, "limite inferior": lo, "limite superior": hi,
                     "outliers IQR": int(((s < lo) | (s > hi)).sum()), "outliers |z|>3": int((z > 3).sum()),
                     "% IQR": 100 * ((s < lo) | (s > hi)).mean()})
    return pd.DataFrame(rows).set_index("variável")


def por_bacia(df):
    g = df.groupby("NOME_BACIA")
    out = g.apply(lambda x: pd.Series({
        "sub_bacias": len(x), "populacao": x.POPULACAO_SUB_BACIA.sum(),
        "ISA_medio": x.ISA_SUB_BACIA.mean(),
        "ISA_ponderado": np.average(x.ISA_SUB_BACIA, weights=x.POPULACAO_SUB_BACIA) if x.POPULACAO_SUB_BACIA.sum() > 0 else np.nan,
    }), include_groups=False)
    return out.sort_values("ISA_ponderado")


# ------------------------------- gráficos ------------------------------------
def fig_hist_isa(df):
    fig, ax = plt.subplots(figsize=(9, 4.5))
    s = df.ISA_SUB_BACIA
    sns.histplot(s, bins=30, kde=True, color=AZUL, ax=ax)
    ax.axvline(s.mean(), color=VERMELHO, ls="--", label=f"Média = {s.mean():.3f}")
    ax.axvline(s.median(), color=LARANJA, ls="-", label=f"Mediana = {s.median():.3f}")
    ax.axvline(s.mode().iloc[0], color="green", ls=":", label=f"Moda = {s.mode().iloc[0]:.3f}")
    ax.set_title("Distribuição do ISA nas sub-bacias: massa à direita, cauda longa à esquerda")
    ax.set_xlabel("ISA"); ax.set_ylabel("Nº de sub-bacias"); ax.legend()
    fig.tight_layout(); return fig


def fig_box_indices(df):
    fig, ax = plt.subplots(figsize=(9, 4.8))
    d = df[IDX].rename(columns=ROT).melt(var_name="índice", value_name="valor")
    sns.boxplot(data=d, y="índice", x="valor", color="#9ecae1", fliersize=3, ax=ax)
    ax.set_title("Boxplot dos índices: quase todos 'colados' em 1,0, com outliers só para baixo")
    ax.set_ylabel(""); fig.tight_layout(); return fig


def fig_corr(df):
    cols = ["AREA_SUB_BACIA", "POPULACAO_SUB_BACIA", "DENSIDADE_SUB_BACIA",
            "POPULACAO_SEM_REDE_COLETORA", "POPULACAO_SEM_INTERCEPTACAO", "POPULACAO_MANCHA_INUNDACAO"] + IDX
    c = df[cols].corr(method="spearman")
    fig, ax = plt.subplots(figsize=(9, 7.5))
    sns.heatmap(c, annot=True, fmt=".2f", cmap="RdBu_r", center=0, vmin=-1, vmax=1,
                annot_kws={"size": 7}, cbar_kws={"shrink": .7}, ax=ax)
    ax.set_title("Correlação de Spearman (robusta a outliers e assimetria)")
    fig.tight_layout(); return fig


def fig_componentes_vs_isa(df):
    comps = ["IES_SUB_BACIA", "ICL_SUB_BACIA", "IDR_SUB_BACIA", "ICE_SUB_BACIA"]
    fig, axs = plt.subplots(2, 2, figsize=(10, 7))
    for ax, c in zip(axs.ravel(), comps):
        sns.regplot(data=df, x=c, y="ISA_SUB_BACIA", ax=ax, scatter_kws={"s": 18, "alpha": .5, "color": AZUL},
                    line_kws={"color": VERMELHO})
        r = df[[c, "ISA_SUB_BACIA"]].corr("spearman").iloc[0, 1]
        ax.set_title(f"{ROT[c]} × ISA (ρ = {r:.2f})", fontsize=10)
    fig.suptitle("Quais componentes 'puxam' o ISA para baixo?", y=1.0)
    fig.tight_layout(); return fig


def fig_faixas(df):
    fig, ax = plt.subplots(figsize=(8, 4.2))
    c = df.FAIXA_ISA.value_counts().reindex(df.FAIXA_ISA.cat.categories)
    cores = [VERMELHO, LARANJA, "#ffd92f", "#2ca02c"]
    ax.bar(c.index.astype(str), c.values, color=cores)
    for i, v in enumerate(c.values):
        ax.text(i, v + 2, f"{v} ({100 * v / c.sum():.1f}%)", ha="center")
    ax.set_title("Sub-bacias por faixa de ISA"); ax.set_ylabel("Nº de sub-bacias")
    fig.tight_layout(); return fig


def fig_ranking_bacias(df, n=12, minimo_pop=0):
    b = por_bacia(df).dropna(subset=["ISA_ponderado"])
    b = b[b.populacao >= minimo_pop].head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.barh(b.index.astype(str), b.ISA_ponderado, color=np.where(b.ISA_ponderado < .8, VERMELHO, LARANJA))
    for y, (v, p) in enumerate(zip(b.ISA_ponderado, b.populacao)):
        ax.text(v + .003, y, f"{v:.3f} · {int(p):,} hab.".replace(",", "."), va="center", fontsize=8)
    ax.set_xlim(0, 1.15); ax.set_xlabel("ISA ponderado pela população")
    ax.set_title(f"As {n} bacias com pior ISA (ponderado por população)")
    fig.tight_layout(); return fig


def fig_pior_subbacias(df, n=10):
    p = df.nsmallest(n, "ISA_SUB_BACIA").copy()
    p["rótulo"] = p.COD_SUB_BACIA.astype(str) + " · " + p.NOME_BACIA.astype(str).str.slice(0, 22)
    m = p.set_index("rótulo")[["ICE_SUB_BACIA", "IIE_SUB_BACIA", "ICL_SUB_BACIA", "IDR_SUB_BACIA", "ISA_SUB_BACIA"]]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    sns.heatmap(m, annot=True, fmt=".2f", cmap="RdYlGn", vmin=0, vmax=1, cbar_kws={"shrink": .7}, ax=ax)
    ax.set_title(f"Diagnóstico das {n} piores sub-bacias: qual componente falhou em cada uma?")
    ax.set_ylabel(""); ax.set_xticklabels([t.get_text().replace("_SUB_BACIA", "") for t in ax.get_xticklabels()], rotation=0)
    fig.tight_layout(); return fig


def fig_pop_vs_isa(df):
    fig, ax = plt.subplots(figsize=(9, 5))
    sc = ax.scatter(df.POPULACAO_SUB_BACIA, df.ISA_SUB_BACIA, c=df.POPULACAO_MANCHA_INUNDACAO,
                    cmap="YlOrRd", s=30 + df.AREA_SUB_BACIA / 5, alpha=.75, edgecolor="k", linewidth=.3)
    plt.colorbar(sc, label="População em mancha de inundação")
    for _, r in df.nsmallest(4, "ISA_SUB_BACIA").iterrows():
        ax.annotate(str(r.NOME_BACIA)[:20], (r.POPULACAO_SUB_BACIA, r.ISA_SUB_BACIA), fontsize=8,
                    xytext=(6, -3), textcoords="offset points")
    ax.set_xscale("log"); ax.set_xlabel("População da sub-bacia (escala log)"); ax.set_ylabel("ISA")
    ax.set_title("População × ISA (cor = risco de inundação, tamanho = área)")
    fig.tight_layout(); return fig


def fig_densidade_faixas(df):
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    d = df.copy()
    d["faixa de densidade"] = pd.cut(d.DENSIDADE_SUB_BACIA, [-1, 50, 100, 150, 300],
                                     labels=["≤50", "50–100", "100–150", ">150"])
    sns.boxplot(data=d, x="faixa de densidade", y="ISA_SUB_BACIA", color="#a1d99b", ax=ax)
    sns.stripplot(data=d, x="faixa de densidade", y="ISA_SUB_BACIA", color="k", size=2.5, alpha=.4, ax=ax)
    ax.set_title("ISA por faixa de densidade: a densidade praticamente não explica o ISA")
    ax.set_xlabel("Densidade (hab./ha)"); fig.tight_layout(); return fig


def fig_qq(df):
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    stats.probplot(df.ISA_SUB_BACIA, dist="norm", plot=axs[0]); axs[0].set_title("Q-Q plot do ISA")
    stats.probplot(np.log1p(df.POPULACAO_SUB_BACIA), dist="norm", plot=axs[1]); axs[1].set_title("Q-Q plot de log(1+População)")
    fig.tight_layout(); return fig


def fig_dist_populacao(df):
    fig, axs = plt.subplots(1, 2, figsize=(10, 4))
    sns.histplot(df.POPULACAO_SUB_BACIA, bins=30, color=AZUL, ax=axs[0]); axs[0].set_title("População (escala original)")
    sns.histplot(np.log1p(df.POPULACAO_SUB_BACIA), bins=30, color=LARANJA, ax=axs[1]); axs[1].set_title("log(1 + população)")
    fig.tight_layout(); return fig