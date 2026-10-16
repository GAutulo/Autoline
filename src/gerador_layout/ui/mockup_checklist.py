"""Checklist de cores do produto — "quadradinho + nome" pra empresa marcar
na própria caixa qual variação do produto foi embalada ali (ex.: uma mesa
que existe em preto/branco/cinza).

Funciona como uma CAIXA DE TEXTO de checklist (como um texto de parágrafo
do CorelDRAW): fonte, tamanho em pontos e negrito de verdade, e os itens se
organizam sozinhos dentro da caixa —

- **empilhado**: um embaixo do outro;
- **lado a lado**: em linha, quebrando pra baixo quando não cabem na largura.

Puxar a largura da caixa reorganiza os itens (a letra não estica); puxar
um canto aumenta/diminui a letra. A altura sempre acompanha o conteúdo.
Duplo clique edita direto no desenho: cada linha é uma cor, Enter cria a
próxima, apagar a linha tira a cor.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QGuiApplication, QPainter, QPen

from ..models import CorImpressao
from .mockup_itens import Alca, ElementoMockup, desenhar_texto_escalado

_PIXELS_REFERENCIA = 400.0  # fonte de referência (1 em) — medido grande e escalado
_MM_POR_PONTO = 25.4 / 72.0
_PISCAR_MS = 530
_COR_SELECAO_TEXTO = QColor(0, 120, 215, 70)

EMPILHADO = "empilhado"
LADO_A_LADO = "lado_a_lado"
DISPOSICOES = {EMPILHADO: "Empilhado", LADO_A_LADO: "Lado a lado"}


class ElementoChecklistCores(ElementoMockup):
    def __init__(
        self,
        variantes: list[str] | None = None,
        fonte_familia: str = "Arial",
        cor_tinta: CorImpressao | None = None,
        tamanho_pt: float = 12.0,
        negrito: bool = False,
        disposicao: str = EMPILHADO,
        largura_letra: float = 1.0,
        parent=None,
    ) -> None:
        super().__init__(largura=30.0, altura=6.0, parent=parent)
        # Largura das letras em relação à normal (0,667 = meio esticada, o
        # padrão da máquina); a altura vem do tamanho em pontos.
        self._largura_letra = max(0.05, float(largura_letra))
        self._variantes = list(variantes) if variantes else ["Cor 1", "Cor 2"]
        self._fonte_familia = fonte_familia
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)
        self._tamanho_pt = max(0.5, float(tamanho_pt))
        self._negrito = bool(negrito)
        self._disposicao = disposicao if disposicao in DISPOSICOES else EMPILHADO
        # edição direto no desenho
        self._editando = False
        self._cursor = 0
        self._ancora: int | None = None
        self._cursor_visivel = True
        self._piscar: QTimer | None = None
        self._estado_antes: tuple | None = None
        self._pt_no_inicio_arrasto = self._tamanho_pt
        self.ao_terminar_edicao = None  # (elemento, antes, depois, era_novo) — o canvas registra o desfazer
        self._ajustar_ao_conteudo(largura_natural=True)

    # ── Propriedades ────────────────────────────────────────────────
    @property
    def variantes(self) -> list[str]:
        return list(self._variantes)

    def definir_variantes(self, variantes: list[str]) -> None:
        self._variantes = list(variantes) if variantes else ["Cor 1"]
        self._ajustar_ao_conteudo()

    def adicionar_variante(self, nome: str) -> None:
        self._variantes.append(nome)
        self._ajustar_ao_conteudo()

    def remover_variante(self, indice: int) -> bool:
        """Nunca deixa a lista vazia (a última variante fica)."""
        if len(self._variantes) > 1 and 0 <= indice < len(self._variantes):
            self._variantes.pop(indice)
            self._ajustar_ao_conteudo()
            return True
        return False

    @property
    def fonte_familia(self) -> str:
        return self._fonte_familia

    def definir_fonte(self, familia: str) -> None:
        self._fonte_familia = familia
        self._ajustar_ao_conteudo()

    @property
    def tamanho_pt(self) -> float:
        return self._tamanho_pt

    def definir_tamanho_pt(self, pt: float) -> None:
        self._tamanho_pt = max(0.5, float(pt))
        self._ajustar_ao_conteudo()

    @property
    def largura_letra(self) -> float:
        return self._largura_letra

    def definir_largura_letra(self, largura: float) -> None:
        self._largura_letra = max(0.05, float(largura))
        self._ajustar_ao_conteudo(largura_natural=self._disposicao == EMPILHADO)
        self.update()

    @property
    def altura_letra_mm(self) -> float:
        """Altura da maiúscula, em mm."""
        m = self._medidas()
        return (m["metrica"].capHeight() or m["metrica"].ascent() * 0.7) * m["escala"]

    def definir_altura_letra_mm(self, altura_mm: float) -> None:
        """Tamanho em pontos que dá esta altura de maiúscula."""
        metrica = QFontMetricsF(self._fonte_referencia())
        cap = metrica.capHeight() or metrica.ascent() * 0.7
        self.definir_tamanho_pt(max(0.05, altura_mm) * _PIXELS_REFERENCIA / cap / _MM_POR_PONTO)

    @property
    def negrito(self) -> bool:
        return self._negrito

    def definir_negrito(self, negrito: bool) -> None:
        self._negrito = bool(negrito)
        self._ajustar_ao_conteudo()

    @property
    def disposicao(self) -> str:
        return self._disposicao

    def definir_disposicao(self, disposicao: str) -> None:
        if disposicao not in DISPOSICOES:
            return
        self._disposicao = disposicao
        # Trocou o arranjo: a caixa volta pro tamanho natural dele (todos
        # numa coluna, ou todos numa linha só).
        self._ajustar_ao_conteudo(largura_natural=True)

    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    # ── Medidas e arranjo ────────────────────────────────────────────
    def _fonte_referencia(self) -> QFont:
        fonte = QFont(self._fonte_familia)
        fonte.setPixelSize(int(_PIXELS_REFERENCIA))
        fonte.setBold(self._negrito)
        return fonte

    def _medidas(self) -> dict:
        """Tudo em mm a partir do tamanho da letra em pontos."""
        em = self._tamanho_pt * _MM_POR_PONTO
        escala = em / _PIXELS_REFERENCIA  # mm por pixel da fonte de referência
        metrica = QFontMetricsF(self._fonte_referencia())
        maiuscula = (metrica.capHeight() or metrica.ascent() * 0.7) * escala
        return {
            "em": em,
            "escala": escala,
            "metrica": metrica,
            "lado": maiuscula * 1.15,  # quadradinho ~ altura da maiúscula
            "linha": em * 1.45,
            "espaco_caixa": em * 0.4,
            "espaco_itens": em * 1.1,
            "traco": max(0.05, maiuscula * 0.09),
        }

    def _largura_item(self, texto: str, m: dict) -> float:
        return m["lado"] + m["espaco_caixa"] + m["metrica"].horizontalAdvance(texto) * m["escala"] * self._largura_letra

    def itens_layout(self, largura_caixa: float | None = None) -> tuple[list[dict], float, float]:
        """Posição de cada item (em mm, local): `caixa` (o quadradinho),
        `base` (origem da linha de base do texto), `texto`, `escala` da fonte
        de referência e `largura` do item — e o tamanho total (largura,
        altura) do conteúdo. Usado pela pintura, pela edição e pelo envio ao
        CorelDRAW (uma conta só)."""
        m = self._medidas()
        largura_caixa = self._largura if largura_caixa is None else largura_caixa
        itens, x, y, largura_total = [], 0.0, 0.0, 0.0
        for indice, texto in enumerate(self._variantes):
            largura = self._largura_item(texto, m)
            if self._disposicao == LADO_A_LADO and x > 0 and x + largura > largura_caixa + 1e-6:
                x, y = 0.0, y + m["linha"]  # não cabe: próxima linha
            topo_caixa = y + (m["linha"] - m["lado"]) / 2
            caixa = QRectF(x, topo_caixa, m["lado"], m["lado"])
            base = QPointF(x + m["lado"] + m["espaco_caixa"], caixa.bottom())
            itens.append({"indice": indice, "caixa": caixa, "base": base, "texto": texto, "largura": largura, "linha_y": y})
            largura_total = max(largura_total, x + largura)
            if self._disposicao == LADO_A_LADO:
                x += largura + m["espaco_itens"]
            else:
                y += m["linha"]
        altura_total = (max((i["linha_y"] for i in itens), default=0.0) + m["linha"]) if itens else m["linha"]
        return itens, max(largura_total, m["lado"]), altura_total

    def _largura_minima_conteudo(self) -> float:
        """O item mais largo tem que caber (senão ele sairia da caixa)."""
        m = self._medidas()
        return max((self._largura_item(t, m) for t in self._variantes), default=m["lado"])

    def _ajustar_ao_conteudo(self, largura_natural: bool = False) -> None:
        """Altura = a do conteúdo. Largura: a natural do arranjo (uma
        coluna / uma linha só) ou a atual, nunca menor que o item mais
        largo."""
        if largura_natural:
            _itens, largura, _altura = self.itens_layout(largura_caixa=float("inf"))
        else:
            largura = self._largura
        largura = max(largura, self._largura_minima_conteudo())
        _itens, _l, altura = self.itens_layout(largura_caixa=largura)
        ElementoMockup.definir_tamanho(self, largura, altura)

    def definir_tamanho(self, largura: float, altura: float) -> None:
        """A largura vem de quem chama (campo L, alça); a altura é sempre a
        do conteúdo — a caixa nunca corta nem sobra."""
        largura = max(largura, self._largura_minima_conteudo())
        _itens, _l, altura_conteudo = self.itens_layout(largura_caixa=largura)
        ElementoMockup.definir_tamanho(self, largura, altura_conteudo)

    # Desfazer de geometria: o tamanho da letra vai junto (um canto puxado
    # muda a letra).
    def _estado_geometria(self) -> tuple:
        return super()._estado_geometria() + (self._tamanho_pt,)

    def _aplicar_estado_extra(self, tamanho_pt: float) -> None:
        self._tamanho_pt = max(0.5, float(tamanho_pt))

    # ── Redimensionar pelas alças ────────────────────────────────────
    def _redimensionar_para(self, ponto_cena: QPointF, modificadores=Qt.KeyboardModifier.NoModifier) -> None:
        super()._redimensionar_para(ponto_cena, modificadores)
        canto = self._alca_ativa in (Alca.SUPERIOR_ESQUERDA, Alca.SUPERIOR_DIREITA, Alca.INFERIOR_ESQUERDA, Alca.INFERIOR_DIREITA)
        if canto and self._arrasto_largura_inicial:
            # Canto: a letra acompanha (como escalar um texto no Corel).
            self._tamanho_pt = max(0.5, self._pt_no_inicio_arrasto * self._largura / self._arrasto_largura_inicial)
        self.definir_tamanho(self._largura, self._altura)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._editando:
            if QRectF(0, 0, self._largura, self._altura).contains(event.pos()):
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
        self._pt_no_inicio_arrasto = self._tamanho_pt
        super().mousePressEvent(event)

    # ── Edição direto no desenho ─────────────────────────────────────
    @property
    def editando(self) -> bool:
        return self._editando

    def _buffer(self) -> str:
        return "\n".join(self._variantes)

    def estado_texto(self) -> tuple:
        return (self._buffer(), self._tamanho_pt, self._fonte_familia, self._negrito, self._disposicao, self._largura)

    def definir_estado_texto(self, estado: tuple) -> None:
        texto, pt, fonte, negrito, disposicao, largura = estado
        self._variantes = texto.split("\n") if texto else ["Cor 1"]
        self._tamanho_pt, self._fonte_familia, self._negrito, self._disposicao = pt, fonte, negrito, disposicao
        self.definir_tamanho(largura, self._altura)
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if not self._editando:
            self.iniciar_edicao(event.pos())
            event.accept()
            return
        # editando: duplo clique seleciona a linha (a cor) inteira
        linha, _coluna = self._linha_coluna(self._cursor)
        inicio = sum(len(t) + 1 for t in self._variantes[:linha])
        self._ancora, self._cursor = inicio, inicio + len(self._variantes[linha])
        self.update()

    def iniciar_edicao(self, ponto_local: QPointF | None = None) -> None:
        if self._editando or self.scene() is None:
            return
        self._estado_antes = self.estado_texto()
        self._editando = True
        self._ancora = None
        self._cursor = self._indice_no_ponto(ponto_local) if ponto_local is not None else len(self._buffer())
        self.definir_alcas_visiveis(False)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if self._piscar is None:
            self._piscar = QTimer()
            self._piscar.setInterval(_PISCAR_MS)
            self._piscar.timeout.connect(self._alternar_cursor)
        self._cursor_visivel = True
        self._piscar.start()
        self.update()

    def terminar_edicao(self) -> None:
        if not self._editando:
            return
        self._editando = False
        self._ancora = None
        if self._piscar is not None:
            self._piscar.stop()
        # Linhas vazias não viram cor (Enter a mais no fim, por exemplo).
        cheias = [t for t in self._variantes if t.strip()]
        self._variantes = cheias or [""]
        self._ajustar_ao_conteudo()
        self.definir_alcas_visiveis(True)
        self.clearFocus()
        antes, depois = self._estado_antes, self.estado_texto()
        self._estado_antes = None
        if not cheias:
            self._variantes = ["Cor 1"]  # (o canvas apaga o checklist vazio; desfazer volta o de antes)
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

    def _linha_coluna(self, indice: int) -> tuple[int, int]:
        antes = self._buffer()[:indice]
        return antes.count("\n"), indice - (antes.rfind("\n") + 1)

    def _indice(self, linha: int, coluna: int) -> int:
        linha = max(0, min(linha, len(self._variantes) - 1))
        return sum(len(t) + 1 for t in self._variantes[:linha]) + max(0, min(coluna, len(self._variantes[linha])))

    def _x_da_coluna(self, item: dict, coluna: int, m: dict) -> float:
        return item["base"].x() + m["metrica"].horizontalAdvance(item["texto"][:coluna]) * m["escala"] * self._largura_letra

    def _indice_no_ponto(self, ponto: QPointF) -> int:
        m = self._medidas()
        itens, _l, _a = self.itens_layout()
        if not itens:
            return 0
        # o item cuja linha está mais perto (e, em lado a lado, o da faixa em x)
        def distancia(item):
            linha_meio = item["linha_y"] + m["linha"] / 2
            fora_x = 0.0 if item["caixa"].left() <= ponto.x() <= item["caixa"].left() + item["largura"] else min(
                abs(ponto.x() - item["caixa"].left()), abs(ponto.x() - item["caixa"].left() - item["largura"])
            )
            return (abs(ponto.y() - linha_meio), fora_x)

        item = min(itens, key=distancia)
        melhor, menor = 0, float("inf")
        for coluna in range(len(item["texto"]) + 1):
            d = abs(self._x_da_coluna(item, coluna, m) - ponto.x())
            if d < menor:
                melhor, menor = coluna, d
        return self._indice(item["indice"], melhor)

    def _selecao(self) -> tuple[int, int] | None:
        if self._ancora is None or self._ancora == self._cursor:
            return None
        return min(self._ancora, self._cursor), max(self._ancora, self._cursor)

    def _inserir(self, texto: str) -> None:
        buffer = self._buffer()
        selecao = self._selecao()
        inicio, fim = selecao if selecao else (self._cursor, self._cursor)
        novo = buffer[:inicio] + texto + buffer[fim:]
        self._variantes = novo.split("\n")
        self._cursor = inicio + len(texto)
        self._ancora = None
        self._ajustar_ao_conteudo()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if not self._editando:
            super().keyPressEvent(event)
            return
        tecla = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        buffer = self._buffer()
        self._cursor_visivel = True
        if tecla == Qt.Key.Key_Escape:
            self.terminar_edicao()
        elif ctrl and tecla == Qt.Key.Key_A:
            self._ancora, self._cursor = 0, len(buffer)
        elif ctrl and tecla in (Qt.Key.Key_C, Qt.Key.Key_X):
            selecao = self._selecao()
            if selecao:
                QGuiApplication.clipboard().setText(buffer[selecao[0] : selecao[1]])
                if tecla == Qt.Key.Key_X:
                    self._inserir("")
        elif ctrl and tecla == Qt.Key.Key_V:
            self._inserir(QGuiApplication.clipboard().text().replace("\r\n", "\n").replace("\r", "\n"))
        elif tecla in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._inserir("\n")  # nova cor
        elif tecla == Qt.Key.Key_Backspace:
            if self._selecao() is None and self._cursor > 0:
                self._ancora = self._cursor - 1
            self._inserir("")
        elif tecla == Qt.Key.Key_Delete:
            if self._selecao() is None and self._cursor < len(buffer):
                self._ancora = self._cursor + 1
            self._inserir("")
        elif tecla in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_Up, Qt.Key.Key_Down):
            if shift and self._ancora is None:
                self._ancora = self._cursor
            elif not shift:
                self._ancora = None
            linha, coluna = self._linha_coluna(self._cursor)
            if tecla == Qt.Key.Key_Left:
                self._cursor = max(0, self._cursor - 1)
            elif tecla == Qt.Key.Key_Right:
                self._cursor = min(len(buffer), self._cursor + 1)
            elif tecla == Qt.Key.Key_Home:
                self._cursor = self._indice(linha, 0)
            elif tecla == Qt.Key.Key_End:
                self._cursor = self._indice(linha, len(self._variantes[linha]))
            elif tecla == Qt.Key.Key_Up:
                self._cursor = self._indice(linha - 1, coluna) if linha > 0 else 0
            else:
                self._cursor = self._indice(linha + 1, coluna) if linha < len(self._variantes) - 1 else len(buffer)
        elif event.text() and event.text().isprintable() and not ctrl:
            self._inserir(event.text())
        else:
            super().keyPressEvent(event)
            return
        self.update()
        event.accept()

    # ── Pintura ──────────────────────────────────────────────────────
    def _pintar_conteudo(self, painter: QPainter) -> None:
        m = self._medidas()
        itens, _l, _a = self.itens_layout()
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        fonte = self._fonte_referencia()
        selecao = self._selecao() if self._editando else None
        inicio_linha = 0
        for item in itens:
            texto = item["texto"]
            if selecao is not None:
                a, b = max(selecao[0], inicio_linha), min(selecao[1], inicio_linha + len(texto))
                if a < b or (selecao[0] <= inicio_linha + len(texto) < selecao[1]):
                    x0 = self._x_da_coluna(item, a - inicio_linha, m)
                    x1 = self._x_da_coluna(item, max(a, b) - inicio_linha, m) + (m["em"] * 0.3 if b < selecao[1] else 0)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(_COR_SELECAO_TEXTO)
                    painter.drawRect(QRectF(QPointF(x0, item["linha_y"]), QPointF(x1, item["linha_y"] + m["linha"])))
            painter.setPen(QPen(cor, m["traco"]))
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            meio_traco = m["traco"] / 2
            painter.drawRect(item["caixa"].adjusted(meio_traco, meio_traco, -meio_traco, -meio_traco))
            if texto:
                painter.save()
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(cor))
                painter.translate(item["base"])
                painter.scale(m["escala"] * self._largura_letra, m["escala"])
                desenhar_texto_escalado(painter, QPointF(0, 0), fonte, texto)
                painter.restore()
            inicio_linha += len(texto) + 1
        if self._editando and self._cursor_visivel and itens:
            linha, coluna = self._linha_coluna(self._cursor)
            item = itens[min(linha, len(itens) - 1)]
            x = self._x_da_coluna(item, coluna, m)
            caneta = QPen(QColor(20, 20, 20), 1.6)
            caneta.setCosmetic(True)
            painter.setPen(caneta)
            painter.drawLine(QPointF(x, item["caixa"].top() - m["em"] * 0.1), QPointF(x, item["base"].y() + m["em"] * 0.2))

    def clonar(self) -> "ElementoChecklistCores":
        novo = ElementoChecklistCores(
            variantes=self._variantes,
            fonte_familia=self._fonte_familia,
            cor_tinta=self._cor_tinta,
            tamanho_pt=self._tamanho_pt,
            negrito=self._negrito,
            disposicao=self._disposicao,
            largura_letra=self._largura_letra,
        )
        self._copiar_geometria_para(novo)
        novo.definir_tamanho(self._largura, self._altura)
        return novo
