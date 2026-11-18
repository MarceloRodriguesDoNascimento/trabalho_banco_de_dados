# Pipeline ETL do Índice de Salubridade Ambiental (ISA) por sub-bacia — Belo Horizonte

Projeto prático da disciplina de **Banco de Dados**: uma pipeline de Engenharia de Dados (ETL) ponta a ponta, com
**Arquitetura Medalhão** (Bronze → Prata → Ouro), modelagem relacional em **MySQL**, Análise Exploratória (EDA) e
dashboard no Power BI.

> Os trechos marcados com **`[PREENCHER]`** dependem de informações da equipe. Complete todos antes de entregar.

- **Equipe:** `[PREENCHER: nomes]`
- **Professor(a):** `[PREENCHER]`
- **Base aprovada pelo professor na Semana 1:** `[PREENCHER: sim, em __/__/____]`

---

## 1. Objetivo e pergunta de negócio

O ISA mede as condições de saneamento de cada sub-bacia da cidade (esgoto, coleta de lixo e drenagem, entre outros
componentes), numa escala de 0 (pior) a 1 (melhor). O projeto organiza esses dados e responde:

> **Quais sub-bacias puxam o ISA para baixo e onde agir primeiro?** `[PREENCHER: ajuste a pergunta com a equipe]`

## 2. Fonte dos dados (Bronze)

| Item | Informação |
|---|---|
| Arquivo original | `20230502_indice_-salubridade_-ambiental_-subbacia.csv` |
| Portal de origem | `[PREENCHER: nome do portal]` |
| Link de download | `[PREENCHER: URL]` |
| Data do download | `[PREENCHER]` |
| Licença / condições de uso | `[PREENCHER]` |
| Formato | CSV, UTF-8 (com BOM), separador vírgula |
| Tamanho | 255 linhas (uma por sub-bacia) × 30 colunas |

Características do arquivo original:

- **Identificadores:** `ID_ISA_SUB_BACIA`, `COD_SUB_BACIA` (únicos) e `ID_ISA_BACIA` (98 bacias).
- **Geometria:** a coluna `GEOMETRIA` traz o polígono de cada sub-bacia em WKT, com coordenadas em UTM (metros).
- **Coluna vazia:** `NOME_SUB_BACIA` está 100% vazia.
- **Sem datas:** a base é uma fotografia de um único momento, então **não há série temporal** (ver Limitações).

O arquivo original fica em `data/raw/` e **nunca é alterado**: todo o tratamento é feito por script.

## 3. Arquitetura Medalhão

```
data/raw/*.csv  ──►  padronizar_base.py  ──►  data/silver/base_isa_padronizada.csv
   (Bronze)            (padronizacao.py)                   (Prata)
                                                              │
                                                              ▼
                                         sql/base_isa_padronizada.sql  ──►  MySQL: bacia + sub_bacia
                                                                                      (Ouro)
```

| Camada | O que contém | Onde |
|---|---|---|
| **Bronze** | CSV original, sem nenhuma modificação | `data/raw/` |
| **Prata** | Base limpa e padronizada (CSV) | `data/silver/` |
| **Ouro** | Tabelas relacionais no MySQL (`bacia` e `sub_bacia`) | banco `isa_bh` |

## 4. Estrutura do repositório

```
.
├── README.md
├── requirements.txt
├── .gitignore                    # [CRIAR] senhas, __pycache__, arquivos temporários
├── data/
│   ├── raw/                      # Bronze: CSV original intocado
│   └── silver/                   # Prata: base_isa_padronizada.csv
├── sql/
│   └── base_isa_padronizada.sql  # DDL + INSERTs (Ouro)
├── docs/
│   ├── der.png                   # [INSERIR] Diagrama Entidade-Relacionamento
│   └── relatorio_eda.md          # [CRIAR] Relatório de EDA
├── padronizar_base.py            # linha de comando: Bronze → Prata → SQL (e carga no MySQL)
├── padronizacao.py               # tratamento (Prata), geração do SQL e carga no MySQL
└── extras (opcionais, usados nos painéis em Streamlit)
    ├── app.py, dashboard.py, graficos.py, isa_lib.py, mapa.py
    └── dados_isa.py              # cópia embutida do CSV original, usada só pelo app
```

