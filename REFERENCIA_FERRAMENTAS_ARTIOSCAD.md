# Referência de comportamento de ferramentas — ArtiosCAD

Documento de apoio pra implementação (não é spec fechada, é referência). Resume, em texto próprio, como o ArtiosCAD implementa as ferramentas de criação/edição de geometria mais próximas do que o Autoline precisa, extraído da documentação oficial da Esko, pra comparar com o que já foi construído e orientar o que falta.

**Fontes consultadas** (resumidas aqui, não reproduzidas — ver os links pra texto completo):
- [Manual oficial ArtiosCAD 22.11 — capítulo Designer](https://docs.esko.com/docs/en-us/artioscad/22.11/userguide/home.html) (Creating geometry, Changing geometry) — fonte principal deste documento, tem tradução automática embutida pra outras línguas
- [ArtiosCAD module descriptions — DirectIndustry](https://pdf.directindustry.com/pdf/esko-graphics/artioscad-module-descriptions/19673-749214.html)
- [Manual ArtiosCAD EAC12 (ES-ES)](https://pdfcoffee.com/manual-artioscad-eac12-guiadelusuario-es-es-pdf-free.html)
- [Esko ArtiosCAD Guia do Administrador (PT)](https://archive.org/details/manualzilla-id-6086900)

Escopo: só as ferramentas já relevantes pro Autoline (ver conversa anterior de triagem CorelDRAW/ArtiosCAD) — não cobre 3D, manufatura/nesting, Bézier livre nem os tópicos descartados como fora de escopo.

---

## 1. Ferramenta de Seleção

**Como o ArtiosCAD faz:**
- Clicar dentro da caixa delimitadora do item = mover (arrastar). Clicar num handle da borda = redimensionar.
- **Ctrl + arrastar** = duplica o que está selecionado (solta o botão pra "largar" as cópias).
- **Shift + arrastar** = restringe o movimento a um eixo (só horizontal ou só vertical).
- Existem *17 modos* de seleção (alternados por botão na status bar), entre eles: seleção normal (grupo inteiro), ignorar agrupamento (seleciona só o membro individual), seleção só por retângulo totalmente-contido vs. que apenas toca, **laço poligonal** (clique pra cada vértice, fecha encostando no ponto inicial), filtro por tipo (só linhas, só texto, só cotas, só gráficos), e 3 modos de "nudge" (mover com teclado).
- Modo de seleção fica lembrado por documento durante a sessão.

**Status no Autoline / recomendação:**
- Já existe seleção, mover, redimensionar, duplicar (Ctrl+D) e copiar/colar. **Gap a conferir**: Ctrl segurado *durante o arrasto* pra duplicar (não só Ctrl+D com deslocamento fixo) e Shift pra restringir a um eixo durante o arrasto — são dois modificadores baratos e muito esperados por quem já usa CorelDRAW/Illustrator.
- Laço poligonal de seleção é um "nice to have" mais trabalhoso — não é prioridade imediata.

---

## 2. Criação de Retângulo

**Como o ArtiosCAD faz:** duas ferramentas na mesma flyout —
- **Horiz/Vert**: dois cliques definindo cantos opostos (o modo padrão, equivalente a um clique-arrasto).
- **From Center**: primeiro clique define o *centro*, segundo define o canto — útil quando o usuário já sabe onde o meio do elemento deve ficar.
- Também existe "Panel from Line" (expande uma linha existente num retângulo/painel) e "Offset Line" (linha paralela a uma distância) — mais ligado a criação de faca do que a mockup.

**Status no Autoline / recomendação:** já existe criação por clique-arrasto (canto a canto). Vale considerar um modificador (ex.: segurar Alt durante o arrasto) pra alternar pro modo "a partir do centro" — convenção comum em ferramentas de desenho, barata de adicionar.

---

## 3. Criação de Elipse/Círculo

**Como o ArtiosCAD faz:** Elipse e Círculo são ferramentas **distintas** (não uma variação da outra) — Elipse só aceita definir por deslocamento a partir de um ponto (não por offset de linha), Círculo tem uma variante "por diâmetro". A criação de arco em geral é resolvida por um sistema paramétrico (o ArtiosCAD só desenha quando sabe 3 de 5 valores possíveis: ângulo inicial, raio, offset X/Y, ângulo final) — mais sofisticado do que o Autoline precisa.

**Status no Autoline / recomendação:** confirma que ter uma ferramenta de Elipse dedicada (já implementada pela outra sessão) é o padrão correto — não precisa do sistema paramétrico completo do ArtiosCAD, clique-arrasto definindo a caixa delimitadora (como Retângulo) é suficiente e é o que Corel/Illustrator também fazem.

---

## 4. Endpoint Offset Mode (posicionamento numérico de precisão)

**Como o ArtiosCAD faz:** durante qualquer ferramenta de criação de geometria, segurar **Alt** e clicar num ponto/linha de referência ativa um modo onde os campos da status bar passam a aceitar um deslocamento **numérico** (X/Y ou distância/ângulo) a partir daquele ponto, em vez de exigir clique visual exato. Ctrl-clicar de novo troca a referência. **Esc sempre reinicia a ferramenta atual** (confirma o atalho permanente que já tínhamos mapeado do catálogo de shortcuts).

**Status no Autoline / recomendação:** não é urgente, mas é uma ideia de precisão barata pra o futuro — permitir digitar um deslocamento numérico exato a partir de um ponto/borda clicado, em vez de só arrastar visualmente. Fica como ideia pro backlog, não pros 3 itens pendentes atuais.

---

## 5. Construction Lines — **não confundir com "zonas seguras"**

**Como o ArtiosCAD faz:** são linhas de apoio ao desenho que **não são geometria final** — não saem no arquivo de manufatura, servem só de referência visual durante a construção da faca (dividir um ângulo, marcar um raio, etc.).

**Atenção pro Autoline:** isso é um conceito **diferente** do que propusemos como "zonas seguras/copy-free" (área de segurança de impressão perto de vinco/corte, que É visível/relevante no mockup final, não é só um apoio de desenho descartável). Vale não reaproveitar o nome "linha de construção" pra essa feature — são coisas distintas mesmo tendo inspiração na mesma família de conceito.

---

## 6. Extend / Measure

**Extend**: clicar numa linha/arco "estende" ela até o infinito (ou fecha um círculo, no caso do arco) só como referência visual de alinhamento — não é geometria de verdade, é descartável (ferramenta "Clear Extend" apaga todas de uma vez). Shift segurado mantém a ferramenta ativa pra estender vários de uma vez; Ctrl ignora agrupamento.

**Measure**: tem **2 modos** — *Medida* (mostra comprimento/ângulo/relação entre 2 pontos) e *Atributos* (mostra propriedades do objeto sob o cursor, tipo de linha, número de vincos, etc.) — trocado por **Tab** ou pelas setas esquerda/direita. Passar o mouse por cima mostra um popup rápido; **clicar fixa o popup na tela** (dá pra deixar várias medições abertas ao mesmo tempo, cada uma fechável individualmente). Também funciona como trena: clique num ponto, arraste até outro, solta pra fixar. Ctrl mede entre pixels.

**Status no Autoline / recomendação:** a outra sessão já implementou conta-gotas + ferramenta de medida. Vale conferir contra esse comportamento de referência: troca de modo por Tab, clique fixa o resultado na tela (em vez de só mostrar durante o hover), e se faz sentido function como trena (clique-arrasta) além de clique-em-2-pontos.

---

## 7. Mover (Move tool) — modelo de "pega e solta"

**Como o ArtiosCAD faz:** em vez de simplesmente arrastar, o Move tool pede primeiro um **ponto de pega** (a referência dentro da seleção) e depois um **ponto de solta** (onde essa referência deve ir) — dois cliques em sequência, não um arrasto contínuo. É um modelo mais preciso pra mover algo um valor exato em relação a um ponto específico do objeto (não o centro/canto genérico).

**Status no Autoline / recomendação:** o Autoline já cobre arrasto direto + setas do teclado (1/10mm) pra mover com precisão — cobre a maior parte do caso de uso sem precisar do modelo de 2 cliques. Não é prioridade.

---

## Resumo de gaps baratos identificados (não é uma lista de tarefas, é observação pra próxima rodada)

1. Ctrl durante o arrasto (não só Ctrl+D) pra duplicar.
2. Shift durante o arrasto pra restringir a um eixo.
3. Medida: confirmar troca de modo por Tab e "clique fixa o popup".
4. Não confundir "construction lines" (apoio de desenho, descartável) com "zonas seguras" (feature de segurança de impressão, ainda pendente) na hora de nomear/implementar.
