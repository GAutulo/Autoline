"""Sistema de design do app: paleta, tipografia e estilo (QSS) de cada
widget, aplicado globalmente em `main.py`.

Widgets nativos do Qt no Windows (QGroupBox, QPushButton, etc.) usam o
estilo padrão do sistema, que é bem neutro/datado — uma paleta e
espaçamento consistentes aqui já resolvem boa parte da percepção de
"acabamento" do programa, sem mudar nenhuma lógica.

Um só acento (`PRIMARIA`) em todo o app — inclusive nas telas de
exportação/CorelDRAW que já tínhamos acertado — não uma cor nova por
elemento. Os arquivos exportados (SVG/PDF/JPG/CorelDRAW) NÃO importam
nada daqui — são sempre preto sobre branco, seja qual for o tema do
app, porque isso é convenção da gráfica, não preferência visual.

## Redesign (REDESIGN.md, seção 2.3)

Grafite técnico com UM acento âmbar (`#F0A04B` no escuro). Superfícies
em degraus: janela → painel (`CARTAO`) → elevado (`ELEVADO`: botão
secundário, menu) → campo (`CAMPO`). Chapado (sem sombra nem gradiente),
raios 6 (campo) / 7 (botão) / 10 (cartão) / pílula (chip de cor).

O âmbar puro só funciona como texto sobre fundo escuro; no tema claro
`PRIMARIA` é o âmbar escurecido da versão clara do logotipo, e `BRANCO`
(texto sobre um botão preenchido com `PRIMARIA`) inverte junto: quase
preto sobre o âmbar do escuro, branco sobre o âmbar escuro do claro.
Contraste calculado (WCAG) pra cada combinação antes de fechar os valores.

O canvas (mesa, página, malha, faca) NÃO usa estas cores — fica igual em
qualquer tema (ver `preview_canvas._COR_MESA`).

## Tema claro/escuro

`Cor` é preenchida, na hora que este módulo é importado, com os valores
do tema salvo em `configuracoes.py` (padrão: claro). Trocar de tema
precisa reiniciar o app pra valer: os valores de `Cor` viram literais
dentro de várias strings de QSS já montadas quando cada tela é
construída, então mudar `Cor` depois disso não re-pinta o que já foi
criado — mais simples e mais confiável salvar a escolha e aplicar tudo
de novo, do zero, no próximo início (ver `configuracoes.definir_tema`).

## Botões primário/secundário

A maioria dos QPushButton no app é ação secundária (ex.: "Ajustar à
tela", "Recalcular") — o padrão (`QPushButton` sem mais nada) já cobre
isso. Pra ação primária (ex.: os botões de exportação na barra de
ferramentas), marca o widget com `botao.setProperty("primario", True)`
*antes* dele ser mostrado — o seletor `QPushButton[primario="true"]`
abaixo pega esse caso.
"""

from . import configuracoes

# Cada dict é um tema completo. `CAMPO` é o fundo dos elementos
# interativos (campo de texto, combobox, indicador de checkbox) — no
# claro precisa ser mais claro/branco que o cartão, no escuro precisa
# ser MAIS CLARO que o cartão (não mais escuro) pra manter o mesmo
# princípio de contraste "isso aqui é uma superfície interativa".
_PALETA_CLARA = {
    # Derivado do escuro (mesma estrutura, ver REDESIGN.md 2.3): neutros
    # quase brancos e o âmbar escurecido da versão clara do logotipo — o
    # âmbar "puro" não tem contraste como texto sobre fundo claro.
    "PRIMARIA": "#A55A0D",  # âmbar escuro (4,8:1 sobre o painel)
    "PRIMARIA_HOVER": "#8A4A0A",
    "PRIMARIA_ATIVA": "#6E3C08",
    "PRIMARIA_CLARA": "#F6E3CC",  # fundo da ferramenta ativa / hover
    "PRIMARIA_PRESSIONADA": "#EED2B0",
    # Seleção (texto marcado num campo, item de lista, botão ligado): tem que
    # destacar do campo E do cartão.
    "SELECAO": "#EBBE86",
    "TEXTO": "#15181B",
    "TEXTO_SECUNDARIO": "#4E555C",
    "TEXTO_TERCIARIO": "#6B7178",
    "BRANCO": "#FFFFFF",  # texto sobre um botão preenchido com PRIMARIA (5,2:1)
    "CAMPO": "#FFFFFF",
    "ELEVADO": "#FFFFFF",  # botão secundário, menus
    "CARTAO": "#F7F6F3",  # painel
    "FUNDO_JANELA": "#ECEAE5",
    "BORDA": "#DAD7D0",
    "BORDA_FORTE": "#C4C0B8",
    "ERRO": "#C1432A",  # tinta / zona segura (igual antes)
    "CANVAS_FUNDO_RGB": (250, 246, 237),
    "CANVAS_GRADE_RGBA": (30, 26, 22, 14),
    "PAINEL_FLUTUANTE_RGBA": (247, 246, 243, 235),
}

