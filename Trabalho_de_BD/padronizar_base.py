"""
Padroniza o CSV do ISA, gera a nova base (CSV + SQL) e, opcionalmente, importa no MySQL.

Exemplos:
  python padronizar_base.py                      (usa a base embutida)
  python padronizar_base.py outro_arquivo.csv
  python padronizar_base.py entrada.csv --outliers sinalizar --ausentes interpolar --sql-saida base.sql
  python padronizar_base.py entrada.csv --mysql-host localhost --mysql-user root --banco isa_bh   (senha: --mysql-senha ou env MYSQL_PWD)
"""
import argparse
import os
import sys

import padronizacao as P
import dados_isa
from isa_lib import carregar_bruto


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("entrada", nargs="?", help="CSV de entrada (opcional: sem ele usa a base embutida)")
    ap.add_argument("--csv-saida", default="base_isa_padronizada.csv")
    ap.add_argument("--sql-saida", default="base_isa_padronizada.sql")
    ap.add_argument("--banco", default="isa_bh")
    ap.add_argument("--ausentes", choices=P.MET_AUSENTES, default="interpolar")
    ap.add_argument("--outliers", choices=P.MET_OUTLIER, default="sinalizar")
    ap.add_argument("--colunas-outliers", nargs="+", default=["isa"])
    ap.add_argument("--metodo-outlier", choices=["iqr", "z"], default="iqr")
    ap.add_argument("-k", type=float, default=1.5)
    ap.add_argument("--escala", choices=["nenhuma", "zscore", "minmax"], default="nenhuma")
    ap.add_argument("--manter-duplicados", action="store_true")
    ap.add_argument("--mysql-host"); ap.add_argument("--mysql-port", type=int, default=3306)
    ap.add_argument("--mysql-user"); ap.add_argument("--mysql-senha", default=os.environ.get("MYSQL_PWD", ""))
    a = ap.parse_args(argv)

    base, log = P.padronizar(carregar_bruto(a.entrada) if a.entrada else dados_isa.carregar(), ausentes=a.ausentes, remover_duplicados=not a.manter_duplicados,
                             outliers=a.outliers, colunas_outliers=tuple(a.colunas_outliers),
                             metodo_outlier=a.metodo_outlier, k=a.k, escala=a.escala)
    print(log.to_string(index=False))
    P.para_csv(base).to_csv(a.csv_saida, index=False, encoding="utf-8")
    with open(a.sql_saida, "w", encoding="utf-8") as f:
        f.write(P.gerar_script_sql(base, a.banco))
    print(f"\nBase: {base.shape[0]} linhas x {base.shape[1]} colunas -> {a.csv_saida} | {a.sql_saida}")

    if a.mysql_host:
        try:
            r = P.importar_mysql(base, a.mysql_host, a.mysql_user, a.mysql_senha, a.banco, a.mysql_port)
        except ImportError:
            sys.exit("Instale o driver: pip install pymysql")
        print(f"Importado no MySQL: {r}")


if __name__ == "__main__":
    main()
