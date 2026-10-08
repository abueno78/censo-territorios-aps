#!/usr/bin/env python3
"""
baixar_dados.py — Baixa os dados brutos necessários para rodar o pipeline.

Rode UMA VEZ antes de executar os módulos (ou use os arquivos já versionados
em data/ — este script existe para documentar a origem e permitir regeneração).

USO:
    pip install -r requirements.txt
    python baixar_dados.py
"""

import zipfile
from pathlib import Path

BASE   = Path(__file__).resolve().parent
DATA   = BASE / "data"
INPUTS = BASE / "inputs"

DATA.mkdir(exist_ok=True)
INPUTS.mkdir(exist_ok=True)


# ─── 1. CNEFE — Cadastro Nacional de Endereços (IBGE, Censo 2022) ────────────
# Fonte: ftp.ibge.gov.br → Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos
#        → Censo_Demografico_2022 → Arquivos_CNEFE → CSV → Municipio → 43_RS
# Arquivo por município: 4314902_PORTO_ALEGRE.zip (~17 MB, 762.239 endereços)
CNEFE_URL = (
    "https://ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/"
    "Censo_Demografico_2022/Arquivos_CNEFE/CSV/Municipio/43_RS/4314902_PORTO_ALEGRE.zip"
)
CNEFE_ZIP = DATA / "cnefe_poa.zip"
CNEFE_DIR = DATA / "cnefe_poa"
CNEFE_CSV = CNEFE_DIR / "4314902_PORTO_ALEGRE.csv"
CNEFE_PQ  = DATA / "cnefe_poa.parquet"


def baixar_cnefe():
    if CNEFE_PQ.exists():
        print("✓ cnefe_poa.parquet já existe — pulando download do CNEFE")
        return
    if not CNEFE_CSV.exists():
        print(f"↓ Baixando CNEFE de Porto Alegre (~17 MB) ...")
        import urllib.request
        urllib.request.urlretrieve(CNEFE_URL, CNEFE_ZIP)
        CNEFE_DIR.mkdir(exist_ok=True)
        with zipfile.ZipFile(CNEFE_ZIP) as z:
            for member in z.namelist():
                if "4314902" in member:
                    z.extract(member, CNEFE_DIR)
                    print(f"  Extraído: {member}")
        CNEFE_ZIP.unlink()
    print("  Convertendo para parquet ...")
    import pandas as pd
    df = pd.read_csv(CNEFE_CSV, sep=";", dtype=str, encoding="utf-8")
    df.to_parquet(CNEFE_PQ)
    print(f"  ✓ cnefe_poa.parquet — {len(df):,} endereços "
          f"(esperado: 762.239)")


# ─── 2. Malha de setores censitários 2022 (IBGE) ─────────────────────────────
# Fonte: geoftp.ibge.gov.br → organizacao_do_territorio → malhas_territoriais →
#        malhas_de_setores_censitarios__divisoes_intramunicipais → censo_2022 →
#        setores → gpkg → UF → RS → RS_setores_CD2022.gpkg (~57 MB)
# Filtra-se CD_MUN = 4314902 → 2.744 setores de Porto Alegre.
TRACTS_URL  = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
    "malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022/"
    "setores/gpkg/UF/RS/RS_setores_CD2022.gpkg"
)
TRACTS_RS = DATA / "rs_setores_2022.gpkg"
TRACTS    = DATA / "poa_tracts_2022.gpkg"
MUNICIPIO = "4314902"


def baixar_malha_setores():
    if TRACTS.exists():
        print("✓ poa_tracts_2022.gpkg já existe — pulando")
        return
    print("↓ Baixando malha de setores 2022 do RS (~57 MB) ...")
    import urllib.request
    urllib.request.urlretrieve(TRACTS_URL, TRACTS_RS)

    import geopandas as gpd
    print("  Filtrando setores de Porto Alegre ...")
    gdf = gpd.read_file(TRACTS_RS)
    poa = gdf[gdf["CD_MUN"] == MUNICIPIO].copy()
    # Compatibilidade com os módulos que usam a nomenclatura do geobr
    poa["code_tract"] = poa["CD_SETOR"]
    poa.to_file(TRACTS, driver="GPKG")
    TRACTS_RS.unlink()
    print(f"  ✓ poa_tracts_2022.gpkg — {len(poa)} setores "
          f"({poa['CD_SETOR'].nunique()} únicos; esperado: 2.744)")


# ─── 3. Banco de agregados por setor (já versionado ou gerado) ───────────────
def verificar_banco_setores():
    f = DATA / "banco_agregados_poa_setores.csv"
    if f.exists():
        import subprocess as sp
        n = sp.run(["wc", "-l", str(f)], capture_output=True, text=True)
        print(f"✓ banco_agregados_poa_setores.csv — {n.stdout.strip()} linhas (2.745 esperado)")
    else:
        print("✗ banco_agregados_poa_setores.csv AUSENTE")
        print("  Gerar com: python modulos/00_construir_banco_setores.py")
        print("  (precisa dos XLSXs do IBGE em inputs/agregados_ibge/ — ~7 GB)")


# ─── 4. Territórios da APS (KMZ — SMS Porto Alegre) ─────────────────────────
def verificar_kmz():
    f = INPUTS / "Territorios_AP.kmz"
    if f.exists():
        print(f"✓ Territorios_AP.kmz — {f.stat().st_size/1024:.0f} KB")
    else:
        print("✗ Territorios_AP.kmz AUSENTE")
        print("  Fonte: Mapa público dos Territórios da APS de Porto Alegre")
        print("  https://www.google.com/maps/d/u/0/viewer?mid=119gTW9fF1HCImSAMSrlHrOJkdqE")


if __name__ == "__main__":
    print("=" * 60)
    print("Verificando / baixando dados brutos do pipeline")
    print("=" * 60)

    baixar_cnefe()
    baixar_malha_setores()
    verificar_banco_setores()
    verificar_kmz()

    print("\n" + "=" * 60)
    print("Próximos passos:")
    print("  python modulos/agrega_territorio.py")
    print("=" * 60)
