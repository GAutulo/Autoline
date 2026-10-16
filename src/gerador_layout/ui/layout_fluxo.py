"""Layout em fluxo: os itens lado a lado, quebrando pra linha de baixo quando
não cabem — como a barra de propriedades do CorelDRAW numa tela estreita.
Sem isso, a barra (que muda de tamanho a cada seleção) obrigava a janela a
ser mais larga que a tela e o fim dela (e a paleta da direita) sumia."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QSpacerItem, QWidget


class LayoutFluxo(QLayout):
    def __init__(self, pai: QWidget | None = None, espaco: int = 5) -> None:
        super().__init__(pai)
        self._itens: list[QLayoutItem] = []
        self._espaco = espaco
        self.setContentsMargins(0, 0, 0, 0)

    # ── API de QLayout ───────────────────────────────────────────────
    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._itens.append(item)

    def addSpacing(self, largura: int) -> None:  # noqa: N802 (mesmo nome do QBoxLayout)
        self.addItem(QSpacerItem(largura, 1, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))

    def count(self) -> int:
        return len(self._itens)

    def itemAt(self, indice: int) -> QLayoutItem | None:  # noqa: N802
        return self._itens[indice] if 0 <= indice < len(self._itens) else None

    def takeAt(self, indice: int) -> QLayoutItem | None:  # noqa: N802
        return self._itens.pop(indice) if 0 <= indice < len(self._itens) else None

    def setSpacing(self, espaco: int) -> None:  # noqa: N802
        self._espaco = espaco
        self.invalidate()

    def spacing(self) -> int:
        return self._espaco

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, largura: int) -> int:  # noqa: N802
        return self._arrumar(QRect(0, 0, largura, 0), so_medir=True)

    def setGeometry(self, retangulo: QRect) -> None:  # noqa: N802
        super().setGeometry(retangulo)
        self._arrumar(retangulo, so_medir=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        """Tudo numa linha só (o tamanho que a barra pede quando cabe)."""
        largura, altura = 0, 0
        visiveis = [i for i in self._itens if not i.isEmpty()]
        for k, item in enumerate(visiveis):
            tamanho = item.sizeHint()
            largura += tamanho.width() + (self._espaco if k else 0)
            altura = max(altura, tamanho.height())
        m = self.contentsMargins()
        return QSize(largura + m.left() + m.right(), altura + m.top() + m.bottom())

    def minimumSize(self) -> QSize:  # noqa: N802
        """O maior item sozinho: a janela pode ficar tão estreita quanto ele."""
        tamanho = QSize()
        for item in self._itens:
            if not item.isEmpty():
                tamanho = tamanho.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        return tamanho + QSize(m.left() + m.right(), m.top() + m.bottom())

    # ── Arrumação ────────────────────────────────────────────────────
    def _arrumar(self, retangulo: QRect, so_medir: bool) -> int:
        m = self.contentsMargins()
        area = retangulo.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y = area.x(), area.y()
        altura_linha = 0
        linha: list[tuple[QLayoutItem, QSize]] = []
        itens_na_linha = 0

        def assentar(itens, topo, altura):
            # Centraliza cada item na altura da linha (campos e botões de alturas diferentes).
            for item, tamanho in itens:
                geo = item.geometry()
                item.setGeometry(QRect(QPoint(geo.x(), topo + (altura - tamanho.height()) // 2), tamanho))

        for item in self._itens:
            if item.isEmpty():
                continue
            tamanho = item.sizeHint()
            proximo_x = x + tamanho.width()
            if itens_na_linha and proximo_x > area.right() + 1:
                if not so_medir:
                    assentar(linha, y, altura_linha)
                x = area.x()
                y += altura_linha + self._espaco
                altura_linha = 0
                linha = []
                itens_na_linha = 0
                proximo_x = x + tamanho.width()
            if not so_medir:
                item.setGeometry(QRect(QPoint(x, y), tamanho))
                linha.append((item, tamanho))
            itens_na_linha += 1
            x = proximo_x + self._espaco
            altura_linha = max(altura_linha, tamanho.height())
        if not so_medir and linha:
            assentar(linha, y, altura_linha)
        return y + altura_linha - retangulo.y() + m.bottom()
