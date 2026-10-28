---
name: Autoline
description: Gerador de layout de caixas de papel (dieline + mockup) para produção gráfica
colors:
  primaria: "#A55A0D"
  primaria-hover: "#8A4A0A"
  primaria-ativa: "#6E3C08"
  primaria-clara: "#F6E3CC"
  primaria-pressionada: "#EED2B0"
  selecao: "#EBBE86"
  texto: "#15181B"
  texto-secundario: "#4E555C"
  texto-terciario: "#6B7178"
  branco: "#FFFFFF"
  campo: "#FFFFFF"
  elevado: "#FFFFFF"
  cartao: "#F7F6F3"
  fundo-janela: "#ECEAE5"
  borda: "#DAD7D0"
  borda-forte: "#C4C0B8"
  erro: "#C1432A"
  painel-flutuante: "rgba(247, 246, 243, 0.922)"
  primaria-escuro: "#F0A04B"
  primaria-hover-escuro: "#FFC27D"
  primaria-ativa-escuro: "#FFD9A8"
  primaria-clara-escuro: "#3A2810"
  primaria-pressionada-escuro: "#2E200C"
  selecao-escuro: "#5A3F1A"
  texto-escuro: "#E7E9EB"
  texto-secundario-escuro: "#A3AAB2"
  texto-terciario-escuro: "#7D858E"
  branco-escuro: "#1A1206"
  campo-escuro: "#23282D"
  elevado-escuro: "#1D2125"
  cartao-escuro: "#16191C"
  fundo-janela-escuro: "#0F1113"
  borda-escuro: "#2A2F35"
  borda-forte-escuro: "#3A4048"
  erro-escuro: "#C1432A"
  painel-flutuante-escuro: "rgba(22, 25, 28, 0.922)"
  canvas-mesa: "#E3E3E1"
typography:
  display:
    fontFamily: "Archivo, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    fontStretch: "112%"
    lineHeight: "normal"
    letterSpacing: "-0.015em"
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
    backgroundColor: "{colors.elevado}"
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

**Creative North Star: "Grafite técnico, um acento âmbar"** (redesign — ver `REDESIGN.md`)

A interface é uma ferramenta de precisão em volta do trabalho, não o trabalho: superfícies grafite em degraus (janela → painel → elevado → campo) e um único acento âmbar, que é também a face kraft do logotipo. O conteúdo que vai para a gráfica — a mesa cinza, a página branca, a faca preta — não muda com o tema: o canvas é o mesmo nos dois.

A personalidade é **densa mas organizada**: o Autoline assume bastante informação técnica de uma vez (painéis, medidas, propriedades de mockup) e resolve isso com hierarquia clara de tons, não escondendo densidade. Chapado por completo (sem gradiente, sem sombra — profundidade só por borda e diferença de tom) e um único acento (`PRIMARIA`) reaproveitado em todo canto.

**Key Characteristics:**
- Grafite neutro + âmbar; o âmbar é a única cor de destaque
- Totalmente chapado: sem gradiente, sem sombra; profundidade só por borda + tom
- Fonte de exibição (Archivo) só na marca e nos títulos de tela
- Tema escuro é o principal; o claro é derivado da mesma estrutura (não um negativo matemático)
- O canvas e os arquivos exportados não herdam o tema

## Colors

### Primary
- **Âmbar** (`{colors.primaria-escuro}` / `{colors.primaria}`): o único acento — botão primário (Exportar), foco de campo, ferramenta ativa (fundo `{colors.primaria-clara-escuro}` com ícone âmbar), indicadores marcados. No tema claro é o âmbar escurecido da versão clara do logotipo, porque o âmbar puro não tem contraste como texto sobre fundo claro. Texto sobre o âmbar: `{colors.branco-escuro}` (`#1A1206`) no escuro, branco no claro. Contraste WCAG calculado para cada par.

