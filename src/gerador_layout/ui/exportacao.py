"""Exportação do layout desenhado no canvas para arquivos.

SVG e PDF saem vetoriais (qualidade perfeita em qualquer escala — e como
as coordenadas da cena já são em milímetros, o PDF sai na escala real
1:1). JPG sai em raster, com a resolução calculada a partir de um DPI alvo
(ver `exportar_jpg`) pra sair nítido o bastante pra impressão.

Os arquivos exportados aqui saem sempre em preto e traço contínuo, com o
vinco como única exceção tracejada — mesmo que a pré-visualização em tela
use cores por tipo de linha pra facilitar a edição (ver `_ESTILO_POR_TIPO`
em `preview_canvas.py`). Ver `_PenasExportacao` abaixo.

Pro CorelDRAW em si não existe exportação de arquivo (.cdr é formato
proprietário, sem biblioteca aberta capaz de gravá-lo) — em vez disso, o
layout é desenhado direto num documento do CorelDRAW por automação COM,
ver `corel_bridge.py`.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QMarginsF, QPointF, QRectF, QSize, QSizeF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPathItem,
    QGraphicsScene,
)

from ..models import CorImpressao, LayoutCaixa, TipoLinha
from . import configuracoes
from .mockup_itens import cache_desligado

# Legenda de cores: tamanho configurável em Configurações (não escala com
# o tamanho do layout — um fator proporcional ainda deixava a legenda
# grande demais em caixas muito pequenas). Arial Negrito, bolinha do
# mesmo tamanho do texto, sem contorno (só preenchimento).
_FATOR_MARGEM_LEGENDA = 0.6  # espaço entre o desenho e a legenda, em relação à altura do texto

# Tamanho de referência (pt) usado pra montar a fonte da legenda — grande
# de propósito, bem maior que o alvo final (`configuracoes.altura_legenda_mm()`).
# Ver `_fonte_e_escala_legenda` pra entender por quê.
_TAMANHO_FONTE_REFERENCIA_PT = 24.0


def _fonte_e_escala_legenda() -> tuple[QFont, float]:
    """Fonte Arial Negrito num tamanho grande fixo (`_TAMANHO_FONTE_REFERENCIA_PT`)
    + o fator de escala geométrica que, aplicado via `QGraphicsItem.setScale`,
    encolhe o texto até a altura de caixa-alta valer `configuracoes.altura_legenda_mm()`
    na cena.

    Pedir a fonte JÁ no tamanho pequeno final (algo entre 1 e 3pt, pelas
    contas) funciona matematicamente, mas na prática o rasterizador de
    fonte perde precisão nesse tamanho — cada letra individualmente ainda
    sai legível, mas o espaçamento entre elas (`advance width`,
    arredondado pro pixel mais próximo nesse tamanho minúsculo) fica
    errado, e a palavra sai com uma quebra estranha no meio (ex.: "CORES:"
    saindo "CO RES:"). Desenhar grande e encolher por transformação
    geométrica depois evita esse problema — o layout do texto é calculado
    no tamanho grande (preciso) e só a apresentação final é escalada.

    Não cacheia (era cacheado antes) porque o valor pode mudar em
    Configurações no meio da sessão — é uma conta bem barata, recalcular
    a cada exportação não pesa."""
    fonte = QFont("Arial", -1, QFont.Weight.Bold)
    fonte.setPointSizeF(_TAMANHO_FONTE_REFERENCIA_PT)
    cap_height_referencia = QFontMetricsF(fonte).capHeight()
    altura_alvo = configuracoes.altura_legenda_mm()
    escala = altura_alvo / cap_height_referencia if cap_height_referencia > 0 else 1.0
    return fonte, escala

# Padrão esperado pela gráfica nos arquivos entregues: tudo preto, só o
# vinco sai tracejado (os demais tipos — corte, corte-serra, meio-corte,
# dobra — saem contínuos), todos na mesma espessura de 1,0pt — mesmo
# padrão usado no CorelDRAW (ver `_LARGURA_LINHA_MM` em `corel_bridge.py`)
# — em vez das espessuras variadas por tipo que a pré-visualização em
# tela usa (0.4-0.6, pensadas só pra ficarem legíveis na tela, nunca
# pra sair fiéis no arquivo final).
_COR_EXPORTACAO = QColor(0, 0, 0)
_LARGURA_LINHA_MM = 1.0 * 25.4 / 72  # 1,0pt


def _traco_ajustado(comprimento: float, traco: float, espaco: float) -> tuple[float, float]:
    """Ajusta o par (traço, espaço) pra caber um número inteiro de vezes
    dentro do comprimento da linha, mantendo a proporção traço:espaço.

    Sem isso, o último ciclo antes do fim da linha quase nunca fecha
    exatamente — sobra um traço cortado pela metade bem no final. Numa
    linha comprida isso passa despercebido, mas nos vincos curtos deste
    layout (às vezes só uns 40mm) sobra pouca margem de erro: esse traço
    cortado aparece bem menor que os outros, lendo como "um traço grande e
    um pequeno" no meio do que devia ser um padrão uniforme. Arredondar
    pro número de ciclos mais próximo e redistribuir o comprimento entre
    eles garante que todo traço sai do mesmo tamanho, do início ao fim."""
    periodo = traco + espaco
    if periodo <= 0 or comprimento <= 0:
        return traco, espaco
    ciclos = max(1, round(comprimento / periodo))
    fator = comprimento / (ciclos * periodo)
    return traco * fator, espaco * fator


class _LegendaExportacao:
    """Desenha a legenda de cores como itens reais da cena, só durante a
    exportação (adicionados antes de renderizar, removidos logo em
    seguida) — assim o SVG/PDF/JPG sai com a legenda de verdade, sem
    afetar a pré-visualização em tela (que usa um widget à parte, ver
    `PainelLegendaCores` em `preview_canvas.py`).

    Fica ACIMA do desenho (acima de `rect_desenho.top()`) e usa
    QFontMetricsF pra medir o texto de verdade, em vez de estimar a
    largura — as duas causas do bug de viewBox que existia quando a
    legenda ainda fazia parte da cena permanente."""

    def __init__(self, scene: QGraphicsScene, cores: list[CorImpressao], rect_desenho: QRectF) -> None:
        self._scene = scene
        self._itens: list = []
        if not cores:
            return

        self._fonte, self._escala = _fonte_e_escala_legenda()
        metrics = QFontMetricsF(self._fonte)  # métrico no tamanho grande de referência
        altura_fonte = metrics.height() * self._escala  # convertido pra mm reais da cena
        margem = altura_fonte * _FATOR_MARGEM_LEGENDA
        diametro = configuracoes.altura_legenda_mm()  # bolinha do mesmo tamanho do texto, sempre

        x = 0.0
        y = rect_desenho.top() - margem - altura_fonte
        self._adicionar_texto("CORES:", x, y, QColor(0, 0, 0))
        x += metrics.horizontalAdvance("CORES:") * self._escala + diametro * 0.5

        # `setPos(x, y)` ancora o topo da caixa do texto em y, não a linha
        # de base — o corpo visível da letra (maiúscula, sem descendente)
        # fica entre `y + ascent - capHeight` e `y + ascent`. Centraliza a
        # bolinha nesse intervalo, não na altura de linha inteira (que
        # inclui espaço acima/abaixo da letra em si).
        raio = diametro / 2
        centro_y = y + (metrics.ascent() - metrics.capHeight() / 2) * self._escala
        for cor in cores:
            bolinha = QGraphicsEllipseItem(QRectF(x, centro_y - raio, diametro, diametro))
            bolinha.setBrush(QBrush(QColor(cor.r, cor.g, cor.b)))
            bolinha.setPen(Qt.PenStyle.NoPen)  # sem contorno, só preenchimento (pedido do usuário)
            scene.addItem(bolinha)
            self._itens.append(bolinha)
            x += diametro + diametro * 0.5

            self._adicionar_texto(cor.nome, x, y, QColor(cor.r, cor.g, cor.b))
            x += metrics.horizontalAdvance(cor.nome) * self._escala + diametro * 1.5

    def _adicionar_texto(self, texto: str, x: float, y: float, cor: QColor) -> None:
        # Desenha no tamanho grande de referência (`self._fonte`) e encolhe
        # via transformação geométrica (`setScale`) — ver
        # `_fonte_e_escala_legenda` pro motivo (evita o texto sair com
        # letras "quebradas"/mal espaçadas que aparecem pedindo a fonte já
        # pequena direto). `setScale` escala em torno da origem local do
        # item (0, 0), que é o mesmo ponto ancorado por `setPos` — a
        # posição (x, y) continua sendo o topo-esquerda de verdade.
        #
        # Desenhado como `QGraphicsPathItem` (contorno via
        # `QPainterPath.addText`), não `QGraphicsSimpleTextItem` — o
        # `QSvgGenerator` posiciona/dimensiona texto nativo errado quando
        # o item tem `setScale()` (mesmo bug de fundo documentado em
        # `desenhar_texto_escalado`, em mockup_itens.py; confirmado aqui
        # via inspeção do SVG exportado no navegador, texto saindo enorme
        # e fora do lugar). Path vetorial não passa pelo mesmo caminho de
        # serialização de texto do gerador, então não sofre o bug.
        metrics = QFontMetricsF(self._fonte)
        caminho = QPainterPath()
        caminho.addText(QPointF(0, metrics.ascent()), self._fonte, texto)
        item = QGraphicsPathItem(caminho)
        item.setPen(Qt.PenStyle.NoPen)
        item.setBrush(QBrush(cor))
        item.setScale(self._escala)
        item.setPos(x, y)
        self._scene.addItem(item)
        self._itens.append(item)

    def remover(self) -> None:
        for item in self._itens:
            self._scene.removeItem(item)


def _rect_com_legenda(
    scene: QGraphicsScene, layout: LayoutCaixa
) -> tuple[QRectF, _LegendaExportacao]:
    # O retângulo do desenho é o tamanho real da faca (`largura_total` ×
    # `altura_total`), NUNCA `scene.itemsBoundingRect()` — esse inclui a
    # margem das alças de seleção de todo elemento de mockup (14mm pra
    # cada lado, ver `ElementoMockup.boundingRect()`), o que inflava o
    # arquivo exportado bem além do tamanho real da caixa assim que
    # qualquer elemento de mockup existia na cena. O conteúdo de mockup
    # em si ainda sai no arquivo — `scene.render()` desenha tudo que
    # intersecta esse retângulo, só o TAMANHO do arquivo é que agora vem
    # da caixa, não da soma de tudo que existe na cena.
    rect_desenho = QRectF(0.0, 0.0, layout.largura_total, layout.altura_total)
    legenda = _LegendaExportacao(scene, layout.cores_legenda, rect_desenho)
    rect_final = rect_desenho
    if legenda._itens:
        for item in legenda._itens:
            rect_final = rect_final.united(item.sceneBoundingRect())
    return rect_final, legenda


class _SelecaoOculta:
    """Desmarca toda seleção de elemento de mockup durante a exportação
    e restaura depois — as alças de redimensionar/rotacionar (ver
    `ElementoMockup._pintar_selecao`) só deveriam aparecer editando na
    tela, nunca dentro de um arquivo exportado."""

    def __init__(self, scene: QGraphicsScene) -> None:
        self._selecionados = list(scene.selectedItems())
        for item in self._selecionados:
            item.setSelected(False)

    def restaurar(self) -> None:
        for item in self._selecionados:
            item.setSelected(True)


class _PenasExportacao:
    """Normaliza temporariamente as linhas técnicas pro padrão esperado nos
    arquivos entregues à gráfica — tudo preto, só o vinco tracejado, com
    traço fino e curto (ver `_COR_EXPORTACAO`/`_TRACO_VINCO_MM` acima) — e
    troca o QPen cosmetic (usado na pré-visualização em tela pra manter
    espessura constante em qualquer zoom, ver `_desenhar_linhas_tecnicas`
    em `preview_canvas.py`) por um pen não-cosmetic equivalente: os
    motores de pintura vetorial/raster usados no `scene.render()` de
    exportação não preservam corretamente o dash pattern de um pen
    cosmetic (ele sai sólido mesmo em linhas que deveriam ser
    tracejadas). Restaura os pens originais (cor, estilo e cosmetic)
    depois do render, então a pré-visualização em tela nunca é afetada
    por isso.

    Também força a espessura pro mesmo padrão real usado no CorelDRAW
    (`_LARGURA_LINHA_MM`, 1,0pt) — a espessura original do pen vem de
    `_ESTILO_POR_TIPO` em `preview_canvas.py`, pensada pra ficar legível
    na tela em qualquer zoom, não pra representar a espessura real de
    impressão.

    Cada vinco é ajustado (ver `_traco_ajustado`) pra caber um número
    inteiro de ciclos traço+espaço no seu próprio comprimento, pra nunca
    sobrar um traço cortado pela metade bem no fim da linha — que é o que
    lia como "um traço grande e um pequeno" no meio de um padrão que
    devia ser uniforme."""

    def __init__(self, scene: QGraphicsScene, fator: float = 1.0) -> None:
        # `fator` engrossa traço e tracejado juntos (layout reduzido numa
        # folha, ex.: a de aprovação, onde o traço de 1 pt sumiria).
        self._originais: list[tuple[QGraphicsLineItem | QGraphicsPathItem, QPen]] = []
        for item in scene.items():
            # Retas da faca são QGraphicsLineItem; ARCOS da faca são
            # QGraphicsPathItem marcados com o tipo de linha em data(0).
            arco = isinstance(item, QGraphicsPathItem) and isinstance(item.data(0), TipoLinha)
            if not isinstance(item, QGraphicsLineItem) and not arco:
                continue
            pen_original = item.pen()
            if not pen_original.isCosmetic():
                continue
            self._originais.append((item, pen_original))
            pen_exportacao = QPen(pen_original)
            pen_exportacao.setCosmetic(False)
            pen_exportacao.setColor(_COR_EXPORTACAO)
            pen_exportacao.setWidthF(_LARGURA_LINHA_MM * fator)
            if item.data(0) == TipoLinha.VINCO:
                # setDashPattern usa múltiplos da espessura da pena, não mm
                # direto — converte pra sair no tamanho ajustado calculado
                # por `_traco_ajustado`. Lê de Configurações a cada chamada
                # (não cacheia) pelo mesmo motivo de `_fonte_e_escala_legenda`.
                comprimento = item.path().length() if arco else item.line().length()
                traco_cfg, espaco_cfg = configuracoes.traco_vinco_mm()
                traco, espaco = _traco_ajustado(comprimento, traco_cfg * fator, espaco_cfg * fator)
                pen_exportacao.setStyle(Qt.PenStyle.CustomDashLine)
                largura = _LARGURA_LINHA_MM * fator
                pen_exportacao.setDashPattern([traco / largura, espaco / largura])
            else:
                pen_exportacao.setStyle(Qt.PenStyle.SolidLine)
            item.setPen(pen_exportacao)

    def restaurar(self) -> None:
        for item, pen_original in self._originais:
            item.setPen(pen_original)


# ── API pública — uma função por formato ────────────────────────────────


def exportar_svg(scene: QGraphicsScene, layout: LayoutCaixa, caminho: str) -> None:
    rect, legenda = _rect_com_legenda(scene, layout)
    selecao = _SelecaoOculta(scene)
    penas = _PenasExportacao(scene)
    sem_cache = cache_desligado(scene)
    sem_cache.__enter__()  # vetorial de verdade, não a imagem do cache de tela
    try:
        # QSvgGenerator só aceita resolução em DPI inteiro. Pra converter
        # "unidades da cena = mm" em tamanho físico SEM erro de arredondamento,
        # usa um fator de escala 100 com resolução 2540 DPI — 2540/100 = 25.4
        # (mm por polegada) exatos, então 1 unidade da cena = 1 mm no arquivo.
        fator = 100
        gerador = QSvgGenerator()
        gerador.setFileName(caminho)
        gerador.setSize(QSize(round(rect.width() * fator), round(rect.height() * fator)))
        gerador.setViewBox(rect)
        gerador.setResolution(2540)
        gerador.setTitle("Layout de caixa")
        gerador.setDescription("Gerado pelo Autoline")

        painter = QPainter(gerador)
        if not painter.isActive():
            raise RuntimeError(f"Não consegui iniciar a exportação SVG em: {caminho}")
        try:
            # `target` explícito é essencial aqui — sem ele, o Qt usa o
            # viewport do device (painter) como destino padrão, e a
            # combinação `fator=100`/`setResolution(2540)` acima faz esse
            # viewport implícito sair com uma escala DUPLICADA (multiplica
            # de novo o que o mapeamento lógico→viewBox já fazia). Um
            # elemento de mockup com posição própria (`setPos`, ao
            # contrário das linhas da dieline, que usam coordenadas
            # absolutas) saía com a posição inteira multiplicada por
            # ~100 — confirmado comparando a matriz `transform` gerada no
            # SVG com/sem `target` explícito. `exportar_pdf` logo abaixo
            # NÃO tem esse fator manual e já funciona certo sem `target`
            # (confirmado à parte) — só SVG e JPG (ver `exportar_jpg`)
            # precisam disso.
            scene.render(painter, target=rect, source=rect)
        finally:
            painter.end()
    finally:
        sem_cache.__exit__(None, None, None)
        penas.restaurar()
        selecao.restaurar()
        legenda.remover()


def exportar_pdf(scene: QGraphicsScene, layout: LayoutCaixa, caminho: str) -> None:
    rect, legenda = _rect_com_legenda(scene, layout)
    selecao = _SelecaoOculta(scene)
    penas = _PenasExportacao(scene)
    sem_cache = cache_desligado(scene)
    sem_cache.__enter__()  # vetorial de verdade, não a imagem do cache de tela
    try:
        # As coordenadas da cena já são em mm — a página do PDF sai com o
        # tamanho exato do layout, então o desenho fica na escala real 1:1,
        # sem margens.
        tamanho_pagina = QPageSize(
            QSizeF(max(rect.width(), 1.0), max(rect.height(), 1.0)),
            QPageSize.Unit.Millimeter,
        )
        layout_pagina = QPageLayout(
            tamanho_pagina, QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0)
        )

        impressora = QPrinter(QPrinter.PrinterMode.HighResolution)
        impressora.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        impressora.setOutputFileName(caminho)
        impressora.setPageLayout(layout_pagina)

        painter = QPainter(impressora)
        if not painter.isActive():
            raise RuntimeError(f"Não consegui iniciar a exportação PDF em: {caminho}")
        try:
            scene.render(painter, source=rect)
        finally:
            painter.end()
    finally:
        sem_cache.__exit__(None, None, None)
        penas.restaurar()
        selecao.restaurar()
        legenda.remover()


def exportar_jpg(
    scene: QGraphicsScene, layout: LayoutCaixa, caminho: str, *, dpi: int | None = None
) -> None:
    """Exporta em raster (JPG) na resolução `dpi` — por padrão, o valor
    configurado em Configurações (`configuracoes.dpi_exportacao_jpg()`,
    300 se nunca ajustado).

    Antes disso a resolução vinha de um fator fixo de "pixels por mm da
    cena" (supersample=4), o que dava só ~101 DPI — pouco pra imprimir com
    nitidez — e a imagem não carregava a informação de DPI, então qualquer
    programa que abrisse o JPG assumia ~96 DPI e mostrava/imprimia o
    arquivo bem maior (e mais borrado) do que o tamanho real em mm.
    Calcular a partir de um DPI alvo e gravar esse DPI na própria imagem
    (`setDotsPerMeterX/Y`) resolve os dois problemas de uma vez.
    """
    if dpi is None:
        dpi = configuracoes.dpi_exportacao_jpg()
    rect, legenda = _rect_com_legenda(scene, layout)
    selecao = _SelecaoOculta(scene)
    penas = _PenasExportacao(scene)
    sem_cache = cache_desligado(scene)
    sem_cache.__enter__()  # vetorial de verdade, não a imagem do cache de tela
    try:
        pixels_por_mm = dpi / 25.4
        largura = max(1, round(rect.width() * pixels_por_mm))
        altura = max(1, round(rect.height() * pixels_por_mm))

        imagem = QImage(largura, altura, QImage.Format.Format_RGB32)
        imagem.fill(0xFFFFFFFF)  # fundo branco
        dots_por_metro = round(pixels_por_mm * 1000)
        imagem.setDotsPerMeterX(dots_por_metro)
        imagem.setDotsPerMeterY(dots_por_metro)

        painter = QPainter(imagem)
        if not painter.isActive():
            raise RuntimeError(f"Não consegui preparar a imagem para exportação em: {caminho}")
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            # `target` explícito em PIXELS DO DEVICE (não em mm, ao
            # contrário do `source`) — sem isso, o posicionamento de
            # qualquer elemento de mockup (que tem `setPos` próprio, ao
            # contrário das linhas da dieline em coordenadas absolutas)
            # saía visivelmente errado: testado com um retângulo em
            # (30,30)mm saindo desenhado em ~(5,5)mm na imagem final, bem
            # menor e fora do lugar. Confirmado comparando o resultado
            # com/sem `target` explícito nessas unidades.
            scene.render(painter, target=QRectF(0, 0, largura, altura), source=rect)
        finally:
            painter.end()
    finally:
        sem_cache.__exit__(None, None, None)
        penas.restaurar()
        selecao.restaurar()
        legenda.remover()

    if not imagem.save(caminho, "JPG", quality=95):
        raise RuntimeError(
            f"Não consegui salvar o JPG em: {caminho} (verifique permissão de escrita e espaço em disco)"
        )
