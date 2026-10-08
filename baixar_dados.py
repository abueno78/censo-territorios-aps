#!/usr/bin/env python3
"""
baixar_dados.py — Baixa os dados brutos necessários para rodar o pipeline.

Precisa ser executado UMA VEZ antes de rodar os módulos.
Os arquivos já processados (banco_agregados_poa_setores.csv, cnefe_poa.parquet,
poa_tracts_2022.gpkg, composicao_com_hrsl.csv) estão versionados no repositório
dentro de data/ — este script serve de documentação da origem e para regeneração.

USO:
    pip install -r requirements.txt
    python baixar_dados.py
"""

import os
import sys
import subprocess
from pathlib import Path

BASE  = Path(__file__).resolve().parent
DATA  = BASE / "data"
INPUTS = BASE / "inputs"

DATA.mkdir(exist_ok=True)
INPUTS.mkdir(exist_ok=True)


# ─── 1. CNEFE — Cadastro Nacional de Endereços (IBGE FTP) ────────────────────
# Fonte: ftp://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/
#        Cadastro_Nacional_de_Enderecos_Fins_Estatisticos/
#        Municipios/RS_Rio_Grande_do_Sul.zip
# O arquivo ZIP contém CSVs por município; o de POA é 4314902_PORTO_ALEGRE.csv
# Tamanho: ~126 MB (CSV) → ~20 MB (parquet após 00_prepara_dados.py)

CNEFE_URL = (
    "https://ftp.ibge.gov.br/Censos/Censo_Demografico_2022/"
    "Cadastro_Nacional_de_Enderecos_Fins_Estatisticos/"
    "Municipios/RS_Rio_Grande_do_Sul.zip"
)
CNEFE_ZIP  = DATA / "cnefe_rs.zip"
CNEFE_CSV  = DATA / "cnefe_poa" / "4314902_PORTO_ALEGRE.csv"
CNEFE_PQ   = DATA / "cnefe_poa.parquet"

def baixar_cnefe():
    if CNEFE_PQ.exists():
        print(f"✓ cnefe_poa.parquet já existe — pulando download do CNEFE")
        return
    if not CNEFE_CSV.exists():
        print(f"↓ Baixando CNEFE RS ({CNEFE_URL}) ...")
        import urllib.request
        urllib.request.urlretrieve(CNEFE_URL, CNEFE_ZIP)
        print(f"  Descompactando ...")
        import zipfile
        (DATA / "cnefe_poa").mkdir(exist_ok=True)
        with zipfile.ZipFile(CNEFE_ZIP) as z:
            for member in z.namelist():
                if "4314902" in member:
                    z.extract(member, DATA / "cnefe_poa")
                    print(f"  Extraído: {member}")
        CNEFE_ZIP.unlink()
    print(f"  Convertendo para parquet ...")
    import pandas as pd
    df = pd.read_csv(CNEFE_CSV, sep=";", dtype=str, encoding="utf-8")
    df.to_parquet(CNEFE_PQ)
    print(f"  ✓ cnefe_poa.parquet — {len(df):,} endereços")


# ─── 2. Malha de setores censitários 2022 (geobr) ────────────────────────────
# Fonte: pacote geobr (R) ou API IBGE via geobr Python
# Municício: 4314902 (Porto Alegre), ano 2022

TRACTS = DATA / "poa_tracts_2022.gpkg"

def baixar_malha_setores():
    if TRACTS.exists():
        print(f"✓ poa_tracts_2022.gpkg já existe — pulando")
        return
    print("↓ Baixando malha de setores 2022 (geobr) ...")
    try:
        import geopandas as gpd
        # API do IBGE para setores censitários 2022 de POA
        url = (
            "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/4314902"
            "?formato=application/vnd.geo+json&qualidade=maxima&intrarregiao=setor"
        )
        gdf = gpd.read_file(url)
        gdf.to_file(TRACTS, driver="GPKG")
        print(f"  ✓ poa_tracts_2022.gpkg — {len(gdf)} setores")
    except Exception as e:
        print(f"  [AVISO] Falha no download automático: {e}")
        print("  Download manual: https://geoftp.ibge.gov.br/organizacao_do_territorio/")
        print("  malhas_territoriais/malhas_de_setores_censitarios__divisoes_intramunicipais/")
        print("  censo_2022/setores_censitarios_shp/RS/")
        print(f"  Salvar o .gpkg em: {TRACTS}")


# ─── 3. Banco de agregados por setor (Censo 2022 — já em data/) ──────────────
# Fonte: IBGE — Resultados do Universo do Censo Demográfico 2022
# URL: https://www.ibge.gov.br/estatisticas/sociais/habitacao/22827-censo-demografico-2022.html
# → Resultados → Agregados por setores censitários → RS
# O arquivo banco_agregados_poa_setores.csv já está versionado em data/ (4.5 MB,
# filtrado para Porto Alegre a partir do arquivo estadual original de ~800 MB).
# Para regenerar a partir do arquivo estadual completo, ver DOCUMENTACAO_METODOLOGICA.md.

def verificar_banco_setores():
    f = DATA / "banco_agregados_poa_setores.csv"
    if f.exists():
        import subprocess
        n = subprocess.run(["wc", "-l", str(f)], capture_output=True, text=True)
        print(f"✓ banco_agregados_poa_setores.csv — {n.stdout.strip()} linhas (2.745 esperado)")
    else:
        print("✗ banco_agregados_poa_setores.csv AUSENTE")
        print("  Baixar de: https://www.ibge.gov.br/estatisticas/sociais/habitacao/22827-censo-demografico-2022.html")
        print("  → Resultados do Universo → Agregados por setores → RS → filtrar CD_MUNICIPIO=4314902")


# ─── 4. Territórios da APS (KMZ — SMS Porto Alegre) ─────────────────────────
# Fonte: Secretaria Municipal de Saúde de Porto Alegre
# O arquivo Territorios_AP.kmz está versionado em inputs/ deste repositório.

def verificar_kmz():
    f = INPUTS / "Territorios_AP.kmz"
    if f.exists():
        print(f"✓ Territorios_AP.kmz — {f.stat().st_size/1024:.0f} KB")
    else:
        print("✗ Territorios_AP.kmz AUSENTE")
        print("  Fonte: Secretaria Municipal de Saúde de Porto Alegre (SMS POA)")
        print("  Contato: http://www2.portoalegre.rs.gov.br/sms/")


# ─── Pipeline ─────────────────────────────────────────────────────────────────

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
