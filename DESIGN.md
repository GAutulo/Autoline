---
name: Autoline
description: Gerador de layout de caixas de papel (dieline + mockup) para produção gráfica
colors:
  primaria: "#8C6A3B"
  primaria-hover: "#6B4F2A"
  primaria-ativa: "#4F3A1E"
  primaria-clara: "#F0E2C8"
  primaria-pressionada: "#E6D2AC"
  texto: "#1E1A16"
  texto-secundario: "#8C6A3B"
  texto-terciario: "#A8916D"
  branco: "#F5F0E6"
  campo: "#FBF8F1"
  cartao: "#F5F0E6"
  fundo-janela: "#EAE1CC"
  borda: "#DBD6CD"
  borda-forte: "#CAC5BC"
  erro: "#C1432A"
  canvas-fundo: "rgb(250, 246, 237)"
  canvas-grade: "rgba(30, 26, 22, 0.055)"
  painel-flutuante: "rgba(250, 246, 237, 0.922)"
  primaria-escuro: "#C79A5D"
  primaria-hover-escuro: "#E7C68C"
  primaria-ativa-escuro: "#F0DDB0"
  primaria-clara-escuro: "#3A2F20"
  primaria-pressionada-escuro: "#2F2519"
  texto-escuro: "#EDE6D8"
  texto-secundario-escuro: "#B9AF9C"
  texto-terciario-escuro: "#8C8270"
  branco-escuro: "#1E1A16"
  campo-escuro: "#3A3025"
  cartao-escuro: "#26201A"
  fundo-janela-escuro: "#1E1A16"
  borda-escuro: "#3A3629"
  borda-forte-escuro: "#585349"
  erro-escuro: "#C1432A"
  canvas-fundo-escuro: "rgb(30, 26, 22)"
  canvas-grade-escuro: "rgba(237, 230, 216, 0.063)"
  painel-flutuante-escuro: "rgba(38, 32, 26, 0.922)"
typography:
  display:
    fontFamily: "Big Shoulders Stencil, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: "normal"
    letterSpacing: "1px"
  body:
    fontFamily: "IBM Plex Sans, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "normal"
    letterSpacing: "normal"
  label:
    fontFamily: "IBM Plex Mono, monospace"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: "normal"
    letterSpacing: "normal"
rounded:
  xs: "3px"
  sm: "4px"
  md: "6px"
  lg: "7px"
  xl: "10px"
  pill: "13px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
components:
  button-secondary:
    backgroundColor: "{colors.campo}"
    textColor: "{colors.texto}"
    rounded: "{rounded.lg}"
    padding: "7px 16px"
  button-secondary-hover:
    backgroundColor: "{colors.primaria-clara}"
    textColor: "{colors.primaria-ativa}"
  button-primary:
    backgroundColor: "{colors.primaria}"
    textColor: "{colors.branco}"
    rounded: "{rounded.lg}"
    padding: "7px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primaria-hover}"
    textColor: "{colors.branco}"
  input-field:
    backgroundColor: "{colors.campo}"
    textColor: "{colors.texto}"
    rounded: "{rounded.md}"
    padding: "4px 8px"
    height: "22px"
  card:
    backgroundColor: "{colors.cartao}"
    rounded: "{rounded.xl}"
    padding: "16px 12px 12px 12px"
  chip-cor:
    rounded: "{rounded.pill}"
    padding: "4px 12px"
---

# Design System: Autoline

## Overview

**Creative North Star: "A Chapa de Papelão"**

O sistema visual parte do material que o produto manipula: papelão kraft, tinta de impressão, o osso/carvão de uma embalagem antes de virar produto acabado. Não é uma paleta neutra genérica com um acento decorativo por cima — Carvão, Kraft, Tinta e Osso são nomes de material, não nomes de cor, e cada um carrega uma função no fluxo real de produção gráfica (kraft é a chapa, tinta é correção/atenção, carvão e osso são os neutros quentes que substituem o cinza puro de qualquer software CAD/SaaS padrão).

A personalidade é **densa mas organizada**: o Autoline assume que a tela vai ter bastante informação técnica de uma vez (painéis, medidas, propriedades de mockup) e resolve isso com hierarquia clara — cartão (`CARTAO`) vs janela (`FUNDO_JANELA`) vs campo interativo (`CAMPO`) sempre em tons distintos — em vez de fingir minimalismo escondendo densidade que o usuário precisa ver. Não há uma anti-referência visual negativa confirmada além do que o próprio código já impõe: chapado por completo (sem gradiente, sem sombra flutuante — profundidade vem só de borda e diferença de tom), um único acento de cor (`PRIMARIA`) reaproveitado em todo canto em vez de uma cor nova por elemento.

**Key Characteristics:**
- Paleta de material (Carvão/Kraft/Tinta/Osso), não paleta de marca genérica
- Um único acento de cor no app inteiro — sua raridade é o ponto
- Totalmente chapado: sem gradiente, sem sombra; profundidade só por borda + tom
- Tipografia de exibição usada em exatamente um lugar (a marca), nunca para hierarquia geral
- Tema claro e escuro são paletas completas e independentes, não um claro invertido matematicamente