> As pastas `data/` e `sql/` precisam existir antes de rodar os comandos da seção 5.

## 5. Como executar

**Requisitos:** Python 3.10+ e MySQL (versão: `[PREENCHER]`).

```bash
pip install -r requirements.txt
```

### 5.1 Bronze → Prata → script SQL

```bash
python padronizar_base.py data/raw/20230502_indice_-salubridade_-ambiental_-subbacia.csv \
    --csv-saida data/silver/base_isa_padronizada.csv \
    --sql-saida sql/base_isa_padronizada.sql
```

O script imprime o **relatório do tratamento** (etapa, detalhe e linhas afetadas). Rodar de novo gera sempre o mesmo resultado
a partir do arquivo bruto.

### 5.2 Ouro: criar o banco e carregar no MySQL

**Opção A — script SQL (estrutura + dados):**

```bash
mysql -u SEU_USUARIO -p < sql/base_isa_padronizada.sql
```

**Opção B — carga automática em Python** (cria o banco e as tabelas e insere os dados):

```bash
export MYSQL_PWD="sua_senha"      # a senha não vai para o código nem para o GitHub
python padronizar_base.py data/raw/20230502_indice_-salubridade_-ambiental_-subbacia.csv \
    --mysql-host localhost --mysql-user SEU_USUARIO --banco isa_bh
```

### 5.3 Opções do tratamento

| Opção | Valores | Padrão |
|---|---|---|
| `--ausentes` | `interpolar`, `mediana`, `media`, `zero`, `remover linhas`, `nenhum` | `interpolar` |
| `--outliers` | `sinalizar`, `winsorizar`, `remover` | `sinalizar` |
| `--colunas-outliers` | colunas a verificar | `isa` |
| `--metodo-outlier` / `-k` | `iqr` ou `z` / sensibilidade | `iqr` / `1.5` |
| `--escala` | `nenhuma`, `zscore`, `minmax` | `nenhuma` |
| `--manter-duplicados` | mantém linhas duplicadas | remove |

## 6. Tratamento da camada Prata

Resultado do tratamento sobre esta base (255 linhas):

| # | Etapa | O que foi feito | Resultado |
|---|---|---|---|
| 1 | Colunas | nomes em `snake_case` com unidade (`area_ha`, `densidade_hab_ha`...); `GEOMETRIA` não segue para a Prata | 29 nomes padronizados |
| 2 | Texto | espaços extras removidos (`trim`) e vazios viram nulo | 10 células ajustadas |
| 3 | Colunas vazias | `nome_sub_bacia` removida (100% nula) | 1 coluna |
| 4 | Duplicidades | linhas inteiras ou repetidas por `cod_sub_bacia` | 0 encontradas |
| 5 | Ausentes | nenhum valor numérico ausente (`--ausentes` fica disponível) | 0 |
| 6 | Consistência | índices forçados ao intervalo [0, 1] | 0 fora do intervalo |
| 7 | Unidade métrica | `area_km2 = area_ha / 100` (1 km² = 100 ha) | coluna criada |
| 8 | Outliers | **sinalizados**, não removidos (coluna `outlier_isa`) | 19 sub-bacias no ISA (IQR, k = 1,5) |
| 9 | Colunas derivadas | `faixa_isa` e `sem_populacao` | colunas criadas |

Resultado final: **255 linhas × 32 colunas**. Datas em ISO-8601 não se aplicam, porque a base não tem campos de data.

## 7. Modelo relacional (camada Ouro)

Duas tabelas, ligadas por `id_bacia` (uma bacia tem várias sub-bacias):

