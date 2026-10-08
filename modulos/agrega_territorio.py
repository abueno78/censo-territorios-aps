"""Módulo 1 — Indicadores do TERRITÓRIO da Unidade de Saúde (nível US).

Constrói tabelas_unidades_saude_v2.xlsx do zero a partir dos dados brutos:
  - banco_agregados_poa_setores.csv  (Censo 2022, filtrado para POA)
  - composicao_com_hrsl.csv          (alocação setor → US via CNEFE)
  - cnefe_poa.parquet                (endereços georreferenciados)
  - Territorios_AP.kmz               (polígonos das US)
  - validacao_tripla_por_us.csv      (se existir)

NÃO depende de nenhuma planilha de resultado anterior (tabelas_unidades_saude.xlsx).

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


# ─── CNEFE → indicadores por US ───────────────────────────────────────────────

def carregar_cnefe() -> pd.DataFrame:
    df = pd.read_parquet(cfg.CNEFE_CSV)
    for c in ("LATITUDE", "LONGITUDE"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["COD_ESPECIE"]      = pd.to_numeric(df["COD_ESPECIE"],      errors="coerce").fillna(0).astype(int)
    df["COD_TIPO_ESPECI"]  = pd.to_numeric(df["COD_TIPO_ESPECI"],  errors="coerce").fillna(0).astype(int)
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
        "n_enderecos_total":   g.size(),
        "n_domic_privados":    g.apply(lambda x: (x["COD_ESPECIE"] == 1).sum(), include_groups=False),
        "n_domic_coletivos":   g.apply(lambda x: (x["COD_ESPECIE"] == 2).sum(), include_groups=False),
        "n_est_ensino":        g.apply(lambda x: (x["COD_ESPECIE"] == 4).sum(), include_groups=False),
        "n_est_saude":         g.apply(lambda x: (x["COD_ESPECIE"] == 5).sum(), include_groups=False),
        "n_est_outras_final":  g.apply(lambda x: (x["COD_ESPECIE"] == 6).sum(), include_groups=False),
        "n_construcao_reforma":g.apply(lambda x: (x["COD_ESPECIE"] == 7).sum(), include_groups=False),
        "n_est_religiosos":    g.apply(lambda x: (x["COD_ESPECIE"] == 8).sum(), include_groups=False),
        "n_casas":             g.apply(lambda x: (x["COD_TIPO_ESPECI"] == 101).sum(), include_groups=False),
        "n_vilas_condos":      g.apply(lambda x: (x["COD_TIPO_ESPECI"] == 102).sum(), include_groups=False),
        "n_apartamentos":      g.apply(lambda x: (x["COD_TIPO_ESPECI"] == 103).sum(), include_groups=False),
        "n_outras_edif":       g.apply(lambda x: (x["COD_TIPO_ESPECI"] == 104).sum(), include_groups=False),
    }).reset_index()
    return res


# ─── Indicadores demográficos e sociais por US ────────────────────────────────

def agregar_censo_por_us(banco: pd.DataFrame, comp: pd.DataFrame) -> pd.DataFrame:
    """Agrega indicadores do Censo 2022 por US usando composição ponderada.

    Contagens: multiplicadas por fator_proporcao e somadas.
    Médias/medianas de renda: ponderadas por responsáveis × fator (V06001).
    Percentuais: derivados das contagens ponderadas.
    """
    banco["CD_SETOR"] = banco["CD_SETOR"].astype(str).str.strip()
    comp["CD_SETOR"]  = comp["CD_SETOR"].astype(str).str.strip()
    comp["fator_proporcao"] = pd.to_numeric(comp["fator_proporcao"], errors="coerce")

    m = comp.merge(banco, on="CD_SETOR", how="left")

    # Contagens numéricas
    CONTAGENS = [
        "v0001",  # domicílios particulares permanentes ocupados
        "V01006",  # pop total
        "V01007", "V01008", "V01009", "V01010", "V01011",  # faixas 0-4…20-24
        "V01012", "V01013", "V01014", "V01015", "V01016",  # 25-29…45-49
        "V01017", "V01018", "V01019", "V01020", "V01021",  # 50-54…70-74
        "V01022",  # 75+
        "V01026",  # pop masc
        "V01027",  # pop fem
        "V00644",  # alfabetizados 15+
        "V00645",  # pop 15+ (denominador alfa)
        "V01317", "V01318", "V01319", "V01320", "V01321",  # cor/raça
        "V06001",  # responsáveis com renda
        "V00001",  # dom particulares
        "V00002", "V00003", "V00004", "V00005", "V00006",  # tipo dom
    ]

    for c in CONTAGENS:
        if c in m.columns:
            m[c] = pd.to_numeric(m[c], errors="coerce")
            m[f"{c}_pond"] = m[c] * m["fator_proporcao"]

    def _pond(col):
        return m.groupby("Unidade de Saúde")[f"{col}_pond"].sum()

    # Tipo de setor (área ponderada)
    for tipo in ["Baixo Patamar", "Favela/Comunidade", "Hospital/ILPI",
                 "Indígena", "Não especial", "Prisional", "Quartel", "Quilombola"]:
        if tipo in m.columns:
            m[f"_tipo_{tipo}"] = (m[tipo].astype(str).str.strip() == tipo).astype(float) * m["fator_proporcao"]

    # Área ponderada (km²)
    if "AREA_KM2" in m.columns:
        m["AREA_KM2"] = pd.to_numeric(m["AREA_KM2"], errors="coerce")
        m["_area_pond"] = m["AREA_KM2"] * m["fator_proporcao"]

    agg = pd.DataFrame(index=m.groupby("Unidade de Saúde").groups.keys())
    agg.index.name = "Unidade de Saúde"

    # População e composição
    if "V01006_pond" in m.columns:
        agg["População Alocada à US"] = _pond("V01006")
    if "V01026_pond" in m.columns and "V01027_pond" in m.columns:
        agg["pct_masc"] = _pond("V01026") / _pond("V01006") * 100
        agg["pct_fem"]  = _pond("V01027") / _pond("V01006") * 100

    # Faixas etárias agrupadas (IBGE)
    faixas = {
        "pct_0_14":  ["V01007","V01008","V01009"],        # 0-4, 5-9, 10-14
        "pct_15_29": ["V01010","V01011","V01012"],        # 15-19, 20-24, 25-29
        "pct_30_59": ["V01013","V01014","V01015","V01016","V01017","V01018"],
        "pct_60_mais": ["V01019","V01020","V01021","V01022"],
    }
    for nome_fx, cols_fx in faixas.items():
        cols_ok = [c for c in cols_fx if f"{c}_pond" in m.columns]
        if cols_ok and "V01006_pond" in m.columns:
            soma = sum(_pond(c) for c in cols_ok)
            agg[nome_fx] = soma / _pond("V01006") * 100

    # Alfabetização
    if "V00644_pond" in m.columns and "V00645_pond" in m.columns:
        agg["taxa_alf_geral"] = _pond("V00644") / _pond("V00645") * 100

    # Cor/raça
    COR = {"pct_Branca": "V01317", "pct_Preta": "V01318", "pct_Amarela": "V01319",
           "pct_Parda": "V01320", "pct_Indígena": "V01321"}
    for nome_cor, vcol in COR.items():
        if f"{vcol}_pond" in m.columns and "V01006_pond" in m.columns:
            agg[nome_cor] = _pond(vcol) / _pond("V01006") * 100

    # Tipo de setor (% área ponderada)
    for tipo in ["Baixo Patamar", "Favela/Comunidade", "Hospital/ILPI",
                 "Indígena", "Não especial", "Prisional", "Quartel", "Quilombola"]:
        col_t = f"_tipo_{tipo}"
        if col_t in m.columns:
            agg[tipo] = m.groupby("Unidade de Saúde")[col_t].sum()

    # Área
    if "_area_pond" in m.columns:
        agg["area_km2_ponderada"] = m.groupby("Unidade de Saúde")["_area_pond"].sum()

    return agg.reset_index()


# ─── Renda winsorizada (v2 — sem bug) ─────────────────────────────────────────

def _quantil_ponderado(vals: np.ndarray, pesos: np.ndarray, q: float) -> float:
    o = np.argsort(vals)
    s = np.cumsum(pesos[o])
    if s[-1] <= 0:
        return np.nan
    return vals[o][np.searchsorted(s, q * s[-1])]


def calcular_renda_winsorizada(comp: pd.DataFrame, banco: pd.DataFrame) -> pd.DataFrame:
    """Calcula renda média por US com winsorização no nível do SETOR (v2).

    Correção do bug da v1: a v1 somava médias ponderadas sem dividir pelo peso
    total, gerando valores absurdos (ex.: R$ 14 milhões). Aqui a média ponderada
    é calculada corretamente: soma(V06004_w × peso) / soma(peso).

    Variáveis produzidas:
      renda_media_winsor   — média ponderada por responsáveis×fator (V06004 winsorizado)
      renda_mediana_aprox  — mediana ponderada das médias setoriais
      renda_dp             — desvio padrão (within + between setores)
      renda_cv             — coeficiente de variação (%)
      flag_renda_suspeita  — 1 se razão média/mediana > 2,5 ou < 3 setores com renda
    """
    b = banco[["CD_SETOR", "V06001", "V06004", "V06005", "V06006"]].copy()
    for c in ("V06001", "V06004", "V06005", "V06006"):
        b[c] = pd.to_numeric(b[c], errors="coerce")

    # Winsorização p1/p99 + teto R$ 100 mil
    lo, hi = b["V06004"].quantile(0.01), b["V06004"].quantile(0.99)
    b["V06004_w"] = b["V06004"].clip(lo, hi).where(b["V06004"] < 100_000)
    vhi = b["V06005"].quantile(0.99)
    b["V06005_w"] = b["V06005"].clip(upper=vhi)

    print(f"  Renda winsorizada: p1=R${lo:,.0f} / p99=R${hi:,.0f} / teto=R$100.000")

    m = comp.merge(b, on="CD_SETOR", how="inner")
    m["peso"] = m["V06001"] * m["fator_proporcao"]

    def _agg(g: pd.DataFrame) -> pd.Series:
        w = g["peso"]
        ok = g["V06004_w"].notna()
        if w.sum() <= 0 or ok.sum() == 0:
            return pd.Series({"renda_media_winsor": np.nan, "renda_mediana_aprox": np.nan,
                              "renda_dp": np.nan, "renda_cv": np.nan,
                              "n_setores_renda_ok": 0})
        mu = (g["V06004_w"] * w).sum() / w.sum()
        var_within  = (g["V06005_w"] * w).sum() / w.sum()
        var_between = (w * (g["V06004_w"] - mu) ** 2).sum() / w.sum()
        var_total   = var_within + var_between
        dp = np.sqrt(max(var_total, 0))
        med = _quantil_ponderado(g["V06004_w"].values, w.values, 0.50)
        return pd.Series({
            "renda_media_winsor":  mu,
            "renda_mediana_aprox": med,
            "renda_dp":            dp,
            "renda_cv":            dp / mu * 100 if mu > 0 else np.nan,
            "n_setores_renda_ok":  int(ok.sum()),
        })

    agg = (m.groupby("Unidade de Saúde")
            .apply(_agg, include_groups=False)
            .reset_index())

    agg["flag_renda_suspeita"] = (
        (agg["renda_media_winsor"] / agg["renda_mediana_aprox"].replace(0, np.nan) > 2.5) |
        (agg["n_setores_renda_ok"].fillna(0) < 3)
    )
    n_flag = agg["flag_renda_suspeita"].sum()
    print(f"  {n_flag} US sinalizadas com flag_renda_suspeita")
    return agg


# ─── Pipeline principal ───────────────────────────────────────────────────────

def principal():
    print("═" * 62)
    print("MÓDULO 1 — Indicadores do território por Unidade de Saúde")
    print("═" * 62)

    # 1. Carregar banco de agregados do Censo (já filtrado para POA)
    print("\n[1/5] Carregando banco_agregados_poa_setores.csv ...")
    banco = pd.read_csv(cfg.BANCO_SETORES, dtype=str, low_memory=False)
    banco["CD_SETOR"] = banco["CD_SETOR"].astype(str).str.strip()
    print(f"  {len(banco)} setores | {banco.shape[1]} colunas")

    # 2. Carregar composição setor → US
    print("\n[2/5] Carregando composicao_com_hrsl.csv ...")
    comp = pd.read_csv(cfg.DATA / "composicao_com_hrsl.csv")
    comp["CD_SETOR"] = comp["CD_SETOR"].astype(str).str.strip()
    comp["fator_proporcao"] = pd.to_numeric(comp["fator_proporcao"], errors="coerce")
    print(f"  {len(comp)} alocações | {comp['Unidade de Saúde'].nunique()} US")

    # 3. Indicadores demográficos e sociais via Censo
    print("\n[3/5] Agregando indicadores do Censo por US ...")
    base = agregar_censo_por_us(banco, comp)
    print(f"  {len(base)} US | {base.shape[1]} colunas")

    # 4. Indicadores CNEFE (tipologia de endereços, densidade)
    print("\n[4/5] Agregando CNEFE por território ...")
    cnefe = carregar_cnefe()
    us_gdf = (gpd.read_file(cfg.KMZ_US, driver="KML")
              .rename(columns={"Name": "Unidade de Saúde"})
              .to_crs(cfg.EPSG_GEO))

    # CNES + coordenadoria + distrito do KMZ
    cnes_meta = us_gdf[["Unidade de Saúde", "CNES",
                         "Coordenadoria_de_Sa__de", "Distrito_Sanit__rio"]].copy()
    cnes_meta = cnes_meta.rename(columns={
        "Coordenadoria_de_Sa__de": "coordenadoria_saude",
        "Distrito_Sanit__rio":     "distrito_sanitario",
    })

    cnefe_us = agregar_cnefe_por_us(cnefe, us_gdf)

    t = base.merge(cnes_meta, on="Unidade de Saúde", how="left")
    t = t.merge(cnefe_us,   on="Unidade de Saúde", how="left")

    # Densidades e proporções derivadas do CNEFE
    t["densidade_hab_km2"]      = t["População Alocada à US"] / t["area_km2_ponderada"]
    t["densidade_enderecos_km2"]= t["n_enderecos_total"] / t["area_km2_ponderada"]
    t["pct_apartamentos"]       = t["n_apartamentos"] / t["n_enderecos_total"] * 100

    # 5. Renda winsorizada (v2 — corrige bug da v1)
    print("\n[5/5] Calculando renda winsorizada (v2) ...")
    renda = calcular_renda_winsorizada(comp, banco)
    t = t.merge(renda, on="Unidade de Saúde", how="left")

    # Validação tripla (se existir)
    val = cfg.DATA / "validacao_tripla_por_us.csv"
    if val.exists():
        v = pd.read_csv(val)[["Unidade de Saúde", "pop_grade2022", "pop_hrsl", "dif_pct"]]
        t = t.merge(v, on="Unidade de Saúde", how="left")
        print(f"  Validação tripla incorporada ({len(v)} US)")

    # Salvar
    cfg.OUTPUTS.mkdir(parents=True, exist_ok=True)
    saida = cfg.OUTPUTS / "tabelas_unidades_saude_v2.xlsx"
    t.to_excel(saida, index=False, sheet_name="Indicadores_Completos_v2")
    print(f"\n✓ Salvo: {saida}")
    print(f"  {t.shape[0]} US × {t.shape[1]} colunas")
    print("\nVariáveis de renda geradas (v2 — sem bug):")
    print("  ✓ renda_media_winsor  (média ponderada, winsorizada p1/p99 ≤ R$100k)")
    print("  ✓ renda_mediana_aprox")
    print("  ✓ renda_dp, renda_cv")
    print("  ✗ renda_media_ponderada — NÃO gerada (bug da v1, somava médias sem dividir)")
    print("  ✗ cv_renda              — NÃO gerada (substituída por renda_cv)")


if __name__ == "__main__":
    principal()
