"""Folha de aprovação do layout (PDF A4 deitado) — a que vai pro cliente
aprovar, no padrão da Bacaro:

- cabeçalho: logotipo da empresa | Cliente, Medidas, Tipo de caixa |
  Referência, Código, Cores (bolinha de cada tinta);
- faixa de ATENÇÃO (conferir impressão, medidas e cores);
- o layout (faca + arte), vetorial, centralizado;
- rodapé: Criado em, Modificado em, Aprovado por (em branco, pro cliente) e
  Desenvolvido por.

Cliente, referência e código são digitados; medidas, tipo e cores vêm do
projeto. A data de criação fica guardada no projeto: gerar de novo noutro dia
preenche "Modificado em" e mantém a de criação.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter, QPen
from PySide6.QtSvg import QSvgRenderer

from ..models import CorImpressao, LayoutCaixa
from .exportacao import _PenasExportacao, _SelecaoOculta
from .mockup_itens import cache_desligado

# Medidas da folha (mm), tiradas do modelo da Bacaro em A4 deitado.
_PAGINA = QSizeF(297.0, 210.0)
_BORDA = 1.0  # espessura da moldura
_LINHA = 0.8  # espessura das divisões
_CAB_ALTURA = 34.5
_COL_LOGO = 60.0
_COL_MEIO = 168.0
_ATENCAO_ALTURA = 12.5
_RODAPE_ALTURA = 16.0
_MARGEM_LAYOUT = 9.0

COR_TITULO = QColor(224, 140, 0)  # "Cliente:", "ATENÇÃO" etc.
_FONTE = "Century Gothic"
_ALTURA_ROTULO_MM = 5.6  # altura da fonte (em) dos rótulos e valores


@dataclass
class DadosFolha:
    cliente: str = ""
    referencia: str = ""
    codigo: str = ""
    medidas: str = ""
    tipo: str = ""
    cores: list[CorImpressao] = field(default_factory=list)
    criado_em: _dt.date | None = None
    modificado_em: _dt.date | None = None
    aprovado_por: str = ""
    desenvolvido_por: str = ""


def data_br(data: _dt.date | None) -> str:
    return data.strftime("%d/%m/%Y") if data else ""


def datas_da_vez(criado_em: _dt.date | None, hoje: _dt.date, modificacao: bool | None = None):
    """(criado_em, modificado_em) desta geração: a primeira vez cria com a
    data de hoje; depois a criação fica e a modificação vira hoje.
    `modificacao` força (True/False) quando o usuário escolhe."""
    if criado_em is None:
        return hoje, None
    if modificacao is None:
        modificacao = hoje != criado_em
    return criado_em, (hoje if modificacao else None)


# As caixas são desenhadas em escala 1:10 (ver o papelão do 3D em
# configuracoes.py): a ficha vai pro cliente com a medida de VERDADE.
ESCALA_DESENHO = 10


def texto_medidas(comprimento: float, largura: float, altura: float, escala: float = ESCALA_DESENHO) -> str:
    """"54X54X38" desenhado em 1:10 → "540X540X380" na ficha."""
    return "X".join(f"{round(v * escala, 3):g}".replace(".", ",") for v in (comprimento, largura, altura))


def nome_do_arquivo(dados: DadosFolha) -> str:
    """Como o modelo: "32792 CAIXA 02 - 06 LONG NECK 355ML TRADICIONAL.pdf"."""
    partes = [p.strip() for p in (dados.codigo, dados.referencia) if p.strip()]
    nome = " ".join(partes) or "Aprovação"
    return "".join("-" if ch in '\\/:*?"<>|' else ch for ch in nome) + ".pdf"


def _fonte(altura_mm: float, negrito: bool = False) -> QFont:
    fonte = QFont(_FONTE)
    fonte.setPixelSize(max(1, round(altura_mm * 10)))  # 10 px por mm (ver _desenhar_texto)
    fonte.setBold(negrito)
    return fonte


def _texto(p: QPainter, x: float, base: float, texto: str, altura_mm: float, cor: QColor, negrito=False) -> float:
    """Escreve com a fonte medida em décimos de mm (fonte inteira nítida) e
    devolve a largura em mm."""
    fonte = _fonte(altura_mm, negrito)
    p.save()
    p.translate(x, base)
    p.scale(0.1, 0.1)
    p.setFont(fonte)
    p.setPen(cor)
    p.drawText(QPointF(0, 0), texto)
    p.restore()
    return QFontMetricsF(fonte).horizontalAdvance(texto) / 10.0


def _largura(texto: str, altura_mm: float, negrito=False) -> float:
    return QFontMetricsF(_fonte(altura_mm, negrito)).horizontalAdvance(texto) / 10.0


def _campo(p, x, y0, y1, rotulo: str, valor: str, largura_max: float) -> None:
    """ "Rótulo: valor" centrado na altura da célula; o valor encolhe se não couber."""
    altura = _ALTURA_ROTULO_MM
    base = (y0 + y1) / 2 + altura * 0.35
    largura_rotulo = _texto(p, x, base, rotulo, altura, COR_TITULO)
    sobra = largura_max - largura_rotulo - 1.5
    tamanho = altura
    while valor and tamanho > 2.5 and _largura(valor, tamanho * 0.86) > sobra:
        tamanho -= 0.2
    _texto(p, x + largura_rotulo + 1.5, base, valor, tamanho * 0.86, QColor(0, 0, 0))


def _cores(p, x, y0, y1, cores: list[CorImpressao], largura_max: float) -> None:
    altura = _ALTURA_ROTULO_MM
    base = (y0 + y1) / 2 + altura * 0.35
    x += _texto(p, x, base, "Cores:", altura, COR_TITULO) + 2.0
    tamanho = altura * 0.82
    for cor in cores:
        raio = tamanho * 0.32
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(cor.r, cor.g, cor.b))
        p.drawEllipse(QPointF(x + raio, base - tamanho * 0.32), raio, raio)
        x += raio * 2 + 1.2
        x += _texto(p, x, base, cor.nome.upper(), tamanho, QColor(0, 0, 0)) + 4.0


def _logo(p: QPainter, caminho: str | None, area: QRectF) -> None:
    if not caminho or not Path(caminho).is_file():
        return
    if caminho.lower().endswith(".svg"):
        renderer = QSvgRenderer(caminho)
        if not renderer.isValid():
            return
        caixa = renderer.viewBoxF()
        largura, altura = caixa.width(), caixa.height()
        desenhar = lambda alvo: renderer.render(p, alvo)  # noqa: E731
    else:
        imagem = QImage(caminho)
        if imagem.isNull():
            return
        largura, altura = imagem.width(), imagem.height()
        desenhar = lambda alvo: p.drawImage(alvo, imagem)  # noqa: E731
    if largura <= 0 or altura <= 0:
        return
    escala = min(area.width() / largura, area.height() / altura)
    alvo = QRectF(0, 0, largura * escala, altura * escala)
    alvo.moveCenter(area.center())
    desenhar(alvo)


def desenhar_folha(
    p: QPainter, cena, layout: LayoutCaixa, dados: DadosFolha, logo: str | None, imagem_3d: QImage | None = None
) -> None:
    """A folha inteira, em mm (o painter já está em mm, A4 deitado). Com
    `imagem_3d`, o meio da folha é a caixa montada em vez do layout (a 2ª
    folha) — o resto (cabeçalho, atenção, rodapé) é o mesmo."""
    w, h = _PAGINA.width(), _PAGINA.height()
    preto = QColor(0, 0, 0)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    y_cab = _CAB_ALTURA
    y_aten = y_cab + _ATENCAO_ALTURA
    y_rod = h - _RODAPE_ALTURA
    linhas_cab = [0.0, y_cab / 3, 2 * y_cab / 3, y_cab]

    # Logotipo e campos do cabeçalho.
    _logo(p, logo, QRectF(4.0, 3.0, _COL_LOGO - 8.0, y_cab - 6.0))
    meio_l, meio_r = _COL_LOGO + 3.5, _COL_MEIO - 2.0
    dir_l, dir_r = _COL_MEIO + 3.5, w - 3.0
    for i, (rotulo, valor) in enumerate((("Cliente:", dados.cliente), ("Medidas:", dados.medidas), ("Tipo de Caixa:", dados.tipo))):
        _campo(p, meio_l, linhas_cab[i], linhas_cab[i + 1], rotulo, valor, meio_r - meio_l)
    _campo(p, dir_l, linhas_cab[0], linhas_cab[1], "Referência:", dados.referencia, dir_r - dir_l)
    _campo(p, dir_l, linhas_cab[1], linhas_cab[2], "Código:", dados.codigo, dir_r - dir_l)
    _cores(p, dir_l, linhas_cab[2], linhas_cab[3], dados.cores, dir_r - dir_l)

    # Atenção.
    titulo = "ATENÇÃO: "
    resto = "CONFIRA IMPRESSÃO, MEDIDAS E CORES ANTES DE CONFIRMAR O LAYOUT."
    linha2 = "Após a aprovação do layout, afirma-se que os dados estão corretos e prontos para impressão."
    a1, a2, a3 = 5.6, 4.1, 3.9
    largura_1 = _largura(titulo, a1, True) + _largura(resto, a2, True)
    x1 = (w - largura_1) / 2
    base1 = y_cab + 5.6
    x1 += _texto(p, x1, base1, titulo, a1, COR_TITULO, True)
    _texto(p, x1, base1, resto, a2, COR_TITULO, True)
    _texto(p, (w - _largura(linha2, a3)) / 2, y_cab + 10.4, linha2, a3, preto)

    # O layout, vetorial, centralizado e na maior escala que cabe.
    area = QRectF(_MARGEM_LAYOUT, y_aten + _MARGEM_LAYOUT, w - 2 * _MARGEM_LAYOUT, y_rod - y_aten - 2 * _MARGEM_LAYOUT)
    fonte_rect = QRectF(0.0, 0.0, layout.largura_total, layout.altura_total)
    if imagem_3d is not None and not imagem_3d.isNull():
        escala = min(area.width() / imagem_3d.width(), area.height() / imagem_3d.height())
        alvo = QRectF(0, 0, imagem_3d.width() * escala, imagem_3d.height() * escala)
        alvo.moveCenter(area.center())
        p.drawImage(alvo, imagem_3d)
        _texto(p, area.left(), area.top() + 3.0, "Caixa montada (3D)", 3.6, COR_TITULO)
    elif fonte_rect.width() > 0 and fonte_rect.height() > 0:
        escala = min(area.width() / fonte_rect.width(), area.height() / fonte_rect.height())
        alvo = QRectF(0, 0, fonte_rect.width() * escala, fonte_rect.height() * escala)
        alvo.moveCenter(area.center())
        selecao = _SelecaoOculta(cena)
        # Traço da faca com ~0,3 mm NA FOLHA (o layout vem reduzido).
        penas = _PenasExportacao(cena, fator=max(1.0, 0.3 / escala / 0.3528))
        sem_cache = cache_desligado(cena)
        sem_cache.__enter__()
        try:
            cena.render(p, alvo, fonte_rect, Qt.AspectRatioMode.KeepAspectRatio)
        finally:
            sem_cache.__exit__(None, None, None)
            penas.restaurar()
            selecao.restaurar()

    # Rodapé.
    altura = _ALTURA_ROTULO_MM
    base = y_rod + _RODAPE_ALTURA / 2 + altura * 0.35
    # Quatro blocos espalhados por igual entre as margens (como no modelo).
    altura = _ALTURA_ROTULO_MM * 0.95
    blocos = [
        ("Criado em:", data_br(dados.criado_em), 22.0),
        ("Modificado em:", data_br(dados.modificado_em), 22.0),
        ("Aprovado por:", dados.aprovado_por, 30.0),
        ("Desenvolvido por:", dados.desenvolvido_por, 0.0),
    ]

    def largura_bloco(rotulo, valor, linha):
        return _largura(rotulo, altura) + 2.0 + (_largura(valor, altura * 0.86) if valor else linha)

    larguras = [largura_bloco(*b) for b in blocos]
    margem_x = 9.0
    vao = max(3.0, (w - 2 * margem_x - sum(larguras)) / (len(blocos) - 1))
    x = margem_x
    for (rotulo, valor, largura_linha), largura in zip(blocos, larguras):
        inicio = x
        x += _texto(p, x, base, rotulo, altura, COR_TITULO) + 2.0
        if valor:
            _texto(p, x, base, valor, altura * 0.86, preto)
        else:
            p.setPen(QPen(preto, 0.3))
            p.drawLine(QPointF(x, base + 0.6), QPointF(x + largura_linha, base + 0.6))
        x = inicio + largura + vao

    # Moldura e divisões por cima de tudo.
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(preto, _BORDA, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.MiterJoin))
    p.drawRect(QRectF(_BORDA / 2, _BORDA / 2, w - _BORDA, h - _BORDA))
    p.setPen(QPen(preto, _LINHA, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
    for y in (y_cab, y_aten, y_rod):
        p.drawLine(QPointF(0, y), QPointF(w, y))
    p.drawLine(QPointF(_COL_LOGO, 0), QPointF(_COL_LOGO, y_cab))
    p.drawLine(QPointF(_COL_MEIO, 0), QPointF(_COL_MEIO, y_cab))
    for y in linhas_cab[1:3]:
        p.drawLine(QPointF(_COL_LOGO, y), QPointF(w, y))


def gerar_pdf(
    cena, layout: LayoutCaixa, dados: DadosFolha, caminho: str | Path, logo: str | None = None,
    imagem_3d: QImage | None = None,
) -> Path:
    """1ª folha: o layout. Com `imagem_3d`, 2ª folha: a caixa montada."""
    caminho = Path(caminho)
    escritor = QPdfWriter(str(caminho))
    escritor.setPageLayout(
        QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape, QMarginsF(0, 0, 0, 0))
    )
    escritor.setResolution(1200)
    escritor.setTitle(f"Aprovação — {dados.codigo} {dados.referencia}".strip())
    escritor.setCreator("Autoline")
    p = QPainter(escritor)
    if not p.isActive():
        raise RuntimeError(f"Não consegui criar o PDF em: {caminho}")
    try:
        px_por_mm = escritor.resolution() / 25.4
        p.scale(px_por_mm, px_por_mm)
        desenhar_folha(p, cena, layout, dados, logo)
        if imagem_3d is not None and not imagem_3d.isNull():
            escritor.newPage()
            desenhar_folha(p, cena, layout, dados, logo, imagem_3d)
    finally:
        p.end()
    return caminho
