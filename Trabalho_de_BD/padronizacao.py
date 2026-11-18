"""
Padronização, tratamento e exportação da base ISA (CSV / SQL / MySQL).

Fluxo de `padronizar()`:
  1. nomes de colunas -> snake_case com unidade (area_ha, densidade_hab_ha ...)
  2. texto -> sem espaços extras; números em texto ("0,865") -> número
  3. colunas 100% vazias removidas
  4. duplicidades (linha inteira e chave cod_sub_bacia) removidas
  5. ausentes tratados (interpolação / mediana / média / zero / nenhum)
  6. índices forçados ao intervalo [0, 1]
  7. unidade métrica padronizada: area_km2 = area_ha / 100
  8. outliers sinalizados (padrão), winsorizados ou removidos
  9. (opcional) colunas em escala z-score ou min-max
"""
import numpy as np
import pandas as pd

RENOMEAR = {
    "ID_ISA_SUB_BACIA": "id_sub_bacia", "COD_SUB_BACIA": "cod_sub_bacia", "NOME_SUB_BACIA": "nome_sub_bacia",
    "AREA_SUB_BACIA": "area_ha", "POPULACAO_SUB_BACIA": "populacao", "DENSIDADE_SUB_BACIA": "densidade_hab_ha",
    "IAB_SUB_BACIA": "iab", "POPULACAO_SEM_REDE_COLETORA": "pop_sem_rede_coletora",
    "POPULACAO_COM_REDE_COLETORA": "pop_com_rede_coletora", "ICE_SUB_BACIA": "ice",
    "POPULACAO_SEM_INTERCEPTACAO": "pop_sem_interceptacao", "POPULACAO_COM_INTERCEPTACAO": "pop_com_interceptacao",
    "IIE_SUB_BACIA": "iie", "IES_SUB_BACIA": "ies", "POPULACAO_CF": "pop_cf",
    "POPULACAO_SEM_COLETA_LIXO_CF": "pop_sem_coleta_lixo_cf", "POPULACAO_COM_COLETA_LIXO_CF": "pop_com_coleta_lixo_cf",
    "ICL_CF_SUB_BACIA": "icl_cf", "POPULACAO_SEM_COLETA_LIXO_VF": "pop_sem_coleta_lixo_vf",
    "POPULACAO_COM_COLETA_LIXO_VF": "pop_com_coleta_lixo_vf", "ICL_VF_SUB_BACIA": "icl_vf",
    "POPULACAO_SEM_COLETA_LIXO_CFVF": "pop_sem_coleta_lixo_cfvf", "POPULACAO_COM_COLETA_LIXO_CFVF": "pop_com_coleta_lixo_cfvf",
    "ICL_SUB_BACIA": "icl", "POPULACAO_MANCHA_INUNDACAO": "pop_mancha_inundacao", "IDR_SUB_BACIA": "idr",
    "ISA_SUB_BACIA": "isa", "ID_ISA_BACIA": "id_bacia", "NOME_BACIA": "nome_bacia",
}
COLS_ID = ["id_sub_bacia", "cod_sub_bacia", "id_bacia"]
COLS_INDICE = ["iab", "ice", "iie", "ies", "icl_cf", "icl_vf", "icl", "idr", "isa"]
COLS_CONTAGEM = ["populacao", "pop_sem_rede_coletora", "pop_com_rede_coletora", "pop_sem_interceptacao",
                 "pop_com_interceptacao", "pop_cf", "pop_sem_coleta_lixo_cf", "pop_com_coleta_lixo_cf",
                 "pop_sem_coleta_lixo_vf", "pop_com_coleta_lixo_vf", "pop_sem_coleta_lixo_cfvf",
                 "pop_com_coleta_lixo_cfvf", "pop_mancha_inundacao"]
COLS_MEDIDA = ["area_ha", "densidade_hab_ha"]
COLS_NUM = COLS_ID + COLS_MEDIDA + COLS_CONTAGEM + COLS_INDICE
COLS_ESCALA = ["area_ha", "populacao", "densidade_hab_ha", "ice", "iie", "ies", "icl", "idr", "isa"]
FAIXAS = ["Crítico", "Baixo", "Médio", "Alto"]          # <0,5 | 0,5-0,7 | 0,7-0,9 | >=0,9
ARREDONDAR = {**{c: 3 for c in COLS_INDICE}, "area_ha": 2, "area_km2": 4, "densidade_hab_ha": 2}
MET_AUSENTES = ["interpolar", "mediana", "media", "zero", "remover linhas", "nenhum"]
MET_OUTLIER = ["sinalizar", "winsorizar", "remover"]