## Colors

A paleta descreve papel e produção gráfica, não uma marca de tecnologia: kraft (cor da própria chapa de papelão) como acento, tinta como cor de atenção/erro, carvão e osso como os dois neutros quentes que substituem preto/branco/cinza puro.

### Primary
- **Kraft** (`{colors.primaria}` / `{colors.primaria-escuro}`): o único acento do app — usado em bordas de foco, ícone/rótulo da marca, indicadores marcados (checkbox, radio), e botões de ação primária (exportar). Kraft não é o mesmo hexadecimal nos dois temas por design: no tema claro é a versão escura (`#8C6A3B`) porque o kraft "puro" claro não tem contraste suficiente como texto sobre fundo claro; no tema escuro é a versão clara/pura (`#C79A5D`). Contraste WCAG foi calculado para cada combinação antes de fechar os valores.

### Neutral
- **Carvão** (`{colors.texto}` no tema claro, `{colors.branco-escuro}` no escuro): o neutro mais escuro — texto principal no tema claro, fundo de janela e superfície mais profunda no tema escuro.
- **Osso** (`{colors.branco}` / `{colors.texto-escuro}`): o neutro mais claro/quente — substitui o branco puro; cartões e campo de texto no tema claro, texto principal no tema escuro.
- **Campo** (`{colors.campo}` / `{colors.campo-escuro}`): fundo reservado só para elementos interativos (campo de texto, combobox). Regra deliberada: no tema claro é *mais claro* que o cartão; no tema escuro é *mais claro* que o cartão também (nunca mais escuro) — mantém o mesmo princípio de "isto é uma superfície interativa" nos dois temas.
- **Borda / Borda Forte** (`{colors.borda}`, `{colors.borda-forte}` + variantes escuras): separação de superfícies inteiramente por borda, nunca por sombra.

### Named Rules
**The One Accent Rule.** `PRIMARIA` é a única cor de destaque em todo o aplicativo — inclusive nas telas de exportação/CorelDRAW. Nenhum elemento novo introduz uma cor de acento própria; tudo que precisa se destacar usa Kraft.

**The Production Truth Rule.** Os arquivos exportados (SVG/PDF/JPG/CorelDRAW) nunca herdam a paleta do app — são sempre preto sobre branco, porque isso é convenção da gráfica de produção, não preferência estética. O tema (claro/escuro) é só para a interface, nunca para o output.

**The Ink Stays Fixed Rule.** `ERRO` (tinta, `#C1432A`) é o único token de cor que não muda entre os temas — correção/atenção precisa ser reconhecível independente do tema ativo.

## Typography

**Display Font:** Big Shoulders Stencil (com fallback sans-serif)
**Body Font:** IBM Plex Sans (com fallback sans-serif)
**Label/Mono Font:** IBM Plex Mono (com fallback monospace)

**Character:** Um stencil condensado e industrial reservado só para a marca, contra um corpo humanista neutro (IBM Plex Sans) que faz o trabalho pesado de telas densas — a mesma dualidade "chão de fábrica gráfico" vs. "ferramenta de precisão" que aparece na paleta.

### Hierarchy
- **Display** (700, 20px, letter-spacing 1px): só a marca (`QLabel#rotuloMarca` na barra de ferramentas). Nunca usado para títulos de seção ou qualquer hierarquia funcional — usar a fonte de exibição em outro lugar dilui a marca.
- **Body** (400, 13px): todo texto de interface — rótulos, campos, botões, menus.
- **Título de cartão** (600, 13px, herdado do body): título de `QGroupBox`, apenas peso mais forte, mesma família.
- **Label/Mono** (500, 13px): leituras técnicas — zoom, cota de medida, DPI (`QLabel#rotuloTecnico`) — a família muda porque números tabulares/técnicos precisam de largura fixa, não porque é uma hierarquia de importância.

### Named Rules
**The Brand-Only Display Rule.** A fonte de exibição (Big Shoulders Stencil) aparece em exatamente um seletor do sistema inteiro (`QLabel#rotuloMarca`). Se aparecer em um segundo lugar, não é mais assinatura — é decoração.

## Layout

Layout de duas colunas fixas (`painelEsquerdo` / `painelDireito`, ambos no tom `FUNDO_JANELA`) ladeando um canvas central, com abas (`QTabBar`) separando os fluxos Dieline e Layout. Painéis flutuantes/docáveis (propriedades do mockup) usam `QScrollArea` com fundo transparente para herdar o tema em vez do chrome nativo cinza do Qt. Densidade de espaçamento é média-alta de propósito (ver `## Overview`): cartões com padding 16/12/12/12px, campos com padding 4px/8px, mas uma exceção documentada existe (`grupoMedidasGeradas`, padding reduzido 6px/8px) para tabelas densas de números onde o padding padrão desperdiçaria altura útil sem ganho de legibilidade.

## Elevation & Depth

