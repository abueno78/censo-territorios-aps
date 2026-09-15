# Território em Mapa — Aplicação Web + Pesquisa sobre Conhecimento do Território pelas Equipes de Saúde

**Status:** Proposta / visão de produto e pesquisa (a implementar)
**Data:** Setembro 2026
**Autor:** André Bueno
**Projeto-mãe:** `pipeline_censo_aps` (este repositório)

> Este documento descreve uma ideia futura, embrionária, que combina: (1) um **produto
> de software** (aplicação web para desenho de territórios e geração automática de
> relatórios sociodemográficos) e (2) uma **pesquisa científica** sobre o conhecimento
> que as equipes de saúde têm do território onde trabalham. O objetivo deste arquivo é
> registrar o pensamento, os requisitos, a arquitetura proposta e o desenho de pesquisa,
> servindo de ponto de partida para implementação e para o projeto de pesquisa.

---

## 1. A ideia em uma frase

> Uma aplicação web onde qualquer Unidade de Saúde (US) do Brasil **desenha no mapa o
> seu território de atuação** (um polígono) e, em segundos, recebe um **relatório
> sociodemográfico completo** do território — o mesmo tipo de análise desenvolvida neste
> repositório para Porto Alegre, escalada para o Brasil inteiro.

E, em paralelo:

> Uma **pesquisa de campo** com profissionais de saúde (com ênfase em Agentes
> Comunitários de Saúde — ACS) para investigar **se eles conhecem de fato o território
> onde trabalham** — testando a hipótese de que o conhecimento territorial é
> sistematicamente inferior ao esperado, mesmo entre profissionais experientes.

---

## 2. Motivação e contexto

### 2.1 Por que o produto

- Políticas públicas de Atenção Primária à Saúde (APS) no Brasil são **territorializadas**:
  cada equipe tem uma área de abrangência e um cadastro populacional.
- Porém, unidades de saúde em municípios de médio/grande porte **nem sempre têm
  formalizado o polígono do próprio território** — em muitos casos o limite é descrito
  por ruas/nomes, ou não existe em formato georreferenciado.
- Este projeto já demonstrou (para POA) que é possível extrair, automaticamente, um
  perfil sociodemográfico completo de **qualquer polígono desenhado**, cruzando:
  - Censo Demográfico 2022 (setores censitários + agregados);
  - CNEFE (endereços e características de edificações);
  - Grades populacionais (Grade Estatística IBGE 2022, HRSL) como validação;
  - Malha de setores censitários para atribuição de setores ao polígono.
- O produto generaliza exatamente este pipeline para todo o país: **desenhou o
  território, recebeu o relatório**.

### 2.2 Por que a pesquisa

- O pesquisador (autor) **conhece pessoalmente** as unidades de saúde e os
  profissionais que nelas trabalham — acesso privilegiado ao campo.
- Observação empírica preliminar: mesmo profissionais com anos de serviço — inclusive
  ACS, cujo papel central é o vínculo com o território — têm dificuldade de responder
  perguntas básicas sobre as características sociodemográficas da área: renda média,
  escolaridade, estrutura etária, densidade, número de domicílios, etc.
- **Hipótese central (H1):** o conhecimento do território pelas equipes de saúde
  (médicos, enfermeiros, técnicos e ACS) é baixo e não se correlaciona com o tempo de
  atuação na unidade.
  - **H1a:** ACS não diferem significativamente dos demais profissionais no
    conhecimento de indicadores sociodemográficos do território (apesar de ser função
    presumida do cargo).
  - **H1b:** o conhecimento tácito/qualitativo (nome de comunidades, equipamentos,
    áreas de risco) é maior que o conhecimento **quantitativo** (indicadores,
    números), sugerindo déficit específico de dado estruturado.

---

## 3. A aplicação web — requisitos de produto

### 3.1 Público-alvo

- Equipes da APS: gerentes de unidade, enfermeiros, médicos, ACS.
- Gestores municipais (planejamento territorial, dimensionamento de equipes).
- Pesquisadores em saúde coletiva e geografia da saúde.

### 3.2 Fluxo do usuário (MVP)

1. **Login** (nível municipal: gestor cadastra unidades e usuários).
2. **Mapa**: usuário navega pelo mapa do seu município com camadas (setores
   censitários, malha urbana, unidades de saúde vizinhas, satélite).
3. **Desenho do território**: ferramenta de desenho de polígonos (à mão livre,
   por retângulo, ou **sugestão automática** a partir de um ponto/lote de endereços).