def _log(log, etapa, detalhe, n=0):
    log.append({"etapa": etapa, "detalhe": detalhe, "linhas_afetadas": int(n)})


def limites(s, metodo="iqr", k=1.5):
    """Limites inferior/superior para outliers. IQR=0 (coluna 'colada' em um valor) => sem detecção."""
    s = pd.Series(s).dropna().astype(float)
    if s.empty:
        return -np.inf, np.inf
    if metodo == "z":
        m, sd = s.mean(), s.std()
        return (m - k * sd, m + k * sd) if sd > 0 else (-np.inf, np.inf)
    q1, q3 = s.quantile([.25, .75])
    i = q3 - q1
    return (q1 - k * i, q3 + k * i) if i > 0 else (-np.inf, np.inf)


def padronizar(raw, ausentes="interpolar", remover_duplicados=True, outliers="sinalizar",
               colunas_outliers=("isa",), metodo_outlier="iqr", k=1.5, escala="nenhuma"):
    """Retorna (base_padronizada, log). `raw` é o CSV original (colunas em MAIÚSCULAS)."""
    log = []
    df = raw.copy()
    df.columns = [str(c).lstrip("\ufeff").strip() for c in df.columns]
    df = df.drop(columns=["GEOMETRIA"], errors="ignore")
    df = df.rename(columns={c: RENOMEAR[c] for c in df.columns if c in RENOMEAR})
    for obrig in ("cod_sub_bacia", "id_bacia", "nome_bacia", "populacao", "isa"):
        if obrig not in df.columns:
            raise ValueError(f"CSV fora do formato esperado: falta a coluna '{obrig}' (ou equivalente em maiúsculas).")
    _log(log, "1. colunas", f"{len(RENOMEAR)} nomes padronizados para snake_case com unidade; coluna GEOMETRIA ignorada")

    # --- textos e números escritos como texto
    txt = [c for c in df.columns if c not in COLS_NUM and not pd.api.types.is_numeric_dtype(df[c])]
    alterados = 0
    for c in txt:
        antes = df[c].astype("string")
        depois = antes.str.strip().str.replace(r"\s+", " ", regex=True).replace("", pd.NA)
        alterados += int(((antes != depois) & antes.notna()).sum())
        df[c] = depois
    _log(log, "2. texto", "espaços extras removidos e vazios -> nulo", alterados)
    conv = 0
    for c in [c for c in COLS_NUM if c in df.columns and not pd.api.types.is_numeric_dtype(df[c])]:
        novo = pd.to_numeric(df[c].astype("string").str.replace(",", ".", regex=False), errors="coerce")
        conv += int(novo.notna().sum())
        df[c] = novo
    if conv:
        _log(log, "2. texto", "números escritos como texto (ex.: '0,865') convertidos", conv)

    # --- colunas vazias
    vazias = [c for c in df.columns if df[c].isna().all()]
    if vazias:
        df = df.drop(columns=vazias)
        _log(log, "3. colunas vazias", "removidas (100% nulas): " + ", ".join(vazias), len(df))

    # --- duplicidades
    n0 = len(df)
    if remover_duplicados:
        df = df.drop_duplicates().drop_duplicates(subset="cod_sub_bacia", keep="first")
    _log(log, "4. duplicidades", "linhas duplicadas (inteiras ou por cod_sub_bacia) removidas", n0 - len(df))

    # --- ausentes
    num = [c for c in COLS_NUM if c in df.columns]
    nulos = df[num].isna().sum()
    nulos = nulos[nulos > 0]
    df = df.sort_values("cod_sub_bacia").reset_index(drop=True)
    if "nome_bacia" in df and df["nome_bacia"].isna().any():
        n = int(df["nome_bacia"].isna().sum())
        df["nome_bacia"] = df["nome_bacia"].fillna(df.groupby("id_bacia")["nome_bacia"].transform("first")).fillna("NÃO INFORMADO")
        _log(log, "5. ausentes", "nome_bacia nulo -> nome do mesmo id_bacia (ou 'NÃO INFORMADO')", n)
    if len(nulos) == 0:
        _log(log, "5. ausentes", "nenhum valor numérico ausente", 0)
    elif ausentes == "remover linhas":
        n = len(df)
        df = df.dropna(subset=list(nulos.index)).reset_index(drop=True)
        _log(log, "5. ausentes", "linhas com nulo removidas", n - len(df))
    elif ausentes != "nenhum":
        for c, qtd in nulos.items():
            if ausentes == "interpolar":
                df[c] = df[c].interpolate(method="linear", limit_direction="both")
            elif ausentes == "mediana":
                df[c] = df[c].fillna(df[c].median())
            elif ausentes == "media":
                df[c] = df[c].fillna(df[c].mean())
            elif ausentes == "zero":
                df[c] = df[c].fillna(0)
            _log(log, "5. ausentes", f"{c}: {ausentes}", qtd)

    # --- consistência: índices em [0, 1]
    fora = 0
    for c in [c for c in COLS_INDICE if c in df.columns]:
        fora += int(((df[c] < 0) | (df[c] > 1)).sum())
        df[c] = df[c].clip(0, 1)
    _log(log, "6. consistência", "índices forçados ao intervalo [0, 1]", fora)

    # --- unidade métrica + derivadas
    if "area_ha" in df.columns:
        df["area_km2"] = df["area_ha"] / 100
        _log(log, "7. unidades", "area_km2 = area_ha / 100 (1 km² = 100 ha); densidade em hab/ha", len(df))
    df["sem_populacao"] = df["populacao"].fillna(-1).eq(0)
    df["faixa_isa"] = pd.cut(df["isa"], [-np.inf, .5, .7, .9, np.inf], labels=FAIXAS, right=False).astype("string")

    # --- outliers
    marcadas = pd.Series(False, index=df.index)
    for c in [c for c in colunas_outliers if c in df.columns]:
        lo, hi = limites(df[c], metodo_outlier, k)
        flag = (df[c] < lo) | (df[c] > hi)
        df[f"outlier_{c}"] = flag
        marcadas |= flag
        det = f"{c}: {int(flag.sum())} fora de [{lo:.3f}; {hi:.3f}]" if np.isfinite(lo) else f"{c}: IQR=0, detecção ignorada"
        if outliers == "winsorizar" and np.isfinite(lo):
            df[c] = df[c].clip(lo, hi)
        _log(log, "8. outliers", f"{outliers} — {det} ({metodo_outlier}, k={k})", flag.sum())
    if outliers == "remover" and marcadas.any():
        n = len(df)
        df = df.loc[~marcadas].reset_index(drop=True)
        _log(log, "8. outliers", "linhas removidas", n - len(df))
    if outliers == "winsorizar":
        df["faixa_isa"] = pd.cut(df["isa"], [-np.inf, .5, .7, .9, np.inf], labels=FAIXAS, right=False).astype("string")

    # --- escala estatística
    if escala in ("zscore", "minmax"):
        for c in [c for c in COLS_ESCALA if c in df.columns]:
            s = df[c].astype(float)
            if escala == "zscore":
                df[f"{c}_z"] = (s - s.mean()) / s.std() if s.std() > 0 else 0.0
            else:
                df[f"{c}_mm"] = (s - s.min()) / (s.max() - s.min()) if s.max() > s.min() else 0.0
        _log(log, "9. escala", f"colunas *_{'z' if escala == 'zscore' else 'mm'} adicionadas", len(df))

    # --- tipos finais
    for c, nd in ARREDONDAR.items():
        if c in df.columns:
            df[c] = df[c].astype(float).round(nd)
    for c in COLS_ID + COLS_CONTAGEM:
        if c in df.columns:
            df[c] = df[c].round().astype("Int64" if df[c].isna().any() else "int64")
    for c in df.columns:                      # texto como `object`: compatível com Plotly/Streamlit/MySQL em qualquer versão do pandas
        if not pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c]):
            df[c] = df[c].astype(object)
    ordem = ([c for c in COLS_ID if c in df.columns] + ["nome_bacia", "area_ha", "area_km2", "populacao", "densidade_hab_ha"]
             + [c for c in COLS_CONTAGEM[1:] if c in df.columns] + [c for c in COLS_INDICE if c in df.columns])
    resto = [c for c in df.columns if c not in ordem]
    df = df[[c for c in ordem if c in df.columns] + resto]
    return df.reset_index(drop=True), pd.DataFrame(log)


