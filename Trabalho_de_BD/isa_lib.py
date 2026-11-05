"""Leitura, estatística descritiva, regressão linear e interpolação (sem dependência de Streamlit/Plotly)."""
import numpy as np
import pandas as pd
from scipy import stats

ROT = {"area_ha": "Área (ha)", "populacao": "População", "densidade_hab_ha": "Densidade (hab/ha)",
       "ice": "ICE – cobertura de esgoto", "iie": "IIE – interceptação", "ies": "IES – esgotamento sanitário",
       "icl_cf": "ICL CF – coleta de lixo (CF)", "icl_vf": "ICL VF – coleta de lixo (VF)", "icl": "ICL – coleta de lixo",
       "idr": "IDR – drenagem/risco", "isa": "ISA – índice geral",
       "pop_sem_rede_coletora": "Pop. sem rede coletora", "pop_sem_interceptacao": "Pop. sem interceptação",
       "pop_mancha_inundacao": "Pop. em mancha de inundação"}
VARS = list(ROT)                      # variáveis numéricas oferecidas na análise
METODOS_INTERP = ["linear", "nearest", "pchip", "quadratic", "cubic", "média global", "mediana global", "média da bacia"]


def carregar_bruto(fonte):
    return pd.read_csv(fonte, encoding="utf-8-sig")


def rotulo(c):
    return ROT.get(c, c)


