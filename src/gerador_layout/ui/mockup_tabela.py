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
        parent=None,
    ) -> None:
        super().__init__(largura=_LARGURA_PADRAO_MM, altura=_ALTURA_PADRAO_MM, parent=parent)
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

        fonte_ref = QFont()
        fonte_ref.setPointSizeF(_TAMANHO_FONTE_REFERENCIA_PT)
        fonte_ref_negrito = QFont(fonte_ref)
        fonte_ref_negrito.setBold(True)
        metrica = QFontMetricsF(fonte_ref)
        metrica_negrito = QFontMetricsF(fonte_ref_negrito)
        altura_ref = metrica.capHeight() or metrica.ascent()
        margem = min(largura_celula, altura_celula) * 0.12
        largura_disponivel = largura_celula - margem * 2

        # UMA escala só pra tabela inteira — nunca por célula. Célula por
        # célula "achando o melhor encaixe" próprio é o que causava o bug
        # real encontrado testando: texto curto (ex.: "Qtd") escapava sem
        # precisar encolher e saía bem maior que texto longo na célula ao
        # lado (ex.: "Nutriente"), quebrando a leitura de "é tudo a mesma
        # fonte" que qualquer tabela precisa. Usa a métrica em NEGRITO
        # pra medir células do cabeçalho (linha 0) — bold é mais largo
        # que a mesma palavra sem bold, ignorar isso subestimava o
        # espaço necessário exatamente nessas células.
        escala = max(0.01, (altura_celula - margem * 2) / altura_ref) if altura_ref else 1.0
        for l in range(self._linhas):
            metrica_linha = metrica_negrito if l == 0 else metrica
            for c in range(self._colunas):
                texto = self._celulas[l][c]
                if not texto:
                    continue
                largura_texto_ref = metrica_linha.horizontalAdvance(texto) or 1.0
                if largura_texto_ref * escala > largura_disponivel:
                    escala = max(0.01, largura_disponivel / largura_texto_ref)

        painter.setPen(QPen(cor))
        painter.setBrush(QBrush(cor))  # desenhar_texto_escalado preenche com o brush, não o pen
        for l in range(self._linhas):
            for c in range(self._colunas):
                texto = self._celulas[l][c]
                if not texto:
                    continue
                fonte_celula = QFont(fonte_ref)
                fonte_celula.setBold(l == 0)
                painter.save()
                painter.translate(c * largura_celula + margem, l * altura_celula + margem)
                painter.scale(escala, escala)
                desenhar_texto_escalado(painter, QPointF(0, altura_ref), fonte_celula, texto)
                painter.restore()

    def clonar(self) -> "ElementoTabela":
        novo = ElementoTabela(
            linhas=self._linhas, colunas=self._colunas, celulas=self.celulas, cor_tinta=self._cor_tinta
        )
        self._copiar_geometria_para(novo)
        return novo
