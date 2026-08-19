"""Elemento de imagem (PNG/raster) do mockup — import posicionável e
redimensionável. Mover, redimensionar e rotacionar vêm do motor em
`mockup_itens.py`; redimensionar aqui estica a imagem pra caber
exatamente na caixa, sem travar proporção — mesma lógica de qualquer
outro elemento (puxar um canto só distorce se os dois eixos não
crescerem na mesma razão, igual num editor vetorial comum; travar
proporção fica pra quando existir um painel de propriedades de verdade).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPixmap

from .mockup_itens import ElementoMockup

_LARGURA_PADRAO_MM = 40.0


class ElementoImagem(ElementoMockup):
    def __init__(self, caminho_arquivo: str, parent=None) -> None:
        pixmap = QPixmap(caminho_arquivo)
        if pixmap.isNull():
            raise ValueError(f"Não consegui abrir a imagem: {caminho_arquivo}")

        largura, altura = _tamanho_inicial_mm(pixmap)
        super().__init__(largura=largura, altura=altura, parent=parent)
        self._caminho_arquivo = caminho_arquivo
        self._pixmap = pixmap

    @property
    def caminho_arquivo(self) -> str:
        return self._caminho_arquivo

    def _pintar_conteudo(self, painter: QPainter) -> None:
        painter.drawPixmap(QRectF(0, 0, self._largura, self._altura), self._pixmap, QRectF(self._pixmap.rect()))


def _tamanho_inicial_mm(pixmap: QPixmap) -> tuple[float, float]:
    """Sempre abre numa largura padrão, mantendo a proporção real do
    pixel — nada de tentar adivinhar o tamanho físico pelo DPI embutido
    no arquivo: na prática o `QImage` do Qt sempre relata *algum* DPI
    (96 por padrão, mesmo quando o arquivo nunca teve isso definido de
    propósito — confirmado testando direto), então esse metadado não é
    confiável pra decidir tamanho. O usuário ajusta o tamanho de
    verdade arrastando, como qualquer outro elemento."""
    proporcao = pixmap.height() / pixmap.width() if pixmap.width() else 1.0
    return _LARGURA_PADRAO_MM, _LARGURA_PADRAO_MM * proporcao
