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

## Rebranding "Autoline" (nome de trabalho, ver `dossie_projeto.html`)

Paleta Carvão/Kraft/Tinta/Osso — kraft é a cor da própria chapa de
papelão, tinta é a cor de correção/atenção (`ERRO`), o resto é
neutro quente em vez de cinza puro. Vem do mesmo material que já foi
usado pra propor o rebranding (`autoline-rebranding.html`), adaptado
pro sistema de tokens que já existia aqui.

Kraft (`#C79A5D`) é um tom médio: contra fundo escuro (Carvão) só
funciona bem como TEXTO se for a versão clara; contra fundo claro
(Osso) só funciona bem como texto se for a versão escura — por isso
`PRIMARIA` não é o mesmo hex nos dois temas (tema escuro usa o kraft
"puro"/claro, tema claro usa o kraft escuro), e por isso `BRANCO`
(cor de texto sobre um botão preenchido com `PRIMARIA`) também
inverte: carvão escuro sobre o kraft claro do tema escuro, osso claro
sobre o kraft escuro do tema claro. Contraste calculado (WCAG) pra
cada combinação antes de fechar os valores, não só "parece bom".

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
    "PRIMARIA": "#8C6A3B",  # kraft escuro — kraft "puro" não tem contraste suficiente como texto sobre fundo claro
    "PRIMARIA_HOVER": "#6B4F2A",
    "PRIMARIA_ATIVA": "#4F3A1E",
    "PRIMARIA_CLARA": "#F0E2C8",
    "PRIMARIA_PRESSIONADA": "#E6D2AC",
    "TEXTO": "#1E1A16",  # carvão
    "TEXTO_SECUNDARIO": "#8C6A3B",  # kraft escuro
    "TEXTO_TERCIARIO": "#A8916D",
    "BRANCO": "#F5F0E6",  # osso 2 — texto claro sobre o kraft escuro de PRIMARIA
    "CAMPO": "#FBF8F1",
    "CARTAO": "#F5F0E6",  # osso 2
    "FUNDO_JANELA": "#EAE1CC",
    "BORDA": "#DBD6CD",
    "BORDA_FORTE": "#CAC5BC",
    "ERRO": "#C1432A",  # tinta
    "CANVAS_FUNDO_RGB": (250, 246, 237),
    "CANVAS_GRADE_RGBA": (30, 26, 22, 14),
    "PAINEL_FLUTUANTE_RGBA": (250, 246, 237, 235),
}

_PALETA_ESCURA = {
    "PRIMARIA": "#C79A5D",  # kraft
    "PRIMARIA_HOVER": "#E7C68C",  # kraft claro
    "PRIMARIA_ATIVA": "#F0DDB0",
    "PRIMARIA_CLARA": "#3A2F20",
    "PRIMARIA_PRESSIONADA": "#2F2519",
    "TEXTO": "#EDE6D8",  # osso
    "TEXTO_SECUNDARIO": "#B9AF9C",  # osso dim
    "TEXTO_TERCIARIO": "#8C8270",
    "BRANCO": "#1E1A16",  # carvão — texto escuro sobre o kraft claro de PRIMARIA
    "CAMPO": "#3A3025",
    "CARTAO": "#26201A",  # carvão 2
    "FUNDO_JANELA": "#1E1A16",  # carvão
    "BORDA": "#3A3629",
    "BORDA_FORTE": "#585349",
    "ERRO": "#C1432A",  # tinta
    "CANVAS_FUNDO_RGB": (30, 26, 22),
    "CANVAS_GRADE_RGBA": (237, 230, 216, 16),
    "PAINEL_FLUTUANTE_RGBA": (38, 32, 26, 235),
}

_PALETAS = {configuracoes.TEMA_CLARO: _PALETA_CLARA, configuracoes.TEMA_ESCURO: _PALETA_ESCURA}


class Cor:
    """Paleta do tema ativo — atributos preenchidos logo abaixo a partir
    de `_PALETAS`. Ver docstring do módulo pra por que trocar de tema
    exige reiniciar o app."""


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
FONTE_DISPLAY = "Big Shoulders Stencil"  # só a marca — ver QLabel#rotuloMarca

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
QComboBox, QDoubleSpinBox {{
    background: {Cor.CAMPO};
    border: 1.5px solid {Cor.BORDA_FORTE};
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 22px;
    selection-background-color: {Cor.PRIMARIA_CLARA};
    selection-color: {Cor.TEXTO};
}}
QComboBox:hover, QDoubleSpinBox:hover {{
    border-color: {Cor.BORDA_FORTE};
}}
QComboBox:focus, QDoubleSpinBox:focus {{
    border: 1.5px solid {Cor.PRIMARIA};
}}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background: {Cor.CAMPO};
    border: 1px solid {Cor.BORDA};
    selection-background-color: {Cor.PRIMARIA_CLARA};
    selection-color: {Cor.TEXTO};
    outline: none;
}}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 16px;
    border: none;
}}

/* ── Botões ──────────────────────────────────────────────────────── */
QPushButton {{
    background: {Cor.CAMPO};
    border: 1px solid {Cor.BORDA};
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
    background: {Cor.CARTAO};
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
"""
