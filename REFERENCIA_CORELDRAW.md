# Referência de interface e comportamento — CorelDRAW 2020

Documento de apoio (mesmo formato de `REFERENCIA_FERRAMENTAS_ARTIOSCAD.md`).
Meta: deixar as telas **Dieline** e **Layout** do Autoline o mais parecidas
possível com o CorelDRAW, pra quem já trabalha nele não precisar reaprender.

**Método (sala limpa):** tudo aqui vem do comportamento visível do programa
e da documentação pública (Guia do Usuário CorelDRAW 2020, lista oficial de
atalhos, referência da API VBA/COM que o `corel_bridge.py` já usa). **Nada de
código, binário, ícone ou arquivo de recurso do CorelDRAW é copiado** — a
licença proíbe engenharia reversa do programa. Os ícones do Autoline
continuam sendo desenhados por nós (`mockup_icones.py`).

---

## 1. Anatomia da janela

| Área | CorelDRAW | Autoline hoje | Gap |
|---|---|---|---|
| Barra padrão | Novo/Abrir/Salvar, Importar/Exportar, Desfazer/Refazer, nível de zoom, "Ajustar a" (snap), Opções | Abas + exportar SVG/PDF/JPG + Ajustar à tela | Faltam zoom em combo e menu "Ajustar a" |
| **Barra de propriedades** | Contextual. Sem seleção: tamanho da página, unidades, deslocamento (nudge) e distância de duplicação. Com objeto: **X, Y, L, A, escala %, travar proporção, ângulo, espelhar H/V**, contorno | Contextual por tipo de elemento (cor, fonte, espessura) | Faltam X/Y/L/A/ângulo/espelhar sempre no começo da barra, estado "sem seleção" |
| **Caixa de ferramentas** | Vertical, **borda esquerda**, com *flyouts* (triângulo no canto do botão agrupa ferramentas irmãs) | Horizontal no topo, sem flyouts | Posição e agrupamento |
| **Paleta de cores** | Vertical, **borda direita**. Clique esquerdo = preenchimento, **clique direito = contorno**, quadrado com X = nenhum | Combo de tinta na barra de propriedades | Falta a paleta |
| Réguas | Topo/esquerda, origem arrastável no canto, **arrastar da régua cria linha-guia** | Réguas sem guias | Guias arrastáveis |
| Área de trabalho | **Página branca com sombra** sobre "mesa" cinza-clara; objetos fora da página continuam visíveis | Canvas escuro | Página/mesa |
| **Barra de status** | Posição do cursor (X, Y), descrição do objeto ("Retângulo na Camada 1"), **amostras de preenchimento e contorno** do selecionado | Mensagem de texto | Coordenadas, descrição, amostras |
| Dockers | Painéis à direita: Propriedades, **Objetos** (camadas), **Alinhar e distribuir**, **Transformações** | Não há | Dockers |
| Navegador | Abas de página no rodapé esquerdo | — | Fora de escopo (1 faca = 1 página) |

## 2. Caixa de ferramentas (ordem do CorelDRAW e equivalente no Autoline)

| Grupo (flyout) | Ferramentas | Atalho | Autoline |
|---|---|---|---|
| Seleção | Seleção, Seleção à mão livre, Transformação livre | Espaço alterna | Selecionar, Laço, Mover de precisão |
| Forma | Forma (nós), Suavizar, Borrar… | F10 | **Falta** (editar nós) |
| Cortar | Cortar, Faca, Apagar segmento virtual, Borracha | — | Falta |
| Zoom | Zoom, Mão (pan) | Z / H | Só roda do mouse |
| Curva | Mão livre, Linha 2 pontos, **Bézier**, Caneta, Polilinha, Curva 3 pontos | F5 | Só Linha |
| Retângulo | Retângulo, Retângulo 3 pontos | F6 | Retângulo |
| Elipse | Elipse, Elipse 3 pontos | F7 | Elipse |
| Objeto | Polígono, Estrela, Espiral, Papel gráfico | Y / A / D | Polígono, Tabela |
| Texto | Texto, Tabela | F8 | Texto, Tabela |
| **Cota** | Paralela, Horizontal/vertical, Angular, Segmento, **Chamada 3 pontos** | — | Medida (temporária), Callout |
| Efeitos | Sombra, Contorno, Mistura, Transparência… | — | Acabamento (verniz etc.) |
| Conta-gotas | Cor, Atributos | E | Conta-gotas |
| Preenchimento | Preenchimento interativo, Preenchimento inteligente | G | — |

## 3. Comportamentos do mouse

