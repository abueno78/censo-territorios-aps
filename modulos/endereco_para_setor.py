"""Módulo 2 — ENDEREÇO TEXTUAL do paciente → SETOR censitário + variáveis sociais.

Pipeline de pré-processamento modular para quando o comitê de ética liberar
os endereços dos pacientes. Entrada: CSV com endereços textuais (logradouro,
número, opcional CEP/bairro). Saída: CD_SETOR + variáveis sociais do setor.

Fluxo:
  1. Normalizar endereço textual (caixa alta, remover acentos, padronizar)
  2. Geocodificar via CNEFE local (match por logradouro + número; fallback
     por logradouro: mediana das coordenadas; fallback CEP: centro médio)
  3. Atribuir setor censitário 2022 (sjoin espacial pt ↔ polígono)
  4. Enriquecer com variáveis sociais do banco agregado por setor

Uso:
    python modulos/endereco_para_setor.py inputs/pacientes.csv -o outputs/setores.csv
    python modulos/endereco_para_setor.py inputs/pacientes.csv \
        --col-logradouro logradouro --col-numero numero --col-cep cep
"""
from __future__ import annotations
import argparse
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg

import geopandas as gpd
import pandas as pd
import numpy as np


# ── 1. Normalização ───────────────────────────────────────────────────────────
def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _padroniza_tipo(tipo: str) -> str:
    """Mapa de tipos de logradouro para o padrão CNEFE (NOM_TIPO_SEGLOGR)."""
    t = _sem_acento((tipo or "").upper()).rstrip(".")
    if not t:
        return t
    mapa = {
        "R": "RUA", "RUA": "RUA", "AV": "AVENIDA", "AVENIDA": "AVENIDA",
        "PC": "PRACA", "PRACA": "PRACA", "TR": "TRAVESSA", "TRAVESSA": "TRAVESSA",
        "AL": "ALAMEDA", "ALAMEDA": "ALAMEDA", "ROD": "RODOVIA", "RODOVIA": "RODOVIA",
        "EST": "ESTRADA", "ESTRADA": "ESTRADA", "BEC": "BECO", "BECO": "BECO",
        "VL": "VIELA", "VIELA": "VIELA", "PSG": "PASSAGEM", "PASSAGEM": "PASSAGEM",
        "RS": "RODOVIA", "LARG": "LARGO", "LARGO": "LARGO",
    }
    return mapa.get(t, t)


def normalizar_endereco(df: pd.DataFrame, col_log: str, col_num: str) -> pd.DataFrame:
    """Retorna df com colunas normalizadas: logradouro, numero, tipo."""
    out = df.copy()
    out["_log"] = out[col_log].fillna("").astype(str).str.upper()
    out["_log"] = out["_log"].map(lambda s: _sem_acento(s).strip())
    # Tipo pode vir junto ("RUA BENTO GONCALVES") ou separado
    out["_tipo"] = out["_log"].str.extract(r"^(RUA|AVENIDA|AV |AV\.|PRACA|PC\.|TRAVESSA|TR\.|ALAMEDA|AL\.|RODOVIA|ROD\.|ESTRADA|BECO|PASSAGEM|LARGO|VIELA)\s*\.?\s*")[0]
    out["_log_limpo"] = out.apply(
        lambda r: _padroniza_tipo(r["_tipo"]) + " " + r["_log"].replace(r["_tipo"], "", 1).strip()
        if isinstance(r["_tipo"], str) else r["_log"], axis=1)
    out["_log_limpo"] = out["_log_limpo"].str.replace(r"\s+", " ", regex=True).str.strip()
    out["_numero"] = (
        pd.to_numeric(out[col_num], errors="coerce")
        .fillna(0).astype(int).astype(str).replace("0", "")  # sem número = ""
    )
    return out


# ── 2. Geocodificação via CNEFE ──────────────────────────────────────────────
def carregar_cnefe_index() -> pd.DataFrame:
    """Índice de logradouros do CNEFE com coordenadas representativas."""
    df = pd.read_parquet(cfg.CNEFE_CSV, columns=[
        "NOM_TIPO_SEGLOGR", "NOM_SEGLOGR", "NUM_ENDERECO", "LATITUDE", "LONGITUDE",
        "COD_SETOR", "NV_GEO_COORD", "CEP"])
    df = df[df["NV_GEO_COORD"].isin(cfg.NV_GEO_OK) & df["LATITUDE"].notna()]
    df["_logradouro"] = (df["NOM_TIPO_SEGLOGR"].fillna("") + " " + df["NOM_SEGLOGR"].fillna("")).str.strip()
    df["_cep"] = df["CEP"].fillna("").astype(str).str.replace(r"\D", "", regex=True)
    return df


