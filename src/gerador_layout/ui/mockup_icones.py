"""Ícones mono do modo Layout (mockup), desenhados na hora com QPainter
— compartilhado entre `painel_propriedades_mockup.py` (property bar) e
`main_window.py` (paleta de ferramentas vertical), pra não duplicar o
mesmo desenho de glyph em dois lugares. Sem pacote de ícone importado de
propósito: um glyph vetorial simples acompanha o tema claro/escuro de
graça, sem precisar de 2 arquivos por ícone.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from .estilo import Cor

TAMANHO_ICONE = 18


def _seta(painter: QPainter, inicio: QPointF, fim: QPointF, cabeca: float = 2.3) -> None:
    """Segmento de reta com cabeça de seta na ponta `fim` — usada em
    quase todo ícone de eixo/medida/ângulo/ferramenta abaixo."""
    painter.drawLine(inicio, fim)
    direcao = fim - inicio
    norma = (direcao.x() ** 2 + direcao.y() ** 2) ** 0.5 or 1.0
    unidade = QPointF(direcao.x() / norma, direcao.y() / norma)
    perp = QPointF(-unidade.y(), unidade.x())
    base = fim - QPointF(unidade.x() * cabeca, unidade.y() * cabeca)
    lado_a = base + QPointF(perp.x() * cabeca * 0.7, perp.y() * cabeca * 0.7)
    lado_b = base - QPointF(perp.x() * cabeca * 0.7, perp.y() * cabeca * 0.7)
    painter.drawLine(fim, lado_a)
    painter.drawLine(fim, lado_b)


_ICONES_PRONTOS: dict[tuple[str, str], QIcon] = {}


def construir_icone(tipo: str) -> QIcon:
    """O ícone `tipo` na cor do tema ativo. Guardado: a barra de
    propriedades é remontada a cada seleção e redesenhava ~20 ícones do
    zero a cada clique."""
    chave = (tipo, str(Cor.TEXTO_SECUNDARIO))
    icone = _ICONES_PRONTOS.get(chave)
    if icone is None:
        icone = _desenhar_icone(tipo)
        _ICONES_PRONTOS[chave] = icone
    return icone


def _desenhar_icone(tipo: str) -> QIcon:
    """Um "tipo" por controle — ver ramos abaixo pra saber o que cada um
    representa. `cor` é sempre `Cor.TEXTO_SECUNDARIO` (tema ativo);
    quem quer destacar (ex.: ferramenta selecionada) faz isso no botão
    via QSS `:checked`, não trocando a cor do ícone."""
    escala = 2  # pixmap em 2x + devicePixelRatio = nítido em tela HiDPI
    lado = TAMANHO_ICONE
    pixmap = QPixmap(lado * escala, lado * escala)
    pixmap.setDevicePixelRatio(escala)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    cor = QColor(Cor.TEXTO_SECUNDARIO)
    caneta = QPen(cor, 1.4)
    caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(caneta)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    c = lado / 2

    if tipo in ("x", "y"):
        # Seta a partir de uma marca de origem — a mesma leitura de uma
        # cota técnica ("medido a partir daqui até aqui").
        if tipo == "x":
            painter.drawLine(QPointF(3, 5), QPointF(3, 13))  # marca de origem
            _seta(painter, QPointF(3, 9), QPointF(15, 9))
        else:
            painter.drawLine(QPointF(5, 3), QPointF(13, 3))
            _seta(painter, QPointF(9, 3), QPointF(9, 15))
    elif tipo in ("largura", "altura"):
        # Cota de dimensão com seta nas 2 pontas + travessões nas
        # extremidades — igual a uma linha de cota de desenho técnico.
        if tipo == "largura":
            painter.drawLine(QPointF(3, 5), QPointF(3, 13))
            painter.drawLine(QPointF(15, 5), QPointF(15, 13))
            _seta(painter, QPointF(9, 9), QPointF(15, 9))
            _seta(painter, QPointF(9, 9), QPointF(3, 9))
        else:
            painter.drawLine(QPointF(5, 3), QPointF(13, 3))
            painter.drawLine(QPointF(5, 15), QPointF(13, 15))
            _seta(painter, QPointF(9, 9), QPointF(9, 15))
            _seta(painter, QPointF(9, 9), QPointF(9, 3))
    elif tipo in ("espelho_h", "espelho_v"):
        # Dois triângulos espelhados em torno de um eixo tracejado.
        painter.save()
        if tipo == "espelho_v":
            painter.translate(c, c)
            painter.rotate(90)
            painter.translate(-c, -c)
        eixo = QPen(cor, 1.0, Qt.PenStyle.DashLine)
        painter.setPen(eixo)
        painter.drawLine(QPointF(c, 2), QPointF(c, 16))
        painter.setPen(caneta)
        painter.drawPolygon(QPolygonF([QPointF(7, 5), QPointF(7, 13), QPointF(2.5, 13)]))
        painter.setBrush(QBrush(cor))
        painter.drawPolygon(QPolygonF([QPointF(11, 5), QPointF(11, 13), QPointF(15.5, 13)]))
        painter.restore()
    elif tipo in ("linha_corte", "linha_vinco"):
        # Linha da faca: corte contínuo, vinco tracejado, com as pontas marcadas.
        caneta_linha = QPen(cor, 1.6, Qt.PenStyle.SolidLine if tipo == "linha_corte" else Qt.PenStyle.DashLine)
        painter.setPen(caneta_linha)
        painter.drawLine(QPointF(3, 15), QPointF(15, 3))
        painter.setPen(caneta)
        painter.setBrush(QBrush(cor))
        painter.drawRect(QRectF(1.5, 13.5, 3, 3))
        painter.drawRect(QRectF(13.5, 1.5, 3, 3))
    elif tipo == "faca_arco":
        # Arco por 2 pontas + curvatura, pontas marcadas.
        painter.drawArc(QRectF(3, 5, 12, 16), 0, 180 * 16)
        painter.setBrush(QBrush(cor))
        painter.drawRect(QRectF(1.5, 11.5, 3, 3))
        painter.drawRect(QRectF(13.5, 11.5, 3, 3))
    elif tipo in ("faca_aparar", "faca_estender"):
        # Linha-limite vertical; a linha horizontal passa dela (aparar,
        # trecho cortado tracejado) ou chega até ela (estender, com seta).
        painter.drawLine(QPointF(12, 2), QPointF(12, 16))
        if tipo == "faca_aparar":
            painter.drawLine(QPointF(2, 9), QPointF(12, 9))
            painter.setPen(QPen(cor, 1.2, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(12, 9), QPointF(16.5, 9))
        else:
            painter.drawLine(QPointF(2, 9), QPointF(6, 9))
            painter.setPen(QPen(cor, 1.2, Qt.PenStyle.DotLine))
            painter.drawLine(QPointF(6, 9), QPointF(11, 9))
            painter.setPen(caneta)
            _seta(painter, QPointF(8, 9), QPointF(11.5, 9), 3)
    elif tipo == "faca_arredondar":
        # Canto com o raio no lugar da quina.
        caminho = QPainterPath(QPointF(3, 15))
        caminho.lineTo(3, 9)
        caminho.quadTo(3, 3, 9, 3)
        caminho.lineTo(15, 3)
        painter.drawPath(caminho)
        painter.setPen(QPen(cor, 1.0, Qt.PenStyle.DotLine))
        painter.drawLine(QPointF(3, 9), QPointF(3, 3))
        painter.drawLine(QPointF(3, 3), QPointF(9, 3))
    elif tipo == "faca_paralela":
        # Duas linhas paralelas com a distância entre elas.
        painter.drawLine(QPointF(2, 6), QPointF(16, 6))
        painter.setPen(QPen(cor, 1.4, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(2, 14), QPointF(16, 14))
        painter.setPen(caneta)
        _seta(painter, QPointF(9, 10), QPointF(9, 14), 2.5)
        _seta(painter, QPointF(9, 10), QPointF(9, 6), 2.5)
    elif tipo == "navegar":
        # Mão aberta (mover a visão).
        painter.drawRoundedRect(QRectF(4, 8, 10, 8), 3, 3)
        for x in (5.5, 8, 10.5, 13):
            painter.drawLine(QPointF(x, 9), QPointF(x, 3.5 if x in (8, 10.5) else 5))
    elif tipo == "ferramenta_bezier":
        # Curva com um nó e as duas alças.
        caminho = QPainterPath(QPointF(2, 15))
        caminho.cubicTo(QPointF(4, 4), QPointF(14, 4), QPointF(16, 13))
        painter.drawPath(caminho)
        painter.drawLine(QPointF(4, 6), QPointF(14, 6))
        painter.setBrush(QBrush(cor))
        painter.drawRect(QRectF(7.5, 4.5, 3, 3))
        painter.drawEllipse(QPointF(4, 6), 1.2, 1.2)
        painter.drawEllipse(QPointF(14, 6), 1.2, 1.2)
    elif tipo == "ferramenta_mao_livre":
        caminho = QPainterPath(QPointF(2, 13))
        caminho.cubicTo(QPointF(5, 3), QPointF(8, 16), QPointF(11, 8))
        caminho.cubicTo(QPointF(13, 3), QPointF(15, 9), QPointF(16, 5))
        painter.drawPath(caminho)
    elif tipo == "ferramenta_forma":
        # Seta de ponteiro com um nó quadrado na ponta (ferramenta Forma).
        painter.setBrush(QBrush(cor))
        painter.drawPolygon(QPolygonF([QPointF(4, 3), QPointF(4, 14), QPointF(7, 11), QPointF(9.5, 16), QPointF(11, 15.3), QPointF(8.6, 10.4), QPointF(12.5, 10.2)]))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(12.5, 2.5, 3.5, 3.5))
    elif tipo == "converter_curvas":
        painter.drawRect(QRectF(2.5, 6, 6, 6))
        _seta(painter, QPointF(9.5, 9), QPointF(12, 9), 1.6)
        caminho = QPainterPath(QPointF(12.5, 13))
        caminho.cubicTo(QPointF(13, 4), QPointF(16, 6), QPointF(16, 12))
        painter.drawPath(caminho)
    elif tipo in ("combinar", "separar"):
        painter.drawRect(QRectF(2.5, 2.5, 8, 8))
        if tipo == "combinar":
            painter.setBrush(QBrush(cor))
            painter.drawRect(QRectF(7.5, 7.5, 8, 8))
            painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
        else:
            painter.drawRect(QRectF(8.5, 8.5, 7, 7))
            painter.drawLine(QPointF(6, 15), QPointF(3, 15))
    elif tipo.startswith("modelar_"):
        # Dois quadrados sobrepostos; o preenchido mostra o que sobra.
        a = QRectF(2.5, 2.5, 9, 9)
        b = QRectF(6.5, 6.5, 9, 9)
        pa, pb = QPainterPath(), QPainterPath()
        pa.addRect(a)
        pb.addRect(b)
        resultado = {
            "modelar_soldar": pa.united(pb),
            "modelar_aparar": pa.subtracted(pb),
            "modelar_intersecao": pa.intersected(pb),
            "modelar_frente_menos_atras": pb.subtracted(pa),
            "modelar_atras_menos_frente": pa.subtracted(pb),
        }.get(tipo, pa)
        painter.setBrush(QBrush(cor))
        painter.drawPath(resultado)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        contorno = QPen(cor, 0.8, Qt.PenStyle.DotLine)
        painter.setPen(contorno)
        painter.drawRect(a)
        painter.drawRect(b)
        if tipo == "modelar_aparar":
            painter.setPen(caneta)
            painter.drawRect(b)  # no Aparar o de cima continua inteiro
    elif tipo == "cota_angular":
        # Dois braços saindo do vértice e o arco com setas entre eles.
        painter.drawLine(QPointF(3, 15), QPointF(16, 15))
        painter.drawLine(QPointF(3, 15), QPointF(12, 3))
        painter.drawArc(QRectF(-5, 7, 16, 16), 0, 53 * 16)
        painter.setBrush(QBrush(cor))
        painter.drawEllipse(QPointF(3, 15), 1.1, 1.1)
    elif tipo in ("cota_paralela", "cota_horizontal", "cota_vertical"):
        # Linha de cota com setas e as duas linhas de chamada.
        painter.save()
        if tipo == "cota_paralela":
            painter.translate(c, c)
            painter.rotate(-35)
            painter.translate(-c, -c)
        elif tipo == "cota_vertical":
            painter.translate(c, c)
            painter.rotate(-90)
            painter.translate(-c, -c)
        painter.drawLine(QPointF(3, 15), QPointF(3, 5))
        painter.drawLine(QPointF(15, 15), QPointF(15, 5))
        _seta(painter, QPointF(9, 8), QPointF(3.5, 8), 2.0)
        _seta(painter, QPointF(9, 8), QPointF(14.5, 8), 2.0)
        painter.restore()
    elif tipo in ("escala_l", "escala_a"):
        # "%" com a seta do eixo que escala.
        fonte = QFont()
        fonte.setPixelSize(10)
        fonte.setBold(True)
        painter.setFont(fonte)
        painter.drawText(QRectF(0, 0, lado, lado), Qt.AlignmentFlag.AlignCenter, "%")
        if tipo == "escala_l":
            _seta(painter, QPointF(4, 16), QPointF(14, 16), 1.8)
        else:
            _seta(painter, QPointF(16, 14), QPointF(16, 4), 1.8)
    elif tipo == "angulo":
        painter.drawArc(QRectF(3, 3, 12, 12), 20 * 16, 220 * 16)
        fim = QPointF(c + 6 * 0.35, c - 6 * 0.93)
        _seta(painter, QPointF(c + 6 * 0.7, c - 6 * 0.6), fim, cabeca=2.0)
    elif tipo == "espaco_letras":  # "AV" com setas pros lados
        fonte = painter.font()
        fonte.setPixelSize(8)
        fonte.setBold(True)
        painter.setFont(fonte)
        painter.drawText(QRectF(2, 1, 14, 9), Qt.AlignmentFlag.AlignCenter, "AV")
        painter.drawLine(QPointF(2, 13.5), QPointF(16, 13.5))
        painter.drawLine(QPointF(2, 13.5), QPointF(4.5, 11.5))
        painter.drawLine(QPointF(2, 13.5), QPointF(4.5, 15.5))
        painter.drawLine(QPointF(16, 13.5), QPointF(13.5, 11.5))
        painter.drawLine(QPointF(16, 13.5), QPointF(13.5, 15.5))
    elif tipo == "espaco_linhas":  # linhas de texto com seta de altura
        for y in (4, 9, 14):
            painter.drawLine(QPointF(7, y), QPointF(16, y))
        painter.drawLine(QPointF(3, 2.5), QPointF(3, 15.5))
        painter.drawLine(QPointF(3, 2.5), QPointF(1.3, 4.5))
        painter.drawLine(QPointF(3, 2.5), QPointF(4.7, 4.5))
        painter.drawLine(QPointF(3, 15.5), QPointF(1.3, 13.5))
        painter.drawLine(QPointF(3, 15.5), QPointF(4.7, 13.5))
    elif tipo == "trava":  # cadeado fechado
        painter.drawRoundedRect(QRectF(4, 8, 10, 7), 1.5, 1.5)
        painter.drawArc(QRectF(6, 2, 6, 8), 0, 180 * 16)
        painter.drawLine(QPointF(6, 6), QPointF(6, 8))
        painter.drawLine(QPointF(12, 6), QPointF(12, 8))
    elif tipo == "trava_aberta":  # cadeado aberto: a alça sobe e solta de um lado
        painter.drawRoundedRect(QRectF(4, 8, 10, 7), 1.5, 1.5)
        painter.drawArc(QRectF(9, 0.5, 6, 8), 0, 180 * 16)
        painter.drawLine(QPointF(15, 4.5), QPointF(15, 8))
    elif tipo == "face":
        margem = 2.5
        painter.drawRect(QRectF(margem, margem, lado - 2 * margem, lado - 2 * margem))
        painter.setBrush(QBrush(cor))
        painter.drawEllipse(QPointF(c, c), 1.3, 1.3)
    elif tipo == "medida":
        painter.drawRect(QRectF(3, 6, 12, 6))
        for x in (6, 9, 12):
            painter.drawLine(QPointF(x, 6), QPointF(x, 8.5))
    elif tipo.startswith("alinhar_"):
        _desenhar_alinhar(painter, tipo, cor, lado)
    elif tipo in ("letra_a", "negrito"):
        fonte = QFont()
        fonte.setPixelSize(12)
        fonte.setBold(True)
        painter.setFont(fonte)
        painter.setPen(QPen(cor, 1.0))
        painter.drawText(QRectF(0, 0, lado, lado), Qt.AlignmentFlag.AlignCenter, "A" if tipo == "letra_a" else "B")
    elif tipo == "fonte_aa":
        fonte = QFont()
        fonte.setPixelSize(9)
        fonte.setBold(True)
        painter.setFont(fonte)
        painter.drawText(QRectF(0, 0, lado, lado), Qt.AlignmentFlag.AlignCenter, "Aa")
    elif tipo == "tinta":
        caminho = QPainterPath()
        caminho.moveTo(c, 2.5)
        caminho.cubicTo(c + 5, 8, c + 4, 15, c, 15)
        caminho.cubicTo(c - 4, 15, c - 5, 8, c, 2.5)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor))
        painter.drawPath(caminho)
    elif tipo == "preenchido":
        quadrado = QRectF(3.5, 3.5, 11, 11)
        painter.setBrush(QBrush(cor))
        painter.setClipRect(QRectF(3.5, 3.5, 5.5, 11))
        painter.drawRect(quadrado)
        painter.setClipping(False)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(quadrado)
    elif tipo == "espessura":
        pesos = (1.0, 2.0, 3.2)
        y = 4.5
        for peso in pesos:
            caneta_peso = QPen(cor, peso)
            caneta_peso.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(caneta_peso)
            painter.drawLine(QPointF(3.5, y), QPointF(14.5, y))
            y += 4.5
    elif tipo == "lista":
        for y in (5, 9, 13):
            painter.setBrush(QBrush(cor))
            painter.drawEllipse(QPointF(4, y), 1.0, 1.0)
            painter.drawLine(QPointF(7, y), QPointF(15, y))
    elif tipo == "mais":
        painter.drawLine(QPointF(c, 4), QPointF(c, 14))
        painter.drawLine(QPointF(4, c), QPointF(14, c))
    elif tipo == "remover":
        painter.drawLine(QPointF(3.5, 5.5), QPointF(14.5, 5.5))
        painter.drawRect(QRectF(4.5, 3, 9, 2.5))
        painter.drawRect(QRectF(5, 5.5, 8, 9.5))
        for x in (7.3, 9, 10.7):
            painter.drawLine(QPointF(x, 7.5), QPointF(x, 13))
    elif tipo == "remapear":
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor))
        painter.drawEllipse(QPointF(c - 2.3, c + 1.0), 4.6, 4.6)
        painter.setBrush(QBrush(QColor(Cor.CARTAO)))
        painter.setPen(caneta)
        painter.drawEllipse(QPointF(c + 2.6, c - 2.0), 4.0, 4.0)
    elif tipo == "selecionar":
        # Ponteiro de seleção — o glyph universal de "ferramenta padrão"
        # em qualquer editor gráfico, pra não ter dúvida de qual botão
        # volta pro modo normal depois de usar outra ferramenta.
        caminho = QPainterPath()
        caminho.moveTo(4, 3)
        caminho.lineTo(4, 15)
        caminho.lineTo(7.2, 12.2)
        caminho.lineTo(9.4, 16.5)
        caminho.lineTo(11.3, 15.5)
        caminho.lineTo(9.1, 11.2)
        caminho.lineTo(13, 10.6)
        caminho.closeSubpath()
        painter.setPen(QPen(cor, 1.0))
        painter.setBrush(QBrush(cor))
        painter.drawPath(caminho)
    elif tipo == "ferramenta_texto":
        fonte = QFont()
        fonte.setPixelSize(13)
        fonte.setBold(True)
        painter.setFont(fonte)
        painter.setPen(QPen(cor, 1.0))
        painter.drawText(QRectF(0, 0, lado, lado - 3), Qt.AlignmentFlag.AlignCenter, "A")
        painter.drawLine(QPointF(4, 15.5), QPointF(14, 15.5))  # linha de base — reforça "isto é texto"
    elif tipo == "ferramenta_retangulo":
        painter.drawRect(QRectF(3.5, 4.5, 11, 9))
    elif tipo == "ferramenta_linha":
        painter.drawLine(QPointF(4, 14), QPointF(14, 4))
        for ponto in (QPointF(4, 14), QPointF(14, 4)):
            painter.setBrush(QBrush(cor))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(ponto, 1.4, 1.4)
            painter.setPen(caneta)
    elif tipo == "ferramenta_imagem":
        painter.drawRect(QRectF(2.5, 3.5, 13, 11))
        painter.setBrush(QBrush(cor))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(6, 7), 1.3, 1.3)  # "sol"
        montanhas = QPainterPath()
        montanhas.moveTo(3.2, 13.5)
        montanhas.lineTo(7.5, 8.5)
        montanhas.lineTo(10, 11)
        montanhas.lineTo(12, 8.8)
        montanhas.lineTo(14.8, 13.5)
        montanhas.closeSubpath()
        painter.drawPath(montanhas)
    elif tipo == "ferramenta_logo":
        # Estrela de 5 pontas — glyph universal de "marca/emblema".
        caminho = QPainterPath()
        pontos_estrela = _pontos_estrela(QPointF(c, c), 7.2, 3.0)
        caminho.moveTo(pontos_estrela[0])
        for ponto in pontos_estrela[1:]:
            caminho.lineTo(ponto)
        caminho.closeSubpath()
        painter.setPen(QPen(cor, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(caminho)
    elif tipo in ("desfazer", "refazer"):
        # Seta circular — "desfazer" gira anti-horário (glyph universal de
        # undo em qualquer editor), "refazer" é o mesmo desenho espelhado
        # no eixo X (equivalente a girar no sentido oposto).
        rect = QRectF(3.5, 4, 11, 11)
        angulo_inicio, angulo_fim = (35, 300) if tipo == "desfazer" else (145, -120)
        painter.drawArc(rect, angulo_inicio * 16, (angulo_fim - angulo_inicio) * 16)
        centro = QPointF(c, c + 0.5)
        raio = 5.5
        ponta = centro + QPointF(raio * math.cos(math.radians(angulo_fim)), -raio * math.sin(math.radians(angulo_fim)))
        antes = centro + QPointF(
            raio * math.cos(math.radians(angulo_fim - 18)), -raio * math.sin(math.radians(angulo_fim - 18))
        )
        _seta(painter, antes, ponta, cabeca=2.4)
    elif tipo == "ferramenta_elipse":
        painter.drawEllipse(QRectF(2.5, 4, 13, 10))
    elif tipo == "ferramenta_poligono":
        caminho = QPainterPath()
        pontos_hexagono = _pontos_poligono(QPointF(c, c), 7.2, lados=6)
        caminho.moveTo(pontos_hexagono[0])
        for ponto in pontos_hexagono[1:]:
            caminho.lineTo(ponto)
        caminho.closeSubpath()
        painter.drawPath(caminho)
    elif tipo == "ferramenta_tabela":
        painter.drawRect(QRectF(3, 4, 12, 10))
        painter.drawLine(QPointF(3, 8), QPointF(15, 8))  # linha de cabeçalho
        painter.drawLine(QPointF(7.5, 4), QPointF(7.5, 14))
        painter.drawLine(QPointF(11.5, 4), QPointF(11.5, 14))
    elif tipo == "ferramenta_callout":
        # Ponto de referência no objeto (círculo vazado) + linha de
        # chamada tracejada até a caixa de anotação com 2 traços de
        # "texto" dentro — distingue de um retângulo genérico e evita
        # ler como lupa/alfinete.
        painter.drawEllipse(QPointF(3.8, 14.2), 1.5, 1.5)
        linha_pen = QPen(cor, 1.0)
        linha_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(linha_pen)
        painter.drawLine(QPointF(5.1, 13.0), QPointF(8, 9.6))
        painter.setPen(caneta)
        painter.drawRoundedRect(QRectF(8, 2.5, 8, 7.5), 1.3, 1.3)
        painter.drawLine(QPointF(9.5, 5.2), QPointF(14.5, 5.2))
        painter.drawLine(QPointF(9.5, 7.5), QPointF(13, 7.5))
    elif tipo == "ferramenta_transparencia":
        # Tabuleiro de xadrez — convenção universal de "transparência" em
        # qualquer editor gráfico (Corel, Illustrator, Photoshop etc.).
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor))
        quadro = QRectF(3, 3, 12, 12)
        painter.drawRect(QRectF(quadro.left(), quadro.top(), 6, 6))
        painter.drawRect(QRectF(quadro.left() + 6, quadro.top() + 6, 6, 6))
        painter.setPen(caneta)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(quadro)
    elif tipo == "ferramenta_simbolo":
        # Triângulo de alerta com exclamação — leitura universal de
        # "símbolo/pictograma de instrução" (mesma família visual dos
        # ícones de manuseio que este elemento desenha no mockup).
        painter.drawPolygon(
            [QPointF(9, 2.5), QPointF(16, 15), QPointF(2, 15)]
        )
        painter.drawLine(QPointF(9, 6.5), QPointF(9, 11))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor))
        painter.drawEllipse(QPointF(9, 13), 0.9, 0.9)
    elif tipo == "ferramenta_laco":
        # Laço poligonal tracejado (contorno irregular, não uma forma
        # geométrica limpa — deixa claro que não é a ferramenta Polígono)
        # com um "x" no vértice inicial, sugerindo "clique aqui pra
        # fechar o laço".
        pen_tracejada = QPen(cor, 1.2, Qt.PenStyle.DashLine)
        painter.setPen(pen_tracejada)
        painter.drawPolygon(
            [QPointF(4, 6), QPointF(8, 3), QPointF(14, 5), QPointF(15, 10), QPointF(10, 14), QPointF(5, 12)]
        )
        painter.setPen(caneta)
        painter.setBrush(QBrush(Qt.GlobalColor.transparent))
        painter.drawEllipse(QPointF(4, 6), 1.4, 1.4)
    elif tipo == "ferramenta_mover_preciso":
        # Ponto de pega (círculo cheio) -> linha tracejada -> ponto de
        # solta (círculo vazado) com seta — o modelo "pega e solta" de 2
        # cliques, diferente do cursor de 4 setas de "mover" comum.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor))
        painter.drawEllipse(QPointF(4, 14), 1.6, 1.6)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen_tracejada = QPen(cor, 1.2, Qt.PenStyle.DashLine)
        painter.setPen(pen_tracejada)
        painter.drawLine(QPointF(5.5, 12.5), QPointF(12, 6))
        painter.setPen(caneta)
        _seta(painter, QPointF(9, 9), QPointF(13.5, 4.5), cabeca=2.2)
        painter.drawEllipse(QPointF(14, 4), 1.6, 1.6)
    elif tipo == "agrupar":
        painter.drawRect(QRectF(3, 3, 8, 8))
        painter.drawRect(QRectF(7, 7, 8, 8))
        caneta_tracejada = QPen(cor, 1.0, Qt.PenStyle.DashLine)
        painter.setPen(caneta_tracejada)
        painter.drawRect(QRectF(2, 2, 14, 14))
    elif tipo == "desagrupar":
        painter.drawRect(QRectF(2.5, 2.5, 6.5, 6.5))
        painter.drawRect(QRectF(9, 9, 6.5, 6.5))
    elif tipo in ("trazer_frente", "enviar_tras"):
        # 3 retângulos empilhados (camadas) + seta indicando a direção
        # do movimento — a que "sobe" fica sólida/em destaque conforme
        # o sentido, as outras ficam mais claras (traço fino).
        offsets = ((5.5, 5.5), (3.5, 3.5), (1.5, 1.5)) if tipo == "trazer_frente" else ((1.5, 1.5), (3.5, 3.5), (5.5, 5.5))
        caneta_fina = QPen(QColor(cor.red(), cor.green(), cor.blue(), 110), 1.1)
        for i, (dx, dy) in enumerate(offsets):
            painter.setPen(caneta if i == 0 else caneta_fina)
            painter.drawRect(QRectF(dx, dy, 7, 7))
        if tipo == "trazer_frente":
            _seta(painter, QPointF(15.5, 9), QPointF(15.5, 3.5))
        else:
            _seta(painter, QPointF(15.5, 3.5), QPointF(15.5, 9))
    elif tipo == "conta_gotas":
        # Pipeta na diagonal — bulbo (círculo vazado) na ponta de cima,
        # gota preenchida (a cor "capturada") na ponta de baixo.
        painter.drawLine(QPointF(12, 4), QPointF(5.5, 10.5))
        painter.drawEllipse(QPointF(13.3, 2.7), 2.0, 2.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor))
        caminho = QPainterPath()
        caminho.moveTo(5.5, 10.5)
        caminho.cubicTo(3, 13, 3, 16, 5.5, 16)
        caminho.cubicTo(8, 16, 8, 13, 5.5, 10.5)
        painter.drawPath(caminho)

    painter.end()
    return QIcon(pixmap)


def _pontos_estrela(centro: QPointF, raio_externo: float, raio_interno: float) -> list[QPointF]:
    pontos = []
    for i in range(10):
        raio = raio_externo if i % 2 == 0 else raio_interno
        angulo = math.radians(-90 + i * 36)
        pontos.append(QPointF(centro.x() + raio * math.cos(angulo), centro.y() + raio * math.sin(angulo)))
    return pontos


def _pontos_poligono(centro: QPointF, raio: float, lados: int) -> list[QPointF]:
    return [
        QPointF(
            centro.x() + raio * math.cos(math.radians(-90 + i * (360 / lados))),
            centro.y() + raio * math.sin(math.radians(-90 + i * (360 / lados))),
        )
        for i in range(lados)
    ]


def _desenhar_alinhar(painter: QPainter, tipo: str, cor: QColor, lado: float) -> None:
    """Alinhamento = "um objeto encostando numa linha de referência no
    local que vai alinhar" — desenha a linha de referência (tracejada, a
    borda/eixo escolhido) e 2 retângulos sólidos de tamanhos diferentes
    encostados nela, exatamente como o glyph de align-left/center/right
    de qualquer editor vetorial. Linha SEMPRE tracejada (mesmo pro
    "esquerda"/"direita", não só "centro") pra ler como guia, separada
    dos blocos sólidos — achado olhando o ícone renderizado de perto,
    não só no código (linha cheia + bloco fino formava a letra "T")."""
    horizontal = tipo in ("alinhar_esquerda", "alinhar_centro_h", "alinhar_direita")
    linha_pen = QPen(cor, 1.0)
    linha_pen.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(linha_pen)

    if horizontal:
        x = {"alinhar_esquerda": 3.0, "alinhar_centro_h": lado / 2, "alinhar_direita": lado - 3.0}[tipo]
        painter.drawLine(QPointF(x, 2), QPointF(x, lado - 2))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor))
        for y, comprimento in ((3.5, 5.0), (10.5, 8.0)):
            if tipo == "alinhar_esquerda":
                painter.drawRect(QRectF(x + 1, y, comprimento, 3.5))
            elif tipo == "alinhar_direita":
                painter.drawRect(QRectF(x - comprimento - 1, y, comprimento, 3.5))
            else:
                painter.drawRect(QRectF(x - comprimento / 2, y, comprimento, 3.5))
    else:
        y = {"alinhar_topo": 3.0, "alinhar_centro_v": lado / 2, "alinhar_base": lado - 3.0}[tipo]
        painter.drawLine(QPointF(2, y), QPointF(lado - 2, y))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(cor))
        for x, comprimento in ((3.5, 5.0), (10.5, 8.0)):
            if tipo == "alinhar_topo":
                painter.drawRect(QRectF(x, y + 1, 3.5, comprimento))
            elif tipo == "alinhar_base":
                painter.drawRect(QRectF(x, y - comprimento - 1, 3.5, comprimento))
            else:
                painter.drawRect(QRectF(x, y - comprimento / 2, 3.5, comprimento))
