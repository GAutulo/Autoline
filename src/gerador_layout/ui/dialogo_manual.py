"""Manual de uso — dentro do próprio app (menu Ajuda > Manual de uso...),
pra não depender de documentação externa que ninguém acha na hora que
precisa. Lista de tópicos à esquerda (agrupados por categoria, cabeçalho
de categoria não é clicável), conteúdo em HTML simples à direita — mesmo
padrão de qualquer painel de ajuda embutido (VSCode, navegador), sem
precisar de nenhuma dependência nova.

Conteúdo escrito uma vez aqui, não duplicado dos tooltips espalhados pela
paleta de ferramentas — os tooltips continuam sendo o "lembrete rápido"
(uma frase, aparece passando o mouse); este manual é o "explica direito"
(parágrafo, com o porquê e os atalhos/modificadores, pra quem quer
entender de verdade uma vez e não precisar mais)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QListWidget, QListWidgetItem, QTextBrowser

from .estilo import Cor

# ── Conteúdo ─────────────────────────────────────────────────────────
# (categoria, [(título, html), ...]) — a ordem aqui é a ordem que aparece
# na lista, léva a léva com o fluxo de uso real: telas -> ferramentas de
# seleção -> ferramentas de criação -> ferramentas de leitura -> recursos
# de apoio (encaixe/guias/desfazer) -> exportação.
_TOPICOS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Visão geral",
        [
            (
                "Dieline × Layout",
                """
                <p>O app tem 2 telas, alternadas pelas abas no topo da janela, sempre
                sobre o mesmo desenho:</p>
                <p><b>Dieline</b> — medidas, tipo de caixa, cores de impressão e a faca
                de corte/vinco calculada automaticamente. É aqui que a caixa nasce.</p>
                <p><b>Tipos de caixa</b> (passe o mouse na lista pra ver a explicação de
                cada um): maleta normal e transpassada, cada uma também em <b>meia
                caixa</b> — só Aba × L × C na impressora (ex.: 40 × 240 × 590), pra
                caixa grande feita em duas metades coladas depois —; os envoltórios
                (fechamento normal ou no meio, com ou sem corte); e o <b>envoltório
                capa (bandeja)</b>: A × C × A na impressora e A × L × A no riscador,
                fundo com 4 paredes e os cantos do envoltório, sem tampa. Em
                "Medidas geradas / ajustáveis" aparecem só os trechos que o tipo usa;
                um trecho em <b>0</b> volta pro valor automático.</p>
                <p><b>Layout</b> — o mesmo desenho da faca, agora como referência pra
                posicionar texto, formas, imagens, logotipo e símbolos de manuseio por
                cima (o "mockup").</p>
                <p>A disposição segue o CorelDRAW: a <b>caixa de ferramentas</b> fica
                na borda esquerda (botões com triângulo no canto agrupam ferramentas
                irmãs: segure o clique ou clique no triângulo pra escolher), a
                <b>barra de propriedades</b> logo abaixo do topo, a <b>paleta de
                cores</b> na borda direita (clique = preenchimento, botão direito =
                contorno, X = sem preenchimento; a tinta usada entra na legenda) e a
                <b>barra de status</b> embaixo mostra a posição do cursor em mm e o
                objeto selecionado com as amostras de preenchimento e contorno. A
                chapa aparece como uma página branca sobre a mesa cinza.</p>
                <p>Editar as medidas sempre volta pra tela de Dieline; os elementos de
                mockup que você já posicionou na tela de Layout continuam lá.</p>
                """,
            ),
            (
                "Editar a faca (tela Dieline)",
                """
                <p>A barra <b>Faca</b> no topo da tela Dieline faz o ajuste à mão que
                antes ia pro CorelDRAW. <b>Navegar</b> é o normal (arrastar move a
                visão). <b>Editar faca</b> (F10): clique numa linha pra selecionar;
                arraste a linha ou uma ponta — as linhas ligadas acompanham (pontas
                em comum e junções em "T"), então a faca não abre. <b>Alt</b> solta a
                ponta das vizinhas e <b>Shift</b> trava na horizontal/vertical. As
                pontas grudam nas outras pontas da faca.</p>
                <p><b>Nova linha de corte / de vinco</b>: arraste de um ponto a outro
                (Ctrl = 15°). Com uma linha selecionada, a caixa da barra muda o tipo
                (corte, vinco, meio corte, serra, dobra) e <b>Delete</b> remove.</p>
                <p><b>Precisão</b>: ao arrastar uma linha ou ponta, ela gruda nos nós
                parados (com o nome do ponto) e alinha na horizontal/vertical com
                eles, com uma guia tracejada até o nó com quem está alinhada. Ao lado
                do cursor aparece a medida: o deslocamento (Δx, Δy) ao mover a linha,
                o comprimento e o ângulo ao mover a ponta ou desenhar linha nova, e
                largura × altura no retângulo.</p>
                <p><b>Ferramentas de desenho</b> (como no ArtiosCAD). As linhas que
                elas criam são do tipo escolhido em <b>Linha nova</b>:</p>
                <ul>
                <li><b>Retângulo</b>: arraste de um canto ao oposto; nascem 4 linhas.</li>
                <li><b>Linha por medida</b>: clique o ponto inicial e digite
                comprimento e ângulo (0° = direita, 90° = cima), Enter. A próxima
                começa onde a anterior acabou, então dá pra desenhar a faca inteira
                só digitando. Esc para.</li>
                <li><b>Arco</b>: arraste de uma ponta à outra e solte; mova o mouse para
                curvar (o arco passa pelo cursor) e clique para confirmar.</li>
                <li><b>Paralela</b> (com uma linha selecionada): pede a distância e cria
                a cópia; negativo cria do outro lado. No arco, sai concêntrica.</li>
                <li><b>Aparar</b>: clique no trecho de uma reta entre dois cruzamentos
                (ou entre um cruzamento e a ponta) para cortá-lo fora.</li>
                <li><b>Estender</b>: clique perto da ponta de uma reta; ela cresce até a
                próxima linha no caminho.</li>
                <li><b>Arredondar canto</b>: clique no canto onde duas retas se
                encontram; o canto vira um arco com o <b>Raio</b> da barra.</li>
                </ul>
                <p>Arcos saem como curva de verdade no SVG/PDF e no CorelDRAW, e
                dobram certo no 3D.</p>
                <p>Com a faca editada, o tipo de caixa e as medidas ficam
                <b>travados</b> (mudar recalcularia a faca e perderia a edição). O
                botão "Descartar edições da faca" volta pra faca calculada — e
                Ctrl+Z desfaz cada passo. A faca editada é a que sai na exportação e
                no envio pro CorelDRAW.</p>
                <p>Na aba <b>3D</b>, a faca editada é dobrada como no ArtiosCAD: as
                regiões entre as linhas viram faces, os vincos viram dobradiças (90°)
                e a face com mais vincos fica parada como base. Furos e janelas
                vazadas aparecem vazados; cortes soltos que não fecham uma região não
                atrapalham.</p>
                <p>Se a faca veio de um tipo de caixa, ela <b>fecha igual à caixa
                calculada</b>: mesma face base, mesmo ângulo e mesma ordem em cada
                dobra. Mudar o formato ou o corte de uma aba não muda o fechamento; um
                vinco novo dobra 90°; um vinco que vira corte solta a aba, e ela some
                do 3D. Na faca em branco, vale a dobra automática.</p>
                <p><b>Navegar no 3D</b>: arrastar gira; botão do meio, botão direito
                ou Shift + arrastar move a vista; a roda aproxima no ponto onde está
                o mouse (além de 1,5× o zoom vira lupa, até 40×, pra chegar perto de uma
                borda sem a câmera entrar na caixa); duplo clique (ou "Vista inicial")
                volta. <b>Salvar imagem…</b> (na barra de baixo do 3D, ou Arquivo &gt;
                Exportar layout &gt; Imagem do 3D) grava a vista como está — pra mandar
                pro cliente: JPG com fundo branco ou PNG com fundo transparente, em alta
                resolução, recortada em volta da caixa e sem os textos de ajuda. <b>Girar sozinho</b>
                deixa a caixa montada girando devagar (desligado por padrão: girando, o
                3D fica redesenhando o tempo todo).</p>
                <p><b>Papelão</b> (na barra do 3D): escolhe a espessura. Em cima, os da <b>escala
                1:10</b> (a caixa desenhada reduzida, o normal aqui): onda B (0,3 mm, o
                padrão), dupla BC (0,7 mm) e micro-ondulado E (0,15 mm). Embaixo,
                separados, os de <b>tamanho real</b> (onda B 3 mm, C 4 mm, BC 7 mm, E,
                cartão) — só pra caixa desenhada em tamanho real; numa caixa em 1:10
                eles saem 10 vezes grossos demais. Ou digite o valor exato no campo ao lado ("Personalizado"). A última espessura fica guardada pra
                próxima vez que abrir o app. De perto, a borda cortada mostra as camadas do papelão: as capas
                e o miolo ondulado — uma ondulação na onda simples (E, B, C) e duas, com
                a capa do meio, na onda dupla BC. As ondas correm na vertical das
                paredes (direção da altura), então aparecem nos cortes atravessados a
                elas (pontas das abas, boca da caixa); nos cortes paralelos aparecem só
                as capas. Valor digitado: até 5 mm vira onda simples, acima, dupla. Com espessura, o lado de
                dentro de cada face fica pra dentro e a borda cortada do papelão
                aparece nas abas, fendas e na boca da caixa aberta (com a caixa
                fechada, as bordas ficam escondidas nas emendas). A faca de um estilo
                do catálogo já escolhe o papelão da espessura E usada nas contas.</p>
                <p>Nesse caso a aba 3D ganha as ferramentas do ArtiosCAD: <b>Ângulo da
                dobra</b> — clique num vinco pra alternar 90° → −90° → 0° (duplo
                clique conta dois), ou digite o valor exato no campo ao lado; e
                <b>Face base</b> — clique numa face pra ela ficar parada e as outras
                dobrarem em volta. Arrastar continua girando a vista em qualquer modo.
                Mudar a faca na Dieline zera os ângulos e a base.</p>
                <p><b>Faca em branco</b> (botão + da barra Faca, ou Arquivo &gt; Nova
                faca em branco): começa a faca do zero, sem modelo — desenhe os cortes
                e vincos e a aba 3D dobra o que você desenhar.</p>
                <p><b>Catálogo de estilos</b> (Ctrl+Shift+N, botão de lista da barra
                Faca ou Arquivo &gt; Nova faca a partir de estilo), como o do ArtiosCAD:
                escolha o estilo (FEFCO 0201 caixa normal com abas, FEFCO 0427 caixa
                e-commerce com tampa de encaixe, ou os seus), digite as medidas internas
                e a espessura do papelão olhando o diagrama cotado; medida que não serve
                aparece em vermelho e não deixa gerar. "Gerar faca" troca a faca (Ctrl+Z
                volta), a chapa fica do tamanho dela e o 3D monta a caixa com os ângulos
                e a ordem do estilo. Abrir o catálogo de novo traz o mesmo estilo e
                medidas, pra refazer com outros valores.</p>
                <p><b>Meus estilos</b>: Arquivo &gt; Salvar faca como estilo guarda a faca
                atual (medidas fixas) na pasta de estilos ("Abrir pasta dos meus
                estilos", no catálogo). Cada estilo é um arquivo .json: dá pra trocar os
                números por expressões com variáveis (C, L, A, E e as que você criar),
                com <code>+ - * / ( )</code> e min, max, sqrt, sin, cos, tan; validações
                ("A &lt; L"); e, em cada vinco, o ângulo e o momento em que dobra no
                3D.</p>
                """,
            ),
            (
                "Construtor de dieline",
                """
                <p><b>Construtor de dieline</b> (Ctrl+Shift+D, Arquivo, ou o botão de régua
                da barra Faca): monta uma faca nova no nosso padrão de trechos, sem escrever
                fórmula de linha. Comece de um modelo (em branco, maleta Aba | L | C | L | C,
                bandeja) ou de um seu.</p>
                <p>À esquerda: as <b>medidas</b> (C, L, A, E e as que você criar, com o valor
                padrão), os trechos da <b>impressora</b> (colunas, da esquerda pra direita) e
                do <b>riscador</b> (linhas, de cima pra baixo), cada um com a medida em
                fórmula (<code>L / 2</code>, <code>A + E</code>, <code>30</code>).</p>
                <p>No desenho: <b>clique numa divisa</b> entre duas peças pra escolher o tipo
                — vinco (com o ângulo da dobra e a ordem de montagem: ordem 1 dobra antes),
                corte, fenda (com a largura, ex.: <code>E + 2</code>), meio-corte, serrilha ou
                sem linha. "Aplicar nas iguais desta linha" muda de uma vez, por exemplo,
                todas as fendas entre L e C. <b>Clique numa peça</b> pra tirar (refugo) ou
                pôr, escolher a que fica parada no 3D e, nas pontas, o chanfro da aba de
                cola. O contorno e a borda com o refugo são sempre corte.</p>
                <p>Embaixo, o <b>resumo pra faca</b>: tamanho da chapa, quantos vincos,
                cortes e fendas, e os metros de vinco e de corte. <b>Usar na faca</b> põe na
                tela (o 3D já dobra com os ângulos e a ordem). <b>Salvar no catálogo</b>
                guarda como estilo: abre em qualquer medida pelo catálogo e volta pro
                construtor em "Começar de" pra editar.</p>
                """,
            ),
            (
                "Salvar o projeto (.autoline)",
                """
                <p><b>Arquivo &gt; Salvar projeto</b> (Ctrl+S) guarda o modelo inteiro num
                arquivo <b>.autoline</b>, onde você quiser — normalmente na pasta do
                cliente, junto do arquivo do Corel: tipo de caixa, medidas e trechos
                digitados, cores, a faca (calculada ou editada), todos os objetos do Layout
                e o papelão/ângulos do 3D. Os logotipos e imagens vão <b>dentro</b> do
                arquivo: dá pra mover, copiar ou mandar pra outro computador sem perder
                nada. Quando o cliente pedir alteração, é só abrir (Ctrl+O, ou Arquivo &gt;
                Abrir recente) e mudar.</p>
                <p>O título da janela mostra o nome do projeto, com um • quando tem
                alteração não salva; fechar ou abrir outro pergunta se quer salvar.
                <b>Recuperação:</b> a cada 2 minutos, se tem alteração não salva, o
                Autoline guarda uma cópia sozinho; se ele fechar sem querer (queda de
                energia, travou), ao abrir de novo pergunta se quer recuperar o trabalho
                de onde parou.</p>
                <p><b>Salvar e exportar tudo</b> (Ctrl+Shift+E, ou "↓ Salvar tudo" na barra):
                depois de uma alteração, um clique salva o projeto, a imagem do layout na
                pasta das imagens e a imagem do 3D na pasta do 3D, todos com o nome do
                projeto (ex.: "Gabinete Flora.jpg" e "Gabinete Flora 3D.jpg"). Pasta ainda
                não configurada é perguntada uma vez e fica guardada; se as imagens já
                existem, pergunta antes de substituir. Em
                Configurações &gt; Arquivos: a pasta das imagens do layout (padrão
                Z:\\Imagens) e a das imagens do 3D, que os botões de exportar já sugerem
                com o nome do projeto, e o botão que faz os .autoline abrirem com dois
                cliques.</p>
                """,
            ),
            (
                "Folha de aprovação (PDF)",
                """
                <p><b>Arquivo &gt; Folha de aprovação</b> (Ctrl+Shift+P, ou "↓ Aprovação"
                na barra): o PDF que vai pro cliente aprovar, no padrão da empresa — A4
                deitado, com o logotipo, Cliente, Medidas, Tipo de caixa, Referência,
                Código, Cores (as marcadas na legenda), o aviso de ATENÇÃO, o layout e o
                rodapé com as datas, "Aprovado por" em branco e "Desenvolvido por".</p>
                <p>Cliente, referência e código você digita (ficam guardados no projeto);
                medidas, tipo e cores vêm do projeto e dá pra corrigir na hora. A
                <b>primeira</b> folha leva a data de hoje em "Criado em"; gerar de novo
                noutro dia preenche "Modificado em" e a de criação continua (dá pra marcar
                ou desmarcar a modificação). Uma <b>2ª folha</b> traz a caixa montada em 3D
                (dá pra desligar na janela). O arquivo sai como "código referência.pdf" na
                pasta das aprovações e abre pra conferir.</p>
                """,
            ),
            (
                "Grupos, alinhar, copiar e cor",
                """
                <p><b>Grupos</b> (como no CorelDRAW): clicar num objeto agrupado pega o
                <b>grupo inteiro</b>; <b>Ctrl+clique</b> entra no grupo e pega só um
                objeto (o grupo se ajusta em volta se ele andar). Com o grupo
                selecionado, a barra tem <b>Desagrupar</b> (Ctrl+U) e <b>Desagrupar
                tudo</b>; com vários selecionados, <b>Agrupar</b> (Ctrl+G).</p>
                <p><b>Alinhar vários</b>: a referência é o <b>primeiro</b> que você
                selecionou — ele fica parado e os outros vão até ele (vale pros botões
                da barra, pro docker Alinhar e pras teclas L/R/T/B/C/E).</p>
                <p><b>Ctrl+C / Ctrl+V</b> cola no mesmo lugar e no mesmo giro do original
                (Ctrl+D é que duplica deslocado).</p>
                <p><b>Cor</b>: paleta da direita, a barra de propriedades, ou embaixo à
                direita (“Cor:” — clique na amostra de preenchimento ou contorno). O
                <b>conta-gotas</b> (ao lado): selecione o objeto que vai receber a cor e
                clique no objeto que tem a cor — ele pega a tinta desse objeto (num pixel
                de imagem, a tinta mais parecida da lista) e já marca na legenda.</p>
                """,
            ),
            (
                "Navegar no canvas",
                """
                <p><b>Zoom:</b> roda do mouse.</p>
                <p><b>Pan (mover a visão):</b> botão do meio do mouse segurado e
                arrastando, em qualquer ferramenta/tela; ou arrastar com o botão
                esquerdo numa área vazia quando a ferramenta Selecionar está ativa e
                você não está na tela de Layout com um elemento por baixo do clique.</p>
                <p><b>Ajustar à tela:</b> botão "Ajustar à tela" na barra de
                ferramentas, ou duplo-clique numa área vazia do canvas.</p>
                <p><b>Réguas:</b> topo e esquerda do canvas, mostram a posição em mm.
                Arrastar a partir de uma régua cria uma guia (ver "Réguas e guias").</p>
                """,
            ),
        ],
    ),
    (
        "Seleção",
        [
            (
                "Selecionar",
                """
                <p>A ferramenta padrão (ponteiro). Clicar um elemento seleciona ele;
                clicar e arrastar move; as alças ao redor de um elemento selecionado
                redimensionam (nos cantos/lados) ou giram (o círculo acima).</p>
                <p>Igual ao CorelDRAW: a alça de <b>canto</b> escala mantendo a
                proporção (segure <b>Alt</b> pra soltar a proporção), a alça do
                <b>meio</b> estica só um lado, e <b>Shift</b> redimensiona a partir do
                centro. Girando, <b>Ctrl</b> prende o ângulo em passos de 15°.</p>
                <p><b>Modificadores durante o arrasto:</b></p>
                <p>• <b>Clique direito</b> (sem soltar o esquerdo) — ao soltar, deixa
                uma cópia no destino e o original volta pro lugar.<br>
                • <b>Alt</b> ao começar a arrastar — duplica: deixa uma cópia parada no
                lugar de onde você começou, e o que se move é a cópia nova.<br>
                • <b>Ctrl</b> ou <b>Shift</b> — restringe o movimento a um eixo só
                (horizontal ou vertical, o que você estiver puxando mais); reavaliado
                o tempo todo, dá pra "corrigir" o eixo sem soltar o botão.</p>
                <p><b>Ctrl/Shift + clique</b> — adiciona/remove elementos individuais da
                seleção atual (seleção múltipla). <b>Arrastar numa área vazia</b> — abre
                uma seleção retangular, seleciona tudo que estiver dentro. Com 2 ou
                mais selecionados, a barra de propriedades mostra os botões de
                <b>alinhar entre si</b> (bordas, centros, topos, bases).</p>
                <p><b>Setas do teclado</b> — move o(s) elemento(s) selecionado(s) aos
                poucos (o passo é uma preferência, ver Configurações > Ferramentas);
                Shift + seta usa o passo maior.</p>
                <p><b>Esc</b> — sempre volta pro ponteiro, de qualquer ferramenta.</p>
                """,
            ),
            (
                "Laço de seleção",
                """
                <p>Seleciona por um contorno poligonal em vez de um retângulo — útil
                quando os elementos que você quer pegar não formam um retângulo limpo
                na tela.</p>
                <p>Clique uma vez pra cada vértice do laço; feche clicando perto do
                primeiro vértice de novo (precisa de pelo menos 3 vértices). Todo
                elemento cujo <i>centro</i> cair dentro do polígono é selecionado — não
                precisa estar 100% contido.</p>
                <p><b>Esc</b> cancela um laço em andamento sem mudar a seleção que já
                existia antes.</p>
                """,
            ),
            (
                "Mover de precisão",
                """
                <p>Desloca a seleção atual por uma distância exata, em vez de arrastar
                visualmente — útil quando você quer mover algo por um valor específico
                a partir de um ponto de referência, não "mais ou menos ali".</p>
                <p>Selecione primeiro (com a ferramenta Selecionar), depois troque pra
                esta ferramenta e dê <b>2 cliques em sequência</b>: o 1º marca o ponto
                de <i>pega</i> (a referência — não precisa ser em cima de um elemento,
                pode ser qualquer ponto da cena), o 2º marca o ponto de <i>solta</i>.
                Toda a seleção desloca pelo vetor entre os 2 pontos. A ferramenta fica
                pronta pra repetir com outro par de cliques.</p>
                """,
            ),
        ],
    ),
    (
        "Criar elementos",
        [
            (
                "Texto",
                """
                <p>Igual ao texto artístico do CorelDRAW: clique no desenho (o clique é
                o começo da linha) e digite direto — sem caixa de edição. <b>Enter</b>
                quebra linha; setas, Home/End, Backspace/Delete, <b>Shift+setas</b>
                (selecionar) e Ctrl+A/C/V/X funcionam. <b>Esc</b> ou clicar fora
                termina; texto que termina vazio some. A letra nasce com o mesmo
                tamanho na tela em qualquer zoom.</p>
                <p><b>Duplo clique</b> num texto (ou clicar nele com a ferramenta Texto)
                edita com o cursor onde você clicou. Redimensionar pelas alças estica o
                texto (canto = proporcional, lado = distorce), como no CorelDRAW.</p>
                <p>Na barra de propriedades: fonte (todas as instaladas), <b>tamanho em
                pontos</b>, negrito, <b>alinhamento das linhas</b> (esquerda, centro,
                direita — também sai assim no CorelDRAW) e tinta. A fonte de um texto novo vem de
                Configurações &gt; Ferramentas.</p>
                """,
            ),
            (
                "Retângulo / Elipse / Polígono",
                """
                <p>Clique e arraste pra desenhar, canto a canto (o clique inicial é um
                canto, solta no canto oposto).</p>
                <p><b>Shift</b> (ou Alt) <b>segurado durante o arrasto</b> — desenha a
                partir do CENTRO em vez de um canto: o ponto onde você clicou vira o
                meio da forma, que cresce simétrica dos 2 lados. <b>Ctrl</b> força
                lados iguais (quadrado, círculo). Dá pra soltar/segurar as teclas no
                meio do gesto e ver o efeito na hora — igual ao CorelDRAW.</p>
                <p>O Polígono tem um campo de "número de lados" na barra de
                propriedades (3 a 20) — poucos lados também cobre losango/triângulo/
                pentágono, sem precisar de uma ferramenta de estrela à parte. Os 3 têm
                cor de tinta, "preenchido" (contorno vazado ou sólido) e espessura de
                traço configuráveis.</p>
                """,
            ),
            (
                "Curvas: Bézier, Mão livre e Forma",
                """
                <p>Como no CorelDRAW. <b>Bézier</b> (no grupo da Mão livre): cada
                clique põe um nó de canto; clicar e arrastar põe um nó suave, puxando
                as alças. Clicar de novo no primeiro nó fecha a forma; duplo clique,
                Enter ou Espaço terminam a curva aberta; Esc cancela. <b>Mão livre</b>
                (F5): arraste pra desenhar — o traço é simplificado ao soltar, e
                terminar perto do começo fecha a forma.</p>
                <p><b>Forma</b> (F10) edita os nós de uma curva: clique na curva,
                arraste um nó (ou a alça do nó selecionado); <b>duplo clique</b> na
                curva adiciona um nó, no nó remove; <b>Delete</b> remove o nó
                selecionado e <b>S</b> alterna entre canto e suave. Cada edição é um
                passo de desfazer.</p>
                <p><b>Converter em curvas</b> (Ctrl+Q) transforma retângulo, elipse,
                polígono, linha e texto numa curva com o mesmo desenho — depois disso
                os nós podem ser editados. <b>Combinar</b> (Ctrl+L) junta vários
                objetos numa curva só (onde se sobrepõem vira furo, como no
                CorelDRAW) e <b>Separar</b> (Ctrl+K) desfaz em uma curva por
                contorno. Os três também ficam na barra Organizar do topo.</p>
                <p><b>Modelar</b> (menu Objeto &gt; Modelar, ou os botões da barra de
                propriedades com 2+ objetos selecionados), como no CorelDRAW:
                <b>Soldar</b> junta tudo numa forma; <b>Aparar</b> recorta o objeto de
                baixo com os de cima (que ficam); <b>Interseção</b> cria a forma da
                área em comum (os originais ficam); <b>Frente menos atrás</b> e
                <b>Atrás menos frente</b> deixam só o de cima / o de baixo, sem a parte
                coberta. O resultado é uma curva com a tinta e o preenchimento do
                objeto de baixo (do de cima, em Frente menos atrás). Trechos curvos
                viram segmentos retos bem curtos (diferença de centésimos de mm).</p>
                """,
            ),
            (
                "Linha",
                """
                <p>Clique e arraste pra desenhar um traço reto entre os 2 pontos. Cor
                de tinta e espessura ficam na barra de propriedades.</p>
                """,
            ),
            (
                "Callout (anotação)",
                """
                <p>Uma caixa de texto com uma "cauda" apontando pro canto
                inferior-esquerdo dela — pra anotações técnicas de revisão, tipo "aqui
                precisa de sangria" ou "cor Pantone tal", marcando pra perto de onde
                aponta.</p>
                <p>Clique no canvas e digite direto no balão, sem caixa de texto (como
                o texto do CorelDRAW): o "Observação" já vem selecionado, então
                digitar substitui, e o balão cresce com o texto. Enter, Esc ou clique
                fora confirmam; duplo clique edita de novo. Apagar tudo remove o
                callout (Ctrl+Z devolve). A cauda é sempre relativa ao próprio balão (não é
                um segundo ponto de controle) — isso é o que deixa o Callout compatível
                com mover/redimensionar/rotacionar/encaixe igual qualquer outro
                elemento, sem precisar de um caso especial.</p>
                """,
            ),
            (
                "Tabela",
                """
                <p>Uma grade de células (linhas × colunas) pra ficha técnica/
                nutricional — clique no canvas pra criar (nasce com um tamanho padrão),
                depois use o botão "Editar tabela..." na barra de propriedades pra
                preencher todas as células de uma vez, num diálogo com uma grade de
                verdade (bem mais rápido que clicar célula por célula pra digitar).</p>
                <p>A 1ª linha vira o cabeçalho automaticamente (fica em negrito).
                Redimensionar linhas/colunas no diálogo preserva o que já foi digitado.</p>
                """,
            ),
            (
                "Acabamento de produção",
                """
                <p>Marca uma área que recebe um processo especial de pós-impressão
                (verniz localizado, laminação fosca/brilho, hot stamping) — clique e
                arraste pra desenhar, Shift = a partir do centro (mesma convenção do
                Retângulo/Elipse/Polígono). O tipo de processo é um campo na barra de
                propriedades.</p>
                <p>Sai desenhado com hachura + a cor de marcação técnica padrão da
                indústria (magenta), <b>não</b> uma das cores de tinta do trabalho —
                de propósito, pra gráfica nunca confundir isso com uma cor que vai pra
                chapa de impressão: é uma instrução à parte pro processo de acabamento.</p>
                """,
            ),
            (
                "Símbolo de manuseio",
                """
                <p>Pictogramas padrão de transporte/manuseio (Frágil, Este lado para
                cima, Manter seco, Não empilhar, Reciclável, Centro de gravidade, Não
                usar gancho) — clique no canvas pra criar, escolha qual símbolo na
                barra de propriedades.</p>
                <p>Tem cor de tinta configurável, igual forma/texto — normalmente fica
                preto, mas pode seguir a cor de uma tinta específica do trabalho se
                fizer sentido pro layout.</p>
                """,
            ),
            (
                "Imagem e logotipo vetorial",
                """
                <p>Pelos botões de ícone na paleta (não são "ferramenta" que fica
                ativa esperando um clique — abrem direto um seletor de arquivo):</p>
                <p><b>Imagem</b> — importa PNG/JPG, nasce numa largura padrão mantendo
                a proporção real do arquivo; redimensionar depois estica livre (sem
                travar proporção).</p>
                <p><b>Logotipo vetorial</b> — importa SVG, com separação de cor
                automática: detecta as cores usadas no arquivo e deixa mapear cada uma
                pra uma das tintas de impressão do trabalho (ou manter a cor original),
                pra gráfica não receber um logo com cor fora da paleta acordada.</p>
                """,
            ),
            (
                "Banco de simbologias",
                """
                <p>Janela de encaixe <b>Simbologias</b> (Ctrl+Shift+Y, ou o último botão
                do grupo de imagem/logotipo na paleta, ou Exibir &gt; Janelas de encaixe):
                os símbolos prontos (cuidado frágil, ícones de manuseio, não pise…) e os
                seus, com miniatura e busca. <b>Dois cliques</b> (ou <b>Inserir</b>) põe
                o símbolo no layout <b>no tamanho real</b> em que foi desenhado; ele é um
                logotipo vetorial: com ele selecionado, <b>um clique numa cor da paleta</b>
                (ou o campo de cor na barra de propriedades) pinta o símbolo todo nessa
                tinta — o branco continua branco; o X da paleta volta às cores do arquivo.
                Pra trocar cor a cor, o botão ao lado separa as cores do arquivo.</p>
                <p><b>Adicionar SVG…</b> guarda um arquivo por símbolo. <b>Importar
                folha…</b> recebe um SVG com vários símbolos (exportado do CorelDRAW):
                cada <b>grupo</b> da folha vira um símbolo — agrupe no Corel do jeito que
                quer separar. Botão direito num símbolo seu: renomear ou apagar.</p>
                <p>Dica: converta os textos em curvas no Corel (Ctrl+Q) antes de exportar
                — a fonte embutida no SVG não é lida aqui, e o texto sai numa fonte
                parecida.</p>
                """,
            ),
            (
                "Checklist de cores",
                """
                <p>Botão de ícone na paleta — uma lista de "quadradinho + nome" pra
                empresa marcar na própria caixa qual variação do produto foi embalada
                ali (ex.: uma peça que existe em preto/branco/cinza).</p>
                <p>Funciona como uma <b>caixa de texto de checklist</b>: na barra de
                propriedades ficam fonte, tamanho em pontos, negrito, cor e o
                <b>arranjo</b> — <b>Empilhado</b> (um embaixo do outro) ou <b>Lado a
                lado</b> (em linha, quebrando pra baixo quando não cabe na largura).
                <b>Espaçamento</b> (o que o F10 do CorelDRAW ajusta): no texto e no
                checklist, os campos <b>AV</b> (entre letras: 0% normal, mais afasta,
                negativo aproxima) e <b>entre linhas</b> (100% normal; menos aproxima as
                linhas/itens). A letra não muda de tamanho, só o espaço.
                <b>Padrão da máquina</b>: texto, checklist e tabela novos já nascem em Arial Black,
                letra de <b>2 mm</b> de altura e <b>meio esticada</b> (66,7% da largura
                normal), em qualquer zoom. No checklist dá pra mudar a altura da letra (mm)
                e a largura (%) na barra; no texto, a altura (H) com o cadeado fechado
                mantém o mesmo esticado. O padrão muda em Configurações (fonte, altura e
                largura das letras de texto novo).
                <b>Duplo clique</b> edita no desenho: cada linha é uma cor, Enter cria a
                próxima, apagar a linha tira a cor (linha vazia não vira cor); Esc ou
                clicar fora termina, e Ctrl+Z desfaz. Puxar a <b>lateral</b> da caixa
                reorganiza os itens sem esticar a letra; puxar um <b>canto</b> aumenta
                ou diminui a letra. A altura acompanha sempre o conteúdo.</p>
                """,
            ),
        ],
    ),
    (
        "Ler / medir",
        [
            (
                "Conta-gotas",
                """
                <p>Clica numa cor renderizada na tela (de qualquer elemento — texto,
                forma, imagem) e aplica a tinta de impressão mais PRÓXIMA (entre as
                marcadas na legenda) no elemento que estava selecionado antes de trocar
                de ferramenta. Não aplica o RGB exato do pixel — a caixa só imprime nas
                cores de tinta reais do trabalho, então isso evitaria criar uma "3ª
                tinta" fora do que a legenda permite.</p>
                """,
            ),
            (
                "Medida",
                """
                <p>2 sub-modos, trocados por <b>Tab</b>:</p>
                <p><b>Medida</b> (padrão) — clique num ponto, arraste até outro, solte:
                mede a distância entre os 2 (funciona como uma trena). Soltar o botão
                FIXA a leitura na tela como uma anotação permanente.</p>
                <p><b>Atributos</b> — passar o mouse por cima de uma linha da faca ou
                de um elemento já mostra o que é (tipo de linha + comprimento, ou tipo
                de elemento + tamanho) sem precisar clicar; <b>clicar fixa</b> essa
                leitura na tela, igual o modo Medida.</p>
                <p>Várias leituras fixadas podem ficar na tela ao mesmo tempo — cada
                uma se fecha só clicando nela, sem afetar as outras. Trocar de
                ferramenta não apaga as leituras já fixadas.</p>
                """,
            ),
            (
                "Cotas (paralela, horizontal, vertical, angular)",
                """
                <p>Como as ferramentas de cota do CorelDRAW (no mesmo grupo da Medida,
                na caixa de ferramentas): arraste de um ponto a outro e a cota fica
                <b>no desenho</b> — sai na exportação e no envio pro CorelDRAW, ao
                contrário da Medida, que é só leitura.</p>
                <p><b>Paralela</b> mede a distância direta (Ctrl prende o ângulo em
                15°); <b>horizontal</b> mede só o Δx e <b>vertical</b> só o Δy. As duas
                últimas vão sozinhas pro lado de fora da chapa. As pontas grudam nos
                cantos da faca, dos objetos e da chapa quando o encaixe está ligado.</p>
                <p><b>Cota angular</b>: clique no vértice, depois num ponto de cada
                braço — mede o menor ângulo entre eles (até 180°), com o arco e o
                valor em graus. Esc cancela no meio. Na barra de propriedades: raio do
                arco, altura do texto e tinta.</p>
                <p>A cota é um objeto como os outros: o valor acompanha quando você a
                redimensiona, e a barra de propriedades muda o afastamento da linha,
                a altura do texto e a tinta. A ferramenta continua ativa depois de
                cada cota, pra cotar várias medidas em sequência (Esc volta pro
                ponteiro).</p>
                """,
            ),
        ],
    ),
    (
        "Precisão e apoio",
        [
            (
                "Encaixe (snap)",
                """
                <p>Ao soltar o arrasto do corpo de um elemento, a borda esquerda, o
                centro e a borda direita dele (nos 2 eixos) são testados contra a
                grade, as bordas/centro de outros elementos, a face (painel) e as
                guias — o alvo mais próximo dentro de um limiar "gruda" ali. Fora do
                limiar, a posição solta exatamente onde o mouse largou.</p>
                <p><b>Encaixe ao vivo</b> (como no CorelDRAW): durante o arrasto, se
                um canto, o meio de uma borda ou o centro do objeto chega perto de um
                ponto de encaixe, ele gruda ali na hora, e aparece um quadradinho azul
                com o nome do ponto ("canto → nó", "centro → centro da chapa"...).
                Pontos de encaixe: nós, pontos médios e interseções da faca; cantos,
                meios das bordas e centro dos objetos; cantos e centro da chapa. Com
                uma ferramenta de desenho, o mesmo nome aparece ao passar o cursor
                sobre o ponto, então dá pra saber exatamente onde vai clicar.
                Sem ponto perto, vale o encaixe ao soltar descrito acima.</p>
                <p><b>Distâncias</b> (como no Illustrator/Figma): enquanto arrasta,
                linhas vermelhas mostram em mm a distância do objeto até o vizinho mais
                próximo em cada direção, até as bordas da face e até as bordas da
                chapa. Com um objeto selecionado, segure <b>Alt</b> para ver as mesmas
                medidas sem arrastar; com o Alt segurado, as <b>setas</b> movem o
                objeto e as medidas acompanham (como no Figma). Soltou o Alt, somem.</p>
                <p>Liga/desliga pelo menu Exibir &gt; "Encaixe (snap) ao arrastar". O
                limiar de distância e o espaçamento da grade são preferências em
                Configurações &gt; Ferramentas.</p>
                <p><b>Guias dinâmicas</b> (Exibir, <b>Alt+Shift+D</b>, ligadas por
                padrão): ao desenhar — formas, linhas, Bézier, cotas e linhas novas da
                faca —, o cursor alinha na vertical e na horizontal com os nós da
                faca, dos objetos, da chapa e com o 1º ponto do gesto, e aparece uma
                linha tracejada azul até o nó (marcado com um ×). Alinhando com dois
                nós ao mesmo tempo, o ponto cai no cruzamento das guias.</p>
                <p><b>Ajustar a</b> (botão na barra do topo e em Exibir, como no
                CorelDRAW) escolhe onde grudar: grade do documento (quando visível),
                guias, objetos (inclui as bordas da face) e página (bordas e centro da
                chapa). <b>Alt+Z</b> liga/desliga objetos e <b>Ctrl+Y</b> a grade.</p>
                """,
            ),
            (
                "Endpoint Offset Mode",
                """
                <p>Recurso de precisão pra quando o clique visual não é exato o
                bastante: com qualquer ferramenta de CRIAR um elemento ativa (Texto,
                Retângulo, Callout, Símbolo...), <b>Alt + clique</b> (em vez do clique
                normal) pausa o gesto, acha o ponto de referência mais próximo (borda/
                centro de outro elemento ou guia — se nada estiver perto, usa o
                próprio clique) e abre 2 campos (X, Y) pra digitar um deslocamento
                exato a partir dali.</p>
                <p><b>Enter</b> confirma e começa a criação normal a partir do ponto
                calculado (referência + deslocamento). <b>Esc</b> cancela sem criar
                nada.</p>
                """,
            ),
            (
                "Réguas e guias",
                """
                <p>Arrastar a partir da régua do topo solta uma guia VERTICAL (marca
                uma posição X); arrastar a partir da régua da esquerda solta uma guia
                HORIZONTAL (posição Y). A guia nasce já arrastável — clicar nela e
                arrastar de novo reposiciona.</p>
                <p>Guias participam do encaixe (snap) como mais um alvo, e podem ser
                selecionadas/removidas (Delete) igual qualquer elemento. Liga/desliga
                pelo menu Exibir &gt; "Réguas".</p>
                """,
            ),
            (
                "Zonas seguras",
                """
                <p>Marca visualmente uma faixa de recuo perto do vinco/corte de cada
                painel (face) onde não é recomendado colocar conteúdo — texto ou
                elemento de mockup ali corre risco de ficar cortado ou dobrado errado
                na produção. Só um guia visual (não trava nem impede colocar conteúdo
                ali, e não sai na exportação).</p>
                <p>Liga/desliga pelo menu Exibir &gt; "Zonas seguras (recuo do
                vinco)" — desligado por padrão.</p>
                """,
            ),
            (
                "Barra de propriedades",
                """
                <p>Igual à do CorelDRAW, começa sempre pela geometria do objeto
                selecionado: posição X/Y, largura/altura, ângulo, <b>escala em %</b>
                (digite 150 e confirme pra aumentar 50% em torno do centro; o campo
                volta pra 100), trava de proporção e <b>espelhar</b> na horizontal/
                vertical. Depois vem a face da caixa (com o menu de alinhar na face — sem
                face escolhida, ele usa a face onde o objeto está) e
                os campos do tipo do objeto (fonte, tinta, espessura...).</p>
                <p><b>Sem nada selecionado</b>, a barra mostra o tamanho da chapa, a
                unidade e as distâncias de deslocamento (setas e Shift+setas) e de
                duplicação (Ctrl+D e colar) — as mesmas de Configurações &gt;
                Ferramentas.</p>
                """,
            ),
            (
                "Janelas de encaixe (dockers)",
                """
                <p>Como no CorelDRAW, abrem na borda direita (em abas) pelo menu
                Exibir &gt; Janelas de encaixe, só na tela de Layout:</p>
                <p><b>Objetos</b> — a camada Arte com cada elemento (de cima pra
                baixo, na ordem da frente pra trás) e a camada Faca, travada. Clicar
                na lista seleciona no desenho e vice-versa; desmarcar oculta o
                elemento, e o oculto não sai na exportação nem vai pro CorelDRAW.</p>
                <p><b>Alinhar e distribuir</b> (<b>Ctrl+Shift+A</b>) — alinhar com a
                seleção, com a página (chapa) ou com a face de cada elemento;
                distribuir 3 ou mais objetos por centros ou por espaços iguais.</p>
                <p><b>Transformações</b> (<b>Alt+F7</b> posição, <b>Alt+F8</b>
                rotação, <b>Alt+F9</b> escala e espelho, <b>Alt+F10</b> tamanho) —
                o campo <b>Cópias</b> funciona como no CorelDRAW: com 0, transforma
                o próprio objeto; com N, deixa o original e cria N cópias, cada uma
                transformada a partir da anterior (ex.: mover 50 mm com 3 cópias faz
                uma fileira). Um Ctrl+Z desfaz tudo de uma vez.</p>
                """,
            ),
            (
                "Desfazer / refazer",
                """
                <p><b>Ctrl+Z</b> desfaz, <b>Ctrl+Shift+Z</b> refaz —
                cobre adicionar (por ferramenta, duplicar, colar), remover, mover,
                redimensionar e girar (inclusive grupos e o nudge pela seta do
                teclado). Cada ação só entra na pilha quando o gesto termina (soltar o
                mouse), não a cada frame do arrasto.</p>
                """,
            ),
            (
                "Atalhos de teclado",
                """
                <p><b>Ctrl+Z</b> / <b>Ctrl+Shift+Z</b> — desfazer/refazer.<br>
                <b>Alt+Z</b> / <b>Ctrl+Y</b> — liga/desliga o encaixe em objetos / na
                grade (como no CorelDRAW).<br>
                <b>Ctrl+D</b> — duplicar a seleção (com deslocamento, "efeito
                cascata").<br>
                <b>Ctrl+C</b> / <b>Ctrl+V</b> — copiar/colar.<br>
                <b>Delete</b> — remove a seleção atual.<br>
                <b>+ do teclado numérico</b> — duplica no lugar (cópia exatamente
                em cima).<br>
                <b>Ctrl+A</b> — seleciona todos os elementos.<br>
                <b>Ctrl+G</b> / <b>Ctrl+U</b> (ou Ctrl+Shift+G) — agrupar/desagrupar.<br>
                <b>Shift+PgUp</b> / <b>Shift+PgDn</b> (ou Ctrl+Home / Ctrl+End) — trazer
                pra frente / enviar pra trás.<br>
                <b>Ctrl+PgUp</b> / <b>Ctrl+PgDn</b> — um nível à frente / atrás.<br>
                <b>L</b> / <b>R</b> / <b>T</b> / <b>B</b> — alinhar à esquerda, direita,
                topo e base; <b>C</b> / <b>E</b> — centros na vertical / horizontal.
                Com um elemento só, alinha com a chapa da dieline.<br>
                <b>P</b> — centraliza a seleção na chapa.<br>
                <b>F4</b> — zoom em tudo; <b>Shift+F4</b> — zoom na chapa;
                <b>Shift+F2</b> — zoom na seleção.<br>
                <b>Ctrl+Q</b> — converter em curvas; <b>Ctrl+L</b> / <b>Ctrl+K</b> —
                combinar / separar.<br>
                <b>F5</b> Mão livre, <b>F6</b> Retângulo, <b>F7</b> Elipse, <b>F8</b> Texto,
                <b>F10</b> Forma,
                <b>Y</b> Polígono; <b>Espaço</b> alterna entre Selecionar e a última
                ferramenta.<br>
                <b>Setas do teclado</b> — move a seleção aos poucos (Shift = passo
                maior, Ctrl = passo de um décimo).<br>
                <b>Tab</b> — troca de sub-modo na ferramenta Medida.<br>
                <b>Esc</b> — cancela o gesto atual (arrasto de criação, laço, Move de
                precisão, campo do Endpoint Offset) ou volta pro ponteiro.</p>
                """,
            ),
        ],
    ),
    (
        "Exportar",
        [
            (
                "SVG / PDF / JPG",
                """
                <p>Botões na barra de ferramentas — geram um arquivo vetorial (SVG/
                PDF, qualidade perfeita em qualquer escala) ou raster (JPG, resolução
                calculada a partir do DPI configurado em Configurações) do layout
                técnico completo (faca + mockup + legenda de cores).</p>
                <p>Sempre sai em preto e traço contínuo (só o vinco tracejado) — mesmo
                sem cor nenhuma marcada, é o padrão esperado pela gráfica pra arquivo
                de faca, independente do tema visual do app na tela.</p>
                """,
            ),
            (
                "CorelDRAW",
                """
                <p>"Enviar para o CorelDRAW" desenha o layout direto num documento
                novo, com automação COM (só Windows, com o CorelDRAW instalado) — em
                vez de exportar um arquivo à parte pra depois abrir manualmente.
                Conecta numa instância já aberta do CorelDRAW, ou abre uma nova se não
                tiver nenhuma rodando.</p>
                """,
            ),
        ],
    ),
]


class DialogoManual(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manual de uso")
        self.resize(820, 600)

        raiz = QHBoxLayout(self)

        self._lista = QListWidget()
        self._lista.setFixedWidth(230)
        self._lista.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        raiz.addWidget(self._lista)

        self._conteudo = QTextBrowser()
        self._conteudo.setOpenExternalLinks(False)
        raiz.addWidget(self._conteudo, 1)

        self._html_por_linha: dict[int, str] = {}
        primeira_linha_selecionavel: int | None = None
        for categoria, topicos in _TOPICOS:
            cabecalho = QListWidgetItem(categoria.upper())
            cabecalho.setFlags(Qt.ItemFlag.NoItemFlags)
            fonte = cabecalho.font()
            fonte.setBold(True)
            cabecalho.setFont(fonte)
            cabecalho.setForeground(Qt.GlobalColor.gray)
            self._lista.addItem(cabecalho)

            for titulo, html in topicos:
                item = QListWidgetItem("    " + titulo)
                self._lista.addItem(item)
                linha = self._lista.row(item)
                self._html_por_linha[linha] = self._formatar(titulo, html)
                if primeira_linha_selecionavel is None:
                    primeira_linha_selecionavel = linha

        self._lista.currentRowChanged.connect(self._ao_selecionar)
        if primeira_linha_selecionavel is not None:
            self._lista.setCurrentRow(primeira_linha_selecionavel)

    def _ao_selecionar(self, linha: int) -> None:
        html = self._html_por_linha.get(linha)
        if html is not None:
            self._conteudo.setHtml(html)

    @staticmethod
    def _formatar(titulo: str, corpo_html: str) -> str:
        return (
            f"<h2 style='color:{Cor.PRIMARIA};margin-bottom:4px;'>{titulo}</h2>"
            f"<div style='font-size:13px;line-height:1.5;'>{corpo_html}</div>"
        )
