"""Módulo 1 — Indicadores do TERRITÓRIO da Unidade de Saúde (nível US).

Constrói tabelas_unidades_saude_v2.xlsx do zero a partir dos dados brutos.

A agregação por US é a MESMA do script que originou o banco da tese
(analise_agregados_unidades_saude.py) — ver DOCUMENTACAO_METODOLOGICA.md —
com UMA correção: a renda média por US agora é winsorizada no nível do SETOR
(v2), eliminando o bug da v1 que somava médias sem dividir pelo peso.

Fontes:
  - banco_agregados_poa_setores.csv  (Censo 2022, filtrado para POA)
  - composicao_com_hrsl.csv          (alocação setor → US via CNEFE)
  - cnefe_poa.parquet                (endereços georreferenciados)
  - Territorios_AP.kmz               (polígonos das US)
  - validacao_tripla_por_us.csv      (se existir)

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


# ─── Núcleo: agregar por US com ponderação (porta fiel da v1) ───────────────

def agregar_por_us(df: pd.DataFrame, colunas_valor: list, comp: pd.DataFrame) -> pd.DataFrame:
    """Merge com a composição das US, multiplica por fator_proporcao e soma por US.

    Iguau à função agregar_por_us() do script original da tese.
    """
    df_m = comp.merge(df, on="CD_SETOR", how="inner")
    for c in colunas_valor:
        df_m[c] = pd.to_numeric(df_m[c], errors="coerce")
        df_m[c + "_pond"] = df_m[c] * df_m["fator_proporcao"]
    agg_dict = {c + "_pond": "sum" for c in colunas_valor}
    df_agg = df_m.groupby("Unidade de Saúde").agg(agg_dict).reset_index()
    for c in colunas_valor:
        df_agg = df_agg.rename(columns={c + "_pond": c})
    return df_agg


# ─── Carregar os agregados do banco, separados por tema ─────────────────────

def carregar_temas(banco: pd.DataFrame):
    banco = banco.copy()
    banco["CD_SETOR"] = banco["CD_SETOR"].astype(str).str.strip()

    def cols(*temps):
        c = ["CD_SETOR"] + list(temps)
        # deduplicar: cols() é chamado mais de uma vez por tema
        seen, out = set(), []
        for x in c:
            if x not in seen and x in banco.columns:
                seen.add(x)
                out.append(x)
        return out

    df_basico = banco[cols("SITUACAO", "CD_TIPO", "AREA_KM2") +
                      [f"v{i:04d}" for i in (1, 2, 3, 4, 7, 8, 9)]].copy()
    df_alf    = banco[cols(*[f"V{i:05d}" for i in range(644, 657)]) +
                      cols(*[f"V{i:05d}" for i in range(826, 852)])].copy()
    df_alf = df_alf.loc[:, ~df_alf.columns.duplicated()]  # CD_SETOR aparece 2x (2 cols())
    df_demo   = banco[cols(*[f"V{i:05d}" for i in range(1006, 1042)])].copy()
    df_raca   = banco[cols(*[f"V{i:05d}" for i in range(1317, 1332)])].copy()
    df_renda  = banco[cols("V06001", "V06002", "V06003", "V06004", "V06005", "V06006")].copy()
    df_dom1   = banco[cols(*[f"V{i:05d}" for i in range(1, 8)])].copy()

    for df_t in (df_basico, df_alf, df_demo, df_raca, df_renda, df_dom1):
        for c in df_t.columns:
            if c != "CD_SETOR":
                df_t[c] = pd.to_numeric(df_t[c], errors="coerce")
    # Tratar o sigilo do IBGE ("X" nunca chegou, mas confirma)
    return df_basico, df_alf, df_demo, df_raca, df_renda, df_dom1


# ─── CNEFE → indicadores por US (dimensão/composição de endereços) ──────────

def carregar_cnefe() -> pd.DataFrame:
    df = pd.read_parquet(cfg.CNEFE_CSV)
    for c in ("LATITUDE", "LONGITUDE"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["COD_ESPECIE"]     = pd.to_numeric(df["COD_ESPECIE"], errors="coerce").fillna(0).astype(int)
    df["COD_TIPO_ESPECI"] = pd.to_numeric(df["COD_TIPO_ESPECI"], errors="coerce").fillna(0).astype(int)
    return df


def agregar_cnefe_por_us(cnefe: pd.DataFrame, us: gpd.GeoDataFrame) -> pd.DataFrame:
    """Join espacial endereços ↔ territórios e agrega indicadores por US."""
    pts = gpd.GeoDataFrame(
        cnefe, geometry=gpd.points_from_xy(cnefe["LONGITUDE"], cnefe["LATITUDE"]),
        crs=f"EPSG:{cfg.EPSG_GEO}",
    )
    joined = gpd.sjoin(pts, us[["Unidade de Saúde", "geometry"]], how="left", predicate="within")
    joined = joined.drop_duplicates(subset="COD_UNICO_ENDERECO", keep="first")
    print(f"  {len(joined):,} endereços | "
          f"{joined['Unidade de Saúde'].notna().sum():,} dentro de territórios")

    g = joined.dropna(subset=["Unidade de Saúde"]).groupby("Unidade de Saúde")
    res = pd.DataFrame({
        "n_enderecos_total":    g.size(),
        "n_domic_privados":     g.apply(lambda x: (x["COD_ESPECIE"] == 1).sum(), include_groups=False),
        "n_domic_coletivos":    g.apply(lambda x: (x["COD_ESPECIE"] == 2).sum(), include_groups=False),
        "n_est_ensino":         g.apply(lambda x: (x["COD_ESPECIE"] == 4).sum(), include_groups=False),
        "n_est_saude":          g.apply(lambda x: (x["COD_ESPECIE"] == 5).sum(), include_groups=False),
        "n_est_outras_final":   g.apply(lambda x: (x["COD_ESPECIE"] == 6).sum(), include_groups=False),
        "n_construcao_reforma": g.apply(lambda x: (x["COD_ESPECIE"] == 7).sum(), include_groups=False),
        "n_est_religiosos":     g.apply(lambda x: (x["COD_ESPECIE"] == 8).sum(), include_groups=False),
        "n_casas":              g.apply(lambda x: (x["COD_TIPO_ESPECI"] == 101).sum(), include_groups=False),
        "n_vilas_condos":       g.apply(lambda x: (x["COD_TIPO_ESPECI"] == 102).sum(), include_groups=False),
        "n_apartamentos":       g.apply(lambda x: (x["COD_TIPO_ESPECI"] == 103).sum(), include_groups=False),
        "n_outras_edif":        g.apply(lambda x: (x["COD_TIPO_ESPECI"] == 104).sum(), include_groups=False),
    }).reset_index()
    return res


# ─── Renda winsorizada (v2 — corrige o bug da v1) ───────────────────────────

def _quantil_ponderado(vals, pesos, q):
    o = np.argsort(vals)
    s = np.cumsum(pesos[o])
    if s[-1] <= 0:
        return np.nan
    return vals[o][np.searchsorted(s, q * s[-1])]


def calcular_renda_winsorizada(comp: pd.DataFrame, df_renda: pd.DataFrame) -> pd.DataFrame:
    """Renda média por US winsorizada no nível do SETOR (somente V06004).

    Correção do bug da v1: valores extremos imputados (ex.: US São Vicente
    Mártir R$ 121 mil) eram somados sem dividir. Aqui clips-se V06004 no
    quantil p1/p99 com teto de R$ 100 mil, e agrega-se pela média ponderada
    por responsáveis × fator.
    """
    b = df_renda[["CD_SETOR", "V06001", "V06004", "V06005", "V06006"]].copy()
    for c in ("V06001", "V06004", "V06005", "V06006"):
        b[c] = pd.to_numeric(b[c], errors="coerce")

    lo, hi = b["V06004"].quantile(0.01), b["V06004"].quantile(0.99)
    b["V06004_w"] = b["V06004"].clip(lo, hi).where(b["V06004"] < 100_000)
    vhi = b["V06005"].quantile(0.99)
    b["V06005_w"] = b["V06005"].clip(upper=vhi)
    print(f"  Renda winsorizada: p1=R${lo:,.0f} / p99=R${hi:,.0f} / teto=R$100.000")

    m = comp.merge(b, on="CD_SETOR", how="inner")
    m["peso"] = m["V06001"] * m["fator_proporcao"]

    def _agg(g):
        w = g["peso"]
        ok = g["V06004_w"].notna()
        if w.sum() <= 0 or ok.sum() == 0:
            return pd.Series({"renda_media_winsor": np.nan, "renda_dp": np.nan,
                              "renda_cv": np.nan, "n_setores_renda_ok": 0})
        mu = (g["V06004_w"] * w).sum() / w.sum()
        var_within  = (g["V06005_w"] * w).sum() / w.sum()
        var_between = (w * (g["V06004_w"] - mu) ** 2).sum() / w.sum()
        dp = np.sqrt(max(var_within + var_between, 0))
        return pd.Series({"renda_media_winsor": mu, "renda_dp": dp,
                          "renda_cv": dp / mu * 100 if mu > 0 else np.nan,
                          "n_setores_renda_ok": int(ok.sum())})

    agg = (m.groupby("Unidade de Saúde").apply(_agg, include_groups=False).reset_index())
    agg["flag_renda_suspeita"] = (
        (agg["renda_media_winsor"] / 1) > 100_000
    ) | (agg["n_setores_renda_ok"].fillna(0) < 3)
    return agg


# ─── Pipeline principal ──────────────────────────────────────────────────────

def principal():
    print("═" * 62)
    print("MÓDULO 1 — Indicadores do território por Unidade de Saúde")
    print("═" * 62)

    # 1. Composição setor → US
    print("\n[1/6] Carregando composição das US ...")
    comp = pd.read_csv(cfg.DATA / "composicao_com_hrsl.csv", dtype=str)
    comp = comp.drop(columns=["Código do Setor"], errors="ignore")  # já tem CD_SETOR
    comp["CD_SETOR"] = comp["CD_SETOR"].astype(str).str.strip()
    comp["fator_proporcao"] = pd.to_numeric(comp["fator_proporcao"], errors="coerce")
    comp["População Total do Setor"] = pd.to_numeric(comp["População Total do Setor"], errors="coerce")
    comp["População Alocada à US"] = pd.to_numeric(comp["População Alocada à US"], errors="coerce")
    print(f"  {len(comp)} alocações | {comp['Unidade de Saúde'].nunique()} US")

    # 2. Banco agregado do Censo → temas
    print("\n[2/6] Carregando banco_agregados_poa_setores.csv ...")
    banco = pd.read_csv(cfg.BANCO_SETORES, dtype=str, low_memory=False)
    df_basico, df_alf, df_demo, df_raca, df_renda, df_dom1 = carregar_temas(banco)
    print(f"  {len(banco):,} setores | {banco.shape[1]} colunas")

    # 3. Tipo de setor (CD_TIPO) — share do fator de alocação
    print("\n[3/6] Tipo de setor ...")
    MAPA_TIPO = {0: "Não especial", 1: "Favela/Comunidade", 2: "Quartel", 3: "Alojamento",
                 4: "Baixo Patamar", 5: "Indígena", 6: "Prisional", 7: "Hospital/ILPI",
                 8: "Agrovila", 9: "Quilombola"}
    df_tipo = comp.merge(df_basico[["CD_SETOR", "CD_TIPO"]], on="CD_SETOR", how="inner")
    df_tipo["CD_TIPO"] = pd.to_numeric(df_tipo["CD_TIPO"], errors="coerce").fillna(0).astype(int)
    df_tipo["Tipo_Setor"] = df_tipo["CD_TIPO"].map(MAPA_TIPO)
    tipo_us_pct = (df_tipo.groupby(["Unidade de Saúde", "Tipo_Setor"])["fator_proporcao"]
                   .sum().unstack(fill_value=0))
    tipo_us_pct = tipo_us_pct.div(tipo_us_pct.sum(axis=1), axis=0) * 100

    # População e área (da composição + AREA_KM2)
    indicadores = comp.groupby("Unidade de Saúde").agg(
        {"População Total do Setor": "sum", "População Alocada à US": "sum",
         "fator_proporcao": "sum"}).reset_index()
    indicadores = indicadores.merge(tipo_us_pct.reset_index(), on="Unidade de Saúde", how="left")
    df_area = comp.merge(df_basico[["CD_SETOR", "AREA_KM2"]], on="CD_SETOR", how="inner")
    df_area["AREA_KM2"] = pd.to_numeric(df_area["AREA_KM2"], errors="coerce")
    df_area["AREA_KM2_pond"] = df_area["AREA_KM2"] * df_area["fator_proporcao"]
    area_us = (df_area.groupby("Unidade de Saúde")["AREA_KM2_pond"].sum()
               .rename("area_km2_ponderada").reset_index())
    indicadores = indicadores.merge(area_us, on="Unidade de Saúde", how="left")

    # 4. Alfabetização, demografia, cor/raça, renda, domicílios
    print("\n[4/6] Alfabetização, demografia, cor/raça, renda, domicílios ...")

    # — Alfabetização (método v1: numerador = V00826..V00851, denominador = V00644..V00656)
    cols_alf_total = [f"V{i:05d}" for i in range(644, 657)]
    alf_masc_cols  = [f"V{i:05d}" for i in range(826, 839)]
    alf_fem_cols   = [f"V{i:05d}" for i in range(839, 852)]
    df_alf_us = agregar_por_us(df_alf, cols_alf_total + alf_masc_cols + alf_fem_cols, comp)
    df_alf_us["total_15+"]   = df_alf_us[cols_alf_total].sum(axis=1)
    df_alf_us["alf_masc_15+"] = df_alf_us[alf_masc_cols].sum(axis=1)
    df_alf_us["alf_fem_15+"]  = df_alf_us[alf_fem_cols].sum(axis=1)
    df_alf_us["taxa_alf_masc"] = df_alf_us["alf_masc_15+"] / df_alf_us["total_15+"] * 100
    df_alf_us["taxa_alf_fem"]  = df_alf_us["alf_fem_15+"]  / df_alf_us["total_15+"] * 100
    df_alf_us["taxa_alf_geral"] = (df_alf_us["alf_masc_15+"] + df_alf_us["alf_fem_15+"]) / df_alf_us["total_15+"] * 100

    # — Demografia (V01006 pop, V01007 masc, V01008 fem; V01009..V01030 faixas M/F)
    demo_cols = [f"V{i:05d}" for i in range(1009, 1031)]
    df_demo_us = agregar_por_us(df_demo, demo_cols + ["V01006", "V01007", "V01008"], comp)
    idades_dict = {"0_4_M": "V01009", "5_9_M": "V01010", "10_14_M": "V01011", "15_19_M": "V01012",
                   "20_24_M": "V01013", "25_29_M": "V01014", "30_39_M": "V01015", "40_49_M": "V01016",
                   "50_59_M": "V01017", "60_69_M": "V01018", "70+_M": "V01019",
                   "0_4_F": "V01020", "5_9_F": "V01021", "10_14_F": "V01022", "15_19_F": "V01023",
                   "20_24_F": "V01024", "25_29_F": "V01025", "30_39_F": "V01026", "40_49_F": "V01027",
                   "50_59_F": "V01028", "60_69_F": "V01029", "70+_F": "V01030"}
    for nome, col in idades_dict.items():
        df_demo_us[f"pct_{nome}"] = df_demo_us[col] / df_demo_us["V01006"] * 100
    df_demo_us["pct_masc"] = df_demo_us["V01007"] / df_demo_us["V01006"] * 100
    df_demo_us["pct_fem"]  = df_demo_us["V01008"] / df_demo_us["V01006"] * 100

    # — Cor/raça (percentual DENTRO das 5 raças — método v1)
    raca_cols = ["V01317", "V01318", "V01319", "V01320", "V01321"]
    raca_nomes = {"V01317": "Branca", "V01318": "Preta", "V01319": "Amarela",
                  "V01320": "Parda", "V01321": "Indígena"}
    df_raca_us = agregar_por_us(df_raca, raca_cols, comp)
    total_raca = df_raca_us[raca_cols].sum(axis=1)
    for col, nome in raca_nomes.items():
        df_raca_us[f"pct_{nome}"] = df_raca_us[col] / total_raca * 100

    # — Renda (V06006 → renda_mediana_aprox = média ponderada por responsáveis)
    df_r = comp.merge(df_renda, on="CD_SETOR", how="inner")
    for c in ["V06001", "V06002", "V06003", "V06004", "V06005", "V06006"]:
        df_r[c] = pd.to_numeric(df_r[c], errors="coerce")
    df_r["peso_renda"] = df_r["V06001"] * df_r["fator_proporcao"]
    df_renda_us = df_r.groupby("Unidade de Saúde").apply(
        lambda g: pd.Series({
            "total_responsaveis": (g["V06001"] * g["fator_proporcao"]).sum(),
            "renda_mediana_aprox":
                (g["V06006"] * g["peso_renda"]).sum() / g["peso_renda"].sum()
                if g["peso_renda"].sum() > 0 else None,
        }), include_groups=False).reset_index()

    # — Domicílios (V00001..V00007 do dom1; v0008/v0009 do básico)
    dom_cols = [f"V{i:05d}" for i in range(1, 8)]
    df_dom_us = agregar_por_us(df_dom1, dom_cols, comp)
    df_dom_us = df_dom_us.rename(columns={
        "V00001": "dom_particulares_permanentes_ocupados", "V00002": "dom_improvisados_ocupados",
        "V00003": "dom_coletivos_com_morador", "V00004": "dom_part_permanentes_ocupados_2",
        "V00005": "moradores_dpou", "V00006": "moradores_dio", "V00007": "moradores_coletivos"})
    df_dom_basico = agregar_por_us(df_basico[["CD_SETOR", "v0008", "v0009"]],
                                   ["v0008", "v0009"], comp)
    df_dom_basico = df_dom_basico.rename(columns={"v0008": "dom_uso_ocasional",
                                                   "v0009": "dom_vagos"})
    df_dom_us = df_dom_us.merge(df_dom_basico, on="Unidade de Saúde", how="left")

    # Juntar tudo
    indicadores = indicadores.merge(
        df_alf_us[["Unidade de Saúde", "taxa_alf_geral", "taxa_alf_masc", "taxa_alf_fem"]],
        on="Unidade de Saúde", how="left")
    indicadores = indicadores.merge(
        df_demo_us[["Unidade de Saúde", "pct_masc", "pct_fem"] +
                   [f"pct_{k}" for k in idades_dict]],
        on="Unidade de Saúde", how="left")
    indicadores = indicadores.merge(
        df_raca_us[["Unidade de Saúde", "pct_Branca", "pct_Parda", "pct_Preta",
                    "pct_Amarela", "pct_Indígena"]], on="Unidade de Saúde", how="left")
    indicadores = indicadores.merge(
        df_renda_us[["Unidade de Saúde", "renda_mediana_aprox", "total_responsaveis"]],
        on="Unidade de Saúde", how="left")
    indicadores = indicadores.merge(
        df_dom_us[["Unidade de Saúde", "dom_particulares_permanentes_ocupados",
                   "dom_improvisados_ocupados", "dom_coletivos_com_morador",
                   "dom_uso_ocasional", "dom_vagos"]], on="Unidade de Saúde", how="left")

    # 5. CNEFE (endereços, densidade) + CNES + coordenadoria/distrito
    print("\n[5/6] Agregando CNEFE por território ...")
    cnefe = carregar_cnefe()
    us_gdf = (gpd.read_file(cfg.KMZ_US, driver="KML")
              .rename(columns={"Name": "Unidade de Saúde"})
              .to_crs(cfg.EPSG_GEO))
    cnes_meta = us_gdf[["Unidade de Saúde", "CNES",
                        "Coordenadoria_de_Sa__de", "Distrito_Sanit__rio"]].copy()
    cnes_meta = cnes_meta.rename(columns={
        "Coordenadoria_de_Sa__de": "coordenadoria_saude",
        "Distrito_Sanit__rio": "distrito_sanitario"})
    cnefe_us = agregar_cnefe_por_us(cnefe, us_gdf)

    indicadores = indicadores.merge(cnes_meta, on="Unidade de Saúde", how="left")
    indicadores = indicadores.merge(cnefe_us, on="Unidade de Saúde", how="left")
    indicadores["densidade_hab_km2"] = indicadores["População Alocada à US"] / indicadores["area_km2_ponderada"]
    indicadores["densidade_enderecos_km2"] = indicadores["n_enderecos_total"] / indicadores["area_km2_ponderada"]
    indicadores["pct_apartamentos"] = indicadores["n_apartamentos"] / indicadores["n_enderecos_total"] * 100

    # 6. Renda winsorizada v2 + validação tripla
    print("\n[6/6] Calculando renda winsorizada (v2) ...")
    renda = calcular_renda_winsorizada(comp, df_renda)
    indicadores = indicadores.merge(renda, on="Unidade de Saúde", how="left")

    val = cfg.DATA / "validacao_tripla_por_us.csv"
    if val.exists():
        v = pd.read_csv(val)[["Unidade de Saúde", "pop_grade2022", "pop_hrsl", "dif_pct"]]
        indicadores = indicadores.merge(v, on="Unidade de Saúde", how="left")

    # Salvar
    cfg.OUTPUTS.mkdir(parents=True, exist_ok=True)
    saida = cfg.OUTPUTS / "tabelas_unidades_saude_v2.xlsx"
    indicadores.to_excel(saida, index=False, sheet_name="Indicadores_Completos_v2")
    print(f"\n✓ Salvo: {saida}")
    print(f"  {indicadores.shape[0]} US × {indicadores.shape[1]} colunas")

    # Verificação da renda
    ok = indicadores["renda_media_winsor"].notna().sum()
    print(f"  renda_media_winsor preenchida: {ok}/{len(indicadores)} US")


if __name__ == "__main__":
    principal()