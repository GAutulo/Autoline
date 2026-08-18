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

# Cada dict é um tema completo. `BRANCO` é sempre branco/quase-branco em
# ambos — é usado só como cor de TEXTO sobre o acento (botão primário,
# "Total"), não como fundo, então não faz sentido escurecer no tema
# escuro. `CAMPO` é o fundo dos elementos interativos (campo de texto,
# combobox, indicador de checkbox) — no claro é branco puro pra
# contrastar com o cartão cinza-claro; no escuro precisa ser MAIS CLARO
# que o cartão (não mais escuro) pra manter o mesmo princípio de
# contraste "isso aqui é uma superfície interativa".
_PALETA_CLARA = {
    "PRIMARIA": "#2f6fed",
    "PRIMARIA_HOVER": "#2559c4",
    "PRIMARIA_ATIVA": "#1d47a0",
    "PRIMARIA_CLARA": "#e3ebfc",
    "PRIMARIA_PRESSIONADA": "#d9e6fc",
    "TEXTO": "#1a1d29",
    "TEXTO_SECUNDARIO": "#5b6069",
    "TEXTO_TERCIARIO": "#8b909a",
    "BRANCO": "#ffffff",
    "CAMPO": "#ffffff",
    "CARTAO": "#eef0f3",
    "FUNDO_JANELA": "#dde0e5",
    "BORDA": "#c4c9d0",
    "BORDA_FORTE": "#9aa0ab",
    "ERRO": "#d64545",
    "CANVAS_FUNDO_RGB": (247, 248, 250),
    "CANVAS_GRADE_RGBA": (0, 0, 0, 14),
    "PAINEL_FLUTUANTE_RGBA": (255, 255, 255, 235),
}

_PALETA_ESCURA = {
    "PRIMARIA": "#5b8def",
    "PRIMARIA_HOVER": "#79a4f2",
    "PRIMARIA_ATIVA": "#9dbdf6",
    "PRIMARIA_CLARA": "#26314a",
    "PRIMARIA_PRESSIONADA": "#1c2538",
    "TEXTO": "#e8eaed",
    "TEXTO_SECUNDARIO": "#a4aab5",
    "TEXTO_TERCIARIO": "#6e7480",
    "BRANCO": "#ffffff",
    "CAMPO": "#2c303a",
    "CARTAO": "#22252b",
    "FUNDO_JANELA": "#17181c",
    "BORDA": "#383c44",
    "BORDA_FORTE": "#525863",
    "ERRO": "#e5807a",
    "CANVAS_FUNDO_RGB": (28, 30, 35),
    "CANVAS_GRADE_RGBA": (255, 255, 255, 18),
    "PAINEL_FLUTUANTE_RGBA": (34, 37, 43, 235),
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


FONTE_FAMILIA = "Segoe UI"

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