4. **Validação**: o sistema mostra o que foi incluído (setores cortados, área total,
   população estimada preliminar) e permite ajustar.
5. **Geração do relatório** (PDF/HTML): perfil sociodemográfico completo (Seção 4).
6. **Salvar/histórico**: territórios salvos por unidade, com versões para
   acompanhamento de mudanças ao longo do tempo.

### 3.3 Funcionalidades-chave (backlog)

| Prioridade | Funcionalidade | Descrição |
|---|---|---|
| P0 | Desenho de polígono | Draw/edit/delete de polígonos no mapa (MapLibre/Leaflet) |
| P0 | Relatório sociodemográfico | Geração automática (estrutura da Seção 4) |
| P0 | Camada de setores censitários | Visualização da malha 2022 (IBGE) |
| P1 | Alinhamento a setores | Ajuste do polígono desenhado aos limites de setores ("snap") |
| P1 | Sugestão de território | A partir de endereços/geocódigos da equipe (auto-built área) |
| P1 | Comparação temporal | Mesmo território em 2022 vs. 2010 (Censo 2010) |
| P2 | Múltiplos municípios | Escala nacional |
| P2 | Modo pesquisa | Integração com o questionário da Seção 5 |
| P3 | Exportação | GeoJSON/Shapefile do território + dados |

---

## 4. O relatório sociodemográfico gerado

Mesma lógica validada no `pipeline_censo_aps` (ver `DOCUMENTACAO_METODOLOGICA.md`),
atribuindo setores ao polígono e agregando por ponderação CNEFE.

### 4.1 Conteúdo do relatório

| Bloco | Indicadores |
|---|---|
| **População** | População total (Censo 2022), população por setor, densidade (hab/km²), comparação com Grade IBGE 2022 |
| **Estrutura etária e sexo** | Pirâmide etária (11 faixas), % M/F |
| **Cor/raça** | % Branca, Preta, Parda, Amarela, Indígena |
| **Escolaridade** | Taxa de alfabetização geral/M/F, nº de analfabetos |
| **Renda** | Renda média (winsorizada), mediana, CV, razão média/mediana, nº de responsáveis |
| **Domicílios e edificações (CNEFE)** | Total de endereços, domicílios particulares/coletivos, casas, apartamentos, % apartamentos |
| **Equipamentos urbanos (CNEFE)** | Estabelecimentos por espécie: saúde, ensino, religioso, outras finalidades; construção/reforma |
| **Território** | Área km², % de setores por tipo (favela, hospital/ILPI, prisão, quilombola), % do território em área de risco/aglomerado subnormal |
| **Notas metodológicas** | Fontes, limitações (falácia ecológica, aproximação CNEFE), referências, validade temporal |

### 4.2 Bloco "sugestões de atenção" (valor percebido para a equipe)

O relatório inclui sinais úteis para a prática, gerados automaticamente:
- Regiões do território com renda média muito abaixo da mediana municipal;
- Presença de equipamentos de saúde/ensino dentro do território;
- Áreas de alta densidade de apartamentos (risco de subnotificação de famílias);
- Setores de tipo especial (prisão, hospital — população não domiciliar significativa);
- Vazios de endereçamento (áreas do território sem endereços CNEFE → possíveis
  ocupações informais ou áreas rurais).

---

## 5. A pesquisa — desenho científico

### 5.1 Problema e pergunta

> Os profissionais de saúde conhecem o território em que atuam?

**Pergunta de pesquisa:** Qual o nível de conhecimento das características
sociodemográficas do território de atuação entre profissionais da Atenção Primária à
Saúde, e como esse conhecimento varia por categoria profissional, tempo de atuação e
frequência de trabalho no território?

### 5.2 Hipóteses

- **H1:** o conhecimento quantitativo do território é baixo na maioria dos
  profissionais, independentemente do tempo de atuação.
- **H1a:** os ACS não apresentam conhecimento quantitativo significativamente superior
  aos demais profissionais (contra a expectativa do papel do cargo).
- **H1b:** o conhecimento tácito (localização de comunidades, áreas de risco,
  equipamentos) é significativamente maior que o conhecimento quantitativo (números de
  população, renda, escolaridade), indicando lacuna de dados estruturados, não de
  vínculo com o território.
- **H2 (exploratória):** o conhecimento correlaciona-se positivamente com o uso de
  dados/instrumentos de territorialização na rotina (mapas, sistemas, cadastros).

### 5.3 Método proposto

