"""Texto artístico do mockup, como no CorelDRAW: clicar com a ferramenta
Texto põe o cursor piscando direto no desenho e é só digitar — sem caixa de
edição por cima. Enter quebra linha; setas, Home/End, Backspace/Delete,
Shift+setas (seleção), Ctrl+A/C/V/X funcionam; Esc ou clicar fora termina.
Duplo clique num texto existente edita com o cursor onde clicou.

Tamanho: o texto é escalado pra caber exatamente na caixa (largura ×
altura), igual "texto artístico" do CorelDRAW — arrastar um canto escala,
arrastar um lado estica. Editar o texto mantém o tamanho da letra (as
escalas atuais), e o canto superior esquerdo fica parado. `tamanho_pt` é o
tamanho da fonte em pontos, como na barra do CorelDRAW.

A fonte de referência é desenhada grande (`_PIXELS_REFERENCIA`) e escalada
com `QPainter.scale()` — evita o bug de rasterização/kerning de fonte
pequena (ver `_fonte_e_escala_legenda` em exportacao.py) e o de posição do
`drawText` na exportação SVG (ver `desenhar_texto_escalado`).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QPainterPath, QPen, QTransform

from ..models import CorImpressao
from .mockup_itens import ElementoMockup

_PIXELS_REFERENCIA = 400.0  # tamanho (em px) da fonte de referência: 1 "em"
_MM_POR_PONTO = 25.4 / 72.0
_ALTURA_PADRAO_MM = 8.0
_PISCAR_MS = 530
_COR_SELECAO_TEXTO = QColor(0, 120, 215, 70)


class ElementoTexto(ElementoMockup):
    # Altura é o tamanho do bloco de texto, não "tamanho de uma forma":
    # letra de rodapé em embalagem fica bem abaixo do mínimo genérico.
    _altura_minima_mm = 0.2
    _largura_minima_mm = 0.2

    def __init__(
        self,
        texto: str = "Texto",
        fonte_familia: str = "Arial",
        negrito: bool = False,
        cor_tinta: CorImpressao | None = None,
        parent=None,
    ) -> None:
        super().__init__(largura=10.0, altura=_ALTURA_PADRAO_MM, parent=parent)
        self._texto = texto
        self._fonte_familia = fonte_familia
        self._negrito = negrito
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)
        # Alinhamento das linhas entre si: "esquerda", "centro" ou "direita".
        self._alinhamento = "esquerda"
        # Edição direto no desenho.
        self._editando = False
        self._cursor = len(texto)
        self._ancora: int | None = None  # início da seleção (None = sem seleção)
        self._estado_antes: tuple | None = None
        self._recem_criado = False
        self._cursor_visivel = True
        self._piscar: QTimer | None = None
        # Chamado ao terminar a edição: (elemento, estado_antes, estado_depois,
        # era_novo) — o canvas usa pra desfazer e pra apagar texto vazio.
        self.ao_terminar_edicao = None
        altura_ref = self._medidas_referencia()[0]
        self.definir_tamanho(self._medidas_referencia()[1] * (_ALTURA_PADRAO_MM / altura_ref), _ALTURA_PADRAO_MM)

    # ── Propriedades ────────────────────────────────────────────────
    @property
    def texto(self) -> str:
        return self._texto

    def definir_texto(self, texto: str) -> None:
        self._mudar(lambda: setattr(self, "_texto", texto))
        self._cursor = min(self._cursor, len(self._texto))

    @property
    def fonte_familia(self) -> str:
        return self._fonte_familia

    def definir_fonte(self, familia: str) -> None:
        self._mudar(lambda: setattr(self, "_fonte_familia", familia))

    @property
    def negrito(self) -> bool:
        return self._negrito

    def definir_negrito(self, negrito: bool) -> None:
        self._mudar(lambda: setattr(self, "_negrito", negrito))

    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    @property
    def tamanho_pt(self) -> float:
        """Tamanho da fonte em pontos (altura do "em"), como no CorelDRAW."""
        _ex, ey = self._escalas()
        return ey * _PIXELS_REFERENCIA / _MM_POR_PONTO

    def definir_tamanho_pt(self, pt: float) -> None:
        """Muda o tamanho da letra mantendo a proporção largura/altura das
        letras e o canto superior esquerdo no lugar."""
        ex, ey = self._escalas()
        nova_ey = max(0.01, pt) * _MM_POR_PONTO / _PIXELS_REFERENCIA
        fator = nova_ey / ey if ey else 1.0
        self._aplicar_escalas(ex * fator, nova_ey)

    # ── Medição (fonte de referência grande) ────────────────────────
    def _fonte_referencia(self) -> QFont:
        fonte = QFont(self._fonte_familia)
        fonte.setPixelSize(int(_PIXELS_REFERENCIA))
        fonte.setBold(self._negrito)
        return fonte

    def _linhas(self) -> list[str]:
        return self._texto.split("\n")

    @property
    def alinhamento(self) -> str:
        return self._alinhamento

    def definir_alinhamento(self, alinhamento: str) -> None:
        """Esquerda, centro ou direita — as linhas se alinham entre si dentro
        do bloco (a caixa do texto não muda de tamanho nem de lugar)."""
        if alinhamento in ("esquerda", "centro", "direita"):
            self._alinhamento = alinhamento
            self.update()

    def _deslocamento_linha(self, linha: int) -> float:
        """Quanto a linha anda pra direita (unidade de referência) pra ficar
        alinhada com a mais larga."""
        if self._alinhamento == "esquerda":
            return 0.0
        metrica = QFontMetricsF(self._fonte_referencia())
        linhas = self._linhas()
        largura_bloco = max((metrica.horizontalAdvance(l) for l in linhas), default=0.0)
        sobra = largura_bloco - metrica.horizontalAdvance(linhas[linha])
        return sobra / 2 if self._alinhamento == "centro" else sobra

    def _medidas_referencia(self) -> tuple[float, float, float, float]:
        """(altura do bloco, largura do bloco, altura das maiúsculas,
        espaço entre linhas) na unidade de referência."""
        metrica = QFontMetricsF(self._fonte_referencia())
        cap = metrica.capHeight() or metrica.ascent()
        entre_linhas = metrica.lineSpacing()
        linhas = self._linhas()
        largura = max((metrica.horizontalAdvance(l) for l in linhas), default=0.0)
        largura = max(largura, cap * 0.05)  # texto vazio ainda tem uma "caixa" mínima
        return cap + (len(linhas) - 1) * entre_linhas, largura, cap, entre_linhas

    def _metrica_referencia(self) -> tuple[float, float]:
        """(altura, largura) de referência — compatibilidade (1 linha)."""
        altura, largura, _cap, _ent = self._medidas_referencia()
        return altura, largura

    def _escalas(self) -> tuple[float, float]:
        altura, largura, _cap, _ent = self._medidas_referencia()
        return (self._largura / largura if largura else 1.0, self._altura / altura if altura else 1.0)

    def _aplicar_escalas(self, ex: float, ey: float) -> None:
        """Novo tamanho a partir das escalas, sem tirar o canto superior
        esquerdo do lugar na cena (a rotação é em torno do centro)."""
        canto = self.mapToScene(QPointF(0.0, 0.0))
        altura, largura, _cap, _ent = self._medidas_referencia()
        self.definir_tamanho(largura * ex, altura * ey)
        self.setPos(self.pos() + (canto - self.mapToScene(QPointF(0.0, 0.0))))
        self.update()

    def _mudar(self, mudanca) -> None:
        """Aplica uma mudança de texto/fonte mantendo o tamanho da letra."""
        ex, ey = self._escalas()
        mudanca()
        self._aplicar_escalas(ex, ey)

    def caminho_local(self) -> QPainterPath:
        """O texto como contorno, nas coordenadas do elemento (pra
        converter em curvas e pra pintar)."""
        _altura, _largura, cap, entre_linhas = self._medidas_referencia()
        fonte = self._fonte_referencia()
        caminho = QPainterPath()
        for k, linha in enumerate(self._linhas()):
            if linha:
                caminho.addText(QPointF(self._deslocamento_linha(k), cap + k * entre_linhas), fonte, linha)
        ex, ey = self._escalas()
        return QTransform.fromScale(ex, ey).map(caminho)

    def clonar(self) -> "ElementoTexto":
        novo = ElementoTexto(
            texto=self._texto, fonte_familia=self._fonte_familia, negrito=self._negrito, cor_tinta=self._cor_tinta
        )
        novo._alinhamento = self._alinhamento
        self._copiar_geometria_para(novo)
        return novo

    # ── Estado pra desfazer ─────────────────────────────────────────
    def estado_texto(self) -> tuple:
        return (self._texto, self._largura, self._altura, QPointF(self.pos()))

    def definir_estado_texto(self, estado: tuple) -> None:
        texto, largura, altura, pos = estado
        self._texto = texto
        self._cursor = min(self._cursor, len(texto))
        self.definir_tamanho(largura, altura)
        self.setPos(pos)
        self.update()

    # ── Edição direto no desenho ────────────────────────────────────
    @property
    def editando(self) -> bool:
        return self._editando

    def iniciar_edicao(self, ponto_local: QPointF | None = None, recem_criado: bool = False) -> None:
        if self._editando or self.scene() is None:
            return
        self._editando = True
        self._recem_criado = recem_criado
        self._estado_antes = self.estado_texto()
        self._cursor = self._indice_no_ponto(ponto_local) if ponto_local is not None else len(self._texto)
        self._ancora = None
        self.definir_alcas_visiveis(False)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if self._piscar is None:
            self._piscar = QTimer()
            self._piscar.setInterval(_PISCAR_MS)
            self._piscar.timeout.connect(self._alternar_cursor)
        self._cursor_visivel = True
        self._piscar.start()
        self.update()

    # Compatibilidade com quem ainda chama o nome antigo.
    def iniciar_edicao_inline(self) -> None:
        self.iniciar_edicao()

    def terminar_edicao(self) -> None:
        if not self._editando:
            return
        self._editando = False
        self._ancora = None
        if self._piscar is not None:
            self._piscar.stop()
        self.definir_alcas_visiveis(True)
        self.clearFocus()
        self.update()
        antes, depois = self._estado_antes, self.estado_texto()
        era_novo = self._recem_criado
        self._estado_antes = None
        self._recem_criado = False
        if self.ao_terminar_edicao is not None:
            self.ao_terminar_edicao(self, antes, depois, era_novo)

    def _alternar_cursor(self) -> None:
        self._cursor_visivel = not self._cursor_visivel
        self.update()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        super().focusOutEvent(event)
        if self._editando and event.reason() != Qt.FocusReason.PopupFocusReason:
            self.terminar_edicao()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._editando:
            if self._contem_corpo(event.pos()):
                # Clique dentro do texto em edição: move o cursor (Shift seleciona).
                indice = self._indice_no_ponto(event.pos())
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

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if not self._editando:
            self.iniciar_edicao(event.pos())
            event.accept()
            return
        # Duplo clique durante a edição: seleciona a palavra.
        inicio, fim = self._palavra_em(self._cursor)
        self._ancora, self._cursor = inicio, fim
        self.update()

    def _palavra_em(self, indice: int) -> tuple[int, int]:
        t = self._texto
        inicio = indice
        while inicio > 0 and not t[inicio - 1].isspace():
            inicio -= 1
        fim = indice
        while fim < len(t) and not t[fim].isspace():
            fim += 1
        return inicio, fim

    def _selecao(self) -> tuple[int, int] | None:
        if self._ancora is None or self._ancora == self._cursor:
            return None
        return min(self._ancora, self._cursor), max(self._ancora, self._cursor)

    def _inserir(self, texto: str) -> None:
        selecao = self._selecao()
        inicio, fim = selecao if selecao else (self._cursor, self._cursor)
        novo = self._texto[:inicio] + texto + self._texto[fim:]
        self._mudar(lambda: setattr(self, "_texto", novo))
        self._cursor = inicio + len(texto)
        self._ancora = None

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if not self._editando:
            super().keyPressEvent(event)
            return
        tecla = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        self._cursor_visivel = True
        if tecla == Qt.Key.Key_Escape:
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
            self._inserir(QGuiApplication.clipboard().text().replace("\r\n", "\n").replace("\r", "\n"))
        elif tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._inserir("\n")
        elif tecla == Qt.Key.Key_Backspace:
            if self._selecao() is None and self._cursor > 0:
                self._ancora = self._cursor - 1
            self._inserir("")
        elif tecla == Qt.Key.Key_Delete:
            if self._selecao() is None and self._cursor < len(self._texto):
                self._ancora = self._cursor + 1
            self._inserir("")
        elif tecla in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_Up, Qt.Key.Key_Down):
            if shift and self._ancora is None:
                self._ancora = self._cursor
            elif not shift:
                self._ancora = None
            self._cursor = self._mover_cursor(tecla, ctrl)
        elif event.text() and event.text().isprintable() and not ctrl:
            self._inserir(event.text())
        else:
            super().keyPressEvent(event)
            return
        self.update()
        event.accept()

    def _linha_coluna(self, indice: int) -> tuple[int, int]:
        antes = self._texto[:indice]
        linha = antes.count("\n")
        return linha, indice - (antes.rfind("\n") + 1)

    def _indice(self, linha: int, coluna: int) -> int:
        linhas = self._linhas()
        linha = max(0, min(linha, len(linhas) - 1))
        coluna = max(0, min(coluna, len(linhas[linha])))
        return sum(len(l) + 1 for l in linhas[:linha]) + coluna

    def _mover_cursor(self, tecla, ctrl: bool) -> int:
        linha, coluna = self._linha_coluna(self._cursor)
        if tecla == Qt.Key.Key_Left:
            if ctrl:
                return self._palavra_em(max(0, self._cursor - 1))[0]
            return max(0, self._cursor - 1)
        if tecla == Qt.Key.Key_Right:
            if ctrl:
                return self._palavra_em(min(len(self._texto), self._cursor + 1))[1]
            return min(len(self._texto), self._cursor + 1)
        if tecla == Qt.Key.Key_Home:
            return 0 if ctrl else self._indice(linha, 0)
        if tecla == Qt.Key.Key_End:
            return len(self._texto) if ctrl else self._indice(linha, len(self._linhas()[linha]))
        x = self._x_da_coluna(linha, coluna)
        destino = linha - 1 if tecla == Qt.Key.Key_Up else linha + 1
        if not (0 <= destino < len(self._linhas())):
            return self._cursor
        return self._indice(destino, self._coluna_do_x(destino, x))

    def _x_da_coluna(self, linha: int, coluna: int) -> float:
        """x (referência) do ponto antes do caractere `coluna` da linha."""
        metrica = QFontMetricsF(self._fonte_referencia())
        return self._deslocamento_linha(linha) + metrica.horizontalAdvance(self._linhas()[linha][:coluna])

    def _coluna_do_x(self, linha: int, x_ref: float) -> int:
        texto = self._linhas()[linha]
        metrica = QFontMetricsF(self._fonte_referencia())
        x_ref -= self._deslocamento_linha(linha)
        melhor, menor = 0, abs(x_ref)
        for k in range(1, len(texto) + 1):
            d = abs(metrica.horizontalAdvance(texto[:k]) - x_ref)
            if d < menor:
                melhor, menor = k, d
        return melhor

    def _indice_no_ponto(self, ponto_local: QPointF) -> int:
        ex, ey = self._escalas()
        _alt, _larg, cap, entre_linhas = self._medidas_referencia()
        y_ref = ponto_local.y() / ey if ey else 0.0
        linha = round((y_ref - cap / 2) / entre_linhas) if entre_linhas else 0
        linha = max(0, min(linha, len(self._linhas()) - 1))
        x_ref = ponto_local.x() / ex if ex else 0.0
        return self._indice(linha, self._coluna_do_x(linha, x_ref))

    # ── Pintura ──────────────────────────────────────────────────────
    def _pintar_conteudo(self, painter: QPainter) -> None:
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        if self._editando:
            self._pintar_selecao_texto(painter)
        # Contorno do texto preenchido (drawPath, não drawText — ver
        # `desenhar_texto_escalado` em mockup_itens.py pro bug do SVG).
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor))
        painter.drawPath(self.caminho_local())
        if self._editando:
            self._pintar_cursor(painter)

    def _caixa_do_trecho(self, linha: int, col_ini: int, col_fim: int) -> QRectF:
        ex, ey = self._escalas()
        _alt, _larg, cap, entre_linhas = self._medidas_referencia()
        topo = (cap + linha * entre_linhas - cap * 1.25) * ey
        x1 = self._x_da_coluna(linha, col_ini) * ex
        x2 = self._x_da_coluna(linha, col_fim) * ex
        return QRectF(QPointF(x1, topo), QPointF(x2, topo + cap * 1.5 * ey))

    def _pintar_selecao_texto(self, painter: QPainter) -> None:
        selecao = self._selecao()
        if selecao is None:
            return
        (l1, c1), (l2, c2) = self._linha_coluna(selecao[0]), self._linha_coluna(selecao[1])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_COR_SELECAO_TEXTO)
        for linha in range(l1, l2 + 1):
            inicio = c1 if linha == l1 else 0
            fim = c2 if linha == l2 else len(self._linhas()[linha])
            painter.drawRect(self._caixa_do_trecho(linha, inicio, fim))

    def _pintar_cursor(self, painter: QPainter) -> None:
        if not self._cursor_visivel:
            return
        linha, coluna = self._linha_coluna(self._cursor)
        caixa = self._caixa_do_trecho(linha, coluna, coluna)
        caneta = QPen(QColor(20, 20, 20), 1.6)
        caneta.setCosmetic(True)  # cursor fino na tela em qualquer zoom
        painter.setPen(caneta)
        painter.drawLine(caixa.topLeft(), caixa.bottomLeft())
