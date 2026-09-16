"""Módulo 1 — Indicadores do TERRITÓRIO da Unidade de Saúde (nível US).

Gera tabelas_unidades_saude_v2.xlsx com:
- Indicadores base (população, demografia, renda, escolaridade) — herdados da v1
- Indicadores CNEFE por território: nº de endereços por espécie, casas,
  apartamentos, estabelecimentos (ensino, saúde, religiosos, outros)
- Densidade populacional e de endereços (hab/km², end/km²)
- Validação tripla: pop CNEFE vs Grade Estatística 2022 vs HRSL

Uso:
    python modulos/agrega_territorio.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg

import geopandas as gpd
import pandas as pd
import numpy as np


def carregar_cnefe() -> pd.DataFrame:
    """CNEFE POA com coordenadas (parquet gerado no 00_prepara_dados)."""
    df = pd.read_parquet(cfg.CNEFE_CSV)
    for c in ("LATITUDE", "LONGITUDE"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["COD_ESPECIE"] = pd.to_numeric(df["COD_ESPECIE"], errors="coerce").fillna(0).astype(int)
    df["COD_TIPO_ESPECI"] = pd.to_numeric(df["COD_TIPO_ESPECI"], errors="coerce").fillna(0).astype(int)
    return df


def agregar_cnefe_por_us(cnefe: pd.DataFrame, us: gpd.GeoDataFrame) -> pd.DataFrame:
    """Join espacial endereços ↔ territórios e agrega indicadores por US."""
    pts = gpd.GeoDataFrame(
        cnefe,
        geometry=gpd.points_from_xy(cnefe["LONGITUDE"], cnefe["LATITUDE"]),
        crs=f"EPSG:{cfg.EPSG_GEO}",
    )
    joined = gpd.sjoin(pts, us[["Unidade de Saúde", "geometry"]], how="left", predicate="within")
    joined = joined.drop_duplicates(subset="COD_UNICO_ENDERECO", keep="first")
    on_us = joined["Unidade de Saúde"].notna()
    print(f"  {len(joined):,} endereços | {on_us.sum():,} dentro de territórios "
          f"({100 * on_us.mean():.1f}%)")

    g = joined.dropna(subset=["Unidade de Saúde"]).groupby("Unidade de Saúde")
    res = pd.DataFrame({
        "n_enderecos_total": g.size(),
        "n_domic_privados": g.apply(lambda x: (x["COD_ESPECIE"] == 1).sum(), include_groups=False),
        "n_domic_coletivos": g.apply(lambda x: (x["COD_ESPECIE"] == 2).sum(), include_groups=False),
        "n_est_ensino": g.apply(lambda x: (x["COD_ESPECIE"] == 4).sum(), include_groups=False),
        "n_est_saude": g.apply(lambda x: (x["COD_ESPECIE"] == 5).sum(), include_groups=False),
        "n_est_outras_final": g.apply(lambda x: (x["COD_ESPECIE"] == 6).sum(), include_groups=False),
        "n_construcao_reforma": g.apply(lambda x: (x["COD_ESPECIE"] == 7).sum(), include_groups=False),
        "n_est_religiosos": g.apply(lambda x: (x["COD_ESPECIE"] == 8).sum(), include_groups=False),
        "n_casas": g.apply(lambda x: (x["COD_TIPO_ESPECI"] == 101).sum(), include_groups=False),
        "n_vilas_condos": g.apply(lambda x: (x["COD_TIPO_ESPECI"] == 102).sum(), include_groups=False),
        "n_apartamentos": g.apply(lambda x: (x["COD_TIPO_ESPECI"] == 103).sum(), include_groups=False),
        "n_outras_edif": g.apply(lambda x: (x["COD_TIPO_ESPECI"] == 104).sum(), include_groups=False),
    }).reset_index()
    return res


def _quantil_ponderado(vals: np.ndarray, pesos: np.ndarray, q: float) -> float:
    """Quantil ponderado (por responsáveis×fator) das rendas setoriais."""
    o = np.argsort(vals)
    s = np.cumsum(pesos[o])
    if s[-1] <= 0:
        return np.nan
    return vals[o][np.searchsorted(s, q * s[-1])]


def corrigir_renda_us(base: pd.DataFrame) -> pd.DataFrame:
    """Recalcula renda média por US com winsorização no nível do SETOR.

    O agregado do IBGE traz renda média (V06004) com valores imputados extremos
    (ex.: US São Vicente Mártir R$ 121 mil). Winsoriza a nível de setor
    (p1/p99 + teto R$ 100 mil) antes de ponderar por responsáveis × fator.

    Variabilidade: combina variância DENTRO dos setores (V06005, que o IBGE já
    divulga) com variância ENTRE setores (dispersão das médias setoriais) —
    fórmula de variância total de estratos. O cv_renda da v1 usava apenas o
    std não-ponderado das médias setoriais, ignorando V06005 → subestimado.
    """
    try:
        comp = pd.read_csv(cfg.DATA / "composicao_com_hrsl.csv")
        banco = pd.read_csv(cfg.BANCO_SETORES, dtype=str, low_memory=False)
    except FileNotFoundError:
        print("  [AVISO] composição/banco ausentes — renda mantida sem correção")
        base["flag_renda_suspeita"] = base["razao_media_mediana"].gt(3) | base["renda_media_ponderada"].gt(50000)
        return base

    comp["CD_SETOR"] = comp["CD_SETOR"].astype(str).str.strip()
    banco["CD_SETOR"] = banco["CD_SETOR"].astype(str).str.strip()
    b = banco[["CD_SETOR", "V06001", "V06002", "V06004", "V06005", "V06006"]].copy()
    for c in ("V06001", "V06004", "V06005", "V06006"):
        b[c] = pd.to_numeric(b[c], errors="coerce")

    lo, hi = b["V06004"].quantile(0.01), b["V06004"].quantile(0.99)
    b["V06004_w"] = b["V06004"].clip(lo, hi).where(b["V06004"] < 100_000)
    vhi = b["V06005"].quantile(0.99)
    b["V06005_w"] = b["V06005"].clip(upper=vhi)

    m = comp.merge(b, on="CD_SETOR", how="inner")
    m["peso"] = m["V06001"] * m["fator_proporcao"]

    def _agg(g: pd.DataFrame) -> pd.Series:
        w = g["peso"]
        if w.sum() <= 0 or g["V06004_w"].notna().sum() == 0:
            return pd.Series({"renda_media_winsor": np.nan, "n_setores_renda_ok": 0})
        mu = (g["V06004_w"] * w).sum() / w.sum()
        var_within = (g["V06005_w"] * w).sum() / w.sum()
        var_between = (w * (g["V06004_w"] - mu) ** 2).sum() / w.sum()
        var_total = var_within + var_between
        vals = g["V06004_w"].values
        ps = w.values
        return pd.Series({
            "renda_media_winsor": mu,
            "renda_dp": np.sqrt(max(var_total, 0)),
            "renda_cv": np.sqrt(max(var_total, 0)) / mu * 100,
            "renda_p10": _quantil_ponderado(vals, ps, 0.10),
            "renda_p25": _quantil_ponderado(vals, ps, 0.25),
            "renda_p75": _quantil_ponderado(vals, ps, 0.75),
            "renda_p90": _quantil_ponderado(vals, ps, 0.90),
            "n_setores_renda_ok": int(g["V06004_w"].notna().sum()),
        })

    agg = m.groupby("Unidade de Saúde").apply(_agg, include_groups=False).reset_index()
    out = base.merge(agg, on="Unidade de Saúde", how="left")
    out["flag_renda_suspeita"] = (out["renda_media_winsor"] / out["renda_mediana_aprox"].replace(0, np.nan) > 2.5) | (
        out["n_setores_renda_ok"].fillna(0) < 3)
    print(f"  Renda winsorizada (p1={lo:,.0f} / p99={hi:,.0f}) — {out['flag_renda_suspeita'].sum()} US sinalizadas | "
          f"DP/CV/P10/P90 calculados ({out['renda_cv'].notna().sum()} US)")
    return out


def principal():
    print("═" * 62)
    print("MÓDULO 1 — Indicadores do território por Unidade de Saúde")
    print("═" * 62)

    # 1. Carregar base
    print("\n[1/4] Carregando tabela base por US ...")
    base = pd.read_excel(cfg.TABELA_BASE, sheet_name="Indicadores_Completos")
    print(f"  {len(base)} US")

    # 2. CNEFE → US
    print("\n[2/4] Agregando CNEFE por território ...")
    cnefe = carregar_cnefe()
    us = gpd.read_file(cfg.KMZ_US, driver="KML").rename(columns={"Name": "Unidade de Saúde"})
    us = us.to_crs(cfg.EPSG_GEO)
    cnefe_us = agregar_cnefe_por_us(cnefe, us)

    # CNES + distrito/coordenadoria do KMZ → colunas na tabela final
    cnes_meta = us[["Unidade de Saúde", "CNES", "Coordenadoria_de_Sa__de", "Distrito_Sanit__rio"]].copy()
    cnes_meta = cnes_meta.rename(columns={
        "Coordenadoria_de_Sa__de": "coordenadoria_saude",
        "Distrito_Sanit__rio": "distrito_sanitario",
    })

    # 3. Densidades e indicadores derivados
    print("\n[3/5] Calculando densidades, proporções e renda corrigida ...")
    t2 = base.merge(cnes_meta, on="Unidade de Saúde", how="left")
    t2 = t2.merge(cnefe_us, on="Unidade de Saúde", how="left")
    t2["densidade_hab_km2"] = t2["População Alocada à US"] / t2["area_km2_ponderada"]
    t2["densidade_enderecos_km2"] = t2["n_enderecos_total"] / t2["area_km2_ponderada"]
    t2["pct_apartamentos"] = t2["n_apartamentos"] / t2["n_enderecos_total"] * 100
    t2["razao_apart_casa"] = t2["n_apartamentos"] / t2["n_casas"].replace(0, np.nan)
    t2["pct_est_saude"] = t2["n_est_saude"] / t2["n_enderecos_total"] * 100
    t2["pct_est_religiosos"] = t2["n_est_religiosos"] / t2["n_enderecos_total"] * 100
    t2 = corrigir_renda_us(t2)

    # 4. Validação tripla (se arquivo existir)
    val = cfg.DATA / "validacao_tripla_por_us.csv"
    if val.exists():
        v = pd.read_csv(val)[["Unidade de Saúde", "pop_grade2022", "pop_hrsl", "dif_pct"]]
        t2 = t2.merge(v, on="Unidade de Saúde", how="left")
        print(f"  Validação tripla incorporada ({len(v)} US)")

    saida = cfg.OUTPUTS / "tabelas_unidades_saude_v2.xlsx"
    cfg.OUTPUTS.mkdir(parents=True, exist_ok=True)
    t2.to_excel(saida, index=False, sheet_name="Indicadores_Completos_v2")
    print(f"\n[5/5] Salvo: {saida} ({t2.shape[0]} US × {t2.shape[1]} colunas)")


if __name__ == "__main__":
    principal()