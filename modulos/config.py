"""Configuração central do pipeline Censo → APS (Porto Alegre).

Centraliza caminhos, constantes e códigos de espécie/tipo do CNEFE.
Todos os módulos importam daqui — ajuste os caminhos UMA vez.
"""
from pathlib import Path

# ── Caminhos ──────────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parents[1]          # pipeline_censo_aps/
INPUTS = BASE / "inputs"
OUTPUTS = BASE / "outputs"
DATA = BASE / "data"

CNEFE_CSV = DATA / "cnefe_poa.parquet"               # parquet (rápido) com lat/lon
TRACTS_GPKG = DATA / "poa_tracts_2022.gpkg"          # malha de setores 2022 (geobr)
BANCO_SETORES = DATA / "banco_agregados_poa_setores.csv"  # 626 colunas/setor
KMZ_US = INPUTS / "Territorios_AP.kmz"               # territórios da APS
GRADE_RS = DATA / "grade_id14.shp"                   # Grade Estatística 2022 (quadrante 14)
TABELA_BASE = DATA / "tabelas_unidades_saude.xlsx"   # indicadores base por US

# ── Constantes ────────────────────────────────────────────────────────────────
MUNICIPIO = "4314902"
EPSG_GEO = 4326
EPSG_UTM = 31982          # SIRGAS2000 / UTM 22S (POA)

# Espécies CNEFE (COD_ESPECIE)
ESPECIE = {
    1: "Domicílio particular",
    2: "Domicílio coletivo",
    3: "Estabelecimento agropecuário",
    4: "Estabelecimento de ensino",
    5: "Estabelecimento de saúde",
    6: "Estabelecimento de outras finalidades",
    7: "Edificação em construção ou reforma",
    8: "Estabelecimento religioso",
}
ESP_DOMICILIO = {1, 2}
ESP_ESTABELECIMENTOS = {3, 4, 5, 6, 8}

# Tipos de edificação (COD_TIPO_ESPECI)
TIPO_EDIFIC = {
    101: "Casa",
    102: "Casa de vila ou condomínio",
    103: "Apartamento",
    104: "Outros",
}

# Níveis de geocodificação confiáveis (1-3 = coordenada de endereço)
NV_GEO_OK = {"1", "2", "3"}

# Variáveis sociais por setor usadas no enriquecimento de pacientes
VARIAVEIS_SETOR = {
    "renda":     {"V06004": "renda_media_responsavel", "V06006": "renda_mediana_responsavel", "V06005": "var_renda"},
    "educacao":  {"V00644": "alfabetizacao_15_mais"},
    "demografia": {"V01006": "pop_total"},
    "territorio": {"CD_TIPO": "tipo_setor"},
}