def br(v, nd=3):
    """Número no formato brasileiro (1.234,567)."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    return f"{v:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def com_rotulo(df):
    """Rótulo único da bacia: o nome NÃO é chave (há 63 nomes para 98 ids)."""
    return df.assign(bacia=df["nome_bacia"].astype(str) + " (#" + df["id_bacia"].astype(str) + ")")


# ------------------------------- descritivas ----------------------------------
def descritivas(df, cols):
    rows = []
    for c in cols:
        s = df[c].dropna().astype(float)
        if s.empty:
            continue
        moda = s.mode()
        rows.append({"variável": c, "n": len(s), "média": s.mean(), "mediana": s.median(), "moda": moda.iloc[0],
                     "freq. da moda": int((s == moda.iloc[0]).sum()), "nº de modas": len(moda),
                     "desvio padrão": s.std(), "variância": s.var(), "mín": s.min(), "Q1": s.quantile(.25),
                     "Q3": s.quantile(.75), "máx": s.max(), "amplitude": s.max() - s.min(),
                     "CV (%)": 100 * s.std() / s.mean() if s.mean() else np.nan,
                     "assimetria": s.skew(), "curtose": s.kurt()})
    return pd.DataFrame(rows).set_index("variável")


def comparar_antes_depois(antes, depois, cols):
    a, d = descritivas(antes, cols), descritivas(depois, cols)
    out = pd.DataFrame({"n antes": a["n"], "n depois": d["n"], "média antes": a["média"], "média depois": d["média"],
                        "mediana antes": a["mediana"], "mediana depois": d["mediana"],
                        "desvio antes": a["desvio padrão"], "desvio depois": d["desvio padrão"]})
    return out


# -------------------------------- bacias ---------------------------------------
def por_bacia(df):
    d = df.assign(_pxi=df["populacao"] * df["isa"])
    g = d.groupby("id_bacia").agg(nome_bacia=("nome_bacia", "first"), sub_bacias=("cod_sub_bacia", "count"),
                                  populacao=("populacao", "sum"), isa_medio=("isa", "mean"), _pxi=("_pxi", "sum"))
    g["isa_ponderado"] = g["_pxi"] / g["populacao"].where(g["populacao"] > 0)
    g["bacia"] = g["nome_bacia"].astype(str) + " (#" + g.index.astype(str) + ")"
    return g.drop(columns="_pxi").sort_values("isa_ponderado")


# ------------------------------- regressão -------------------------------------
def regressao_simples(x, y):
    """OLS y = a + b·x com IC95% do coeficiente e termos para IC/IP de previsões."""
    m = pd.Series(x).notna().to_numpy() & pd.Series(y).notna().to_numpy()
    x = np.asarray(x, float)[m]; y = np.asarray(y, float)[m]
    n = len(x)
    if n < 3 or np.ptp(x) == 0:
        raise ValueError("São necessários pelo menos 3 pontos e variação em X para a regressão.")
    r = stats.linregress(x, y)
    pred = r.intercept + r.slope * x
    resid = y - pred
    sse = float((resid ** 2).sum())
    s2 = sse / (n - 2)
    t = stats.t.ppf(.975, n - 2)
    rho = stats.spearmanr(x, y)[0]
    return {"n": n, "x": x, "y": y, "pred": pred, "resid": resid, "slope": r.slope, "intercept": r.intercept,
            "r": r.rvalue, "r2": r.rvalue ** 2, "p": r.pvalue, "stderr": r.stderr,
            "ic_slope": (r.slope - t * r.stderr, r.slope + t * r.stderr), "rmse": np.sqrt(sse / n),
            "mae": float(np.abs(resid).mean()), "s2": s2, "xbar": x.mean(), "sxx": float(((x - x.mean()) ** 2).sum()),
            "t": t, "spearman": rho}


def prever(mod, x0):
    """Previsão, IC95% da média e intervalo de predição 95% para novos valores de x0 (escalar ou array)."""
    x0 = np.asarray(x0, float)
    yhat = mod["intercept"] + mod["slope"] * x0
    base = (x0 - mod["xbar"]) ** 2 / mod["sxx"]
    se_m = np.sqrt(mod["s2"] * (1 / mod["n"] + base))
    se_p = np.sqrt(mod["s2"] * (1 + 1 / mod["n"] + base))
    return yhat, yhat - mod["t"] * se_m, yhat + mod["t"] * se_m, yhat - mod["t"] * se_p, yhat + mod["t"] * se_p


def regressao_multipla(df, y, xs):
    d = df[[y] + list(xs)].dropna()
    n, p = len(d), len(xs) + 1
    if n <= p:
        raise ValueError("Poucas observações para o número de variáveis.")
    X = np.column_stack([np.ones(n), d[list(xs)].to_numpy(float)])
    yy = d[y].to_numpy(float)
    beta = np.linalg.lstsq(X, yy, rcond=None)[0]
    resid = yy - X @ beta
    gl = n - p
    sse = float((resid ** 2).sum()); sst = float(((yy - yy.mean()) ** 2).sum())
    s2 = sse / gl
    cov = s2 * np.linalg.pinv(X.T @ X)
    se = np.sqrt(np.diag(cov))
    t = beta / se
    pv = 2 * stats.t.sf(np.abs(t), gl)
    r2 = 1 - sse / sst if sst > 0 else np.nan
    r2aj = 1 - (1 - r2) * (n - 1) / gl
    f = ((sst - sse) / (p - 1)) / s2 if p > 1 and s2 > 0 else np.nan
    tc = stats.t.ppf(.975, gl)
    tab = pd.DataFrame({"coeficiente": beta, "erro padrão": se, "t": t, "p-valor": pv,
                        "IC95% inf.": beta - tc * se, "IC95% sup.": beta + tc * se}, index=["intercepto"] + list(xs))
    return {"n": n, "tabela": tab, "r2": r2, "r2_aj": r2aj, "rmse": np.sqrt(sse / n),
            "p_f": float(stats.f.sf(f, p - 1, gl)) if np.isfinite(f) else np.nan,
            "pred": X @ beta, "y": yy, "resid": resid, "cond": float(np.linalg.cond(X))}


# ------------------------------- interpolação ----------------------------------
def preencher(df, col, metodo, ordem="cod_sub_bacia"):
    """Preenche NaN de `col`. Interpolação percorre as linhas na ordem de `ordem` (é a 'régua' da interpolação)."""
    d = df.sort_values(ordem)
    s = d[col].astype(float).reset_index(drop=True)
    if metodo in ("linear", "nearest", "pchip", "quadratic", "cubic"):
        r = s.interpolate(method=metodo, limit_direction="both")
    elif metodo == "média global":
        r = s.fillna(s.mean())
    elif metodo == "mediana global":
        r = s.fillna(s.median())
    elif metodo == "média da bacia":
        g = s.groupby(d["id_bacia"].to_numpy()).transform("mean")
        r = s.fillna(g).fillna(s.mean())
    else:
        raise ValueError(f"método desconhecido: {metodo}")
    r = r.bfill().ffill().clip(s.min(), s.max())                       # extrapolações (cubic/quadratic) não passam do observado
    return pd.Series(r.to_numpy(), index=d.index).reindex(df.index)


def validar_interpolacao(df, col, metodos, frac=.10, repeticoes=20, seed=0, ordem="cod_sub_bacia"):
    """Esconde `frac` dos valores conhecidos, preenche e mede o erro. Compara métodos e o desvio padrão (referência)."""
    base = df[[col, "id_bacia", ordem]].dropna(subset=[col]).reset_index(drop=True)
    rng = np.random.default_rng(seed)
    erros = {m: [] for m in metodos}
    for _ in range(repeticoes):
        mask = rng.random(len(base)) < frac
        if mask.sum() == 0:
            continue
        t = base.copy(); t.loc[mask, col] = np.nan
        for m in metodos:
            r = preencher(t, col, m, ordem)
            e = r[mask].to_numpy() - base.loc[mask, col].to_numpy()
            erros[m].append((np.sqrt((e ** 2).mean()), np.abs(e).mean()))
    res = pd.DataFrame({m: {"RMSE": np.mean([a for a, _ in v]), "MAE": np.mean([b for _, b in v]),
                            "RMSE (desvio entre repetições)": np.std([a for a, _ in v])} for m, v in erros.items()}).T
    return res.sort_values("RMSE"), float(base[col].std())