def geocodificar(cnefe: pd.DataFrame, norm: pd.DataFrame, cep_col: str | None) -> pd.DataFrame:
    """Atribui LATITUDE/LONGITUDE/COD_SETOR a cada endereço a partir do CNEFE.

    Estratégia por prioridade:
      A. logradouro + número exato  (coordenada do próprio endereço)
      B. logradouro apenas           (mediana das coordenadas do logradouro)
      C. CEP apenas                  (mediana das coordenadas do CEP)
    Retorna código de status: 'exato' | 'logradouro' | 'cep' | 'nao_encontrado'.
    """
    cnefe["_log_cmp"] = cnefe["_logradouro"].map(lambda s: _sem_acento(s).upper())
    out = norm.copy()
    lat, lon, setor, status = [], [], [], []

    for _, r in out.iterrows():
        log = r["_log_limpo"]
        num = r["_numero"]
        m_log = cnefe["_log_cmp"] == log
        if m_log.any() and num:
            m = cnefe[m_log & (cnefe["NUM_ENDERECO"].astype(str) == num)]
            if not m.empty:
                lat.append(m["LATITUDE"].iloc[0]); lon.append(m["LONGITUDE"].iloc[0])
                setor.append(m["COD_SETOR"].iloc[0]); status.append("exato"); continue
        if m_log.any():
            lat.append(m_log["LATITUDE"].median() if False else cnefe[m_log]["LATITUDE"].median())
            lon.append(cnefe[m_log]["LONGITUDE"].median())
            setor.append(cnefe[m_log]["COD_SETOR"].mode().iloc[0] if not cnefe[m_log]["COD_SETOR"].mode().empty else np.nan)
            status.append("logradouro"); continue
        if cep_col and str(r.get(cep_col, "")).strip():
            cep_limpo = re.sub(r"\D", "", str(r[cep_col]))
            m_cep = cnefe["_cep"] == cep_limpo
            if m_cep.any():
                lat.append(cnefe[m_cep]["LATITUDE"].median())
                lon.append(cnefe[m_cep]["LONGITUDE"].median())
                setor.append(np.nan); status.append("cep"); continue
        lat.append(np.nan); lon.append(np.nan); setor.append(np.nan); status.append("nao_encontrado")

    out["LATITUDE"], out["LONGITUDE"] = lat, lon
    out["COD_SETOR_cnefe"], out["status_geocod"] = setor, status
    return out


# ── 3. Setor censitário + enriquecimento ─────────────────────────────────────
def atribuir_setor(geodf: pd.DataFrame, tracts: gpd.GeoDataFrame) -> pd.DataFrame:
    """Atribui CD_SETOR via join espacial (coordenada do paciente ↔ malha 2022)."""
    pts = gpd.GeoDataFrame(
        geodf,
        geometry=gpd.points_from_xy(geodf["LONGITUDE"], geodf["LATITUDE"]),
        crs=f"EPSG:{cfg.EPSG_GEO}",
    ).dropna(subset=["LONGITUDE", "LATITUDE"])
    tracts = tracts.to_crs(cfg.EPSG_GEO)
    joined = gpd.sjoin(pts, tracts[["code_tract", "geometry"]], how="left", predicate="within")
    joined["CD_SETOR"] = joined["code_tract"].astype(str).str.replace(r"\.0$", "", regex=True)
    return joined.drop(columns=["code_tract", "geometry"])


def enriquecer(df: pd.DataFrame) -> pd.DataFrame:
    """Junta variáveis sociais do Censo 2022 (banco por setor) em cada paciente."""
    if "CD_SETOR" not in df.columns or df["CD_SETOR"].isna().all():
        return df
    banco = pd.read_csv(cfg.BANCO_SETORES, dtype=str, low_memory=False)
    banco["CD_SETOR"] = banco["CD_SETOR"].astype(str).str.strip()
    cols = ["CD_SETOR", "CD_TIPO", "AREA_KM2"] + list(cfg.VARIAVEIS_SETOR["renda"]) \
        + list(cfg.VARIAVEIS_SETOR["educacao"]) + list(cfg.VARIAVEIS_SETOR["demografia"])
    cols = [c for c in cols if c in banco.columns]
    return df.merge(banco[cols], on="CD_SETOR", how="left")


def main():
    ap = argparse.ArgumentParser(description="Endereço textual → setor censitário (POA)")
    ap.add_argument("entrada", help="CSV com endereços dos pacientes")
    ap.add_argument("-o", "--saida", default=str(cfg.OUTPUTS / "pacientes_setores.csv"))
    ap.add_argument("--col-logradouro", default="logradouro")
    ap.add_argument("--col-numero", default="numero")
    ap.add_argument("--col-cep", default="cep")
    args = ap.parse_args()

    print("═" * 62)
    print("MÓDULO 2 — Endereço textual → Setor censitário")
    print("═" * 62)

    print(f"\n[1/5] Lendo {args.entrada} ...")
    raw = pd.read_csv(args.entrada, dtype=str)
    print(f"  {len(raw)} pacientes")

    print("\n[2/5] Normalizando endereços ...")
    norm = normalizar_endereco(raw, args.col_logradouro, args.col_numero)

    print("\n[3/5] Geocodificando via CNEFE local ...")
    cnefe = carregar_cnefe_index()
    print(f"  Índice CNEFE: {len(cnefe):,} endereços")
    geo = geocodificar(cnefe, norm, args.col_cep)
    print(geo["status_geocod"].value_counts().to_string())

    print("\n[4/5] Atribuindo setor censitário 2022 ...")
    tracts = gpd.read_file(cfg.TRACTS_GPKG)
    com_setor = atribuir_setor(geo, tracts)

    print("\n[5/5] Enriquecendo com variáveis sociais do Censo ...")
    final = enriquecer(com_setor)
    cfg.OUTPUTS.mkdir(parents=True, exist_ok=True)
    final.to_csv(args.saida, index=False, encoding="utf-8-sig")
    print(f"  Salvo: {args.saida} ({len(final)} linhas)")


if __name__ == "__main__":
    main()