| Tabela | Linhas | Chaves e restrições |
|---|---|---|
| `bacia` | 98 | **PK** `id_bacia`; `nome_bacia` `NOT NULL` |
| `sub_bacia` | 255 | **PK** `id_sub_bacia`; **UNIQUE** `cod_sub_bacia`; **FK** `id_bacia` → `bacia(id_bacia)`; `NOT NULL` nos identificadores e nos indicadores de sinalização |

`sub_bacia` guarda a área, a população (total, com e sem rede coletora, com e sem interceptação, coleta de lixo, mancha de
inundação), os índices (`iab`, `ice`, `iie`, `ies`, `icl_cf`, `icl_vf`, `icl`, `idr`, `isa`) e as colunas derivadas
(`area_km2`, `faixa_isa`, `sem_populacao`, `outlier_isa`). Há um índice em `sub_bacia(isa)`.

- **DER:** `docs/der.png` — `[INSERIR]`
- **Classificação em fato e dimensão:** `[PREENCHER: quais tabelas são fato e dimensão e por quê]`

### Validação da carga

Depois de carregar, confira se o banco bate com o arquivo (marque quando conferir):

- [ ] `SELECT COUNT(*) FROM bacia;` retorna **98**
- [ ] `SELECT COUNT(*) FROM sub_bacia;` retorna **255**
- [ ] a restrição de chave estrangeira impede inserir uma sub-bacia com `id_bacia` inexistente

## 8. Análise Exploratória (EDA)

O relatório completo fica em [`docs/relatorio_eda.md`](docs/relatorio_eda.md) `[CRIAR]`.

| # | Pergunta de negócio | Consulta SQL | Resposta / insight |
|---|---|---|---|
| 1 | `[PREENCHER]` | `[PREENCHER]` | `[PREENCHER]` |
| 2 | `[PREENCHER]` | `[PREENCHER]` | `[PREENCHER]` |
| 3 | `[PREENCHER]` | `[PREENCHER]` | `[PREENCHER]` |

## 9. Dashboard

- **Power BI (entregável do projeto):** conectado ao MySQL (banco `isa_bh`). `[PREENCHER: link ou captura de tela]`
- **Medidas em DAX:** `[PREENCHER: lista das medidas e KPIs]`
- **Painéis em Streamlit (complemento):** `streamlit run app.py` (painel completo, com mapa) e `streamlit run dashboard.py`
  (painel executivo simples, que lê `base_isa_padronizada.csv` da mesma pasta).

## 10. Uso de IA Generativa e Engenharia de Prompt

A IA (Claude) foi usada como copiloto de desenvolvimento. Os prompts abaixo resumem o que foi pedido, a técnica usada e como o
resultado foi conferido. `[PREENCHER: datas e ajustes; os textos completos dos prompts podem ir em docs/prompts.md]`

