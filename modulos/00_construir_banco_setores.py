#!/usr/bin/env python3
"""
00_construir_banco_setores.py — Constrói banco_agregados_poa_setores.csv

Filtra os XLSXs do Censo 2022 (IBGE) para Porto Alegre e consolida em um único
CSV por setor censitário com todas as variáveis necessárias para o pipeline.

Este script precisa ser executado apenas se você quiser regenerar o banco a
partir dos arquivos brutos do IBGE. O arquivo banco_agregados_poa_setores.csv
já está versionado em data/ — pule este passo se ele estiver presente.

ENTRADAS (XLSXs do IBGE — baixar manualmente):
  Fonte: https://www.ibge.gov.br/estatisticas/sociais/habitacao/22827-censo-demografico-2022.html
         → Resultados do Universo → Agregados por setores censitários → RS
  Colocar os arquivos em: inputs/agregados_ibge/

  Arquivos necessários:
    Agregados_por_setores_basico_BR.xlsx            (~2 GB)
    Agregados_por_setores_renda_responsavel_BR.xlsx (~800 MB)
    Agregados_por_setores_demografia_BR.xlsx        (~1.5 GB)
    Agregados_por_setores_cor_ou_raca_BR.xlsx       (~800 MB)
    Agregados_por_setores_alfabetizacao_BR.xlsx     (~800 MB)
    Agregados_por_setores_caracteristicas_domicilio1_BR.xlsx (~1 GB)

  Alternativa: baixar os arquivos já filtrados para o RS (menores):
    → Resultados do Universo → Agregados por setores → RS → arquivos estaduais

SAÍDA:
  data/banco_agregados_poa_setores.csv  (4.5 MB — apenas POA, ~2.745 setores)

DEPENDÊNCIAS:
  pip install pandas openpyxl xlsx2csv

USO:
  python modulos/00_construir_banco_setores.py
"""

import os
import sys
import subprocess
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg

import pandas as pd

MUNICIPIO_CODE = "4314902"
PROGRESS_FILE  = cfg.DATA / ".progress_00.json"

AGREGADOS_DIR  = cfg.INPUTS / "agregados_ibge"

ARQUIVOS = [
    ("basico",         "Agregados_por_setores_basico_BR.xlsx"),
    ("renda",          "Agregados_por_setores_renda_responsavel_BR.xlsx"),
    ("demografia",     "Agregados_por_setores_demografia_BR.xlsx"),
    ("raca",           "Agregados_por_setores_cor_ou_raca_BR.xlsx"),
    ("alfabetizacao",  "Agregados_por_setores_alfabetizacao_BR.xlsx"),
    ("domicilio1",     "Agregados_por_setores_caracteristicas_domicilio1_BR.xlsx"),
]


def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {}


def save_progress(p):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(p, f)


def _checar_xlsx2csv():
    """Garante que o xlsx2csv está disponível (necessário para ler os XLSXs do IBGE)."""
    try:
        subprocess.run([sys.executable, "-m", "xlsx2csv", "--version"],
                       capture_output=True, check=True)
    except Exception:
        raise RuntimeError(
            "xlsx2csv não está instalado — necessário para converter os XLSXs do IBGE.\n"
            "Instale com:  pip install xlsx2csv")


def filtrar_um_xlsx(nome: str, arquivo: str) -> Path:
    """Converte XLSX → CSV e filtra apenas setores de Porto Alegre."""
    entrada = AGREGADOS_DIR / arquivo
    saida   = cfg.DATA / f"poa_{nome}.csv"

    if saida.exists():
        print(f"  [{nome}] já existe — pulando")
        return saida

    if not entrada.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {entrada}\n"
            f"Baixar de: https://www.ibge.gov.br/estatisticas/sociais/habitacao/"
            f"22827-censo-demografico-2022.html\n"
            f"→ Resultados do Universo → Agregados por setores → RS"
        )

    print(f"  [{nome}] Convertendo XLSX → CSV ({arquivo}) ...")
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = tmp.name

    subprocess.run([sys.executable, "-m", "xlsx2csv", str(entrada), tmp_path], check=True)

    print(f"  [{nome}] Filtrando setores de Porto Alegre ...")
    with open(tmp_path, "r", encoding="utf-8") as f:
        header = f.readline().strip()

    filtered_path = tmp_path + ".poa"
    with open(filtered_path, "w", encoding="utf-8") as out:
        out.write(header + "\n")
    subprocess.run(
        f"grep '^{MUNICIPIO_CODE}' '{tmp_path}' >> '{filtered_path}'",
        shell=True, check=False,
    )

    df = pd.read_csv(filtered_path, low_memory=False, dtype=str)
    # Garantir que a coluna do setor se chama CD_SETOR
    for c in df.columns:
        if c.upper() == "CD_SETOR":
            if c != "CD_SETOR":
                df = df.rename(columns={c: "CD_SETOR"})
            break
    else:
        df = df.rename(columns={df.columns[0]: "CD_SETOR"})

    df.to_csv(saida, index=False, encoding="utf-8-sig")
    print(f"  [{nome}] {len(df)} setores → {saida.name}")

    os.unlink(tmp_path)
    os.unlink(filtered_path)
    return saida


def consolidar(csvs_poa: list[Path]) -> pd.DataFrame:
    """Merge outer de todos os CSVs filtrados em um único banco por setor."""
    df_merged = None
    for path in csvs_poa:
        df = pd.read_csv(path, low_memory=False, dtype=str)
        df["CD_SETOR"] = df["CD_SETOR"].astype(str).str.strip()
        dup = [c for c in df.columns if df_merged is not None
               and c in df_merged.columns and c != "CD_SETOR"]
        if dup:
            df = df.drop(columns=dup)
        if df_merged is None:
            df_merged = df
        else:
            df_merged = df_merged.merge(df, on="CD_SETOR", how="outer")
        print(f"  {path.name}: merge → {len(df_merged)} setores × {df_merged.shape[1]} colunas")

    cols = ["CD_SETOR"] + sorted(c for c in df_merged.columns if c != "CD_SETOR")
    return df_merged[cols]


def principal():
    print("=" * 62)
    print("Construindo banco_agregados_poa_setores.csv")
    print("=" * 62)

    saida_final = cfg.DATA / "banco_agregados_poa_setores.csv"
    if saida_final.exists():
        import subprocess as sp
        n = sp.run(["wc", "-l", str(saida_final)], capture_output=True, text=True)
        print(f"\n✓ Já existe: {saida_final.name} ({n.stdout.strip()} linhas)")
        print("  Use --force para regenerar.")
        if "--force" not in sys.argv:
            return

    AGREGADOS_DIR.mkdir(parents=True, exist_ok=True)
    _checar_xlsx2csv()
    progress = load_progress()
    csvs_poa = []

    for nome, arquivo in ARQUIVOS:
        if progress.get(nome) == "done":
            path = cfg.DATA / f"poa_{nome}.csv"
            if path.exists():
                print(f"  [{nome}] já processado")
                csvs_poa.append(path)
                continue

        try:
            path = filtrar_um_xlsx(nome, arquivo)
            csvs_poa.append(path)
            progress[nome] = "done"
            save_progress(progress)
        except FileNotFoundError as e:
            print(f"\nERRO: {e}")
            sys.exit(1)

    print("\nConsolidando ...")
    df = consolidar(csvs_poa)
    df.to_csv(saida_final, index=False, encoding="utf-8-sig")
    print(f"\n✓ Salvo: {saida_final}")
    print(f"  {len(df)} setores | {df.shape[1]} colunas")

    # Limpar arquivos intermediários
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()


if __name__ == "__main__":
    principal()
