"""Módulo 0 — Preparação de dados brutos para o pipeline.

- Converte CNEFE POA (CSV 126MB, separador ';') para parquet otimizado
- Garante estrutura de diretórios inputs/ outputs/ data/
- Copia/projeta a malha de setores para data/

Uso:
    python modulos/00_prepara_dados.py
"""
from __future__ import annotations
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg

import pandas as pd


def principal():
    for d in (cfg.INPUTS, cfg.OUTPUTS, cfg.DATA):
        d.mkdir(parents=True, exist_ok=True)

    # CNEFE: CSV → parquet (se ainda não existir)
    if not cfg.CNEFE_CSV.exists():
        origem = cfg.DATA / "cnefe_poa" / "4314902_PORTO_ALEGRE.csv"
        if not origem.exists():
            origem = cfg.INPUTS / "cnefe_poa.csv"
        print(f"Convertendo CNEFE: {origem} → parquet ...")
        df = pd.read_csv(origem, sep=";", dtype=str, encoding="utf-8")
        df.to_parquet(cfg.CNEFE_CSV)
        print(f"  {len(df):,} registros")
    else:
        print(f"CNEFE parquet já existe ({cfg.CNEFE_CSV})")

    # Malha de setores (gpkg do geobr) — copiar se estiver em inputs
    if not cfg.TRACTS_GPKG.exists():
        cand = cfg.INPUTS / "poa_tracts_2022.gpkg"
        if cand.exists():
            shutil.copy(cand, cfg.TRACTS_GPKG)
            print(f"Malha copiada para {cfg.TRACTS_GPKG}")
        else:
            print("[AVISO] poa_tracts_2022.gpkg não encontrado em inputs/")

    print("\nPreparação concluída.")


if __name__ == "__main__":
    principal()