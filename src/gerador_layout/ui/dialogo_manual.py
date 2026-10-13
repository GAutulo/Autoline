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
                uma seleção retangular, seleciona tudo que estiver dentro.</p>
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
                <p>Clique no canvas — o cursor de texto já aparece na hora, digite
                direto (sem precisar de um diálogo à parte) e clique fora ou aperte
                Enter pra confirmar.</p>
                <p><b>Duplo-clique</b> num texto já existente reabre a edição no
                lugar. Redimensionar (alças) estica o texto nos 2 eixos — puxar só um
                canto/lado distorce de propósito, igual "texto artístico" em qualquer
                editor vetorial: é assim que se ajusta largura/altura de letra sem
                precisar de um campo numérico de "tamanho de fonte".</p>
                <p>Fonte, negrito e cor de tinta ficam na barra de propriedades quando o
                texto está selecionado. A fonte usada num texto novo vem de
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
                <p>Clique no canvas, digite direto (igual a ferramenta Texto), clique
                fora pra confirmar. A cauda é sempre relativa ao próprio balão (não é
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
                "Checklist de cores",
                """
                <p>Botão de ícone na paleta — uma lista de "quadradinho + nome" pra
                empresa marcar na própria caixa qual variação do produto foi embalada
                ali (ex.: uma peça que existe em preto/branco/cinza). Editar a lista de
                variantes fica num popup pela barra de propriedades.</p>
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
                "Cotas (paralela, horizontal, vertical)",
                """
                <p>Como as ferramentas de cota do CorelDRAW (no mesmo grupo da Medida,
                na caixa de ferramentas): arraste de um ponto a outro e a cota fica
                <b>no desenho</b> — sai na exportação e no envio pro CorelDRAW, ao
                contrário da Medida, que é só leitura.</p>
                <p><b>Paralela</b> mede a distância direta (Ctrl prende o ângulo em
                15°); <b>horizontal</b> mede só o Δx e <b>vertical</b> só o Δy. As duas
                últimas vão sozinhas pro lado de fora da chapa. As pontas grudam nos
                cantos da faca, dos objetos e da chapa quando o encaixe está ligado.</p>
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
                <p>Uma linha-guia tracejada aparece DURANTE o arrasto mostrando pra
                onde vai grudar, se soltar ali — o encaixe em si só é aplicado ao
                soltar (não durante o arrasto).</p>
                <p>Liga/desliga pelo menu Exibir &gt; "Encaixe (snap) ao arrastar". O
                limiar de distância e o espaçamento da grade são preferências em
                Configurações &gt; Ferramentas.</p>
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
                vertical. Depois vem a face da caixa (com o menu de alinhar na face) e
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
                <b>F5</b> Linha, <b>F6</b> Retângulo, <b>F7</b> Elipse, <b>F8</b> Texto,
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