Sistema inteiramente chapado — nenhum `box-shadow`/sombra em lugar nenhum do QSS. Profundidade é comunicada só por diferença de tom entre camadas (janela → cartão → campo, cada um um tom distinto) e por borda (`BORDA` para separação leve, `BORDA_FORTE` para campos que precisam ler como "clicável/editável").

### Named Rules
**The Flat-By-Default Rule.** Nenhuma superfície ganha sombra em nenhum estado, nem hover, nem foco. Estado muda cor de fundo/borda, nunca eleva o elemento.

## Shapes

Escala de raio consistente por categoria de elemento, nunca arbitrária por widget: `3px` para indicadores pequenos (checkbox), `4px` para elementos utilitários (tooltip, item de menu), `6px` para campos de entrada, `7px` para botões e abas, `10px` para cartões (`QGroupBox`), e uma exceção deliberada de `13px` (quase pílula) só para o chip de cor da legenda de tinta — a única forma verdadeiramente arredondada do sistema, reservada para representar uma amostra de cor física, não um botão comum.

## Components

### Buttons
- **Shape:** raio 7px (`{rounded.lg}`)
- **Secundário (padrão):** fundo `{colors.campo}`, borda `{colors.borda}`, peso 600 — é o padrão de qualquer `QPushButton` sem marcação extra; a maioria dos botões do app é secundária.
- **Primário:** fundo `{colors.primaria}`, texto `{colors.branco}` — reservado para ação primária (ex.: exportação na barra de ferramentas); exige `setProperty("primario", True)` explícito antes do widget ser mostrado.
- **Hover / Pressed:** hover clareia para `{colors.primaria-clara}` (secundário) ou `{colors.primaria-hover}` (primário); pressed aprofunda para `{colors.primaria-pressionada}` / `{colors.primaria-ativa}`. Sem transição de sombra ou elevação, só troca de cor.
- **Flat (`QPushButton:flat`):** sem borda nem fundo em repouso, usado para ações terciárias dentro de linhas densas.

### Chips (chip de cor)
- **Style:** raio 13px, cor de fundo/texto vem da própria tinta representada (não é um token do sistema) — só o raio e o peso de fonte (600) são do design system.

### Cards / Containers
- **Corner Style:** 10px
- **Background:** `{colors.cartao}` sobre `{colors.fundo-janela}`
- **Shadow Strategy:** nenhuma (ver Elevation & Depth) — separação só por tom + borda 1px
- **Internal Padding:** 16px 12px 12px 12px (exceção: `grupoMedidasGeradas` em 6px 8px)

### Inputs / Fields
- **Style:** fundo `{colors.campo}` (sempre mais claro que o cartão ao redor, nos dois temas), borda 1.5px `{colors.borda-forte}`, raio 6px
- **Focus:** borda muda de cor para `{colors.primaria}`, mantendo a mesma espessura — sem glow nem sombra
- **Disabled:** fundo cai para `{colors.fundo-janela}`, texto para `{colors.texto-terciario}`

### Navigation (abas Dieline/Layout)
- **Style:** aba inativa transparente com texto `{colors.texto-secundario}`; aba ativa ganha fundo `{colors.cartao}` e borda mais forte; hover em aba inativa só muda a cor do texto para `{colors.primaria}`, sem fundo.

### Dock de Propriedades do Mockup (componente assinatura)
Painel lateral docável e rolável usado para editar qualquer elemento de mockup selecionado — é a tela mais densa do sistema (campos de geometria, alinhamento a painel, cor de tinta, propriedades específicas por tipo de elemento) e por isso a que mais se apoia nas regras de Layout/Elevation acima para não virar ruído visual.

## Do's and Don'ts

### Do:
- **Do** reutilizar `{colors.primaria}` para qualquer novo destaque — nunca introduzir uma segunda cor de acento.
- **Do** manter toda superfície nova chapada (sem sombra); comunicar profundidade só com tom de fundo + borda.
- **Do** manter a fonte de exibição (Big Shoulders Stencil) restrita à marca; qualquer título novo usa o corpo (IBM Plex Sans) em peso 600-700.
- **Do** garantir que `CAMPO` seja sempre mais claro que o `CARTAO` ao redor, nos dois temas, para qualquer elemento interativo novo.
- **Do** manter arquivos exportados (SVG/PDF/JPG/CorelDRAW) em preto sobre branco, independente do tema ativo do app.

### Don't:
- **Don't** adicionar `box-shadow` ou qualquer efeito de elevação — quebra a regra Flat-By-Default.
- **Don't** usar a mesma cor de acento em ambos os temas — o par claro/escuro do Kraft existe porque o contraste WCAG exige valores diferentes; copiar o hex de um tema para o outro quebra a legibilidade.
- **Don't** introduzir gradiente em nenhum componente — o sistema é inteiramente chapado, de propósito, como anti-referência a SaaS genérico.
- **Don't** usar raio de canto fora da escala documentada (3/4/6/7/10/13px) sem justificar por que o elemento é excepcional (como o chip de cor).