| Dimensão | Proposta |
|---|---|
| **Desenho** | Estudo transversal, misto (quantitativo + qualitativo) |
| **Participantes** | Profissionais de APS de unidades selecionadas (médicos, enfermeiros, técnicos/auxiliares, ACS), amostragem por conveniência + intencional para ACS |
| **Instrumento quantitativo** | Questionário estruturado (online ou presencial), com: (a) perfil profissional; (b) estimativas numéricas do território (população, renda média, % analfabetismo, faixa etária predominante, nº de domicílios, aproximada de área); (c) questões de conhecimento tácito (localização de 3–5 pontos de referência no mapa mudo) |
| **Instrumento qualitativo** | Entrevistas semiestruturadas com subamostra (ex.: 5–8 profissionais, incluindo ACS) sobre como a equipe produz/usa conhecimento do território |
| **Mensuração** | Comparação das estimativas dos profissionais com os **valores de referência do relatório sociodemográfico** (o produto da Seção 4 gera a "gabarito" de cada território) — erro relativo por indicador |
| **Análise** | Estatística descritiva, testes de comparação (Mann-Whitney/Kruskal-Wallis por categoria), correlação (Spearman) com tempo de atuação e uso de ferramentas; análise temática para o qualitativo |
| **Ética** | Submissão ao Comitê de Ética em Pesquisa (CEP) — obrigatório, pela caracterização como pesquisa com seres humanos. Inclui TCLE, anonimização, devolutiva aos participantes |

### 5.4 O papel da aplicação na pesquisa

A aplicação é, ao mesmo tempo, **ferramenta de intervenção e de medida**:

1. **Medida:** o relatório gerado para cada território serve de valor de referência
   (gabarito) para comparar as respostas dos profissionais;
2. **Intervenção (pós-teste):** após responder, o profissional interage com o relatório
   do seu território — medindo-se o impacto imediato no conhecimento (design
   pré/pós simples);
3. **Fonte de dados de campo:** as respostas dos profissionais alimentam o sistema,
   permitindo mapear lacunas de conhecimento por território/categoria.

### 5.5 Riscos e cuidados

- **Cegamento:** profissionais não podem ver o relatório antes de responder.
- **Expectativa de papel:** informar que não é avaliação de desempenho individual.
- **Comparabilidade:** territórios de tamanhos muito diferentes geram erros relativos
  não comparáveis — estratificar por porte da unidade.
- **Validade ecológica:** o referencial (Censo 2022) tem defasagem temporal em relação à
  realidade percebida pela equipe; documentar isso na análise.

---

## 6. Arquitetura técnica proposta (infraestrutura / framework)

> Hipótese de projeto — a validar durante o desenvolvimento. A escolha prioriza:
> stack enxuta, custo baixo, código reutilizável do `pipeline_censo_aps` e
> escalabilidade nacional eventual.

### 6.1 Visão geral

```
┌──────────────────────────┐    ┌────────────────────────────────────────┐
│   FRONTEND (web)         │    │   BACKEND (API)                        │
│  • MapLibre GL JS        │    │  • Python + FastAPI                    │
│  • desenho de polígonos  │◄──►│  • recorte do polígono → setores       │
│  • relatório interativo  │    │  • agregação (reuso pipeline)          │
│  • Next.js/React         │    │  • geração PDF (ReportLab/WeasyPrint)  │
└──────────────────────────┘    └──────────┬─────────────────────────────┘
                                           │
                              ┌────────────▼─────────────────────────────┐
                              │   DADOS / BANCO                         │
                              │  • PostGIS (tabelas espaciais)          │
                              │    - malha setores 2022                 │
                              │    - CNEFE (endereços)                  │
                              │    - agregados Censo (por setor)        │
                              │    - grade estatística (células)        │
                              │  • Cache de relatórios (S3/arquivos)    │
                              └────────────────────────────────────────┘
```

### 6.2 Decisões de stack e justificativa

