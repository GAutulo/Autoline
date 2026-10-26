"""Tela de Início (REDESIGN.md, seção 2.2): medidas C × L × A + "Criar
faca", a grade de estilos e os projetos recentes com miniatura.

Só um ponto de partida — cada botão chama o que já existe na janela
(tipo de caixa + medidas, catálogo de estilos, faca em branco, construtor,
abrir projeto, galeria de recentes). Quem liga os callbacks é a
`JanelaPrincipal` (`_montar_inicio`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..models import TipoCaixa
from .marca import TituloTela
from .mockup_icones import construir_icone


@dataclass
class Cartao:
    titulo: str
    detalhe: str
    icone: str = ""  # chave de icones_svg (ou "" com `sigla`)
    sigla: str = ""
    tipo: TipoCaixa | None = None  # tipo de caixa: escolhe e depois "Criar faca"
    acao: Callable[[], object] | None = None  # os outros: um clique já faz


class TelaInicio(QWidget):
    def __init__(self, cartoes: list[Cartao], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("telaInicio")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Ligados pela janela.
        self.criar: Callable[[TipoCaixa, float, float, float], object] | None = None
        self.abrir_projeto: Callable[[str | None], object] | None = None
        self.ver_todos: Callable[[], object] | None = None
        self.abrir_configuracoes: Callable[[], object] | None = None
        self.obter_recentes: Callable[[], list[str]] | None = None
        self.ler_miniatura: Callable[[str], QImage | None] | None = None

        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(48, 36, 48, 36)
        raiz.setSpacing(40)

        # ── Nova caixa ──────────────────────────────────────────────
        principal = QVBoxLayout()
        principal.setSpacing(18)
        cabecalho = QHBoxLayout()
        titulos = QVBoxLayout()
        titulos.setSpacing(4)
        titulos.addWidget(TituloTela("Nova caixa", 30))
        subtitulo = QLabel("Escolha o estilo, digite C × L × A e a faca sai pronta. Tudo o mais se ajusta depois.")
        subtitulo.setObjectName("legendaMuted")
        subtitulo.setWordWrap(True)
        titulos.addWidget(subtitulo)
        cabecalho.addLayout(titulos, 1)
        botao_abrir = QPushButton("Abrir projeto…")
        botao_abrir.clicked.connect(lambda: self.abrir_projeto and self.abrir_projeto(None))
        cabecalho.addWidget(botao_abrir, 0, Qt.AlignmentFlag.AlignTop)
        botao_config = QPushButton("Configurações")
        botao_config.clicked.connect(lambda: self.abrir_configuracoes and self.abrir_configuracoes())
        cabecalho.addWidget(botao_config, 0, Qt.AlignmentFlag.AlignTop)
        principal.addLayout(cabecalho)

        medidas = QHBoxLayout()
        medidas.setSpacing(10)
        self.spins: dict[str, QDoubleSpinBox] = {}
        for chave, rotulo, valor in (("c", "Comprimento (C)", 300.0), ("l", "Largura (L)", 200.0), ("a", "Altura (A)", 150.0)):
            coluna = QVBoxLayout()
            coluna.setSpacing(6)
            texto = QLabel(rotulo)
            texto.setObjectName("legendaMuted")
            spin = QDoubleSpinBox()
            spin.setRange(1.0, 10000.0)
            spin.setDecimals(1)
            spin.setSuffix(" mm")
            spin.setValue(valor)
            spin.setMinimumWidth(120)
            spin.setObjectName(f"inicio_{chave}")
            self.spins[chave] = spin
            coluna.addWidget(texto)
            coluna.addWidget(spin)
            medidas.addLayout(coluna)
            if chave != "a":
                vezes = QLabel("×")
                vezes.setObjectName("legendaMuted")
                medidas.addWidget(vezes, 0, Qt.AlignmentFlag.AlignBottom)
        medidas.addStretch(1)
        self.botao_criar = QPushButton("Criar faca")
        self.botao_criar.setProperty("primario", True)
        self.botao_criar.clicked.connect(self._criar)
        medidas.addWidget(self.botao_criar, 0, Qt.AlignmentFlag.AlignBottom)
        principal.addLayout(medidas)

        grade = QGridLayout()
        grade.setSpacing(12)
        self._grupo_tipo = QButtonGroup(self)
        self._grupo_tipo.setExclusive(True)
        self.cartoes: dict[str, QPushButton] = {}
        self._tipo_escolhido: TipoCaixa | None = None
        for i, cartao in enumerate(cartoes):
            botao = QPushButton()
            botao.setObjectName("cartaoEstilo")
            botao.setMinimumHeight(96)
            # Ignored: o texto do cartão não dita a largura mínima da janela.
            botao.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            botao.setMinimumWidth(110)
            botao.setText(f"{cartao.sigla + '   ' if cartao.sigla else ''}{cartao.titulo}\n{cartao.detalhe}")
            if cartao.icone:
                botao.setIcon(construir_icone(cartao.icone))
                botao.setIconSize(QSize(24, 24))
            if cartao.tipo is not None:
                botao.setCheckable(True)
                self._grupo_tipo.addButton(botao)
                botao.clicked.connect(lambda _c=False, t=cartao.tipo: self._escolher_tipo(t))
            elif cartao.acao is not None:
                botao.clicked.connect(cartao.acao)
            self.cartoes[cartao.titulo] = botao
            grade.addWidget(botao, i // 4, i % 4)
        principal.addLayout(grade)
        principal.addStretch(1)
        raiz.addLayout(principal, 3)

        # ── Recentes ────────────────────────────────────────────────
        lateral = QVBoxLayout()
        lateral.setSpacing(12)
        rotulo_recentes = QLabel("Recentes")
        rotulo_recentes.setObjectName("tituloSecao")
        lateral.addWidget(rotulo_recentes)
        self.lista_recentes = QListWidget()
        self.lista_recentes.setObjectName("listaRecentes")
        self.lista_recentes.setViewMode(QListView.ViewMode.ListMode)
        self.lista_recentes.setIconSize(QSize(96, 64))
        self.lista_recentes.setSpacing(4)
        self.lista_recentes.setMinimumWidth(220)
        self.lista_recentes.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.lista_recentes.setWordWrap(False)
        self.lista_recentes.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.lista_recentes.itemClicked.connect(self._abrir_item)
        lateral.addWidget(self.lista_recentes, 1)
        botao_todos = QPushButton("Ver todos com prévia")
        botao_todos.clicked.connect(lambda: self.ver_todos and self.ver_todos())
        lateral.addWidget(botao_todos)
        raiz.addLayout(lateral, 2)

        primeiro = next((c for c in cartoes if c.tipo is not None), None)
        if primeiro is not None:
            self.cartoes[primeiro.titulo].setChecked(True)
            self._tipo_escolhido = primeiro.tipo

    def _escolher_tipo(self, tipo: TipoCaixa) -> None:
        self._tipo_escolhido = tipo

    @property
    def tipo_escolhido(self) -> TipoCaixa | None:
        return self._tipo_escolhido

    def _criar(self) -> None:
        if self.criar is not None and self._tipo_escolhido is not None:
            self.criar(self._tipo_escolhido, self.spins["c"].value(), self.spins["l"].value(), self.spins["a"].value())

    def recarregar_recentes(self) -> None:
        self.lista_recentes.clear()
        caminhos = self.obter_recentes() if self.obter_recentes is not None else []
        for caminho in [c for c in caminhos if Path(c).is_file()][:8]:
            miniatura = self.ler_miniatura(caminho) if self.ler_miniatura is not None else None
            icone = QIcon(QPixmap.fromImage(miniatura)) if miniatura is not None else QIcon()
            item = QListWidgetItem(icone, f"{Path(caminho).stem}\n{Path(caminho).parent}")
            item.setToolTip(caminho)
            item.setData(Qt.ItemDataRole.UserRole, caminho)
            self.lista_recentes.addItem(item)
        if not self.lista_recentes.count():
            vazio = QListWidgetItem("Nenhum projeto recente ainda.")
            vazio.setFlags(Qt.ItemFlag.NoItemFlags)
            self.lista_recentes.addItem(vazio)

    def _abrir_item(self, item: QListWidgetItem) -> None:
        caminho = item.data(Qt.ItemDataRole.UserRole)
        if caminho and self.abrir_projeto is not None:
            self.abrir_projeto(caminho)
