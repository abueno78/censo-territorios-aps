# Pipeline Dados Censo → Territórios da Atenção Primária (POA)

Pipeline modular e reprodutível para análise sociodemográfica das Unidades de Saúde
de Porto Alegre, cruzando Censo Demográfico 2022 (IBGE), CNEFE e Grades Populacionais.

> **📄 Documentação completa:** [`DOCUMENTACAO_METODOLOGICA.md`](DOCUMENTACAO_METODOLOGICA.md)
> — inclui fundamentação metodológica, validações e limitações a declarar em publicações.

---

## Como reproduzir do zero

```bash
git clone https://github.com/abueno78/censo-territorios-aps
cd censo-territorios-aps
pip install -r requirements.txt
```

Depois seguir a sequência abaixo.

---

## Sequência dos módulos

### Etapa 0-A — Banco de setores censitários (opcional — já em `data/`)

O arquivo `data/banco_agregados_poa_setores.csv` (2.745 setores × 626 variáveis do
Censo 2022, filtrado para Porto Alegre) **já está versionado** neste repositório.

Para regenerá-lo a partir dos XLSXs brutos do IBGE:

1. Baixar os arquivos estaduais do RS em:
   https://www.ibge.gov.br/estatisticas/sociais/habitacao/22827-censo-demografico-2022.html
   → Resultados do Universo → Agregados por setores censitários → RS
2. Colocar os XLSXs em `inputs/agregados_ibge/`
3. Rodar: `python modulos/00_construir_banco_setores.py`

### Etapa 0-B — Dados geoespaciais e CNEFE (opcional — já em `data/`)

O script `baixar_dados.py` documenta a origem e regenera os arquivos geoespaciais
caso não estejam presentes:

```bash
python baixar_dados.py
```

| Arquivo | Origem | Já no repo? |
|---------|--------|-------------|
| `data/cnefe_poa.parquet` | IBGE FTP (CNEFE RS, ~126 MB CSV → 20 MB parquet) | ✅ Sim |
| `data/poa_tracts_2022.gpkg` | API IBGE / geobr (malha setores 2022) | ✅ Sim |
| `data/banco_agregados_poa_setores.csv` | Censo 2022 IBGE filtrado para POA | ✅ Sim |
| `data/composicao_com_hrsl.csv` | Resultado do pipeline (alocação setor→US) | ✅ Sim |
| `inputs/Territorios_AP.kmz` | Secretaria Municipal de Saúde de Porto Alegre | ✅ Sim |

### Etapa 1 — Gerar `tabelas_unidades_saude_v2.xlsx`

```bash
python modulos/agrega_territorio.py
```

Lê os dados de `data/` e `inputs/`, agrega por Unidade de Saúde e salva em
`outputs/tabelas_unidades_saude_v2.xlsx` (133 US × ~83 indicadores).

---

## Arquivos de entrada

| Arquivo | Localização | Descrição |
|---------|-------------|-----------|
| `cnefe_poa.parquet` | `data/` | 762 mil endereços de POA com lat/lon |
| `poa_tracts_2022.gpkg` | `data/` | 2.744 setores censitários (polígonos) |
| `banco_agregados_poa_setores.csv` | `data/` | Censo 2022 — 626 variáveis por setor |
| `composicao_com_hrsl.csv` | `data/` | Alocação proporcional setor → US |
| `Territorios_AP.kmz` | `inputs/` | 133 polígonos das Unidades de Saúde |

---

## Saída principal

**`outputs/tabelas_unidades_saude_v2.xlsx`** — aba `Indicadores_Completos_v2`

133 Unidades de Saúde × ~83 indicadores:

| Grupo | Variáveis |
|-------|-----------|
| População | `População Alocada à US`, faixas etárias, sexo |
| Cor/raça | `pct_Branca`, `pct_Preta`, `pct_Parda`, `pct_Amarela`, `pct_Indígena` |
| Escolaridade | `taxa_alf_geral` |
| Renda (v2 — sem bug) | `renda_media_winsor`, `renda_mediana_aprox`, `renda_dp`, `renda_cv` |
| Domicílios | `pct_apartamentos`, tipo de setor (Favela/Comunidade, etc.) |
| Território | `area_km2_ponderada`, `densidade_hab_km2`, `coordenadoria_saude`, `distrito_sanitario` |
| CNEFE | `n_enderecos_total`, tipos de edificação |
| Identificação | `CNES` |

> **Variáveis de renda:** a v1 tinha um bug onde a média ponderada somava médias
> sem dividir pelo peso total, gerando valores absurdos (máximo R$ 14 milhões).
> A v2 corrige isso com winsorização p1/p99 ≤ R$ 100 mil e agregação correta.
> As variáveis `renda_media_ponderada` e `cv_renda` da v1 **não são geradas**.

---

## Metodologia resumida

1. Cada endereço do CNEFE é alocado ao território da US via join espacial (`sjoin within`)
2. Em setores compartilhados entre duas ou mais US, a população é distribuída
   proporcionalmente ao número de endereços em cada parte (`fator_proporcao`)
3. Indicadores do Censo (contagens) são multiplicados pelo fator e somados por US
4. Validação: correlação com Grade Estatística IBGE 2022 = **r = 0,999**

Para detalhes, ver [`DOCUMENTACAO_METODOLOGICA.md`](DOCUMENTACAO_METODOLOGICA.md).

---

## Dependências

```bash
pip install -r requirements.txt
# pandas, pyarrow, geopandas, fiona, openpyxl, numpy, requests
```