def para_csv(df):
    """Booleanos como 0/1 (aceito por MySQL Workbench/LOAD DATA em colunas TINYINT)."""
    return df.assign(**{c: df[c].astype(int) for c in df.columns if pd.api.types.is_bool_dtype(df[c])})


# ======================= SQL / MySQL ==========================================
_SQL_FIXO = {"id_sub_bacia": "INT NOT NULL", "cod_sub_bacia": "INT NOT NULL", "id_bacia": "INT NOT NULL",
             "area_ha": "DECIMAL(10,2)", "area_km2": "DECIMAL(10,4)", "densidade_hab_ha": "DECIMAL(8,2)",
             "faixa_isa": "VARCHAR(10)", "nome_bacia": "VARCHAR(120) NOT NULL"}


def _tipo_sql(col, serie):
    if col in _SQL_FIXO:
        return _SQL_FIXO[col]
    if col in COLS_INDICE:
        return "DECIMAL(4,3)"
    if pd.api.types.is_bool_dtype(serie):
        return "TINYINT(1) NOT NULL"
    if pd.api.types.is_integer_dtype(serie):
        return "INT"
    if pd.api.types.is_float_dtype(serie):
        return "DOUBLE"
    return "VARCHAR(255)"


def _partes(df):
    bacia = df[["id_bacia", "nome_bacia"]].drop_duplicates("id_bacia").sort_values("id_bacia")
    sub = df.drop(columns=["nome_bacia"])
    return bacia, sub