| # | Data | Técnica | Objetivo | Prompt (resumo) | Conferência / correção |
|---|---|---|---|---|---|
| 1 | `[data]` | Persona + zero-shot | Análise descritiva e gráficos | "Atue como especialista em storytelling e Python; análise descritiva da base, gráficos no Streamlit, padrões e anomalias, média, moda, mediana, desvio padrão e variância" | A IA avisou que a base não tem datas (sem tendência nem sazonalidade) em vez de inventar um padrão |
| 2 | `[data]` | Zero-shot com contexto e exemplo | Dashboard interativo e padronização | "Corrija o código, deixe o dashboard mais interativo, com interpolação e regressão linear; padronize os dados, trate ausentes, duplicidades e outliers, gere a nova base e importe para o MySQL" | A IA corrigiu um erro da própria análise: `NOME_BACIA` não identifica a bacia (63 nomes para 98 ids); regressão conferida com scikit-learn; carga testada em SQLite |
| 3 | `[data]` | Zero-shot | Mapa das regiões | "Adicione um mapa para visualizar as regiões" | Conversão UTM → latitude/longitude conferida por dois métodos independentes e pelo contorno da cidade |
| 4 | `[data]` | Depuração (erro) | Corrigir o mapa e embutir a base | "O mapa mostra que o CSV não tem a coluna GEOMETRIA; resolva e deixe a base integrada" | Erro reproduzido antes de corrigir (CSV padronizado enviado, sem geometria) |
| 5 | `[data]` | Prompt estruturado (PACEF: Papel, Ação, Contexto, Exemplos, Formato) | Painel executivo | Modelo PACEF com wireframe, KPIs, semáforo, regra dos 5 segundos e mapa | KPIs conferidos com consultas SQL independentes; limites do semáforo são escolhas da equipe, não oficiais |
| 6 | `[data]` | Zero-shot com imagem | Retirar gráficos | Prints dos gráficos a remover do projeto | Execução testada sem os gráficos |
| 7 | `[data]` | Zero-shot | Simplificar gráficos | "Troque os gráficos das abas de outliers e regressão por gráficos mais simples" | Números de cada gráfico conferidos |
| 8 | `[data]` | Zero-shot com anexo (PDF) | Auditoria do projeto | "Diga se a pasta atende a todos os requisitos do guia" | Lacunas identificadas e corrigidas pela equipe `[PREENCHER]` |
| 9 | `[data]` | Zero-shot | Documentação | "Faça um README para o GitHub" | `[PREENCHER]` |

**Supervisão humana.** O código gerado por IA foi testado criticamente pela equipe, que responde pelo seu funcionamento.
A IA validou o código com simulações das bibliotecas de interface e com o SQL em SQLite; **a execução no MySQL real é conferida
pela equipe** (ver "Validação da carga"). `[PREENCHER: o que a equipe testou, corrigiu e aprendeu]`

## 11. Decisões técnicas

- **Chave da bacia:** `id_bacia`. O nome não serve de chave (63 nomes para 98 bacias; "Córrego Sem Nome" aparece em várias).
- **Unidade da área:** hectares. Foi inferido porque `densidade = população / área` bate com a coluna de densidade.
- **Fórmula do ISA:** `ISA = 0,05·IAB + 0,35·IES + 0,20·ICL + 0,40·IDR`, com `IES = 0,30·ICE + 0,70·IIE`. Foi recuperada
  por regressão sobre os dados (erro ≈ 0) e **não vem de documentação oficial**.
- **Faixas de ISA:** Crítico (< 0,5), Baixo (0,5–0,7), Médio (0,7–0,9) e Alto (≥ 0,9): critério adotado pela equipe.
- **Outliers:** sinalizados e mantidos, porque os valores mais baixos são casos reais (ex.: sub-bacias sem rede de esgoto),
  e removê-los esconderia o problema que a análise quer encontrar.
- **Mapa e geoprocessamento:** a geometria só é usada nos painéis em Streamlit. As coordenadas parecem estar em UTM zona 23 Sul
  (inferido) e a conversão para latitude/longitude é feita em `mapa.py`, **sem GeoPandas**.
- **Driver MySQL:** `PyMySQL`, e não SQLAlchemy ou mysql-connector. `[PREENCHER: justificativa ou troca]`

## 12. Limitações

- A base **não tem datas**: não é possível analisar evolução temporal nem sazonalidade.
- São **255 registros**, abaixo dos 1.000 recomendados no guia da disciplina.
- A carga automática foi validada em SQLite; falta a conferência no MySQL (ver seção 7).

## 13. Status dos entregáveis

- [x] Scripts de tratamento (Prata) e geração do SQL
- [x] DDL com PK, UNIQUE, FK e NOT NULL
- [x] Carga automática em Python
- [ ] Arquivo original em `data/raw/` e `.gitignore` criados
- [ ] DER (`docs/der.png`)
- [ ] Carga conferida no MySQL real
- [ ] Relatório de EDA e perguntas de negócio
- [ ] Dashboard Power BI conectado ao MySQL
- [ ] Prompts de IA revisados e completos
