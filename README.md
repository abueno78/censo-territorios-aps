# Pipeline Dados Censo → Territórios da Atenção Primária (POA)

Pipeline modular para análise sociodemográfica das Unidades de Saúde de Porto Alegre,
cruzando Censo Demográfico 2022 (IBGE), CNEFE e Grades Populacionais.

> **📄 Para o raciocínio completo, validações e desafios técnicos, leia
> [`DOCUMENTACAO_METODOLOGICA.md`](DOCUMENTACAO_METODOLOGICA.md)**

---

## Como reproduzir

### 1. Clonar e instalar dependências

```bash
git clone https://github.com/abueno78/censo-territorios-aps
cd censo-territorios-aps
pip install -r requirements.txt
```

### 2. Verificar / baixar dados brutos

```bash
python baixar_dados.py
```

Este script verifica se os dados necessários estão presentes e baixa
automaticamente o que for possível. Ver detalhes na seção **Dados** abaixo.

### 3. Rodar o pipeline

```bash
# Módulo 1 — gera outputs/tabelas_unidades_saude_v2.xlsx
python modulos/agrega_territorio.py
```

---

## Dados

### Arquivos já versionados neste repositório

| Arquivo | Origem | Descrição |
|---------|--------|-----------|
| `data/banco_agregados_poa_setores.csv` | IBGE Censo 2022 | 2.744 setores × 626 indicadores (filtrado para POA) |
| `data/cnefe_poa.parquet` | IBGE FTP | 762 mil endereços de POA com lat/lon |
| `data/composicao_com_hrsl.csv` | gerado | Proporção de cada setor por unidade de saúde |
| `data/poa_tracts_2022.gpkg` | geobr/IBGE | Malha de setores censitários 2022 |
| `data/validacao_tripla_por_us.csv` | gerado | Validação da alocação vs Grade IBGE e HRSL |
| `data/tabelas_unidades_saude.xlsx` | gerado | Indicadores base por unidade de saúde (v1) |
| `inputs/Territorios_AP.kmz` | SMS POA | Polígonos dos 133 territórios de saúde |

### Fontes originais dos dados brutos

| Dado | URL de download |
|------|----------------|
| CNEFE Porto Alegre | [FTP IBGE — RS_Rio_Grande_do_Sul.zip](https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Cadastro_Nacional_de_Enderecos_Fins_Estatisticos/Municipios/RS_Rio_Grande_do_Sul.zip) |
| Malha de setores 2022 | [API IBGE Malhas](https://servicodados.ibge.gov.br/api/v3/malhas/municipios/4314902?formato=application/vnd.geo+json&qualidade=maxima&intrarregiao=setor) |
| Agregados por setor (Censo 2022) | [IBGE — Censo 2022 resultados do universo](https://www.ibge.gov.br/estatisticas/sociais/habitacao/22827-censo-demografico-2022.html) → Agregados por setores → RS |
| Territórios da APS | Secretaria Municipal de Saúde de Porto Alegre (SMS POA) |

> **Nota:** os arquivos já processados estão versionados em `data/` para
> que a reprodução não dependa de baixar centenas de MB. O script
> `baixar_dados.py` documenta a origem de cada um e os regenera se necessário.

---

## Estrutura

```
censo-territorios-aps/
├── baixar_dados.py              ← verifica/baixa os dados brutos
├── requirements.txt             ← dependências Python
├── modulos/
│   ├── config.py                ← caminhos e constantes centralizados
│   ├── 00_prepara_dados.py      ← CNEFE CSV → parquet
│   └── agrega_territorio.py     ← pipeline principal → tabelas_unidades_saude_v2.xlsx
├── data/                        ← dados processados (versionados)
├── inputs/                      ← dados de entrada externos
└── outputs/                     ← resultados gerados
    └── tabelas_unidades_saude_v2.xlsx   ← SAÍDA PRINCIPAL (133 US × 83 indicadores)
```

---

## Saída principal

**`outputs/tabelas_unidades_saude_v2.xlsx`** (aba `Indicadores_Completos_v2`)
- 133 unidades de saúde × 83 indicadores
- Chave para merge externo: coluna `CNES` (7 dígitos com zero à esquerda)
- Utilizado pela tese via repositório `abueno78/tese-analise-exploratoria`

## Método (resumo)

1. Cada endereço CNEFE é atribuído ao território da US por join espacial (`within`)
2. Setores partilhados por mais de uma US têm população distribuída proporcionalmente ao nº de endereços (`fator_proporcao`)
3. Validação: correlação 0,999 com Grade Estatística IBGE 2022 e 0,992 com HRSL (satélite)
