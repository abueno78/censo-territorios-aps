# Documentação Metodológica — Censo 2022 × Territórios da Atenção Primária (Porto Alegre)

**Projeto:** Análise sociodemográfica dos territórios de saúde de Porto Alegre a partir do Censo Demográfico 2022
**Município:** Porto Alegre/RS — código IBGE 4314902
**Unidades analisadas:** 133 Unidades de Saúde (132 territórios mapeados + 1 agregado residual)
**Data da documentação:** Setembro de 2026
**Contexto de uso:** docência e pesquisa (diretório `02_Docencia`)

---

## Sumário

1. [Sumário executivo](#1-sumário-executivo)
2. [Contexto e problema de pesquisa](#2-contexto-e-problema-de-pesquisa)
3. [Ponto de partida: auditoria do estado inicial](#3-ponto-de-partida-auditoria-do-estado-inicial)
4. [O método CNEFE: como funciona](#4-o-método-cnefe-como-funciona)
5. [Fundamentação na literatura](#5-fundamentação-na-literatura)
6. [Alternativas avaliadas e por que não substituem o método](#6-alternativas-avaliadas-e-por-que-não-substituem-o-método)
7. [Validações realizadas](#7-validações-realizadas)
8. [Diagnósticos de robustez](#8-diagnósticos-de-robustez)
9. [Desafios técnicos e soluções](#9-desafios-técnicos-e-soluções)
10. [Arquitetura da solução](#10-arquitetura-da-solução)
11. [Entregáveis](#11-entregáveis)
12. [Limitações e recomendações](#12-limitações-e-recomendações)
13. [Referências](#13-referências)

---

## 1. Sumário executivo

O projeto estima indicadores sociodemográficos (população, renda, escolaridade, estrutura etária, cor/raça, domicílios) para os **territórios das 133 Unidades de Saúde (US)** de Porto Alegre, a partir dos agregados do **Censo Demográfico 2022** por setor censitário.

Como os setores censitários não coincidem com os limites dos territórios de saúde, a população de setores partilhados por mais de uma US é distribuída proporcionalmente ao número de **endereços do CNEFE** (Cadastro Nacional de Endereços para Fins Estatísticos) em cada território.

**Resultados principais desta rodada de trabalho:**

| Verificação | Resultado |
|---|---|
| População total alocada (133 US) | 1.331.830 hab vs. Censo 2022 = 1.332.570 (99,94%) |
| Setores 100% dentro de uma única US | 1.960 setores / 914.550 hab (**68,7%** da população, sem aproximação) |
| Setores compartilhados (com aproximação) | 784 setores / 417.280 hab (**31,3%**) |
| Validação da população por US — **Grade Estatística IBGE 2022** | r = **0,9988**; mediana −0,82%; MAPE 8,0% |
| Validação da população por US — **HRSL 2018 (satélite)** | r = **0,9919**; mediana +10,2%; MAPE 20,9% |
| Correlação entre as duas referências independentes | r = 0,9902 |
| Impacto de trocar o peso CNEFE por peso de satélite | MAPE 3,1% por US; nenhuma US muda > 20% |

**Conclusão:** o método CNEFE reproduz a Grade Estatística oficial do IBGE com correlação 0,999 e é corroborado de forma independente pela grade de satélite HRSL. A alocação está validada para uso em pesquisa. As divergências remanescentes concentram-se em territórios pequenos (< 5 mil habitantes).

---

## 2. Contexto e problema de pesquisa

### 2.1 O objetivo em duas etapas

O projeto tem **dois momentos de análise**, com necessidades de dados distintas:

**Momento 1 — Território de saúde (atual, sem dados individuais).**
Não há acesso ao endereço exato do paciente. Portanto, o dado analisado é o **território da US como um todo**: um perfil sociodemográfico agregado de cada unidade, com suas limitações declaradas.

**Momento 2 — Setor censitário (futuro, após Comitê de Ética).**
Quando os endereços dos pacientes forem liberados, cada endereço textual será convertido em **setor censitário**, permitindo estimar variáveis individuais (renda, educação etc.) pelo contexto socioeconômico do setor de residência.

### 2.2 O obstáculo central

O IBGE publica dados por **setor censitário** (a menor unidade de coleta, ~2.744 em POA). Os serviços de saúde organizam-se por **territórios de Unidades de Saúde** (132 polígonos). Esses dois recortes **não são congruentes**:

- Um setor pode ser cortado por duas ou mais fronteiras de US;
- Um território de US agrega muitos setores (mediana = 16 setores por US; máximo = 302).

Sem uma regra explícita de alocação, não é possível somar os dados censitários por unidade de saúde sem introduzir erro. Este documento descreve a regra utilizada, sua fundamentação, os testes de validade e as limitações.

---

## 3. Ponto de partida: auditoria do estado inicial

A pasta `02_Docencia/dados_censo` continha um pipeline funcional (scripts 01–04 + `analise_agregados_unidades_saude.py`) e um banco consolidado. A auditoria inicial identificou:

### 3.1 O que estava correto

- **Cobertura completa:** 133/133 US presentes na planilha final; 2.728 setores alocados; nenhum valor nulo.
- **Consistência interna:** a soma dos fatores de alocação por setor = 1,000 em **todos** os 2.728 setores (divisão sem lacunas).
- **População:** soma alocada = 1.331.830 ≈ Censo 2022 municipal (99,94%).
- **Percentuais coerentes:** sexo soma 100%; cor/raça soma 100%.

### 3.2 Problemas e sinais de alerta identificados

| # | Achado | Gravidade | Diagnóstico |
|---|---|---|---|
| 1 | `renda_media_ponderada` com valores absurdos (US Nonoai = R$ 14.096.275) | **Alta** | A agregação **somava** médias ponderadas em vez de calcular a média ponderada (divisão ausente pelo total de peso) |
| 2 | `Fora de Território Mapeado` existe como "US" (8.239 hab, só 293 alocados) | Média | Agregado residual: setores sem polígono. 0,6% da população fora dos territórios |
| 3 | Soma das faixas etárias = 96,2–100% | Baixa | População sem faixa declarada ("idade ignorada") |
| 4 | 424 alocações com fator < 0,05 | Média | Fatias minúsculas geradas por 1–2 endereços de borda (ruído) |
| 5 | `indicadores_sociais_por_unidade_saude.xlsx` continha apenas a lista de nomes das US | Baixa | Arquivo stub; os indicadores reais estavam em outro arquivo |
| 6 | 39 US com "renda média" acima de R$ 100 mil | **Alta** | Mesma causa do item 1 |
| 7 | Nenhuma validação externa da alocação | Média | Não havia como afirmar a confiabilidade das estimativas por US |

Os itens 1 e 6 foram corrigidos nesta rodada. Os itens 2–5 foram documentados e tratados quando possível.

---

## 4. O método CNEFE: como funciona

### 4.1 A ideia central

O **CNEFE** é o cadastro georreferenciado de todos os endereços do Brasil, levantado pelo IBGE na operação censitária. No Censo 2022, **100% dos endereços foram geocodificados** (primeira vez na história do IBGE); a qualidade posicional é alta: erro quadrático médio de 5,84 m em condições ideais, com 99,68% dos endereços do país geocodificados no nível de endereço.

Em Porto Alegre: **762.239 endereços**, dos quais **759.445 (99,6%)** têm coordenadas de nível 1–3 (coordenada de endereço, não estimada por face de quadra ou centróide de setor).

### 4.2 Premissa metodológica

> **A distribuição dos endereços dentro de um setor é um proxy válido da distribuição da população dentro desse setor.**

Como o Censo informa a população **total** do setor, mas não sua distribuição interna, o CNEFE fornece a informação intra-setorial. Se um setor é cortado por duas US, a fração da população atribuída a cada uma é proporcional ao número de endereços em cada parte:

```
fator_proporcao(US_i, setor_k) = endereços(US_i ∩ setor_k) / endereços(setor_k)

População alocada(US_i) = Σ_k [ População(setor_k) × fator_proporcao(US_i, setor_k) ]
```

### 4.3 Estatísticas de alocação em Porto Alegre

| Categoria | Nº de setores | População | % da população |
|---|---|---|---|
| 1 US (exclusivo — **sem aproximação**) | 1.960 | 914.550 | **68,7%** |
| 2 US | 627 | 325.656 | 24,5% |
| 3 US | 124 | 80.744 | 6,1% |
| 4 US | 12 | 7.758 | 0,6% |
| 5 ou mais US | 5 | 3.122 | 0,2% |

**Leitura:** quase 70% da população de POA está em setores integralmente contidos em uma única US — nesses casos o método não faz nenhuma aproximação. A aproximação por endereços afeta os 31,3% restantes.

### 4.4 Regra de agregação de variáveis (contagens vs. estatísticas)

Um ponto metodológico decisivo, frequentemente fonte de erro:

- **Contagens** (população, domicílios, responsáveis, moradores) → multiplicam-se pelo `fator_proporcao` e somam-se.
- **Médias, medianas e variâncias** (renda, média de moradores) → **não podem ser somadas**. Devem ser combinadas por **média ponderada**, com peso = nº de responsáveis (V06001) × fator de alocação.

O não-cumprimento dessa regra foi exatamente a causa dos itens 1 e 6 da auditoria (rendas na casa dos milhões).

---

## 5. Fundamentação na literatura

O método é classificado como **interpolação areal com ponderação dasimétrica por pontos de endereço** (*dasymetric areal interpolation with address points*). A literatura brasileira específica sobre uso do CNEFE para esse fim é escassa — mas existe e foi localizada:

### 5.1 Referências centrais

**(a) IBGE (2025) — Grade Estatística 2022, Notas metodológicas 01/2025.**
O próprio IBGE **recomenda a dasimetria com o CNEFE** para compatibilizar dados censitários com recortes territoriais divergentes (setores ≠ bairros ≠ territórios de saúde). A nota descreve que a Grade Estatística 2022 foi construída vinculando microdados do universo do Censo 2022 às células por meio das **coordenadas geográficas dos domicílios do CNEFE** — ou seja, o instituto oficial valida exatamente a premissa deste projeto.

**(b) IJSN/ES (Nota Técnica) — "Notas para compatibilização da população de setores censitários".**
Aplicação do **mesmo método** para o estado do Espírito Santo: densidade habitantes/domicílio por setor (V0001 ÷ nº de domicílios) × nº de domicílios na intersecção, para estimar população de bairros. É o precedente metodológico mais próximo do pipeline deste projeto.

**(c) Salgado, Dal'Asta, Adorno & Amaral (2025)** — *Revista Brasileira de Cartografia*, v. 77.
DOI: 10.14393/rbcv77n0a-75653. Avalia grades populacionais globais na Amazônia usando **o CNEFE como referência de validação**, demonstrando que endereços/domicílios são proxy confiável para a distribuição populacional. Conclui recomendando replicação com a Grade Estatística 2022 quando disponível — o que este trabalho faz.

### 5.2 Por que isso importa

A ausência de validação externa (item 7 da auditoria) era o principal ponto fraco do projeto para fins de publicação. Com essas três referências, o método passa a ter: (i) **recomendação oficial** do IBGE, (ii) **precedente publicado** de aplicação, e (iii) **referencial teórico** de validação.

---

## 6. Alternativas avaliadas e por que não substituem o método

Foram consideradas quatro alternativas de dados globais de população em grade. Todas foram avaliadas quanto à adequação ao problema **específico** deste projeto.

| Produto | Origem | Método | Resolução | Situação |
|---|---|---|---|---|
| **Grade Estatística 2022** | IBGE (2025) | Dasimetria com CNEFE + microdados do Censo 2022 | 200 m (urbano) / 1 km (rural) | ✅ **Adotado** como referência oficial de validação |
| **HRSL** | Meta/Facebook + CIESIN | Dasimetria volumétrica com CNN sobre satélite (50 cm) | ~30 m | ✅ **Adotado** como validação externa independente |
| WorldPop | Univ. Southampton | Random Forest sem restrição de volume | ~100 m | ❌ Não adotado (ver 6.1) |
| GHS-POP | Comissão Europeia (JRC) | Dasimetria binária sobre áreas construídas | ~100 m | ⚪ Alternativa secundária |
| Kontur Population | Kontur Inc. | Grade hexagonal H3 | ~400 m | ❌ Não adotado (ver 6.2) |

### 6.1 Por que o WorldPop não foi adotado

O artigo de referência (Salgado et al., 2025) testou o WorldPop no Brasil e obteve o **pior desempenho**: MAPE de 22,96% (municipal) e 24,34% (contra o Censo 2022), com correlação de apenas 0,22 em células rurais. A causa apontada: o modelo Random Forest **não preserva o volume populacional de entrada**, e parte das variáveis auxiliares não é sintomática de população no contexto brasileiro. Apesar de existirem versões recentes (2023/2024), o método de estimativa permanece o mesmo.

### 6.2 Por que o Kontur não foi adotado

O Kontur Population é uma **grade derivada**: sua construção integra dados do próprio HRSL, do GHSL e de pegadas de edificações da Microsoft. Usá-lo para validar o HRSL seria **validação circular** — os dois produtos compartilham a mesma fonte. Além disso, a resolução de 400 m é mais grosseira que os ~30 m do HRSL.

### 6.3 A distinção decisiva: validação ≠ substituição

Um ponto que merece destaque: **nenhuma grade populacional substitui o método CNEFE para o objetivo final do projeto**, porque:

- As grades fornecem apenas **população e domicílios**;
- As variáveis de interesse (renda, escolaridade, cor/raça, estrutura etária) só existem nos **agregados do Censo por setor censitário**.

Consequentemente:
- **Para alocar VARIÁVEIS entre territórios** → o CNEFE continua sendo o instrumento adequado (é a única fonte de distribuição intra-setorial disponível com granularidade de endereço);
- **Para validar a POPULAÇÃO alocada** → as grades (Grade 2022, HRSL) fornecem a referência externa.

---

## 7. Validações realizadas

### 7.1 Validação municipal (sanidade dos totais)

| Fonte | População em POA | Comparação com Censo 2022 (1.332.570) |
|---|---|---|
| Censo 2022 (referência) | 1.332.570 | — |
| **Grade Estatística 2022 (IBGE)** | 1.341.898 (12.904 células) | razão **1,007** (0,7% acima — células de borda extravasam o município) |
| HRSL 2018 (satélite) | 1.454.315 | razão 1,091 (9,1% acima — grade de 2018, dois anos anterior ao Censo) |
| Alocação CNEFE por US | 1.331.830 | razão 0,9994 |

### 7.2 Validação por Unidade de Saúde (a verificação principal)

Comparação da população alocada por US contra as duas referências:

| Comparação | Correlação (Pearson) | Correlação log-log | Mediana da diferença | MAPE |
|---|---|---|---|---|
| CNEFE × **Grade Estatística 2022** | **0,9988** | — | **−0,82%** | **8,0%** |
| CNEFE × **HRSL 2018** | 0,9919 | 0,943 | +10,2% | 20,9% |
| Grade 2022 × HRSL | 0,9902 | — | — | — |

**Interpretação:**

1. A concordância com a Grade oficial (0,9988) indica que a implementação manual reproduz o método oficial do IBGE com fidelidade praticamente total.
2. A concordância com o HRSL (satélite, fonte **independente**) em 0,9919 confirma que a estrutura espacial estimada não é artefato do método CNEFE.
3. A mediana de −0,82% contra a Grade é um viés desprezível; a mediana de +10,2% contra o HRSL reflete o intervalo temporal (2018 vs 2022) e a tendência conhecida da grade de satélite a superestimar.

### 7.3 Divergências por porte da Unidade de Saúde

A divergência contra o HRSL **cai consistentemente com o tamanho do território**:

| Porte da US | Mediana da diferença | MAPE |
|---|---|---|
| < 3.000 hab | +28,9% | 39,2% |
| 3.000–10.000 hab | +9,5% | 20,3% |
| 10.000–30.000 hab | +8,2% | 15,2% |
| > 30.000 hab | +13,1% | 14,6% |

Isso é esperado: territórios pequenos têm menos endereços, e o erro relativo da amostragem por endereços cresce quando o denominador é pequeno. **Nenhuma US divergiu mais de 20% da Grade oficial.**

---

## 8. Diagnósticos de robustez

Além das validações, foram conduzidos testes para quantificar o risco residual do método.

### 8.1 Teste da hipótese alternativa: e se o peso fosse por satélite?

Questão natural: *"se o HRSL enxerga prédios (e não endereços), não seria um peso melhor?"*

Foram comparados os **fatores de alocação** nos 766 setores compartilhados (1.406 alocações), calculando o fator por HRSL:

```
fator_hrsl = população HRSL no (setor ∩ território da US) / população HRSL no setor
```

| Métrica | Resultado |
|---|---|
| Correlação entre os dois fatores | 0,896 |
| Alocações com divergência > 0,10 no fator | 31,2% |
| Alocações com divergência > 0,30 no fator | 7,8% |

**Porém**, ao propagar a troca de peso para o resultado final (população por US):

| Métrica (população por US) | Resultado |
|---|---|
| Correlação CNEFE × HRSL | 1,000 |
| MAPE | **3,1%** |
| US com divergência > 10% | 11 de 133 |
| US com divergência > 20% | **0** |

**Conclusão:** embora os fatores individuais divirjam (esperado — são métodos diferentes nos setores partilhados), o **erro agregado é pequeno** (~3%). A troca de peso não se justifica como método principal; o HRSL é mais útil como validação. Divergências extremas por US são limitadas (pior caso: US Tijuca −16,5%; US São Borja +18,2%).

### 8.2 Correção da renda (winsorização)

O agregado do IBGE apresenta **valores imputados extremos** em alguns setores (renda média implausível), que contaminavam a agregação. Correção implementada:

1. Winsorização no **nível do setor** (percentis 1 e 99), com teto adicional de R$ 100.000;
2. Recomposição da média ponderada por responsáveis (V06001) × fator de alocação;
3. Bandeira de qualidade (`flag_renda_suspeita`) para US cuja renda média exceda 2,5× a mediana ou cujo nº de setores válidos seja < 3.

**Resultado:**

| | Antes | Depois |
|---|---|---|
| US Nonoai | R$ 14.096.275 | **R$ 6.771** |
| US Mato Sampaio | R$ 10.684.589 | R$ 8.176 |
| CF Santa Marta | R$ 6.417.246 | R$ 8.044 |
| Mediana municipal | inflada | **R$ 2.658** |
| Correlação média × mediana | — | 0,964 |
| US com bandeira | 39 | **0** |

### 8.2.1 Variabilidade da renda (desvios, CV e percentis)

Para descrever a **variabilidade** da renda por território (fundamental para
interpretar a média), a v2 implementa medidas de dispersão corretas, que
revelaram um erro adicional na v1.

**Erro do `cv_renda` da v1.** O script antigo calculava:

```python
cv_renda = V06004.std() / V06004.mean()   # groupby US — sem pesos, sem V06005
```

Ou seja: desvio padrão **não ponderado** das médias setoriais dividido pela
média **não ponderada** — e, principalmente, **sem incluir a variância interna
dos setores (V06005)**, que o IBGE divulga no agregado e que é a maior fonte de
desigualdade. Resultado: CV sistematicamente **subestimado** (Vila Jardim: 62,7% →
114,9% no cálculo correto).

**Cálculo correto implementado (fórmula de variância total de estratos):**

```
peso_i        = V06001 (responsáveis) × fator_proporcao (CNEFE)
μ_US          = Σ(V06004_w × peso) ÷ Σpeso                              → média ponderada

Var_dentro    = Σ(V06005_w × peso) ÷ Σpeso    (variância interna dos setores, do IBGE)
Var_entre     = Σ[peso × (μ_setor − μ_US)²] ÷ Σpeso   (dispersão entre setores)
Var_total     = Var_dentro + Var_entre
DP_US         = √Var_total
CV_US         = DP_US ÷ μ_US × 100
```

Percentis ponderados (P10, P25, P75, P90) calculados por **quantil ponderado**
das rendas médias setoriais (pesos = responsáveis × fator).

**Exemplo — US Vila Jardim (46 setores):**

| Medida | v1 (antiga) | v2 (correta) |
|---|---|---|
| Renda média | R$ 470.339 (bug, sem dividir) | **R$ 9.824** (winsorizada) |
| Desvio padrão | — | **R$ 11.283** |
| CV | 62,7% ❌ (sem V06005, sem pesos) | **114,9%** ✅ |
| P10 | — | R$ 2.753 |
| P25 | — | R$ 5.481 |
| Mediana (aprox.) | R$ 7.367 | R$ 7.367 (vem da v1) |
| P75 | — | R$ 12.616 |
| P90 | — | R$ 19.239 |
| Razão P90/P10 | — | ~7,0× |

Decomposição da variância da Vila Jardim: Var_dentro ≈ R$ 101M (79%) +
Var_entre ≈ R$ 26M (21%) → a maior parte da desigualdade está **dentro** dos
setores, não entre eles — exatamente o que a v1 não enxergava.

**Exemplo de descrição pronta para texto científico:**

> O território apresenta renda média de R$ 9.824 (mediana R$ 7.367), com elevada
> desigualdade interna (DP = R$ 11.283; CV = 114,9%). Um responsável do P10 ganha
> R$ 2.753 enquanto o do P90 ganha R$ 19.239 (razão de ~7×). A assimetria moderada
> (média/mediana = 1,07) indica que o contraste vem de segmentos concentrados, não
> de cauda longa: as vilas do sul (P25 ≈ R$ 5.481) convivem com o núcleo de alta
> renda do norte (P75 ≈ R$ 12.616).

**Valores municipais (133 US):** o CV correto tem mediana de **107%** (mín. 58%,
máx. 421%) — todos os territórios de POA apresentam desigualdade alta. As US mais
desiguais: Farrapos (421%), Nonoai (343%), Santa Anita (327%). A Vila Jardim está
na mediana do ranking.

**Colunas na tabela v2:** `renda_dp`, `renda_cv` (%), `renda_p10`, `renda_p25`,
`renda_p75`, `renda_p90`, além de `renda_media_winsor`, `n_setores_renda_ok` e
`flag_renda_suspeita`. As colunas antigas `renda_media_ponderada` e `cv_renda`
**não devem ser usadas** (soma sem divisão e CV sem variância interna).

### 8.3 Contagem de endereços e estabelecimentos (CNEFE)

Foram agregados, por território de US, os dados de espécie e tipo de edificação do CNEFE:

| Espécie (CNEFE) | Total em POA |
|---|---|
| Domicílio particular | 686.846 |
| Domicílio coletivo | 833 |
| Estabelecimento de ensino | 1.194 |
| Estabelecimento de saúde | 1.592 |
| Estabelecimento religioso | 1.951 |
| Estabelecimento de outras finalidades | 61.068 |
| Edificação em construção/reforma | 8.627 |
| Estabelecimento agropecuário | 128 |

| Tipo de edificação (domicílios) | Total em POA |
|---|---|
| Casa | 311.160 |
| Casa de vila ou condomínio | 18.128 |
| **Apartamento** | **355.799** |
| Outros | 2.592 |

Este teste **revelou a limitação central do método**: 46,6% dos endereços residenciais de POA são apartamentos — e cada apartamento conta como **um** endereço no fator de alocação, independentemente de quantas unidades habitacionais existem no edifício. A coluna `pct_apartamentos` por US permite **identificar e ponderar essa limitação** nos territórios mais afetados (ex.: US Jardim Leopoldina = 91,6% de apartamentos).

**Nota:** a distribuição dos 757.512 endereços únicos por território foi praticamente total — 757.364 (99,98%) caem dentro de algum território de US; apenas 149 endereços (0,02%) ficaram fora.

---

## 9. Desafios técnicos e soluções

Esta seção documenta os obstáculos enfrentados na execução, para reprodutibilidade e para evitar retrabalho.

### 9.1 Desafios de acesso a dados

| # | Desafio | Solução |
|---|---|---|
| 1 | O portal do CNEFE do IBGE (`ibge.gov.br/...`) está protegido por Cloudflare e bloqueia acesso automatizado | Localização do caminho direto no FTP: `ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/Municipio/43_RS/4314902_PORTO_ALEGRE.zip` |
| 2 | As Notas Metodológicas da Grade 2022 não informam o esquema de particionamento dos arquivos | Os arquivos são organizados por **quadrantes** (`grade_id04`…`grade_id93`), não por UF. Foi necessário baixar candidatos e verificar *bounds* até localizar POA no **quadrante 14** |
| 3 | A grade HRSL do Brasil não vem recortada por município | Descoberta do tile correto (`bra_southwest`) por comparação de *bounds*; leitura **apenas da janela** de POA, pois o arquivo completo tem 18 GiB em memória |

### 9.2 Desafios de ambiente e bibliotecas

| # | Desafio | Solução |
|---|---|---|
| 4 | `pyarrow` 25 incompatível com `pandas` 3.0.5 (`ArrowKeyError: type extension already defined`) | Fixação de `pandas==2.2.3` e `pyarrow<20` |
| 5 | O kernel de execução é persistente: módulos antigos permanecem em memória após troca de versões | **Reset do kernel** antes de recarregar as bibliotecas atualizadas |
| 6 | `geobr` falhava ao gravar cache em parquet por conflito de engines | Instalação de `fastparquet` e ajuste das versões |
| 7 | `unzip` não disponível no ambiente | Extração via `zipfile` do Python |

### 9.3 Desafios de dados e geoinformação

| # | Desafio | Solução |
|---|---|---|
| 8 | Códigos de setor em formatos divergentes entre fontes (`"431490205000001.0"` no geobr vs. `"431490205000001"` na composição) | Normalização sistemática: `str.replace(r"\.0$", "")` em todas as chaves de junção |
| 9 | Erro `'index_right' cannot be a column name` em junções espaciais encadeadas | Remoção da coluna herdada antes do novo `sjoin` |
| 10 | Divergência de CRS entre malhas: EPSG:4674 (SIRGAS2000) vs. EPSG:4326 (WGS84) | Reprojeção explícita para o CRS comum antes de toda operação espacial |
| 11 | Setores de borda geram fatias de alocação irrelevantes (424 alocações com fator < 0,05) | Documentado; recomendação de limiar mínimo para análises por US |
| 12 | 8.239 hab em `Fora de Território Mapeado` (0,6%) | Documentado como limitação de cobertura do KMZ |

### 9.4 Desafios de correspondência de endereços textuais (Módulo 2)

| # | Desafio | Solução |
|---|---|---|
| 13 | O CNEFE grava o tipo do logradouro no campo `NOM_TIPO_SEGLOGR` e abreviações no texto livre dos pacientes ("AV." vs "AVENIDA") | Normalização com dicionário de tipos (`RUA`, `AV`, `PC`, `TR`, `AL`…) + remoção de acentos + caixa alta |
| 14 | Endereços informados pelo paciente podem ter tipo divergente do cadastro (ex.: "RUA João Pessoa" quando o cadastro é "AVENIDA João Pessoa") | Estratégia de **fallback em três níveis**: endereço exato → logradouro (mediana das coordenadas) → CEP (centro médio), com código de status por registro |
| 15 | CEP com e sem hífen (`90110-000` vs `90110000`) | Normalização por remoção de todos os caracteres não numéricos |
| 16 | Nem todo endereço existe no CNEFE (logradouros inexistentes, erros de digitação) | Código de status `nao_encontrado` — os registros não são descartados nem imputados silenciosamente; ficam disponíveis para revisão manual |

---

## 10. Arquitetura da solução

### 10.1 Estrutura de diretórios

```
pipeline_censo_aps/
├── README.md                       ← visão geral e instruções de uso
├── DOCUMENTACAO_METODOLOGICA.md    ← este documento
├── modulos/
│   ├── config.py                   ← caminhos, constantes, dicionários CNEFE
│   ├── 00_prepara_dados.py         ← CNEFE CSV → parquet; estrutura de pastas
│   ├── agrega_territorio.py        ← MÓDULO 1: indicadores por US
│   └── endereco_para_setor.py      ← MÓDULO 2: endereço → setor censitário
├── inputs/                         ← dados de entrada (KMZ, CSVs do usuário)
├── data/                           ← dados intermediários (CNEFE, malhas, banco)
└── outputs/                        ← resultados (planilhas, mapas, relatórios)
```

### 10.2 Módulo 1 — Indicadores do território de saúde

**Quando usar:** agora, sem dados individuais de pacientes.
**Entrada:** CNEFE + KMZ dos territórios + tabela base + banco por setor.
**Saída:** `tabelas_unidades_saude_v2.xlsx` (133 US × 80 colunas).

Fluxo:
1. Carrega CNEFE (com coordenadas convertidas e códigos normalizados);
2. Junção espacial ponto↔polígono (`sjoin` com predicado `within`);
3. Agregação por US: total de endereços, domicílios (particulares/coletivos), casas, vilas/condomínios, apartamentos, estabelecimentos (ensino, saúde, religiosos, outras finalidades), edificações em construção;
4. Cálculo de densidades (populacional e de endereços) e proporções derivadas;
5. Correção de renda por winsorização com média ponderada;
6. Incorporação dos resultados de validação tripla.

### 10.3 Módulo 2 — Endereço textual → setor censitário

**Quando usar:** depois da aprovação do Comitê de Ética, com os endereços dos pacientes.
**Entrada:** CSV com colunas `logradouro`, `numero` e, opcionalmente, `cep`.
**Saída:** CSV com o `CD_SETOR` de cada paciente + variáveis sociais do setor.

Fluxo:
1. **Normalização** — caixa alta, remoção de acentos, padronização do tipo de logradouro, limpeza de CEP;
2. **Geocodificação** — via CNEFE local (sem API externa, sem envio de dados a terceiros — relevante para conformidade com a LGPD), com fallback em três níveis;
3. **Atribuição do setor** — junção espacial da coordenada do paciente com a malha de setores 2022;
4. **Enriquecimento** — junção com o banco de agregados por setor (renda média/mediana, alfabetização, população, tipo de setor);
5. Saída com código de status de geocodificação por registro, para auditoria.

**Validação do módulo:** teste com 10 endereços reais de Porto Alegre → 6 resolvidos por endereço exato, 3 por logradouro (o número não existia no cadastro), 1 corretamente não encontrado (endereço fictício). As rendas atribuídas conferem com a geografia da cidade (Belém Novo ≈ R$ 1.959; Moinhos de Vento ≈ R$ 15.360).

### 10.4 Decisão de projeto: por que geocodificação local

Optou-se por geocodificar **contra o CNEFE local** em vez de APIs públicas (Google, Nominatim) por três razões:
1. **Privacidade/LGPD** — endereços de pacientes não saem do ambiente de análise;
2. **Precisão** — o CNEFE é o cadastro oficial do IBGE, com qualidade posicional medida (5,84 m);
3. **Reprodutibilidade** — sem dependência de serviços externos, cotas ou chaves de API.

---

## 11. Entregáveis

| Arquivo | Descrição |
|---|---|
| `outputs/tabelas_unidades_saude_v2.xlsx` | **133 US × 80 colunas** — indicadores sociodemográficos, densidades, contagens CNEFE, renda corrigida, validação tripla |
| `outputs/mapa_indicadores_cnefe.png` | Mapas coropléticos: densidade populacional, % apartamentos, estabelecimentos religiosos por território |
| `outputs/teste_setores.csv` | Resultado do teste do Módulo 2 (10 endereços) |
| `data/cnefe_poa.parquet` | CNEFE de POA otimizado (762.239 endereços, 34 campos) |
| `data/composicao_com_hrsl.csv` | 3.659 alocações setor×US com fatores CNEFE **e** HRSL |
| `data/validacao_tripla_por_us.csv` | População por US nas três fontes (CNEFE, Grade 2022, HRSL) + divergências |
| `data/poa_grade2022_cells.gpkg` | 12.904 células da Grade Estatística 2022 recortadas para POA |
| Scripts em `modulos/` | Pipeline reproduzível e modular |

### 11.1 Colunas novas na tabela v2 (em relação à v1)

**Contagens CNEFE:** `n_enderecos_total`, `n_domic_privados`, `n_domic_coletivos`, `n_est_ensino`, `n_est_saude`, `n_est_outras_final`, `n_construcao_reforma`, `n_est_religiosos`, `n_casas`, `n_vilas_condos`, `n_apartamentos`, `n_outras_edif`

**Densidades e proporções:** `densidade_hab_km2`, `densidade_enderecos_km2`, `pct_apartamentos`, `razao_apart_casa`, `pct_est_saude`, `pct_est_religiosos`

**Renda corrigida e variabilidade:** `renda_media_winsor`, `renda_dp`, `renda_cv`, `renda_p10`, `renda_p25`, `renda_p75`, `renda_p90`, `n_setores_renda_ok`, `flag_renda_suspeita`

**Validação:** `pop_grade2022`, `pop_hrsl`, `dif_pct`

---

## 12. Limitações e recomendações

### 12.1 Limitações a declarar em publicações

1. **Aproximação em setores partilhados (31,3% da população).** A distribuição proporcional ao número de endereços pressupõe densidade populacional uniforme dentro do setor quanto ao número de domicílios por endereço.
2. **Apartamentos contam como um endereço.** Em territórios com alta verticalização (46,6% dos endereços de POA são apartamentos), o fator de alocação subestima a população dos edifícios. Mitigação: coluna `pct_apartamentos` permite identificar e ponderar o risco.
3. **Cobertura territorial incompleta.** 8.239 habitantes (0,6%) residem em setores não abrangidos pelos polígonos (`Fora de Território Mapeado`).
4. **Ausência de idade declarada.** As faixas etárias somam 96,2–100% conforme a US.
5. **Falácia ecológica no Módulo 2.** As variáveis atribuídas ao paciente são as do **setor de residência**, não do indivíduo — o que deve constar explicitamente na metodologia do estudo clínico.
6. **Renda mediana é uma aproximação.** A mediana agregada por US resulta de média ponderada de medianas setoriais, e não de uma mediana verdadeira.
7. **Dados suprimidos por sigilo.** Setores pequenos têm valores "X" — tratados como ausentes (NaN), nunca imputados.
8. **Divergência maior em territórios pequenos.** US com menos de 3.000 habitantes apresentam MAPE de ~39% contra a grade de satélite.

### 12.2 Recomendações

**Para o artigo/tese:**
- Declarar o método como interpolação areal com ponderação dasimétrica por endereços CNEFE, citando IBGE (2025), IJSN e Salgado et al. (2025);
- Apresentar a validação tripla como análise de sensibilidade (Grade oficial + HRSL);
- Usar `renda_media_winsor` (nunca `renda_media_ponderada` da v1, que está com erro de agregação) e descrever a variabilidade com `renda_dp`, `renda_cv` e os percentis `renda_p10`–`renda_p90` (nunca `cv_renda` da v1, que ignora a variância interna V06005 e os pesos);
- Utilizar `densidade_hab_km2` e `pct_apartamentos` como covariáveis de contexto territorial.

**Melhorias potenciais (não implementadas):**
1. **Ponderação por domicílios** — em vez de contar endereços igualmente, ponderar pela densidade domiciliar do setor (nº de domicílios do Censo ÷ nº de endereços CNEFE), aproximando-se do método do IJSN;
2. **Tratamento de setores especiais** — hospitais, ILPIs, presídios e quartéis concentram população em um único endereço; alocá-los por ponto (ponto-em-polígono) em vez de proporcionalmente;
3. **Limiar de fatias mínimas** — agregar ao maior fator as alocações com `fator_proporcao` < 0,05 (424 casos), reduzindo ruído;
4. **Uso da Grade 2022 como peso principal** — agora que a grade oficial está disponível, é possível alocar a população diretamente por células de 200 m, o que captura a distribuição intra-setorial com resolução superior ao endereço;
5. **Modelo de densidade populacional** — estimar moradores por endereço a partir de regressão (como no artigo de referência: POP² = a + b·DOM), permitindo ponderar endereços por população esperada.

---

## 13. Referências

1. **IBGE** (2025). *Censo Demográfico 2022 — Grade Estatística: Notas metodológicas 01/2025*. Rio de Janeiro: IBGE. Disponível em: https://geoftp.ibge.gov.br/recortes_para_fins_estatisticos/grade_estatistica/censo_2022/

2. **IBGE** (2024). *Censo Demográfico 2022: Coordenadas Geográficas dos Endereços*. Nota metodológica n. 01. Rio de Janeiro: IBGE. https://biblioteca.ibge.gov.br/visualizacao/livros/liv102063.pdf

3. **IBGE** (2024). *Cadastro Nacional de Endereços para Fins Estatísticos — CNEFE*. https://www.ibge.gov.br/estatisticas/sociais/populacao/38734-cadastro-nacional-de-enderecos-para-fins-estatisticos.html

4. **SALGADO, G. P. L.; DAL'ASTA, A. P.; ADORNO, B. V.; AMARAL, S.** (2025). Avaliação das Grades Populacionais Globais para Representar a Distribuição da População Residente na Amazônia Brasileira: o Caso do Baixo Tocantins (PA). *Revista Brasileira de Cartografia*, v. 77. DOI: 10.14393/rbcv77n0a-75653

5. **IJSN — Instituto Jones dos Santos Neves** (s.d.). *Notas para compatibilização da população de setores censitários*. Vitória: IJSN. https://ijsn.es.gov.br/

6. **Tiecke, T. G. et al.** (2017). *Mapping the world population one building at a time*. arXiv. DOI: 10.48550/arXiv.1712.05839 (metodologia HRSL)

7. **Facebook Connectivity Lab & CIESIN** (2019). *Brazil: High Resolution Population Density Maps + Demographic Estimates*. Humanitarian Data Exchange. https://data.humdata.org/dataset/brazil-high-resolution-population-density-maps-demographic-estimates

8. **OPENSHAW, S.** (1984). *The modifiable areal unit problem*. Norwich: Geo Books.

---

## Anexo A — Reprodução

```bash
# Ambiente
uv venv .venv --python 3.13
uv pip install pandas==2.2.3 "pyarrow<20" geopandas rasterio shapely pyproj fiona \
    matplotlib openpyxl xlrd geobr fastparquet

# Preparar dados (CNEFE CSV → parquet, estrutura de pastas)
python modulos/00_prepara_dados.py

# Módulo 1 — indicadores por Unidade de Saúde
python modulos/agrega_territorio.py
# → outputs/tabelas_unidades_saude_v2.xlsx

# Módulo 2 — endereços de pacientes → setor censitário
python modulos/endereco_para_setor.py inputs/pacientes.csv -o outputs/pacientes_setores.csv
```

## Anexo B — Fontes de dados originais

| Dado | Fonte | Caminho |
|---|---|---|
| CNEFE POA | IBGE FTP | `ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/Arquivos_CNEFE/CSV/Municipio/43_RS/4314902_PORTO_ALEGRE.zip` |
| Grade Estatística 2022 (quadrante 14) | IBGE geoftp | `geoftp.ibge.gov.br/recortes_para_fins_estatisticos/grade_estatistica/censo_2022/grade_estatistica/grade_id14.zip` |
| Malha de setores censitários 2022 | geobr / IBGE | `geobr.read_census_tract(code_tract=4314902, year=2022)` |
| HRSL Brasil (tile SW) | HDX / Meta-CIESIN | `data.humdata.org → Brazil: High Resolution Population Density Maps` |
| Territórios da Atenção Primária | SMS/PMPA (KMZ) | `02_Docencia/dados_censo/mapas/Territórios da Atenção Primária.kmz` |
| Agregados por setor (Censo 2022) | IBGE / Base dos Dados | `ftp.ibge.gov.br/Censos/Censo_Demografico_2022/Agregados_por_Setores_Censitarios/` |