### Neutral (escuro → claro)
- **Janela** `#0F1113` / `#ECEAE5` · **Painel** (`CARTAO`) `#16191C` / `#F7F6F3` · **Elevado** (botão secundário, menu) `#1D2125` / `#FFFFFF` · **Campo** `#23282D` / `#FFFFFF`.
- **Borda / Borda forte**: `#2A2F35` / `#3A4048` no escuro; separação inteiramente por borda, nunca por sombra.
- **Texto / Secundário / Terciário**: `#E7E9EB` / `#A3AAB2` / `#7D858E` no escuro.

### Canvas (fora do tema)
- Mesa `#E3E3E1`, página branca com malha, faca preta (corte contínuo, vinco tracejado) — iguais em qualquer tema.

### Named Rules
**The One Accent Rule.** `PRIMARIA` (âmbar) é a única cor de destaque em todo o aplicativo — inclusive nas telas de exportação/CorelDRAW. Nenhum elemento novo introduz uma cor de acento própria.

**The Production Truth Rule.** Os arquivos exportados (SVG/PDF/JPG/CorelDRAW) e a folha de aprovação nunca herdam a paleta do app — são sempre preto sobre branco (a folha mantém o próprio padrão), porque isso é convenção da gráfica de produção, não preferência estética.

**The Ink Stays Fixed Rule.** `ERRO` (tinta, `#C1432A`, também a zona segura) é o único token de cor que não muda entre os temas.

## Typography

**Display Font:** Archivo 700, semi-expandida (eixo de largura 112) — `ui/marca.py::fonte_marca`
**Body Font:** IBM Plex Sans 13 px
**Label/Mono Font:** IBM Plex Mono (números e medidas)

### Hierarchy
- **Display** (Archivo 700, semi-expandida): só a assinatura "autoline" e os títulos de tela (Início, Exportar). Nunca para títulos de seção ou hierarquia funcional.
- **Body** (Plex Sans 400, 13px): todo texto de interface — rótulos, campos, botões, menus. Seção: 600, 15px.
- **Título de cartão** (600, 13px): título de `QGroupBox`.
- **Label/Mono** (Plex Mono 500, 13px): leituras técnicas — zoom, cota, medidas, DPI (`QLabel#rotuloTecnico`).

### Named Rules
**The Brand-Only Display Rule.** A fonte de exibição aparece só na marca e nos títulos de tela. Em qualquer outro lugar, é decoração.

## Brand — logotipo "Dobra"

- **Símbolo** (viewBox 0 0 120 120, `ui/marca.py::SIMBOLO_SVG`): o A de duas faces de uma caixa dobrada — interna clara `#E7E9EB`, externa âmbar `#F0A04B` — com a travessa tracejada como um vinco.
- **Abaixo de 64 px**: travessa cheia (sem tracejado), `x1=44 x2=76`, espessura 9–12.
- **Versão clara** (impressos e tema claro): face esquerda `#15181B`, face direita `#B4630F`, travessa `#15181B`.
- **Assinatura**: símbolo + "autoline" em caixa baixa, Archivo 700 semi-expandida (`AssinaturaMarca`).
- **Ícone do app** (`assets/gerar_icone.py` → `icon.ico`): quadrado arredondado `#1D2125` com borda `#3A4048` e o símbolo; 16–256 px.

## Layout

A moldura (`ui/moldura.py`) tem duas partes:
- **Barra de título** de 48 px: símbolo, menus, nome do projeto (● âmbar se há alteração não salva), seletor central Dieline | Layout | 3D, desfazer/refazer e o botão primário Exportar.
- **Barra de status** embaixo: mensagem com reticências e a frase inteira na dica, posição do cursor, objeto, amostras de cor, Encaixe, Guias dinâmicas, tintas, CorelDRAW e zoom.

Abaixo da barra de título, cada tela tem a sua **linha de contexto** de 44 px:
- Dieline: barra Faca.
- Layout: tipo do objeto e opções principais, mais Organizar.
- 3D: os controles ficam na própria vista.