_PALETA_ESCURA = {
    # Grafite técnico com um acento âmbar (REDESIGN.md 2.3) — valores exatos.
    "PRIMARIA": "#F0A04B",  # âmbar, o único acento
    "PRIMARIA_HOVER": "#FFC27D",
    "PRIMARIA_ATIVA": "#FFD9A8",
    "PRIMARIA_CLARA": "#3A2810",  # fundo da ferramenta ativa / hover
    "PRIMARIA_PRESSIONADA": "#2E200C",
    "SELECAO": "#5A3F1A",
    "TEXTO": "#E7E9EB",
    "TEXTO_SECUNDARIO": "#A3AAB2",
    "TEXTO_TERCIARIO": "#7D858E",
    "BRANCO": "#1A1206",  # texto sobre o âmbar (botão primário)
    "CAMPO": "#23282D",
    "ELEVADO": "#1D2125",  # botão secundário, menus
    "CARTAO": "#16191C",  # painel
    "FUNDO_JANELA": "#0F1113",  # janela
    "BORDA": "#2A2F35",
    "BORDA_FORTE": "#3A4048",
    "ERRO": "#C1432A",  # tinta / zona segura (igual antes)
    "CANVAS_FUNDO_RGB": (30, 26, 22),
    "CANVAS_GRADE_RGBA": (237, 230, 216, 16),
    "PAINEL_FLUTUANTE_RGBA": (22, 25, 28, 235),
}

_PALETAS = {configuracoes.TEMA_CLARO: _PALETA_CLARA, configuracoes.TEMA_ESCURO: _PALETA_ESCURA}


class Cor:
    """Paleta do tema ativo — atributos preenchidos logo abaixo a partir
    de `_PALETAS`. Ver docstring do módulo pra por que trocar de tema
    exige reiniciar o app."""


def cor_legivel_sobre(r: int, g: int, b: int, fundo: str | None = None) -> tuple[int, int, int]:
    """A própria cor (vermelho escrito em vermelho), clareada ou escurecida
    o mínimo pra ter contraste de leitura (≥ 3:1) sobre o fundo do tema —
    "Preto" sobre o fundo escuro, "Amarelo" sobre o claro."""

    def luminancia(c):
        def canal(v):
            v /= 255.0
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        return 0.2126 * canal(c[0]) + 0.7152 * canal(c[1]) + 0.0722 * canal(c[2])

    fundo = fundo or Cor.FUNDO_JANELA
    f = tuple(int(fundo[i : i + 2], 16) for i in (1, 3, 5))
    lf = luminancia(f)
    alvo = (255, 255, 255) if lf < 0.4 else (0, 0, 0)
    cor = (r, g, b)
    for passo in range(11):
        t = passo / 10
        c = tuple(round(cor[i] + (alvo[i] - cor[i]) * t) for i in range(3))
        lc = luminancia(c)
        if (max(lc, lf) + 0.05) / (min(lc, lf) + 0.05) >= 3.0:
            return c
    return alvo


def _aplicar_paleta(paleta: dict) -> None:
    for nome, valor in paleta.items():
        setattr(Cor, nome, valor)


