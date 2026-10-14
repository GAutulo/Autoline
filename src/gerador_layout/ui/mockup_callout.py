"""Callout (linha de chamada com texto) — anotação técnica de revisão,
tipo "aqui precisa de sangria" ou "cor Pantone tal", apontando pra perto
de onde está. A "geometria" (largura × altura, mover/redimensionar/
rotacionar) é sempre só a caixa de texto — a cauda sai sempre do canto
inferior-esquerdo dela numa direção fixa (como um balão de fala), não é
um segundo ponto de controle independente: isso mantém o callout
compatível com o mesmo motor de mover/redimensionar/rotacionar/snap que
todo outro elemento usa, sem precisar de um caso especial.

Edição de texto: digitada direto no balão, como o texto do CorelDRAW
(sem caixa por cima) — ver `iniciar_edicao`.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QPainterPath, QPen

from ..models import CorImpressao
from .mockup_itens import ElementoMockup, desenhar_texto_escalado

_LARGURA_PADRAO_MM = 45.0
_ALTURA_PADRAO_MM = 16.0
_TAMANHO_FONTE_REFERENCIA_PT = 200.0
_COMPRIMENTO_CAUDA_MM = 9.0
_RAIO_CANTO_MM = 2.0
_MARGEM_MM = 3.0
_PISCAR_MS = 530


class ElementoCallout(ElementoMockup):
    def __init__(
        self,
        texto: str = "Observação",
        cor_tinta: CorImpressao | None = None,
        parent=None,
    ) -> None:
        super().__init__(largura=_LARGURA_PADRAO_MM, altura=_ALTURA_PADRAO_MM, parent=parent)
        self._texto = texto or " "
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)
        self._editando = False
        self._cursor = 0
        self._ancora: int | None = None
        self._cursor_visivel = True
        self._piscar: QTimer | None = None
        self._estado_antes: tuple | None = None
        # Chamado ao terminar a edição: (callout, antes, depois, era_novo) —
        # o canvas registra o desfazer (mesmo contrato do ElementoTexto).
        self.ao_terminar_edicao = None

    @property
    def texto(self) -> str:
        return self._texto

    def definir_texto(self, texto: str) -> None:
        self._texto = texto or " "
        self.update()

    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    # ── Edição direto no balão (como o texto do CorelDRAW) ─────────────
    # Sem caixa de texto por cima: digita no próprio balão, com cursor
    # piscando e seleção; o balão cresce/encolhe com o texto. Enter ou Esc
    # terminam; clicar fora também.
    @property
    def editando(self) -> bool:
        return self._editando

    def estado_texto(self) -> tuple:
        return (self._texto, self._largura)

    def definir_estado_texto(self, estado: tuple) -> None:
        texto, largura = estado
        self._texto = texto or " "
        self.definir_largura(largura)
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if not self._editando:
            self.iniciar_edicao(event.pos())
            event.accept()
            return
        self._ancora, self._cursor = 0, len(self._texto)  # duplo clique editando: tudo
        self.update()

    def iniciar_edicao(self, ponto_local: QPointF | None = None, selecionar_tudo: bool = False) -> None:
        if self._editando or self.scene() is None:
            return
        self._estado_antes = (self._texto, self._largura)
        if self._texto == " ":
            self._texto = ""
        self._editando = True
        if selecionar_tudo:
            self._ancora, self._cursor = 0, len(self._texto)
        else:
            self._ancora = None
            self._cursor = self._indice_no_x(ponto_local.x()) if ponto_local is not None else len(self._texto)
        self.definir_alcas_visiveis(False)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if self._piscar is None:
            self._piscar = QTimer()
            self._piscar.setInterval(_PISCAR_MS)
            self._piscar.timeout.connect(self._alternar_cursor)
        self._cursor_visivel = True
        self._piscar.start()
        self.update()

    # Callout recém-criado já entra digitando, com o texto padrão
    # selecionado (digitar substitui).
    def iniciar_edicao_inline(self) -> None:
        self.iniciar_edicao(selecionar_tudo=True)

    def terminar_edicao(self) -> None:
        if not self._editando:
            return
        self._editando = False
        self._ancora = None
        if self._piscar is not None:
            self._piscar.stop()
        self.definir_alcas_visiveis(True)
        self.clearFocus()
        antes, depois = self._estado_antes, (self._texto, self._largura)
        self._estado_antes = None
        if not self._texto:
            self._texto = " "
        self.update()
        if self.ao_terminar_edicao is not None:
            self.ao_terminar_edicao(self, antes, depois, False)

    def _alternar_cursor(self) -> None:
        self._cursor_visivel = not self._cursor_visivel
        self.update()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        if self._editando and event.reason() != Qt.FocusReason.PopupFocusReason:
            self.terminar_edicao()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._editando:
            if QRectF(0, 0, self._largura, self._altura).contains(event.pos()):
                # Clique dentro do balão em edição: move o cursor (Shift seleciona).
                indice = self._indice_no_x(event.pos().x())
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    if self._ancora is None:
                        self._ancora = self._cursor
                else:
                    self._ancora = None
                self._cursor = indice
                self._cursor_visivel = True
                self.update()
                event.accept()
                return
            self.terminar_edicao()
        super().mousePressEvent(event)

    def _selecao(self) -> tuple[int, int] | None:
        if self._ancora is None or self._ancora == self._cursor:
            return None
        return min(self._ancora, self._cursor), max(self._ancora, self._cursor)

    def _inserir(self, texto: str) -> None:
        selecao = self._selecao()
        inicio, fim = selecao if selecao else (self._cursor, self._cursor)
        self._texto = self._texto[:inicio] + texto + self._texto[fim:]
        self._cursor = inicio + len(texto)
        self._ancora = None
        self._ajustar_largura_ao_texto()

    def _ajustar_largura_ao_texto(self) -> None:
        """O balão acompanha o texto digitado, na altura atual."""
        _fonte, metrica, _alt, escala = self._medidas_texto(sem_limite=True)
        largura = metrica.horizontalAdvance(self._texto or "M") * escala + _MARGEM_MM * 2
        self.definir_largura(max(self._altura * 1.5, largura))

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if not self._editando:
            super().keyPressEvent(event)
            return
        tecla = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        self._cursor_visivel = True
        if tecla in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.terminar_edicao()
        elif ctrl and tecla == Qt.Key.Key_A:
            self._ancora, self._cursor = 0, len(self._texto)
        elif ctrl and tecla in (Qt.Key.Key_C, Qt.Key.Key_X):
            selecao = self._selecao()
            if selecao:
                QGuiApplication.clipboard().setText(self._texto[selecao[0] : selecao[1]])
                if tecla == Qt.Key.Key_X:
                    self._inserir("")
        elif ctrl and tecla == Qt.Key.Key_V:
            self._inserir(" ".join(QGuiApplication.clipboard().text().splitlines()))
        elif tecla == Qt.Key.Key_Backspace:
            if self._selecao() is None and self._cursor > 0:
                self._ancora = self._cursor - 1
            self._inserir("")
        elif tecla == Qt.Key.Key_Delete:
            if self._selecao() is None and self._cursor < len(self._texto):
                self._ancora = self._cursor + 1
            self._inserir("")
        elif tecla in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End):
            if shift and self._ancora is None:
                self._ancora = self._cursor
            elif not shift:
                self._ancora = None
            if tecla == Qt.Key.Key_Left:
                self._cursor = max(0, self._cursor - 1)
            elif tecla == Qt.Key.Key_Right:
                self._cursor = min(len(self._texto), self._cursor + 1)
            elif tecla == Qt.Key.Key_Home:
                self._cursor = 0
            else:
                self._cursor = len(self._texto)
        elif event.text() and event.text().isprintable() and not ctrl:
            self._inserir(event.text())
        else:
            super().keyPressEvent(event)
            return
        self.update()
        event.accept()

    def _x_do_indice(self, indice: int) -> float:
        _fonte, metrica, _alt, escala = self._medidas_texto()
        return _MARGEM_MM + metrica.horizontalAdvance(self._texto[:indice]) * escala

    def _indice_no_x(self, x: float) -> int:
        melhor, menor = 0, float("inf")
        for i in range(len(self._texto) + 1):
            d = abs(self._x_do_indice(i) - x)
            if d < menor:
                melhor, menor = i, d
        return melhor

    # ── Pintura ──────────────────────────────────────────────────────
    def _medidas_texto(self, sem_limite: bool = False):
        """(fonte de referência, métrica, altura de referência, escala): a
        altura das maiúsculas ocupa a caixa menos as margens; se o texto
        não cabe na largura (balão estreitado à mão), encolhe. Fonte de
        referência grande, como no resto do app — evita rasterização ruim
        em fonte pequena."""
        fonte_ref = QFont()
        fonte_ref.setPointSizeF(_TAMANHO_FONTE_REFERENCIA_PT)
        metrica = QFontMetricsF(fonte_ref)
        altura_ref = metrica.capHeight() or metrica.ascent()
        altura_disponivel = max(1.0, self._altura - _MARGEM_MM * 2)
        escala = altura_disponivel / altura_ref if altura_ref else 1.0
        largura_texto_ref = metrica.horizontalAdvance(self._texto) or 1.0
        if not sem_limite and largura_texto_ref * escala > self._largura - _MARGEM_MM * 2:
            escala = max(0.01, (self._largura - _MARGEM_MM * 2) / largura_texto_ref)
        return fonte_ref, metrica, altura_ref, escala

    def _pintar_conteudo(self, painter: QPainter) -> None:
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        painter.setPen(QPen(cor, 0.4))
        painter.setBrush(QBrush(QColor(255, 255, 255, 235)))

        caminho = QPainterPath()
        caminho.addRoundedRect(QRectF(0, 0, self._largura, self._altura), _RAIO_CANTO_MM, _RAIO_CANTO_MM)
        # Cauda saindo do canto inferior-esquerdo, apontando pra fora —
        # mesmo ângulo (225°, sudoeste) não importa o tamanho da caixa,
        # pra sempre ler como "isso aqui aponta pra baixo-esquerda de
        # onde a caixa está", igual um balão de fala.
        base_x, base_y = self._largura * 0.18, self._altura
        ponta = QPointF(base_x - _COMPRIMENTO_CAUDA_MM * 0.75, base_y + _COMPRIMENTO_CAUDA_MM * 0.75)
        cauda = QPainterPath()
        cauda.moveTo(base_x, base_y)
        cauda.lineTo(ponta)
        cauda.lineTo(base_x + _RAIO_CANTO_MM * 2.2, base_y)
        cauda.closeSubpath()
        caminho = caminho.united(cauda)
        painter.drawPath(caminho)

        # Ponto de referência na ponta da cauda — deixa claro que é ISSO
        # que está sendo apontado, não só uma decoração.
        painter.setBrush(QBrush(cor))
        painter.drawEllipse(ponta, 1.0, 1.0)

        fonte_ref, _metrica, altura_ref, escala = self._medidas_texto()
        topo = (self._altura - altura_ref * escala) / 2
        alto, baixo = topo - altura_ref * escala * 0.25, topo + altura_ref * escala * 1.25
        selecao = self._selecao() if self._editando else None
        if selecao is not None:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 120, 215, 70))
            painter.drawRect(QRectF(QPointF(self._x_do_indice(selecao[0]), alto), QPointF(self._x_do_indice(selecao[1]), baixo)))
        if self._texto.strip():
            painter.save()
            painter.setPen(QPen(cor))
            painter.translate(_MARGEM_MM, topo)
            painter.scale(escala, escala)
            desenhar_texto_escalado(painter, QPointF(0, altura_ref), fonte_ref, self._texto)
            painter.restore()
        if self._editando and self._cursor_visivel:
            x = self._x_do_indice(self._cursor)
            caneta = QPen(QColor(20, 20, 20), 1.6)
            caneta.setCosmetic(True)  # cursor fino na tela em qualquer zoom
            painter.setPen(caneta)
            painter.drawLine(QPointF(x, alto), QPointF(x, baixo))

    def clonar(self) -> "ElementoCallout":
        novo = ElementoCallout(texto=self._texto, cor_tinta=self._cor_tinta)
        self._copiar_geometria_para(novo)
        return novo