| Camada | Escolha | Justificativa |
|---|---|---|
| **Frontend map** | **MapLibre GL JS** (open source, fork do Mapbox GL) | Renderização vetorial performática, plugin de draw (`@maplibre/maplibre-gl-draw`), sem custo de licença (Mapbox é pago) |
| **Frontend app** | **Next.js (React) + TypeScript** | Ecossistema maduro, SSR, fácil deploy; ou alternativa enxuta: Vite + React |
| **Geocodificação** | CNEFE local + fallback | LGPD: endereços de pacientes não saem do sistema; sem dependência de API paga |
| **Backend** | **Python + FastAPI** | Reuso direto do código do `pipeline_censo_aps` (geopandas, rasterio); async; auto-docs |
| **Banco espacial** | **PostgreSQL + PostGIS** | Padrão de fato para SIG server-side; índices espaciais (GIST) para consultas ponto-em-polígono em escala nacional |
| **Armazenamento vetorial leve** | Parquet/GeoParquet + DuckDB (alternativa) | Para MVP com volume municipal é suficiente e mais simples |
| **Cálculo pesado** | Offload para workers (Celery/ARQ) | Relatórios de municípios grandes podem levar segundos; não bloquear a API |
| **PDF** | WeasyPrint (HTML→PDF) | Estilo controlado por CSS, fácil manter o layout do relatório |
| **Auth** | Keycloak (self-hosted) ou Supabase Auth | RBAC por papel (município/gerente/usuário) |
| **Deploy** | Docker Compose → posteriormente Kubernetes/Cloud Run | MVP: um host; escala: contêineres |
| **Observabilidade** | Sentry + Prometheus/Grafana | Erros e métricas |

### 6.3 Escala nacional — considerações

- **CNEFE Brasil:** ~111 milhões de registros de coordenadas (Censo 2022). Em PostGIS
  com índices GIST e particionamento por UF/município é viável; alternativamente,
  **cache por município** (baixar CNEFE do município do usuário no primeiro uso) evita
  manter o Brasil inteiro em linha.
- **Setores censitários:** ~452.000 nacional; com geometria leve (simplificada) e
  índice espacial, consultas são rápidas.
- **Grade Estatística:** células 200 m/1 km — Brasil inteiro é pesado; recorte por
  município + cache é a estratégia.
- **Custo:** a maior parte dos dados é pública e hospedável em storage de baixo custo;
  o MVP cabe em um VPS (~8–16 GB RAM) por município piloto.

### 6.4 Roadmap sugerido

| Fase | Escopo | Resultado |
|---|---|---|
| **Fase 0 (piloto POA)** | Refatorar `pipeline_censo_aps` em serviço; API com relatório de polígonos pré-cadastrados (132 territórios reais) | API funcional + relatórios idênticos aos validados |
| **Fase 1 (MVP web)** | Mapa + desenho de polígono + relatório + login | Piloto com 3–5 unidades reais de POA |
| **Fase 2 (pesquisa)** | Módulo de questionário integrado; base de respostas; comparação com gabarito | Coleta de dados da pesquisa |
| **Fase 3 (escala)** | Multi-município; cache nacional; observabilidade | Produto disponível para outras cidades |
| **Fase 4 (publicação)** | Análise dos dados; artigo(s) | Publicação em periódico de saúde coletiva |

---

## 7. Entregáveis previstos deste repositório

- [ ] `app/` — aplicação web (frontend + backend FastAPI)
- [ ] `api/` — endpoint `/territorio/relatorio` (polígono GeoJSON → relatório)
- [ ] `pesquisa/` — instrumento (questionário), base de respostas, scripts de análise
- [ ] `infra/` — Dockerfile, docker-compose, migrations (PostGIS)
- [ ] `docs/` — manual do usuário, metodologia da pesquisa, submissão CEP (modelo)

---

## 8. Perguntas em aberto (para decisões futuras)

1. **Município piloto:** POA é o natural (dados prontos). Há interesse de outra cidade?
2. **Formato do território desenhado:** o sistema deve exigir alinhamento aos setores
   censitários, ou aceitar qualquer polígono livre (com ponderação por fração de área)?
3. **Pesquisa e produto:** a pesquisa deve ser conduzida **antes** ou **depois** da
   entrega do relatório às equipes (contaminação do pré-teste)?
4. **Governança de dados:** os territórios desenhados pelas unidades devem ser públicos
   (transparência) ou privados (uso interno)?
5. **Financiamento/hospedagem:** há infraestrutura institucional (universidade,
   secretaria) ou o custo é do pesquisador?

---

## 9. Conclusão

Este projeto une três forças complementares: (1) um **produto de tecnologia pública** de
baixo custo que democratiza a territorialização da APS; (2) uma **pesquisa científica**
com acesso raro ao campo, que testa uma hipótese original sobre o conhecimento
territorial das equipes; e (3) a **reutilização de um pipeline já validado** (correlação
0,999 com a Grade Estatística do IBGE), garantindo credibilidade metodológica desde o
início. O próximo passo recomendado é a **Fase 0** — transformar o pipeline de POA em
serviço — e a submissão do projeto de pesquisa ao CEP.