A área de trabalho:
- O painel esquerdo (tipo, medidas e trechos) aparece na Dieline e no 3D.
- O canvas fica ao centro, com a legenda de cores (chips) e as réguas.
- No Layout, o **inspetor** fica à direita, entre o desenho e a paleta de tintas.
- A tela de **Início** substitui a área de trabalho inteira.

Restrição de tamanho: tudo cabe numa tela de **1366 px**. Página escondida de pilha não conta na largura mínima, e a janela volta à largura de antes depois de uma troca de tela.

Densidade de espaçamento média-alta de propósito (ver `## Overview`):
- Cartões com padding 16/12/12/12 px.
- Campos com padding 4/8 px.
- Seções do inspetor com 16 px de margem e 18 px entre seções.
- Exceção documentada: `grupoMedidasGeradas` com padding 6/8 px, para tabelas densas de números.

## Elevation & Depth

Sistema inteiramente chapado — nenhum `box-shadow`/sombra em lugar nenhum do QSS. Profundidade é comunicada só por diferença de tom entre camadas (janela → cartão → campo, cada um um tom distinto) e por borda (`BORDA` para separação leve, `BORDA_FORTE` para campos que precisam ler como "clicável/editável").

### Named Rules
**The Flat-By-Default Rule.** Nenhuma superfície ganha sombra em nenhum estado, nem hover, nem foco. Estado muda cor de fundo/borda, nunca eleva o elemento.

## Shapes

Escala de raio consistente por categoria de elemento, nunca arbitrária por widget:
- `3px`: indicadores pequenos (checkbox, amostra de 12 px da legenda).
- `4px`: elementos utilitários (tooltip, item de menu).
- `5px`: botões discretos (botão flat em hover, botões da barra de status).
- `6px`: campos de entrada, abas, botões do inspetor e segmentados, painel flutuante do canvas.
- `7px`: botões e botões de barra de ferramentas.
- `8px`: contêineres (seletor Dieline | Layout | 3D, caixa de posição na face).
- `10px`: cartões (`QGroupBox`, cartões do Início).

As abas do inspetor não têm raio: só o sublinhado.

As formas de pílula (`11px` no chip da legenda, `13px` no chip de cor e `14px` nos chips de tinta do inspetor) ficam reservadas para o que representa uma **tinta física**, nunca um botão comum.

## Components

### Buttons
- **Shape:** raio 7px (`{rounded.lg}`)
- **Secundário (padrão):** fundo `{colors.elevado}`, borda `{colors.borda-forte}`, peso 600 — é o padrão de qualquer `QPushButton` sem marcação extra; a maioria dos botões do app é secundária.
- **Primário:** fundo `{colors.primaria}`, texto `{colors.branco}` — reservado para ação primária (ex.: exportação na barra de ferramentas); exige `setProperty("primario", True)` explícito antes do widget ser mostrado.
- **Hover / Pressed:** hover clareia para `{colors.primaria-clara}` (secundário) ou `{colors.primaria-hover}` (primário); pressed aprofunda para `{colors.primaria-pressionada}` / `{colors.primaria-ativa}`. Sem transição de sombra ou elevação, só troca de cor.
- **Flat (`QPushButton:flat`):** sem borda nem fundo em repouso, usado para ações terciárias dentro de linhas densas.

### Chips (tintas)
- **Legenda de cores** (acima do desenho, `chipLegenda`): fundo `{colors.elevado}`, borda `{colors.borda}`, raio 11px, amostra de 12 px da tinta e nome na cor do texto do tema. Antes o nome era escrito na cor da tinta, e "Preto" sumia no tema escuro.
- **Chip de tinta do inspetor** (`chipTinta`, raio 14px): amostra + nome; marcado ganha borda 2px `{colors.primaria}`. "+ Nova tinta" é o mesmo chip com borda tracejada.
- **Chip de cor do painel esquerdo** (`chipCor`, raio 13px): desmarcado, borda e nome na cor da tinta, clareada ou escurecida o mínimo para 4,5:1 sobre o cartão (`estilo.cor_legivel_sobre(..., minimo=4.5)`; o padrão da função é 3:1).

