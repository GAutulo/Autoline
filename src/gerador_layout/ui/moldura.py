"""Moldura da janela do redesign (REDESIGN.md, seção 2.1): barra de título
e barra de status. Só a "casca" em volta do trabalho — quem preenche e
liga as ações é a `JanelaPrincipal`; nada aqui muda o que o programa faz.

- Barra de título (48 px): símbolo, menus, nome do projeto (● âmbar se não
  salvo), seletor central Dieline | Layout | 3D, Desfazer / Refazer e o
  botão primário Exportar.
- Barra de status (30 px): cursor em mm, encaixe, guias dinâmicas, ponte
  CorelDRAW (ponto cinza/verde + texto), Ajustar à tela e zoom.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenuBar,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QStyle,
    QStyleOption,
    QTabBar,
    QToolButton,
    QToolTip,
    QWidget,
)

from .estilo import Cor
from .marca import AssinaturaMarca

ALTURA_TITULO = 48
ALTURA_CONTEXTO = 44
ALTURA_STATUS = 30
LARGURA_COLUNA_FERRAMENTAS = 56


class BarraTitulo(QWidget):
    """A barra de cima. O seletor central é o próprio `QTabBar` das telas
    (mesmos nomes Dieline / Layout / 3D), só com outro visual."""

    def __init__(self, menus: QMenuBar, seletor: QTabBar, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("barraTitulo")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(ALTURA_TITULO)

        grade = QGridLayout(self)
        grade.setContentsMargins(12, 0, 12, 0)
        grade.setHorizontalSpacing(12)

        esquerda = QWidget()
        linha_esq = QHBoxLayout(esquerda)
        linha_esq.setContentsMargins(0, 0, 0, 0)
        linha_esq.setSpacing(10)
        self.simbolo = AssinaturaMarca(altura=24, so_simbolo=True)
        linha_esq.addWidget(self.simbolo)
        menus.setObjectName("menusTitulo")
        menus.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        linha_esq.addWidget(menus)
        separador = QFrame()
        separador.setObjectName("divisoriaTitulo")
        separador.setFixedSize(1, 18)
        linha_esq.addWidget(separador)
        self.rotulo_projeto = QLabel("Sem título")
        self.rotulo_projeto.setObjectName("rotuloProjeto")
        linha_esq.addWidget(self.rotulo_projeto)
        self.ponto_alterado = QLabel("●")
        self.ponto_alterado.setObjectName("pontoAlterado")
        self.ponto_alterado.setToolTip("Alterações não salvas")
        self.ponto_alterado.setVisible(False)
        linha_esq.addWidget(self.ponto_alterado)
        linha_esq.addStretch(1)

        seletor.setObjectName("seletorTela")
        seletor.setDrawBase(False)
        seletor.setExpanding(False)

        direita = QWidget()
        linha_dir = QHBoxLayout(direita)
        linha_dir.setContentsMargins(0, 0, 0, 0)
        linha_dir.setSpacing(4)
        linha_dir.addStretch(1)
        self.botao_desfazer = QToolButton()
        self.botao_desfazer.setObjectName("botaoTitulo")
        self.botao_desfazer.setToolTip("Desfazer (Ctrl+Z)")
        self.botao_refazer = QToolButton()
        self.botao_refazer.setObjectName("botaoTitulo")
        self.botao_refazer.setToolTip("Refazer (Ctrl+Shift+Z)")
        linha_dir.addWidget(self.botao_desfazer)
        linha_dir.addWidget(self.botao_refazer)
        linha_dir.addSpacing(8)
        self.botao_exportar = QPushButton("Exportar")
        self.botao_exportar.setProperty("primario", True)
        self.botao_exportar.setToolTip("PDF, SVG, JPG, folha de aprovação, imagem do 3D, salvar tudo, CorelDRAW")
        linha_dir.addWidget(self.botao_exportar)

        # Três colunas: as das pontas esticam igual, então o seletor fica no
        # meio da JANELA (não no meio do que sobra entre esquerda e direita).
        grade.addWidget(esquerda, 0, 0)
        grade.addWidget(seletor, 0, 1, Qt.AlignmentFlag.AlignCenter)
        grade.addWidget(direita, 0, 2)
        grade.setColumnStretch(0, 1)
        grade.setColumnStretch(2, 1)

    def definir_projeto(self, nome: str, alterado: bool) -> None:
        self.rotulo_projeto.setText(nome)
        self.rotulo_projeto.setToolTip(nome)
        self.ponto_alterado.setVisible(alterado)


class PonteCorel(QWidget):
    """Ponto cinza (desligado) ou verde (conectado) + texto."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        linha = QHBoxLayout(self)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(5)
        self._ponto = QLabel("●")
        self._texto = QLabel()
        self._texto.setObjectName("textoStatus")
        linha.addWidget(self._ponto)
        linha.addWidget(self._texto)
        self.definir_conectado(False)

    def definir_conectado(self, conectado: bool) -> None:
        self.conectado = conectado
        self._ponto.setStyleSheet(f"color: {'#3FB27F' if conectado else Cor.TEXTO_TERCIARIO};")
        self._texto.setText("CorelDRAW conectado" if conectado else "CorelDRAW desligado")
        self.setToolTip(
            "Ponte com o CorelDRAW: Exportar → Enviar para o CorelDRAW" if conectado
            else "Ponte com o CorelDRAW desligada — conecta sozinha ao enviar (Exportar → Enviar para o CorelDRAW)"
        )


class BarraStatus(QStatusBar):
    """Barra de status que corta a mensagem com "…" quando não cabe (a do
    Qt só decepa a frase, ex. "Envoltório fechamento r") e mostra a frase
    inteira na dica ao passar o mouse."""

    def _area_mensagem(self) -> QRect:
        # Como o Qt: da margem esquerda até o 1º item permanente visível —
        # ou até onde ele começa a ter texto, se a frente dele é lugar
        # reservado em branco (`inicio_do_conteudo`, ex. o `PainelStatus`).
        direita = self.width() - 12
        for filho in self.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
            if filho.isVisible() and not filho.isWindow():
                inicio = getattr(filho, "inicio_do_conteudo", None)
                direita = min(direita, filho.x() + (inicio() if inicio else 0) - 2)
        return QRect(6, 0, max(0, direita - 6), self.height())

    def _mensagem_visivel(self) -> str:
        area = self._area_mensagem()
        return self.fontMetrics().elidedText(self.currentMessage(), Qt.TextElideMode.ElideRight, area.width())

    def paintEvent(self, evento) -> None:  # noqa: N802 - API do Qt
        pintor = QPainter(self)
        opcao = QStyleOption()
        opcao.initFrom(self)
        self.style().drawPrimitive(QStyle.PrimitiveElement.PE_PanelStatusBar, opcao, pintor, self)
        if self.currentMessage():
            pintor.setPen(self.palette().windowText().color())
            pintor.drawText(
                self._area_mensagem(),
                Qt.AlignmentFlag.AlignLeading | Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextSingleLine,
                self._mensagem_visivel(),
            )

    def event(self, evento) -> bool:  # noqa: N802 - API do Qt
        if evento.type() == QEvent.Type.ToolTip:
            mensagem = self.currentMessage()
            if (
                mensagem
                and self._area_mensagem().contains(evento.pos())
                and self._mensagem_visivel() != mensagem
            ):
                QToolTip.showText(evento.globalPos(), mensagem, self)
            else:
                QToolTip.hideText()
            return True
        return super().event(evento)


def divisoria_status() -> QFrame:
    linha = QFrame()
    linha.setObjectName("divisoriaStatus")
    linha.setFixedSize(1, 16)
    return linha