- **Clique no objeto selecionado de novo** → alças viram **rotação/inclinação** (setas curvas nos cantos, centro de rotação arrastável).
- Arrastar alça de canto = escala proporcional; alça do meio = estica num eixo.
- **Shift** ao redimensionar = a partir do centro. **Ctrl** = restringe (proporção/ângulo em passos de 15°).
- Ao desenhar retângulo/elipse: **Ctrl = quadrado/círculo**, **Shift = a partir do centro**.
- **Clique direito durante o arrasto** (ou barra de espaço) = solta uma **cópia** e mantém o original.
- Arrastar com o botão direito e soltar → menu "Copiar aqui / Mover aqui / PowerClip dentro".
- Alt + clique = seleciona o objeto de baixo; Alt + arrasto = seleção por toque (não precisa conter inteiro).
- Duplo clique na ferramenta Seleção = seleciona tudo.

## 4. Atalhos de teclado (os que o usuário de CorelDRAW usa no automático)

| Ação | CorelDRAW | Autoline hoje |
|---|---|---|
| Desfazer / Refazer | Ctrl+Z / **Ctrl+Shift+Z** | igual (também Ctrl+Y) |
| Duplicar | Ctrl+D (com deslocamento) ou **+ do teclado numérico** (no lugar) | Ctrl+D |
| Agrupar / Desagrupar | Ctrl+G / **Ctrl+U** | Ctrl+G / Ctrl+Shift+G |
| Combinar / Separar | Ctrl+L / Ctrl+K | — |
| Converter em curvas | Ctrl+Q | — |
| Frente / Trás da página | **Shift+PgUp / Shift+PgDn** | Ctrl+Home / Ctrl+End |
| Um à frente / um atrás | **Ctrl+PgUp / Ctrl+PgDn** | — |
| Alinhar esquerda/direita/topo/base | **L / R / T / B** | só pelo painel |
| Centralizar horiz./vert. | **E / C** | — |
| Centralizar na página | **P** | — |
| Zoom em tudo / na página / na seleção | **F4 / Shift+F4 / Shift+F2** | "Ajustar à tela" |
| Ferramentas | F5 curva, F6 retângulo, F7 elipse, F8 texto, F10 forma, Y polígono, H mão, Z zoom | — |
| Deslocar (nudge) | Setas = 0,1 mm; **Shift = super (×2 mm)**; **Ctrl = micro** | setas 1 mm, Shift 10 mm (configurável) |
| Selecionar tudo | Ctrl+A | — |
| Transformações | Alt+F7 (posição), Alt+F8 (rotação), Alt+F9 (escala) | — |
| Ajustar a objetos / grade / guias | Alt+Z / Ctrl+Y / — | snap fixo |
| Exportar / Importar | Ctrl+E / Ctrl+I | menu |
| Opções | Ctrl+J | menu Configurações |

## 5. Dieline no CorelDRAW (como a gráfica trabalha hoje)

O fluxo atual manda a faca pro CorelDRAW (`corel_bridge.desenhar_layout`) e lá
o usuário: confere as medidas com a **ferramenta de cota paralela** (que fica
no desenho, ao contrário da Medida temporária do Autoline), separa corte e
vinco em **camadas**, aplica **contorno tracejado** no vinco e ajusta à mão
algum segmento com a ferramenta **Forma**. Pro Autoline ficar no lugar disso:
cotas persistentes, camadas Corte/Vinco/Arte, e edição de nós na faca.

---

## Plano de entrega (um PR por etapa) — situação

| # | Etapa | Situação |
|---|---|---|
| 1 | Atalhos e gestos (seção 3 e 4) | Feito — PR #2 |
| 2 | Área de trabalho: caixa de ferramentas à esquerda com flyouts, paleta à direita, barra de status, página branca sobre a mesa | Feito — PR #3 |
| 3 | Barra de propriedades: escala %, espelhar, estado sem seleção | Feito — PR #3 |
| 4 | "Ajustar a" (grade, guias, objetos, página), Alt+Z / Ctrl+Y | Feito — PR #4. Guias arrastadas da régua já existiam |
| 5 | Dockers: Objetos, Alinhar e distribuir, Transformações (com Cópias) | Feito — PR #5 |
| 6 | Cotas persistentes: paralela, horizontal, vertical | Feito — PR #6 |
| 7 | Curvas: Bézier, Mão livre, Forma (nós), Ctrl+Q / Ctrl+L / Ctrl+K | Feito — PR #7 |

### Ainda não coberto (próximas rodadas, por ordem de valor)

- **Guias dinâmicas** (linhas temporárias de alinhamento durante o arrasto).
- **Cota angular** e **cota de segmento**; chamada de 3 pontos (hoje o Callout cobre o uso).
- **Faca editável na tela Dieline** com a ferramenta Forma (hoje a faca vem só das medidas).
- **Soldar / Aparar / Interseção** (operações booleanas entre formas).
- **Clique duplo pra girar/inclinar** (no Autoline a rotação é pela alça redonda).
- **Zoom (Z) e Mão (H)** como ferramentas; hoje é roda do mouse e botão do meio.
- **Cores CMYK/Pantone** e separação: a paleta usa as tintas da legenda.
- O envio ao CorelDRAW de **curvas, cotas e espelho** foi escrito pela API documentada e testado
  com um objeto COM falso; falta conferir com o CorelDRAW aberto.
