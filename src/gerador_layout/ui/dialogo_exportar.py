"""Diálogo único "Exportar" (REDESIGN.md, seção 2.2).

Só REORGANIZA as exportações que já existem: cada destino chama a mesma
função de antes (o mesmo arquivo sai, as mesmas perguntas de onde salvar
aparecem). A folha de aprovação abre o diálogo dela, sem mudança.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .marca import TituloTela


@dataclass
class Destino:
    chave: str
    grupo: str
    sigla: str  # o "selo" à esquerda (PDF, SVG…) ou um símbolo curto
    titulo: str
    descricao: str
    rotulo_botao: str
    acao: Callable[[], object]
    com_previa: bool = False  # mostra a prévia do layout (arquivos de produção)


class DialogoExportar(QDialog):
    def __init__(self, destinos: list[Destino], previa: Callable[[], QImage | None] | None = None, parent=None,
                 inicial: str = "pdf") -> None:
        super().__init__(parent)
        self.setObjectName("dialogoExportar")
        self.setWindowTitle("Exportar")
        self.resize(900, 560)
        self._destinos = {d.chave: d for d in destinos}
        self._previa = previa
        self._imagem_previa: QImage | None = None
        self.escolhido: Destino | None = None

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        titulo = TituloTela("Exportar", 20)
        cabecalho = QWidget()
        cabecalho.setObjectName("cabecalhoDialogo")
        linha_cab = QHBoxLayout(cabecalho)
        linha_cab.setContentsMargins(20, 14, 20, 14)
        linha_cab.addWidget(titulo)
        raiz.addWidget(cabecalho)

        corpo = QHBoxLayout()
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.setSpacing(0)
        raiz.addLayout(corpo, 1)

        navegacao = QWidget()
        navegacao.setObjectName("navDestinos")
        navegacao.setFixedWidth(290)
        coluna = QVBoxLayout(navegacao)
        coluna.setContentsMargins(12, 12, 12, 12)
        coluna.setSpacing(4)
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        self.botoes: dict[str, QPushButton] = {}
        grupo_atual = None
        for destino in destinos:
            if destino.grupo != grupo_atual:
                grupo_atual = destino.grupo
                if destino.grupo:
                    rotulo = QLabel(destino.grupo.upper())
                    rotulo.setObjectName("rotuloGrupoDestino")
                    coluna.addWidget(rotulo)
                else:
                    divisoria = QFrame()
                    divisoria.setObjectName("divisoriaDestinos")
                    divisoria.setFixedHeight(1)
                    coluna.addWidget(divisoria)
            botao = QPushButton(f"{destino.sigla}   {destino.titulo}")
            botao.setObjectName("botaoDestino")
            botao.setCheckable(True)
            botao.setToolTip(destino.descricao)
            botao.clicked.connect(lambda _c=False, ch=destino.chave: self.escolher(ch))
            self._grupo.addButton(botao)
            self.botoes[destino.chave] = botao
            coluna.addWidget(botao)
        coluna.addStretch(1)
        corpo.addWidget(navegacao)

        direita = QWidget()
        coluna_dir = QVBoxLayout(direita)
        coluna_dir.setContentsMargins(20, 20, 20, 20)
        coluna_dir.setSpacing(16)
        self.area_previa = QLabel()
        self.area_previa.setObjectName("areaPrevia")
        self.area_previa.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.area_previa.setMinimumHeight(260)
        self.area_previa.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        coluna_dir.addWidget(self.area_previa, 1)
        self.titulo_destino = QLabel()
        self.titulo_destino.setObjectName("tituloSecao")
        coluna_dir.addWidget(self.titulo_destino)
        self.descricao = QLabel()
        self.descricao.setObjectName("legendaMuted")
        self.descricao.setWordWrap(True)
        coluna_dir.addWidget(self.descricao)
        corpo.addWidget(direita, 1)

        rodape = QWidget()
        rodape.setObjectName("rodapeDialogo")
        linha_rod = QHBoxLayout(rodape)
        linha_rod.setContentsMargins(20, 12, 20, 12)
        linha_rod.addStretch(1)
        cancelar = QPushButton("Cancelar")
        cancelar.clicked.connect(self.reject)
        self.botao_confirmar = QPushButton()
        self.botao_confirmar.setProperty("primario", True)
        self.botao_confirmar.setDefault(True)
        self.botao_confirmar.clicked.connect(self._confirmar)
        linha_rod.addWidget(cancelar)
        linha_rod.addWidget(self.botao_confirmar)
        raiz.addWidget(rodape)

        self.escolher(inicial if inicial in self._destinos else destinos[0].chave)

    def escolher(self, chave: str) -> None:
        destino = self._destinos[chave]
        self._atual = destino
        self.botoes[chave].setChecked(True)
        self.titulo_destino.setText(destino.titulo)
        self.descricao.setText(destino.descricao)
        self.botao_confirmar.setText(destino.rotulo_botao)
        self._mostrar_previa(destino.com_previa)

    def _mostrar_previa(self, com_previa: bool) -> None:
        if com_previa and self._previa is not None and self._imagem_previa is None:
            self._imagem_previa = self._previa()
        if com_previa and self._imagem_previa is not None and not self._imagem_previa.isNull():
            tamanho = self.area_previa.size() if self.area_previa.width() > 50 else QSize(560, 280)
            pixmap = QPixmap.fromImage(self._imagem_previa).scaled(
                tamanho - QSize(24, 24), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            self.area_previa.setPixmap(pixmap)
            self.area_previa.setText("")
        else:
            self.area_previa.setPixmap(QPixmap())
            self.area_previa.setText(self._atual.titulo)

    def resizeEvent(self, evento) -> None:  # noqa: N802
        super().resizeEvent(evento)
        if getattr(self, "_atual", None) is not None:
            self._mostrar_previa(self._atual.com_previa)

    def _confirmar(self) -> None:
        """Fecha primeiro e depois exporta: as perguntas de onde salvar abrem
        sobre a janela principal, como antes."""
        self.escolhido = self._atual
        self.accept()