def gerar_ddl(df, mysql=True):
    """Lista de comandos CREATE (tabelas `bacia` e `sub_bacia`). mysql=False remove ENGINE (útil p/ testes em SQLite)."""
    bacia, sub = _partes(df)
    fim = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if mysql else ""
    cols_sub = [f"  {c} {_tipo_sql(c, sub[c])}" for c in sub.columns]
    return [
        f"CREATE TABLE bacia (\n  id_bacia INT NOT NULL,\n  nome_bacia VARCHAR(120) NOT NULL,\n  PRIMARY KEY (id_bacia)\n){fim}",
        "CREATE TABLE sub_bacia (\n" + ",\n".join(cols_sub) +
        ",\n  PRIMARY KEY (id_sub_bacia),\n  UNIQUE (cod_sub_bacia),\n"
        "  CONSTRAINT fk_sub_bacia_bacia FOREIGN KEY (id_bacia) REFERENCES bacia (id_bacia)\n)" + fim,
        "CREATE INDEX idx_sub_bacia_isa ON sub_bacia (isa)",
    ]


def _py(v):
    if v is None or v is pd.NA or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (np.bool_, bool)):
        return int(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return v


def _lit(v):
    v = _py(v)
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("\\", "\\\\").replace("'", "''") + "'"


def _registros(d):
    return [tuple(_py(v) for v in row) for row in d.itertuples(index=False, name=None)]


def gerar_script_sql(df, banco="isa_bh", lote=200):
    """Script .sql completo (para `mysql < arquivo.sql`)."""
    bacia, sub = _partes(df)
    out = [f"-- Base ISA padronizada: {len(bacia)} bacias, {len(sub)} sub-bacias",
           f"CREATE DATABASE IF NOT EXISTS {banco} DEFAULT CHARACTER SET utf8mb4;", f"USE {banco};", "SET NAMES utf8mb4;",
           "DROP TABLE IF EXISTS sub_bacia;", "DROP TABLE IF EXISTS bacia;"]
    out += [c + ";" for c in gerar_ddl(df)]
    for nome, d in (("bacia", bacia), ("sub_bacia", sub)):
        cols = ", ".join(d.columns)
        regs = ["(" + ", ".join(_lit(v) for v in r) + ")" for r in _registros(d)]
        for i in range(0, len(regs), lote):
            out.append(f"INSERT INTO {nome} ({cols}) VALUES\n" + ",\n".join(regs[i:i + lote]) + ";")
    return "\n".join(out) + "\n"


def _inserir(cur, df, ph="%s"):
    bacia, sub = _partes(df)
    for nome, d in (("bacia", bacia), ("sub_bacia", sub)):
        sql = f"INSERT INTO {nome} ({', '.join(d.columns)}) VALUES ({', '.join([ph] * d.shape[1])})"
        cur.executemany(sql, _registros(d))


def importar_mysql(df, host, user, password, database="isa_bh", port=3306, recriar=True):
    """Cria o banco/tabelas e carrega os dados. Requer `pip install pymysql`. Retorna contagens."""
    import pymysql
    con = pymysql.connect(host=host, port=int(port), user=user, password=password, charset="utf8mb4", autocommit=False)
    try:
        with con.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{database}` DEFAULT CHARACTER SET utf8mb4")
            cur.execute(f"USE `{database}`")
            if recriar:
                cur.execute("DROP TABLE IF EXISTS sub_bacia")
                cur.execute("DROP TABLE IF EXISTS bacia")
            for cmd in gerar_ddl(df):
                cur.execute(cmd)
            _inserir(cur, df)
            cur.execute("SELECT COUNT(*) FROM bacia")
            nb = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sub_bacia")
            ns = cur.fetchone()[0]
        con.commit()
        return {"banco": database, "bacia": nb, "sub_bacia": ns}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()
