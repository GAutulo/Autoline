"""Tabela do mockup — ficha técnica/nutricional, bem específico de
embalagem de produto (composição, modo de uso, tabela nutricional...).
Célula guarda só texto simples (sem fórmula/formatação por célula, fora
de escopo aqui); editar todas de uma vez por um diálogo (ver
`dialogo_tabela.py`) em vez de clique-a-clique como o texto normal —
com várias células, editar uma de cada vez pelo canvas seria bem mais
lento que preencher tudo numa grade só, que é como se preenche uma
ficha técnica na prática (colar de uma planilha, por exemplo).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPainter, QPen

from ..models import CorImpressao
from .mockup_itens import ElementoMockup, desenhar_texto_escalado

_LARGURA_PADRAO_MM = 70.0
_ALTURA_PADRAO_MM = 45.0
_LINHAS_PADRAO = 4
_COLUNAS_PADRAO = 2
_LIMITE_LINHAS = 20
_LIMITE_COLUNAS = 10
_TAMANHO_FONTE_REFERENCIA_PT = 100.0


class ElementoTabela(ElementoMockup):
    def __init__(
        self,
        linhas: int = _LINHAS_PADRAO,
        colunas: int = _COLUNAS_PADRAO,
        celulas: list[list[str]] | None = None,
        cor_tinta: CorImpressao | None = None,
        fonte_familia: str = "",
        altura_letra_mm: float | None = None,
        largura_letra: float = 1.0,
        parent=None,
    ) -> None:
        super().__init__(largura=_LARGURA_PADRAO_MM, altura=_ALTURA_PADRAO_MM, parent=parent)
        # Letra: fonte ("" = a padrão do sistema, como era antes), altura da
        # maiúscula em mm (None = a maior que cabe na célula, como era antes)
        # e largura (0,667 = meio esticada, o padrão da máquina).
        self._fonte_familia = fonte_familia
        self._altura_letra_mm = altura_letra_mm if altura_letra_mm and altura_letra_mm > 0 else None
        self._largura_letra = max(0.05, float(largura_letra))
        self._linhas = max(1, min(_LIMITE_LINHAS, linhas))
        self._colunas = max(1, min(_LIMITE_COLUNAS, colunas))
        self._celulas = self._normalizar_celulas(celulas)
        self._cor_tinta = cor_tinta or CorImpressao(nome="Preto", r=0, g=0, b=0)

    def _normalizar_celulas(self, celulas: list[list[str]] | None) -> list[list[str]]:
        base = celulas or []
        return [
            [
                (base[l][c] if l < len(base) and c < len(base[l]) else "")
                for c in range(self._colunas)
            ]
            for l in range(self._linhas)
        ]

    @property
    def linhas(self) -> int:
        return self._linhas

    @property
    def colunas(self) -> int:
        return self._colunas

    @property
    def celulas(self) -> list[list[str]]:
        return [linha.copy() for linha in self._celulas]

    def definir_dimensoes(self, linhas: int, colunas: int) -> None:
        """Muda o número de linhas/colunas preservando o conteúdo que já
        existia nas células que continuam existindo — só descarta o que
        ficou fora da nova grade (encolher) ou nasce vazio (crescer)."""
        self._linhas = max(1, min(_LIMITE_LINHAS, linhas))
        self._colunas = max(1, min(_LIMITE_COLUNAS, colunas))
        self._celulas = self._normalizar_celulas(self._celulas)
        self.update()

    def definir_celula(self, linha: int, coluna: int, texto: str) -> None:
        if 0 <= linha < self._linhas and 0 <= coluna < self._colunas:
            self._celulas[linha][coluna] = texto
            self.update()

    def definir_celulas(self, celulas: list[list[str]]) -> None:
        self._celulas = self._normalizar_celulas(celulas)
        self.update()

    @property
    def fonte_familia(self) -> str:
        return self._fonte_familia

    def definir_fonte(self, familia: str) -> None:
        self._fonte_familia = familia
        self.update()

    @property
    def altura_letra_mm(self) -> float | None:
        return self._altura_letra_mm

    def definir_altura_letra_mm(self, mm: float | None) -> None:
        self._altura_letra_mm = mm if mm and mm > 0 else None
        self.update()

    @property
    def largura_letra(self) -> float:
        return self._largura_letra

    def definir_largura_letra(self, largura: float) -> None:
        self._largura_letra = max(0.05, float(largura))
        self.update()

    def _fonte_ref(self, negrito: bool) -> QFont:
        fonte = QFont(self._fonte_familia) if self._fonte_familia else QFont()
        fonte.setPointSizeF(_TAMANHO_FONTE_REFERENCIA_PT)
        fonte.setBold(negrito)
        return fonte

    def textos_layout(self) -> list[dict]:
        """Cada texto com a posição final (mm, local): `x`, `base` (linha de
        base), `largura`, `altura` (da maiúscula), `escala_x`/`escala_y` da
        fonte de referência e `negrito`. Uma conta só pra tela e Corel."""
        largura_celula = self._largura / self._colunas
        altura_celula = self._altura / self._linhas
        metrica = QFontMetricsF(self._fonte_ref(False))
        metrica_negrito = QFontMetricsF(self._fonte_ref(True))
        altura_ref = metrica.capHeight() or metrica.ascent()
        margem = min(largura_celula, altura_celula) * 0.12
        largura_disponivel = largura_celula - margem * 2
        if self._altura_letra_mm is not None:
            # Altura fixa (padrão da máquina): não encolhe pra caber.
            escala_y = self._altura_letra_mm / altura_ref if altura_ref else 1.0
        else:
            # UMA escala só pra tabela inteira — nunca por célula (texto curto
            # saía maior que o longo ao lado). Negrito mede o cabeçalho.
            escala_y = max(0.01, (altura_celula - margem * 2) / altura_ref) if altura_ref else 1.0
            for l in range(self._linhas):
                metrica_linha = metrica_negrito if l == 0 else metrica
                for c in range(self._colunas):
                    texto = self._celulas[l][c]
                    if not texto:
                        continue
                    largura_ref = (metrica_linha.horizontalAdvance(texto) or 1.0) * self._largura_letra
                    if largura_ref * escala_y > largura_disponivel:
                        escala_y = max(0.01, largura_disponivel / largura_ref)
        escala_x = escala_y * self._largura_letra
        cap = altura_ref * escala_y
        itens = []
        for l in range(self._linhas):
            metrica_linha = metrica_negrito if l == 0 else metrica
            for c in range(self._colunas):
                texto = self._celulas[l][c]
                if not texto:
                    continue
                itens.append({
                    "texto": texto,
                    "negrito": l == 0,
                    "x": c * largura_celula + margem,
                    "base": l * altura_celula + (altura_celula + cap) / 2,
                    "largura": metrica_linha.horizontalAdvance(texto) * escala_x,
                    "altura": cap,
                    "escala_x": escala_x,
                    "escala_y": escala_y,
                })
        return itens

    @property
    def cor_tinta(self) -> CorImpressao:
        return self._cor_tinta

    def definir_cor_tinta(self, cor: CorImpressao) -> None:
        self._cor_tinta = cor
        self.update()

    # ── Pintura ──────────────────────────────────────────────────────
    def _pintar_conteudo(self, painter: QPainter) -> None:
        cor = QColor(self._cor_tinta.r, self._cor_tinta.g, self._cor_tinta.b)
        largura_celula = self._largura / self._colunas
        altura_celula = self._altura / self._linhas

        painter.setPen(QPen(cor, 0.3))
        painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        painter.drawRect(QRectF(0, 0, self._largura, self._altura))
        for c in range(1, self._colunas):
            x = c * largura_celula
            painter.drawLine(QPointF(x, 0), QPointF(x, self._altura))
        for l in range(1, self._linhas):
            y = l * altura_celula
            painter.drawLine(QPointF(0, y), QPointF(self._largura, y))
        # Cabeçalho (primeira linha) com um pouco mais de peso — lê como
        # título das colunas, convenção universal de qualquer tabela.
        if self._linhas > 1:
            pen_cabecalho = QPen(cor, 0.6)
            painter.setPen(pen_cabecalho)
            painter.drawLine(QPointF(0, altura_celula), QPointF(self._largura, altura_celula))

        painter.setPen(QPen(cor))
        painter.setBrush(QBrush(cor))  # desenhar_texto_escalado preenche com o brush, não o pen
        for item in self.textos_layout():
            painter.save()
            painter.translate(item["x"], item["base"])
            painter.scale(item["escala_x"], item["escala_y"])
            desenhar_texto_escalado(painter, QPointF(0, 0), self._fonte_ref(item["negrito"]), item["texto"])
            painter.restore()

    def clonar(self) -> "ElementoTabela":
        novo = ElementoTabela(
            linhas=self._linhas, colunas=self._colunas, celulas=self.celulas, cor_tinta=self._cor_tinta,
            fonte_familia=self._fonte_familia, altura_letra_mm=self._altura_letra_mm, largura_letra=self._largura_letra,
        )
        self._copiar_geometria_para(novo)
        return novo