### Cards / Containers
- **Corner Style:** 10px
- **Background:** `{colors.cartao}` sobre `{colors.fundo-janela}`
- **Shadow Strategy:** nenhuma (ver Elevation & Depth) — separação só por tom + borda 1px
- **Internal Padding:** 16px 12px 12px 12px (exceção: `grupoMedidasGeradas` em 6px 8px)

### Inputs / Fields
- **Style:** fundo `{colors.campo}` (sempre mais claro que o cartão ao redor, nos dois temas), borda 1px `{colors.borda-forte}`, raio 6px
- **Focus:** borda muda de cor para `{colors.primaria}`, mantendo a mesma espessura — sem glow nem sombra
- **Disabled:** fundo cai para `{colors.fundo-janela}`, texto para `{colors.texto-terciario}`

### Navigation (seletor Dieline | Layout | 3D)
- **Style:** segmentado e centralizado na barra de título. A tela atual tem fundo `{colors.campo}` e texto `{colors.texto}`; nas outras, o hover só clareia o texto para `{colors.texto}`. O símbolo do logotipo leva ao Início.

### Inspetor (componente assinatura)
Dock à direita no Layout, com as abas **Propriedades | Objetos | Alinhar | ···**. Transformações e Simbologias aparecem quando são escolhidas no "···".
- **Abas:** sublinhado de 2 px `{colors.primaria}` na aba atual, sem caixa.
- **Seções:** título em caixa alta 11 px, peso 700, espaçamento 1 px e cor `{colors.texto-terciario}`.
- **Propriedades:** título do objeto e face, Geometria · mm em grade (X, Y, L, A, giro, travar proporção, espelhar), Alinhar ao painel, Tinta e as seções do tipo do objeto, que quebram linha (`LayoutFluxo`).
- **Botões de alinhar:** fundo `{colors.elevado}`. Quando não se aplicam (por exemplo, "Entre os selecionados" com um objeto), ficam sem fundo e com borda tracejada, e uma dica diz o que fazer.

É a tela mais densa do sistema e a que mais se apoia nas regras de Layout e Elevation acima.

### Tela de Início
- **Título:** "Nova caixa" em Archivo.
- **Medidas:** campos C × L × A e o botão primário Criar faca.
- **Cartões de estilo:** grade 4 × 2, com ícone ou sigla FEFCO em mono, título em negrito e detalhe que quebra a linha.
- **Variantes:** do estilo escolhido, em botões segmentados (`opcaoVariante`).
- **Recentes:** com miniatura, à direita.

## Do's and Don'ts

### Do:
- **Do** reutilizar `{colors.primaria}` para qualquer novo destaque — nunca introduzir uma segunda cor de acento.
- **Do** manter toda superfície nova chapada (sem sombra); comunicar profundidade só com tom de fundo + borda.
- **Do** manter a fonte de exibição (Archivo) restrita à marca e aos títulos de tela; qualquer título de seção usa o corpo (IBM Plex Sans) em peso 600-700.
- **Do** garantir que `CAMPO` seja sempre mais claro que o `CARTAO` ao redor, nos dois temas, para qualquer elemento interativo novo.
- **Do** manter arquivos exportados (SVG/PDF/JPG/CorelDRAW) em preto sobre branco, independente do tema ativo do app.

### Don't:
- **Don't** adicionar `box-shadow` ou qualquer efeito de elevação — quebra a regra Flat-By-Default.
- **Don't** usar a mesma cor de acento em ambos os temas — o par claro/escuro do âmbar existe porque o contraste WCAG exige valores diferentes; copiar o hex de um tema para o outro quebra a legibilidade.
- **Don't** introduzir gradiente em nenhum componente — o sistema é inteiramente chapado, de propósito, como anti-referência a SaaS genérico.
- **Don't** usar raio de canto fora da escala documentada (3/4/5/6/7/8/10 px, e pílula só para tinta) sem justificar por que o elemento é excepcional.
- **Don't** deixar uma tela alargar a janela além de 1366 px; o texto longo quebra a linha ou termina em "…" com a frase inteira na dica.
