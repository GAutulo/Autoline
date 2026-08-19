"""Ponte de automação COM com o CorelDRAW — desenha o layout técnico
diretamente num documento do CorelDRAW, do jeito que o sistema original em
C# fazia (em vez de só exportar um arquivo à parte).

Só funciona no Windows, com o CorelDRAW instalado (usa win32com/pywin32).
CorelDRAW é servidor COM single-instance: `Dispatch` sozinho já resolve
tanto "conectar numa instância aberta" quanto "abrir uma nova se não
tiver nenhuma rodando" — não precisa de `GetActiveObject`.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QFont, QFontMetricsF

from ..models import LayoutCaixa, TipoLinha
from . import configuracoes
from .mockup_checklist import ElementoChecklistCores
from .mockup_checklist import _ALTURA_LINHA_MM as _CHECKLIST_ALTURA_LINHA_MM
from .mockup_checklist import _ESPACO_CAIXA_TEXTO_FATOR as _CHECKLIST_ESPACO_CAIXA_TEXTO_FATOR
from .mockup_checklist import _ESPACO_ENTRE_LINHAS_FATOR as _CHECKLIST_ESPACO_ENTRE_LINHAS_FATOR
from .mockup_checklist import _ESPESSURA_TRACO_FATOR as _CHECKLIST_ESPESSURA_TRACO_FATOR
from .mockup_formas import ElementoLinha, ElementoRetangulo
from .mockup_imagem import ElementoImagem
from .mockup_itens import ElementoMockup, GrupoMockup
from .mockup_logo import ElementoLogoVetorial
from .mockup_texto import ElementoTexto

_CDR_MILLIMETER = 3

# Padrão esperado pela gráfica: tudo preto. Só o vinco sai tracejado — os
# demais tipos (corte, corte-serra, meio-corte, dobra) saem contínuos. A
# pré-visualização em tela usa cores por tipo pra facilitar a edição (ver
# `_ESTILO_POR_TIPO` em `preview_canvas.py`), mas o arquivo entregue via
# CorelDRAW segue a mesma convenção do SVG/PDF/JPG (ver `exportacao.py`).
_COR_LINHA = (0, 0, 0)

# Padrão da gráfica: linhas em 1pt. Outline.Width usa a unidade do
# documento (mm — ver `doc.Unit` em `desenhar_layout`), então convertemos
# pt → mm aqui (1pt = 1/72 pol = 25,4/72 mm) em vez de guardar o valor já
# convertido, pra facilitar ajustar no futuro em pt.
_LARGURA_LINHA_PT = 1.0
_LARGURA_LINHA_MM = _LARGURA_LINHA_PT * 25.4 / 72

# Traço do vinco — DashLength/GapLength do CorelDRAW são multiplicadores
# INTEIROS da espessura da linha (Outline.Width), não mm direto —
# confirmado testando direto contra o CorelDRAW. O valor em mm configurável
# (`configuracoes.traco_vinco_mm()`) é convertido pro multiplicador mais
# próximo na hora de desenhar (ver `_estilo_tracejado_vinco`).


def _estilo_tracejado_vinco(app):
    """Cria (e devolve) um `OutlineStyle` novo pro traço do vinco, a
    partir do traço/espaço configurado em mm (Configurações) — convertido
    pro multiplicador inteiro da espessura da linha, unidade real do
    CorelDRAW.

    A API documentada é `OutlineStyles.Add()` seguida de
    `SetDashLength`/`SetGapLength` — bem diferente do antigo
    `Application.CreateOutlineStyle(count, array)` que o código usava
    antes (aceitava a chamada sem erro, mas renderizava errado).

    Duas coisas confirmadas testando direto contra o CorelDRAW: (1)
    `DashLength`/`GapLength` só aceitam número inteiro (valor fracionário
    é truncado, não arredondado) — por isso não dá pra replicar aqui o
    ajuste fino por comprimento de linha que existe em `exportacao.py`
    (`_traco_ajustado`), que depende de valores fracionários; (2) os
    setters são pouco confiáveis — às vezes simplesmente não pegam —
    mas atribuir `DashCount = 3` antes de chamar os Set* (mesmo que o
    valor em si não "pegue", ele fica 1 do mesmo jeito) faz os dois
    setters funcionarem de forma consistente (15/15 em teste direto)."""
    traco_mm, espaco_mm = configuracoes.traco_vinco_mm()
    dash_length = max(1, round(traco_mm / _LARGURA_LINHA_MM))
    gap_length = max(1, round(espaco_mm / _LARGURA_LINHA_MM))

    estilo = app.OutlineStyles.Add()
    estilo.DashCount = 3
    estilo.SetDashLength(1, dash_length)
    estilo.SetGapLength(1, gap_length)
    app.OutlineStyles.Save()
    return estilo


_FONTE_LEGENDA = "Arial"

# Legenda de cores: tamanho configurável em Configurações — não escala
# com o tamanho do layout, então não fica grande demais numa caixa
# pequena. Bolinha sem contorno (só preenchimento). O `Size` do
# `CreateArtisticText` não é em mm — pelos testes numerados que o usuário
# comparou contra uma caixa de referência, `Size=6` deu 1,5mm de altura
# (proporção confirmada: ~4pt de `Size` por mm de altura).
_FATOR_SIZE_CDR_POR_MM = 4.0
_MARGEM_LEGENDA_MM = 0.6  # relativo à altura da legenda, ver _desenhar_legenda


class CorelIndisponivel(RuntimeError):
    """Levantado quando não dá pra conectar ou desenhar no CorelDRAW."""


def conectar():
    """Conecta a uma instância do CorelDRAW já aberta, ou abre uma nova se
    não houver nenhuma rodando. Devolve o objeto `Application` (COM)."""
    try:
        import win32com.client
    except ImportError as exc:
        raise CorelIndisponivel(
            "pywin32 não está instalado — a automação com o CorelDRAW só "
            "funciona no Windows, com o pacote pywin32 instalado."
        ) from exc

    try:
        app = win32com.client.gencache.EnsureDispatch("CorelDRAW.Application")
    except Exception as exc:  # noqa: BLE001
        raise CorelIndisponivel(
            "Não consegui conectar ao CorelDRAW. Confirme se ele está instalado."
        ) from exc

    app.Visible = True
    return app


def desenhar_layout(
    app, layout: LayoutCaixa, elementos_mockup: list[ElementoMockup] | None = None
) -> None:
    """Desenha as linhas técnicas do layout — e, se fornecidos, os
    elementos de mockup (texto, formas, imagem, logotipo, checklist) por
    cima — num documento NOVO do CorelDRAW. Sempre cria um documento,
    nunca reaproveita um que já esteja aberto (senão a automação desenha
    por cima de um arquivo que pode estar em edição)."""
    doc = app.CreateDocument()
    doc.Unit = _CDR_MILLIMETER

    layer = doc.ActiveLayer
    altura = layout.altura_total
    cor_linha = app.CreateRGBColor(*_COR_LINHA)
    estilo_vinco = _estilo_tracejado_vinco(app)  # um só, reaproveitado por todo vinco do layout

    for linha in layout.linhas:
        # CorelDRAW usa eixo Y crescendo pra cima; nosso layout usa Y
        # crescendo pra baixo (mesma convenção da pré-visualização e do
        # SVG/PDF/JPG) — espelha verticalmente pra sair com a mesma
        # orientação que já aparece no app.
        y1 = altura - linha.y1
        y2 = altura - linha.y2
        shape = layer.CreateLineSegment(linha.x1, y1, linha.x2, y2)
        shape.Outline.Color = cor_linha
        shape.Outline.Width = _LARGURA_LINHA_MM

        if linha.tipo == TipoLinha.VINCO:
            shape.Outline.Style = estilo_vinco

    _desenhar_legenda(app, layer, layout)

    for elemento in elementos_mockup or []:
        _desenhar_elemento_mockup(app, layer, elemento, altura)

    doc.ActiveWindow.Refresh()


# ── Elementos de mockup (Fase 2) ──────────────────────────────────────
# DashLength/GapLength e Size de texto já precisaram de teste ao vivo
# contra o CorelDRAW antes (ver `_estilo_tracejado_vinco`/`_desenhar_legenda`
# acima) — o mesmo valeu aqui pra `SetPosition`/`SetSize`/`Rotate`, que não
# funcionam do jeito mais "óbvio". Confirmado testando direto (CorelDRAW
# 22, documento em mm):
#   - `Shape.SetPosition(x, y)` e `Shape.SetSize(w, h)` são ancorados no
#     canto SUPERIOR-esquerdo da shape (`LeftX`/`TopY`), não no centro
#     nem no canto inferior-esquerdo — mesmo o documento inteiro usando Y
#     crescendo pra cima.
#   - `Shape.Rotate(ângulo)` gira em torno do CENTRO atual da shape, no
#     sentido ANTI-horário pra ângulo positivo (padrão matemático — Y do
#     documento cresce pra cima). Como a nossa cena usa Y pra baixo (temos
#     que espelhar verticalmente pra converter, ver `altura - y` acima), e
#     Qt gira no sentido HORÁRIO pra ângulo positivo (padrão de tela, Y pra
#     baixo), o espelho de eixo inverte também o sentido da rotação — por
#     isso `angulo_cdr = -angulo_qt` (não uma coincidência: as duas
#     convenções usam a mesma fórmula de rotação "matemática padrão", só
#     que em sistemas de eixo Y opostos).
#   - `Layer.Import(caminho, 0, None)` (não `Document.Import`, que não
#     existe nessa API) importa arquivo raster ou vetorial como 1 shape
#     só (SVG com vários elementos vem AGRUPADO automaticamente) — dá pra
#     tratar imagem e logotipo vetorial exatamente da mesma forma.
#   - Pra girar várias shapes juntas em torno de um centro comum (o
#     checklist, que é várias shapes por trás dos panos), cria todas
#     paradas (ângulo 0), junta numa `ShapeRange` (`app.CreateShapeRange()`
#     + `.Add()`) e gira a RANGE — ela gira em torno do centro combinado
#     da seleção, mantendo a posição relativa entre as peças (confirmado
#     testando 2 retângulos: distância entre os centros idêntica antes e
#     depois de girar a range 90°).
_TAMANHO_FONTE_REFERENCIA_CDR = 200.0


def _rotacao_absoluta_graus(elemento: ElementoMockup) -> float:
    """`elemento.rotation()` sozinho só dá a rotação LOCAL, relativa ao
    pai imediato — dentro de um `GrupoMockup` já rotacionado, a rotação
    visual de verdade é a soma da rotação de todo mundo na cadeia."""
    total = 0.0
    item: ElementoMockup | None = elemento
    while item is not None:
        total += item.rotation()
        item = item.parentItem()
    return total


def _centro_e_rotacao_cdr(elemento: ElementoMockup, altura_total: float) -> tuple[float, float, float]:
    """(x, y, ângulo) do CENTRO do elemento já convertidos pro sistema do
    CorelDRAW — ver nota grande acima pro motivo de cada conversão."""
    centro_cena = elemento.mapToScene(QPointF(elemento.largura / 2, elemento.altura / 2))
    x = centro_cena.x()
    y = altura_total - centro_cena.y()
    angulo = -_rotacao_absoluta_graus(elemento)
    return x, y, angulo


def _cor_rgb(app, cor_impressao):
    return app.CreateRGBColor(cor_impressao.r, cor_impressao.g, cor_impressao.b)


def _desenhar_elemento_mockup(app, layer, elemento: ElementoMockup, altura_total: float) -> None:
    if isinstance(elemento, GrupoMockup):
        for filho in elemento.elementos:
            _desenhar_elemento_mockup(app, layer, filho, altura_total)
        return
    if isinstance(elemento, ElementoTexto):
        _desenhar_texto_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, ElementoChecklistCores):
        _desenhar_checklist_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, ElementoRetangulo):
        _desenhar_retangulo_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, ElementoLinha):
        _desenhar_linha_mockup_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, (ElementoImagem, ElementoLogoVetorial)):
        _desenhar_imagem_cdr(app, layer, elemento, altura_total)
    # Tipo desconhecido: ignora silenciosamente — não é motivo pra falhar
    # a exportação inteira por causa de 1 elemento não reconhecido.


def _desenhar_retangulo_cdr(app, layer, elemento: ElementoRetangulo, altura_total: float) -> None:
    x, y, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    shape = layer.CreateRectangle2(
        x - elemento.largura / 2, y - elemento.altura / 2, elemento.largura, elemento.altura
    )
    if elemento.preenchido:
        _aplicar_cor_preenchimento(app, shape, elemento.cor_tinta.r, elemento.cor_tinta.g, elemento.cor_tinta.b)
    else:
        shape.Fill.ApplyNoFill()
    shape.Outline.Color = _cor_rgb(app, elemento.cor_tinta)
    shape.Outline.Width = elemento.largura_traco
    if angulo:
        shape.Rotate(angulo)


def _desenhar_linha_mockup_cdr(app, layer, elemento: ElementoLinha, altura_total: float) -> None:
    x, y, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    shape = layer.CreateLineSegment(x - elemento.largura / 2, y, x + elemento.largura / 2, y)
    shape.Outline.Color = _cor_rgb(app, elemento.cor_tinta)
    shape.Outline.Width = elemento.largura_traco
    if angulo:
        shape.Rotate(angulo)


def _desenhar_texto_cdr(app, layer, elemento: ElementoTexto, altura_total: float) -> None:
    x, y, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    shape = layer.CreateArtisticText(
        0, 0, elemento.texto, Font=elemento.fonte_familia, Size=_TAMANHO_FONTE_REFERENCIA_CDR
    )
    shape.Text.Story.Bold = elemento.negrito
    _aplicar_cor_preenchimento(app, shape, elemento.cor_tinta.r, elemento.cor_tinta.g, elemento.cor_tinta.b)
    # Força pro tamanho exato que o usuário viu na tela (ver `SetSize`
    # na nota grande acima) — em vez de tentar replicar a métrica de
    # fonte do Qt aqui, deixa o CorelDRAW medir a fonte dele mesmo e só
    # estica pro tamanho final; mesmo princípio de `ElementoTexto`, que
    # também estica o texto pra caber na caixa em vez de mudar o "Size".
    shape.SetSize(elemento.largura, elemento.altura)
    shape.SetPosition(x - elemento.largura / 2, y + elemento.altura / 2)
    if angulo:
        shape.Rotate(angulo)


def _desenhar_imagem_cdr(app, layer, elemento, altura_total: float) -> None:
    x, y, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    antes = layer.Shapes.Count
    layer.Import(elemento.caminho_arquivo, 0, None)
    if layer.Shapes.Count == antes:
        return  # import falhou — não trava a exportação inteira por causa de 1 imagem
    shape = layer.Shapes.Item(layer.Shapes.Count)
    shape.SetSize(elemento.largura, elemento.altura)
    shape.SetPosition(x - elemento.largura / 2, y + elemento.altura / 2)
    if angulo:
        shape.Rotate(angulo)


def _desenhar_checklist_cdr(app, layer, elemento: ElementoChecklistCores, altura_total: float) -> None:
    """Mesma matemática de layout de `ElementoChecklistCores._pintar_conteudo`
    (por isso os imports de `mockup_checklist` no topo do arquivo — uma
    cópia divergente dessas constantes aqui seria fácil de esquecer de
    manter em sincronia), só que criando shapes de verdade em vez de
    pintar num QPainter. Cada linha (quadradinho + texto) nasce parada
    (ângulo 0) na posição final; se o elemento como um todo estiver
    rotacionado, todas as shapes entram numa `ShapeRange` e giram juntas
    no final (ver nota grande acima pro motivo de girar por último)."""
    x_centro, y_centro, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    largura_natural, altura_natural = elemento._layout_natural()
    escala_x = elemento.largura / largura_natural if largura_natural else 1.0
    escala_y = elemento.altura / altura_natural if altura_natural else 1.0

    origem_x = x_centro - elemento.largura / 2
    origem_y = y_centro + elemento.altura / 2

    def ponto_cdr(x_qt: float, y_qt: float) -> tuple[float, float]:
        # (x, y) local do desenho Qt (0,0 = canto superior-esquerdo, Y
        # cresce pra baixo) → posição real no documento CorelDRAW, já
        # escalado (independente por eixo) e sem rotação — a rotação do
        # elemento inteiro é aplicada depois, numa ShapeRange única.
        return origem_x + x_qt * escala_x, origem_y - y_qt * escala_y

    fonte_ref = QFont(elemento.fonte_familia)
    fonte_ref.setPointSizeF(200.0)
    metrica = QFontMetricsF(fonte_ref)
    altura_ref = metrica.capHeight() or metrica.ascent()
    escala_fonte = _CHECKLIST_ALTURA_LINHA_MM / altura_ref if altura_ref else 1.0

    espaco_linhas = _CHECKLIST_ALTURA_LINHA_MM * _CHECKLIST_ESPACO_ENTRE_LINHAS_FATOR
    espaco_caixa_texto = _CHECKLIST_ALTURA_LINHA_MM * _CHECKLIST_ESPACO_CAIXA_TEXTO_FATOR
    espessura_traco = max(
        0.05, _CHECKLIST_ALTURA_LINHA_MM * _CHECKLIST_ESPESSURA_TRACO_FATOR * min(escala_x, escala_y)
    )
    cor = _cor_rgb(app, elemento.cor_tinta)

    formas = []
    y_qt = 0.0
    for variante in elemento.variantes:
        x0, y0 = ponto_cdr(0.0, y_qt)
        x1, y1 = ponto_cdr(_CHECKLIST_ALTURA_LINHA_MM, y_qt + _CHECKLIST_ALTURA_LINHA_MM)
        quadrado = layer.CreateRectangle2(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
        quadrado.Fill.ApplyNoFill()
        quadrado.Outline.Color = cor
        quadrado.Outline.Width = espessura_traco
        formas.append(quadrado)

        largura_texto_qt = max(0.1, metrica.horizontalAdvance(variante) * escala_fonte)
        tx0, ty0 = ponto_cdr(_CHECKLIST_ALTURA_LINHA_MM + espaco_caixa_texto, y_qt)
        tx1, ty1 = ponto_cdr(
            _CHECKLIST_ALTURA_LINHA_MM + espaco_caixa_texto + largura_texto_qt,
            y_qt + _CHECKLIST_ALTURA_LINHA_MM,
        )
        texto_shape = layer.CreateArtisticText(
            0, 0, variante, Font=elemento.fonte_familia, Size=_TAMANHO_FONTE_REFERENCIA_CDR
        )
        _aplicar_cor_preenchimento(app, texto_shape, elemento.cor_tinta.r, elemento.cor_tinta.g, elemento.cor_tinta.b)
        texto_shape.SetSize(max(0.1, abs(tx1 - tx0)), max(0.1, abs(ty1 - ty0)))
        texto_shape.SetPosition(min(tx0, tx1), max(ty0, ty1))
        formas.append(texto_shape)

        y_qt += _CHECKLIST_ALTURA_LINHA_MM + espaco_linhas

    if angulo and formas:
        intervalo = app.CreateShapeRange()
        for forma in formas:
            intervalo.Add(forma)
        intervalo.Rotate(angulo)


def _desenhar_legenda(app, layer, layout: LayoutCaixa) -> None:
    """Desenha a legenda de cores de impressão (nome + bolinha) acima do
    layout — mesmo conteúdo que já vai pro SVG/PDF/JPG (ver
    `_LegendaExportacao` em `exportacao.py`), só que direto no documento
    do CorelDRAW. O nome de cada cor sai escrito na própria cor (pedido do
    usuário), igual à pré-visualização em tela — só o título "CORES:" fica
    preto. Tamanho vem de Configurações (não escala com o layout)."""
    if not layout.cores_legenda:
        return

    altura = configuracoes.altura_legenda_mm()
    tamanho_fonte_cdr = altura * _FATOR_SIZE_CDR_POR_MM
    raio_bolinha = altura / 2
    margem = altura * _MARGEM_LEGENDA_MM

    # CorelDRAW usa Y crescendo pra cima (mesma convenção do loop de
    # linhas acima) — "acima do desenho" é y > altura_total.
    y = layout.altura_total + margem
    x = 0.0

    titulo = layer.CreateArtisticText(x, y, "CORES:", Font=_FONTE_LEGENDA, Size=tamanho_fonte_cdr)
    titulo.Text.Story.Bold = True
    _aplicar_cor_preenchimento(app, titulo, 0, 0, 0)
    x += titulo.SizeWidth + raio_bolinha

    for cor in layout.cores_legenda:
        # CreateArtisticText ancora (x, y) na linha de base do texto, então
        # o corpo visível da letra fica de y até y + altura aproximada —
        # centraliza a bolinha nesse intervalo (texto é só maiúsculas, sem
        # descendente abaixo da base, ver `nome.upper()` em main_window.py).
        bolinha = layer.CreateEllipse2(x + raio_bolinha, y + altura * 0.5, raio_bolinha)
        bolinha.Outline.SetNoOutline()  # sem contorno, só preenchimento (pedido do usuário)
        _aplicar_cor_preenchimento(app, bolinha, cor.r, cor.g, cor.b)
        x += raio_bolinha * 3

        texto = layer.CreateArtisticText(x, y, cor.nome, Font=_FONTE_LEGENDA, Size=tamanho_fonte_cdr)
        texto.Text.Story.Bold = True
        _aplicar_cor_preenchimento(app, texto, cor.r, cor.g, cor.b)
        x += texto.SizeWidth + raio_bolinha * 3


def _aplicar_cor_preenchimento(app, shape, r: int, g: int, b: int) -> None:
    cor = app.CreateRGBColor(r, g, b)
    try:
        shape.Fill.UniformColor = cor
    except Exception:  # noqa: BLE001
        shape.Fill.ApplyUniformFill(cor)
