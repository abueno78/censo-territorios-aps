# Pipeline Dados Censo → Territórios da Atenção Primária (POA)

Pipeline modular para análise sociodemográfica das Unidades de Saúde de Porto Alegre,
cruzando Censo Demográfico 2022 (IBGE), CNEFE e Grades Populacionais.

> **📄 Para o raciocínio completo, validações, comparações e desafios técnicos, leia
> [`DOCUMENTACAO_METODOLOGICA.md`](DOCUMENTACAO_METODOLOGICA.md)** — inclui a auditoria
> do estado inicial, a fundamentação na literatura, os testes de validação (Grade IBGE 2022
> e HRSL) e as limitações a declarar em publicações.


## Visão geral

```
                        ┌─────────────────────────────────────────────────┐
                        │  ENTRADAS (dados brutos)                       │
                        │  • CNEFE POA (endereços + coordenadas)          │
                        │  • Malha de setores censitários 2022            │
                        │  • Banco agregados por setor (Censo 2022)       │
                        │  • Grade Estatística 2022 (células 200m/1km)    │
                        │  • Territórios da APS (KMZ)                     │
                        └──────────────────┬──────────────────────────────┘
                                           ▼
        ┌────────────────────────────────────────────────────────────────┐
        │  MÓDULO 1 — agrega_territorio.py                              │
        │  (nível: Unidade de Saúde — HOJE, sem endereço do paciente)    │
        │  • Join espacial endereços CNEFE ↔ territórios US              │
        │  • Indicadores do território como um todo                      │
        │  • Densidade, estabelecimentos, domicílios, validação          │
        └────────────────────────────────────────────────────────────────┘
                                           ▼
        ┌────────────────────────────────────────────────────────────────┐
        │  MÓDULO 2 — endereco_para_setor.py                            │
        │  (nível: Setor censitário — FUTURO, com endereço do paciente)  │
        │  • Normaliza endereço textual (rua + número)                   │
        │  • Geocodifica via CNEFE local (sem API externa)               │
        │  • Atribui setor censitário + variáveis sociais do setor       │
        └────────────────────────────────────────────────────────────────┘
```

## Dados por nível de análise

### Nível 1 — Território da US (Módulo 1)

Para cada unidade de saúde (133), com as limitações de não ter o endereço do paciente:

| Grupo | Variáveis |
|---|---|
| População | pop_alocada_us (CNEFE), pop_grade2022 (Grade IBGE), pop_hrsl, % pop aproximada |
| Demografia | sexo, faixas etárias (11), cor/raça |
| Escolaridade | alfabetização geral/M/F |
| Renda | média ponderada, mediana, CV, razão média/mediana |
| Domicílios CNEFE | domicílios particulares, coletivos, casas, vilas/cond, apartamentos |
| Estabelecimentos CNEFE | ensino, saúde, religiosos, outras finalidades, em construção |
| Território | área km², densidade hab/km², densidade end/km², % apartamentos |
| Validação | dif% vs Grade 2022 e HRSL (correlação > 0,99) |

### Nível 2 — Setor censitário (Módulo 2)

Com o endereço textual do paciente (após comitê de ética):

| Grupo | Variáveis (do setor do paciente) |
|---|---|
| Renda | V06004 média, V06006 mediana, V06005 variância |
| Educação | V00644..V00656 alfabetização |
| Demografia | V01006..V01041 sexo/faixas etárias |
| Cor/raça | V01317..V01331 |
| Domicílios | V00001..V00007 + características |
| Território | CD_TIPO (favela, urbano, etc.), AREA_KM2 |

**Limitações (declarar em metodologia):**
- Falácia ecológica: valor do setor ≠ valor do indivíduo
- Setores com "X" (sigilo) → tratados como NaN
- Endereços não encontrados no CNEFE → fluxo de fallback (ver Módulo 2)

## Arquivos de entrada (esperados em `inputs/`)

| Arquivo | Origem | Descrição |
|---|---|---|
| `cnefe_poa.csv` | IBGE FTP | 762k endereços com lat/lon, espécie, tipo edificação |
| `poa_tracts_2022.gpkg` | geobr/IBGE | Malha 2.744 setores censitários |
| `banco_agregados_poa_setores.csv` | Drive (ETL) | 626 colunas por setor (Censo 2022) |
| `Territorios_AP.kmz` | SMS POA | 132 polígonos de territórios |
| `grade_id14.shp` | IBGE FTP | Grade Estatística 2022 (quadrante RS/POA) |
| `tabelas_unidades_saude.xlsx` | Drive (ETL) | Indicadores base por US |

## Execução

```bash
# Módulo 1 — gera tabelas_unidades_saude_v2.xlsx (nível US)
python modulos/agrega_territorio.py

# Módulo 2 — gera setores dos pacientes (nível setor)
python modulos/endereco_para_setor.py inputs/pacientes_enderecos.csv -o outputs/pacientes_setores.csv
```

## Metodologia (resumo para citação)

1. **CNEFE como proxy espacial** — cada endereço georreferenciado (99,7% geocodificados
   no Brasil; nível 1-3 em 99,6% de POA) é alocado ao território da US via `sjoin
   within`; populações de setores partilhados são distribuídas proporcionalmente ao
   nº de endereços (fator_proporcao).
2. **Validação tripla** — alocação por US comparada com (a) Grade Estatística 2022
   (IBGE, oficial; correlação 0,999), (b) HRSL 2018 (satélite, 30m; correlação 0,992).
3. **Referências**: IBGE (2025) Grade Estatística 2022 — Notas metodológicas 01/2025;
   Salgado et al. (2025) Revista Brasileira de Cartografia v.77.