_aplicar_paleta(_PALETAS.get(configuracoes.tema(), _PALETA_CLARA))


# As 3 fontes vêm de arquivo (ver `main.py::_carregar_fontes`, carregadas
# via QFontDatabase antes desta folha de estilo ser aplicada) — não são
# fontes do sistema, então título/corpo/mono ficam garantidos iguais em
# qualquer máquina Windows, independente do que estiver instalado.
FONTE_FAMILIA = "IBM Plex Sans"  # corpo — texto normal em todo o app
FONTE_MONO = "IBM Plex Mono"  # leituras técnicas: zoom, cota de medida, DPI
FONTE_DISPLAY = "Archivo"  # marca e títulos de tela (700, semi-expandida — ver marca.py)

FOLHA_DE_ESTILO = f"""
* {{
    font-family: "{FONTE_FAMILIA}";
}}

QMainWindow, QDialog {{
    background: {Cor.FUNDO_JANELA};
}}

QWidget {{
    color: {Cor.TEXTO};
    font-size: 13px;
}}

QToolTip {{
    background: {Cor.TEXTO};
    color: {Cor.FUNDO_JANELA};
    border: none;
    padding: 4px 8px;
    border-radius: 4px;
}}

/* ── Cartões (QGroupBox) ─────────────────────────────────────────── */
QGroupBox {{
    background: {Cor.CARTAO};
    border: 1px solid {Cor.BORDA};
    border-radius: 10px;
    margin-top: 14px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: 3px;
    padding: 0 4px;
    background: transparent;
    color: {Cor.TEXTO};
}}
/* Só os QGroupBox retráteis (setCheckable) têm esse indicador — o resto
   do app não usa. Mesmo desenho do QCheckBox::indicator, pra ler como o
   mesmo tipo de controle. */
QGroupBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {Cor.BORDA_FORTE};
    border-radius: 3px;
    background: {Cor.CAMPO};
}}
QGroupBox::indicator:checked {{
    background: {Cor.PRIMARIA};
    border-color: {Cor.PRIMARIA};
}}

/* ── Campos ──────────────────────────────────────────────────────────
   Fundo de campo (`CAMPO`) de propósito, contra o cartão — o contraste
   deixa claro onde o campo começa/termina (borda mais forte que o
   resto do app, mesmo motivo). */
QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit, QTextEdit, QPlainTextEdit {{
    color: {Cor.TEXTO};
    background: {Cor.CAMPO};
    border: 1px solid {Cor.BORDA_FORTE};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 22px;
    selection-background-color: {Cor.SELECAO};
    selection-color: {Cor.TEXTO};
}}
QComboBox:hover, QDoubleSpinBox:hover, QSpinBox:hover, QLineEdit:hover {{
    border-color: {Cor.BORDA_FORTE};
}}
QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1px solid {Cor.PRIMARIA};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {Cor.ELEVADO};
    border: 1px solid {Cor.BORDA};
    selection-background-color: {Cor.SELECAO};
    selection-color: {Cor.TEXTO};
    outline: none;
}}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 16px;
    border: none;
}}

/* ── Botões ──────────────────────────────────────────────────────── */
QPushButton {{
    background: {Cor.ELEVADO};
    border: 1px solid {Cor.BORDA_FORTE};
    border-radius: 7px;
    padding: 7px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {Cor.PRIMARIA_CLARA};
    border-color: {Cor.PRIMARIA};
    color: {Cor.PRIMARIA_ATIVA};
}}
QPushButton:pressed {{
    background: {Cor.PRIMARIA_PRESSIONADA};
}}
QPushButton:disabled {{
    background: {Cor.FUNDO_JANELA};
    color: {Cor.TEXTO_TERCIARIO};
    border-color: {Cor.BORDA};
}}

/* Ação primária — ver docstring do módulo pra como marcar um botão assim. */
QPushButton[primario="true"] {{
    background: {Cor.PRIMARIA};
    border: 1px solid {Cor.PRIMARIA};
    color: {Cor.BRANCO};
}}
QPushButton[primario="true"]:hover {{
    background: {Cor.PRIMARIA_HOVER};
    border-color: {Cor.PRIMARIA_HOVER};
    color: {Cor.BRANCO};
}}
QPushButton[primario="true"]:pressed {{
    background: {Cor.PRIMARIA_ATIVA};
    border-color: {Cor.PRIMARIA_ATIVA};
}}
/* Botão de modo (ex.: Girar / Ângulo da dobra / Face base no 3D): o
   escolhido fica com o acento, pra saber em que modo o clique está. */
QPushButton:checked {{
    background: {Cor.PRIMARIA_CLARA};
    border: 1px solid {Cor.PRIMARIA};
    color: {Cor.PRIMARIA_ATIVA};
}}

QPushButton:flat {{
    border: none;
    background: transparent;
    padding: 3px 8px;
    font-weight: 600;
}}
QPushButton:flat:hover {{
    background: {Cor.PRIMARIA_CLARA};
    border-radius: 5px;
    color: {Cor.PRIMARIA_ATIVA};
}}

/* Chip de cor da legenda (ver `_montar_chip_cor` em main_window.py) —
   cor de fundo/texto é definida por widget (própria cor da tinta), só o
   raio/peso da fonte vem daqui. */
QPushButton[chipCor="true"] {{
    border-radius: 13px;
    padding: 4px 12px;
    font-weight: 600;
}}

/* ── Checkbox (ainda usado fora da legenda de cores) ────────────────*/
QCheckBox {{
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 15px;
    height: 15px;
    border: 1px solid {Cor.BORDA_FORTE};
    border-radius: 3px;
    background: {Cor.CAMPO};
}}
QCheckBox::indicator:checked {{
    background: {Cor.PRIMARIA};
    border-color: {Cor.PRIMARIA};
}}

/* ── Barra de ferramentas / menu ─────────────────────────────────── */
QToolBar {{
    background: {Cor.CARTAO};
    border-bottom: 1px solid {Cor.BORDA};
    padding: 6px 10px;
    spacing: 8px;
}}
QToolBar QToolButton {{
    background: {Cor.CAMPO};
    border: 1px solid {Cor.BORDA};
    border-radius: 7px;
    padding: 6px 12px;
    font-weight: 600;
}}
QToolBar QToolButton:hover {{
    background: {Cor.PRIMARIA_CLARA};
    border-color: {Cor.PRIMARIA};
    color: {Cor.PRIMARIA_ATIVA};
}}
QToolBar::separator {{
    background: {Cor.BORDA};
    width: 1px;
    margin: 6px 6px;
}}

/* ── Paleta de ferramentas do Layout (horizontal, topo, só ícone) ────
   Mesmo lugar/formato de qualquer CAD/vetorial de verdade — botão
   quadrado, ícone centralizado, sem o padding largo (pensado pra botão
   com texto) da regra `QToolBar QToolButton` genérica acima. `:checked`
   marca a ferramenta ativa (Selecionar/Texto/Retângulo/Linha, ver
   `FerramentaMockup`); as ações de um clique só (Agrupar, Trazer p/
   frente...) não ficam `:checked` nunca, só têm o `:hover`. */
QToolBar#paletaFerramentasMockup {{
    padding: 8px 6px;
    spacing: 4px;
}}
QToolBar#paletaFerramentasMockup QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 7px;
    min-width: 20px;
    min-height: 20px;
}}
QToolBar#paletaFerramentasMockup QToolButton:hover {{
    background: {Cor.PRIMARIA_CLARA};
    border-color: {Cor.PRIMARIA};
}}
QToolBar#paletaFerramentasMockup QToolButton:checked {{
    background: {Cor.PRIMARIA_CLARA};
    border-color: {Cor.PRIMARIA};
}}
QToolBar#paletaFerramentasMockup QToolButton::menu-indicator {{
    image: none;  /* o flyout desenha o próprio triângulo no canto (ver BotaoFlyout) */
}}
QToolBar#paletaCores {{
    padding: 4px 2px;
    border-left: 1px solid {Cor.BORDA};
}}
QToolBar#paletaFerramentasMockup::separator:horizontal {{
    background: {Cor.BORDA};
    width: 1px;
    margin: 4px 4px;
}}
/* Caixa de ferramentas vertical (borda esquerda, estilo CorelDRAW). */
QToolBar#paletaFerramentasMockup::separator:vertical {{
    background: {Cor.BORDA};
    height: 1px;
    margin: 4px 6px;
}}

QMenuBar {{
    background: {Cor.CARTAO};
    border-bottom: 1px solid {Cor.BORDA};
    padding: 2px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: {Cor.PRIMARIA_CLARA};
}}
QMenu {{
    background: {Cor.ELEVADO};
    border: 1px solid {Cor.BORDA};
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {Cor.PRIMARIA_CLARA};
}}
QMenu::separator {{
    height: 1px;
    background: {Cor.BORDA};
    margin: 4px 8px;
}}

QStatusBar {{
    background: {Cor.CARTAO};
    border-top: 1px solid {Cor.BORDA};
    color: {Cor.TEXTO_SECUNDARIO};
}}

/* ── Abas de tela (Dieline / Layout, ver main_window.py) ────────────
   Mesma linguagem visual do resto (cartão + borda), sem o gradiente/
   sombreado padrão do Qt nativo pra combinar com o estilo chapado do
   resto do app. */
QTabBar::tab {{
    background: transparent;
    color: {Cor.TEXTO_SECUNDARIO};
    border: 1px solid {Cor.BORDA};
    border-bottom: none;
    padding: 7px 20px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 600;
}}
QTabBar::tab:selected {{
    background: {Cor.CARTAO};
    color: {Cor.TEXTO};
    border-color: {Cor.BORDA_FORTE};
}}
QTabBar::tab:hover:!selected {{
    color: {Cor.PRIMARIA};
}}

/* ── Barra de propriedades do mockup (property bar estilo CorelDRAW) ──
   Uma barra horizontal por baixo da barra de criar elemento, com um
   botão de ícone (sem texto) por controle — o mesmo padrão de qualquer
   CAD/vetorial de verdade. `QToolBar#barraPropriedadesMockup` é o
   contêiner (fundo/borda de cartão, como as outras barras do app);
   `QToolButton#botaoIconePropriedade` é cada botão individual —
   `:checked` marca estado ligado (negrito ativo, preenchido ativo,
   proporção travada) do mesmo jeito que `:hover` já sinaliza clique
   possível, sem precisar de 2 ícones (ligado/desligado) por botão. */
QToolBar#barraPropriedadesMockup {{
    background: {Cor.CARTAO};
    border-bottom: 1px solid {Cor.BORDA};
    padding: 2px 6px;
    spacing: 3px;
}}
QToolButton#botaoIconePropriedade {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px;
}}
QToolButton#botaoIconePropriedade:hover {{
    background: {Cor.PRIMARIA_CLARA};
    border-color: {Cor.PRIMARIA};
}}
QToolButton#botaoIconePropriedade:checked {{
    background: {Cor.SELECAO};
    border-color: {Cor.PRIMARIA};
}}
QLabel#iconeCampoPropriedade {{
    padding: 0 1px;
}}
/* Abas da barra de propriedades (Letra / Espaçamento / Posição...):
   compactas, em pílula — não as abas grandes de tela (Dieline/Layout). */
QTabBar#abasPropriedades::tab {{
    background: transparent;
    color: {Cor.TEXTO_SECUNDARIO};
    border: 1px solid {Cor.BORDA};
    border-radius: 6px;
    padding: 4px 10px;
    margin: 0 3px 0 0;
    font-weight: 600;
}}
QTabBar#abasPropriedades::tab:selected {{
    background: {Cor.SELECAO};
    color: {Cor.TEXTO};
    border-color: {Cor.PRIMARIA};
}}
QTabBar#abasPropriedades::tab:hover:!selected {{
    color: {Cor.PRIMARIA};
    border-color: {Cor.PRIMARIA};
}}
QScrollArea#rolagemPropriedades, QScrollArea#rolagemPropriedades > QWidget > QWidget {{
    background: transparent;
}}
QScrollArea#rolagemPropriedades QScrollBar:horizontal {{
    height: 6px;
}}

/* Marca no canto da barra de ferramentas (ver `_montar_barra_ferramentas`
   em main_window.py) — única fonte que usa a fonte de exibição; o resto
   do app fica no corpo/mono de propósito, pra não virar cartaz. */
QLabel#rotuloMarca {{
    font-family: "{FONTE_DISPLAY}";
    font-weight: 700;
    font-size: 20px;
    letter-spacing: 1px;
    color: {Cor.PRIMARIA};
    padding-right: 6px;
}}

/* Fronteira entre campos universais e campos do tipo selecionado na barra
   de propriedades horizontal (ver `PainelPropriedadesMockup._separador`,
   achado numa revisão de UI/UX) — mais grosso que o traço nativo do Qt
   (fino/cinza, some no meio dos outros separadores), mas em `BORDA_FORTE`
   (neutro), não `PRIMARIA` — é uma fronteira de leitura, não uma ação, e
   `PRIMARIA` é reservado a destaque/ação (ver "The One Accent Rule" em
   DESIGN.md). */
QFrame#separadorForte {{
    background: {Cor.BORDA_FORTE};
    max-width: 2px;
    min-width: 2px;
    border: none;
}}

/* Leituras técnicas (zoom, cota de medida) — ver docstring de FONTE_MONO. */
QLabel#rotuloTecnico {{
    font-family: "{FONTE_MONO}";
    font-weight: 500;
}}

/* ── Dock de propriedades do mockup (ver painel_propriedades_mockup.py)
   Sem isso, o título do dock fica com o chrome nativo do Qt (cinza claro
   fixo) — ignora o tema por completo, mais visível ainda no escuro. */
QDockWidget {{
    color: {Cor.TEXTO};
}}
QDockWidget::title {{
    background: {Cor.CARTAO};
    border-bottom: 1px solid {Cor.BORDA};
    padding: 8px 10px;
    font-weight: 700;
}}

/* Árvore do docker Objetos (dockers_corel.py) — sem isso o fundo fica
   branco nativo com o texto claro do tema escuro por cima. */
QTreeWidget {{
    background: {Cor.CAMPO};
    color: {Cor.TEXTO};
    border: 1px solid {Cor.BORDA};
    border-radius: 6px;
}}
QTreeWidget::item {{
    padding: 3px 2px;
}}
QTreeWidget::item:selected {{
    background: {Cor.PRIMARIA};
    color: {Cor.BRANCO};
}}

/* Sem isso, o viewport de dentro de um QScrollArea (ex.: o dock de
   propriedades do mockup, ver main_window.py) pinta com a cor de fundo
   padrão do estilo nativo do Qt em vez de acompanhar o tema. */
QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}

QScrollBar:vertical, QScrollBar:horizontal {{
    background: transparent;
    border: none;
}}
QScrollBar::handle {{
    background: {Cor.BORDA_FORTE};
    border-radius: 4px;
}}
QScrollBar::handle:hover {{
    background: {Cor.TEXTO_SECUNDARIO};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    height: 0px;
    width: 0px;
}}
/* Sem isso o Qt pinta a área vazia da barra com um pontilhado (o
   "xadrezinho" em volta do desenho). */
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}
QScrollBar:vertical {{
    width: 10px;
}}
QScrollBar:horizontal {{
    height: 10px;
}}

/* Texto selecionado em QUALQUER campo de texto (os campos da barra de
   propriedades, nomes, buscas): marcado com o tom de seleção do tema. */
QLineEdit, QAbstractSpinBox, QTextEdit, QPlainTextEdit {{
    selection-background-color: {Cor.SELECAO};
    selection-color: {Cor.TEXTO};
}}
QAbstractItemView {{
    selection-background-color: {Cor.SELECAO};
    selection-color: {Cor.TEXTO};
}}

/* Divisória entre o painel da esquerda e o desenho: discreta no tema
   (o padrão do Qt era uma faixa clara no tema escuro). */
QSplitter::handle {{
    background: {Cor.BORDA};
}}
QSplitter::handle:hover {{
    background: {Cor.PRIMARIA};
}}

/* ── Áreas específicas (ver main_window.py) ─────────────────────── */
QWidget#painelEsquerdo, QWidget#painelDireito {{
    background: {Cor.FUNDO_JANELA};
}}
/* "Medidas geradas/ajustáveis" é uma tabela densa de números, não um
   formulário — o padding generoso do QGroupBox padrão (pensado pros
   cartões da esquerda) só faz ela ocupar mais altura do que precisa,
   sobrando menos espaço pro canvas. */
QGroupBox#grupoMedidasGeradas {{
    padding: 6px 8px 6px 8px;
    margin-top: 10px;
}}
/* Cartão de cada trecho (Riscador/Impressora) dentro de "Medidas
   geradas" — ver `LinhaTrechos` em segmented_row.py. Fundo um tom
   diferente do cartão pai só pra separar visualmente as duas linhas
   sem precisar de um rótulo de seção numa linha própria (era assim
   antes: título acima, campos embaixo — duas linhas em vez de uma). */
QWidget#linhaTrechos {{
    background: {Cor.FUNDO_JANELA};
    border: 1px solid {Cor.BORDA};
    border-radius: 8px;
}}
QLabel#tituloSecao {{
    font-weight: 700;
    font-size: 13px;
    color: {Cor.TEXTO};
}}
QLabel#legendaMuted {{
    color: {Cor.TEXTO_SECUNDARIO};
}}

/* ── Moldura do redesign (REDESIGN.md 2.1, ver moldura.py) ─────────── */
QWidget#barraTitulo {{
    background: {Cor.CARTAO};
    border-bottom: 1px solid {Cor.BORDA};
}}
QMenuBar#menusTitulo {{
    background: transparent;
    border: none;
    padding: 0;
}}
QMenuBar#menusTitulo::item {{
    color: {Cor.TEXTO_SECUNDARIO};
    padding: 5px 8px;
    border-radius: 6px;
}}
QMenuBar#menusTitulo::item:selected {{
    background: {Cor.ELEVADO};
    color: {Cor.TEXTO};
}}
QLabel#rotuloProjeto {{
    color: {Cor.TEXTO};
    font-weight: 600;
}}
QLabel#pontoAlterado {{
    color: {Cor.PRIMARIA};
    font-size: 10px;
}}
QFrame#divisoriaTitulo, QFrame#divisoriaStatus {{
    background: {Cor.BORDA};
    border: none;
}}
/* Seletor central Dieline | Layout | 3D: segmentado, não abas de pasta. */
QTabBar#seletorTela {{
    background: {Cor.FUNDO_JANELA};
    border: 1px solid {Cor.BORDA};
    border-radius: 8px;
}}
QTabBar#seletorTela::tab {{
    background: transparent;
    color: {Cor.TEXTO_SECUNDARIO};
    border: none;
    border-radius: 6px;
    padding: 5px 16px;
    margin: 3px 1px;
    font-weight: 600;
}}
QTabBar#seletorTela::tab:selected {{
    background: {Cor.CAMPO};
    color: {Cor.TEXTO};
}}
QTabBar#seletorTela::tab:hover:!selected {{
    color: {Cor.TEXTO};
}}
QToolButton#botaoTitulo {{
    background: transparent;
    border: none;
    border-radius: 7px;
    padding: 6px;
}}
QToolButton#botaoTitulo:hover {{
    background: {Cor.ELEVADO};
}}
QWidget#barraTitulo QPushButton[primario="true"] {{
    padding: 6px 16px;
}}

/* Barra de contexto (44 px): opções da ferramenta ativa. */
QToolBar#barraContexto {{
    background: {Cor.CARTAO};
    border-bottom: 1px solid {Cor.BORDA};
    padding: 0 10px;
    spacing: 6px;
}}
QToolBar#barraContexto QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 5px 8px;
}}
QToolBar#barraContexto QToolButton:hover {{
    background: {Cor.ELEVADO};
    border-color: {Cor.BORDA_FORTE};
}}
QToolBar#barraContexto QLabel {{
    color: {Cor.TEXTO_SECUNDARIO};
}}

/* Coluna de ferramentas vertical (56 px, botões 40 × 40). */
QToolBar#colunaFerramentas {{
    background: {Cor.CARTAO};
    border: none;
    border-right: 1px solid {Cor.BORDA};
    padding: 8px 7px;
    spacing: 4px;
}}
QToolBar#colunaFerramentas QToolButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    min-width: 40px;
    max-width: 40px;
    min-height: 40px;
    max-height: 40px;
    padding: 0;
}}
QToolBar#colunaFerramentas QToolButton:hover {{
    background: {Cor.ELEVADO};
}}
QToolBar#colunaFerramentas QToolButton:checked {{
    background: {Cor.PRIMARIA_CLARA};
}}
QToolBar#colunaFerramentas QToolButton::menu-indicator {{
    image: none;  /* o flyout desenha o próprio triângulo no canto (ver BotaoFlyout) */
}}
QToolBar#colunaFerramentas::separator:vertical {{
    background: {Cor.BORDA};
    height: 1px;
    margin: 6px 4px;
}}

/* Barra de status (30 px). */
QStatusBar QToolButton#botaoStatus, QStatusBar QPushButton#botaoStatus {{
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 2px 8px;
    color: {Cor.TEXTO_SECUNDARIO};
    font-weight: 500;
}}
QStatusBar QToolButton#botaoStatus:hover, QStatusBar QPushButton#botaoStatus:hover {{
    background: {Cor.ELEVADO};
    color: {Cor.TEXTO};
}}
QStatusBar QToolButton#botaoStatus:checked {{
    color: {Cor.PRIMARIA};
}}
QStatusBar QToolButton#botaoStatus[popupMode="1"] {{
    padding-right: 18px;
}}
QStatusBar QToolButton#botaoStatus::menu-button {{
    border: none;
    width: 16px;
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}}
QStatusBar QToolButton#botaoStatus::menu-button:hover {{
    background: {Cor.BORDA_FORTE};
}}
QStatusBar QToolButton#botaoStatus::menu-arrow {{
    width: 8px;
    height: 8px;
}}
QLabel#textoStatus {{
    color: {Cor.TEXTO_SECUNDARIO};
}}

/* Diálogo Exportar (dialogo_exportar.py). */
QWidget#cabecalhoDialogo {{
    border-bottom: 1px solid {Cor.BORDA};
}}
QWidget#rodapeDialogo {{
    background: {Cor.FUNDO_JANELA};
    border-top: 1px solid {Cor.BORDA};
}}
QWidget#navDestinos {{
    background: {Cor.CARTAO};
    border-right: 1px solid {Cor.BORDA};
}}
QLabel#rotuloGrupoDestino {{
    color: {Cor.TEXTO_SECUNDARIO};
    font-size: 12px;
    font-weight: 600;
    padding: 10px 8px 4px 8px;
}}
QFrame#divisoriaDestinos {{
    background: {Cor.BORDA};
    margin: 8px 4px;
}}
QPushButton#botaoDestino {{
    text-align: left;
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px;
    font-weight: 500;
}}
QPushButton#botaoDestino:hover {{
    background: {Cor.ELEVADO};
    color: {Cor.TEXTO};
}}
QPushButton#botaoDestino:checked {{
    background: {Cor.CAMPO};
    border: none;
    color: {Cor.TEXTO};
    font-weight: 600;
}}
/* A prévia mostra o arquivo de produção: mesa cinza do canvas, fixa. */
QLabel#areaPrevia {{
    background: #E3E3E1;
    color: #4E555C;
    border-radius: 10px;
}}
QLabel#tituloTela {{
    color: {Cor.TEXTO};
}}
"""
