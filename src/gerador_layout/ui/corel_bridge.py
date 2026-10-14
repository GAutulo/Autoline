"""Ponte de automação COM com o CorelDRAW — desenha o layout técnico
diretamente num documento do CorelDRAW, do jeito que o sistema original em
C# fazia (em vez de só exportar um arquivo à parte).

Só funciona no Windows, com o CorelDRAW instalado (usa win32com/pywin32).
CorelDRAW é servidor COM single-instance: `Dispatch` sozinho já resolve
tanto "conectar numa instância aberta" quanto "abrir uma nova se não
tiver nenhuma rodando" — não precisa de `GetActiveObject`.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF
from PySide6.QtGui import QFont, QFontMetricsF

from .. import geometria_faca
from ..models import LayoutCaixa, TipoLinha
from . import configuracoes
from .mockup_acabamento import ElementoAcabamento
from .mockup_callout import ElementoCallout
from .mockup_checklist import ElementoChecklistCores
from .mockup_cota import ElementoCota
from .mockup_cota_angular import ElementoCotaAngular
from .mockup_curva import ElementoCurva
from .mockup_checklist import _ALTURA_LINHA_MM as _CHECKLIST_ALTURA_LINHA_MM
from .mockup_checklist import _ESPACO_CAIXA_TEXTO_FATOR as _CHECKLIST_ESPACO_CAIXA_TEXTO_FATOR
from .mockup_checklist import _ESPACO_ENTRE_LINHAS_FATOR as _CHECKLIST_ESPACO_ENTRE_LINHAS_FATOR
from .mockup_checklist import _ESPESSURA_TRACO_FATOR as _CHECKLIST_ESPESSURA_TRACO_FATOR
from .mockup_formas import ElementoElipse, ElementoLinha, ElementoPoligono, ElementoRetangulo
from .mockup_imagem import ElementoImagem
from .mockup_itens import ElementoMockup, GrupoMockup
from .mockup_logo import ElementoLogoVetorial
from .mockup_simbolos import ElementoSimbolo
from .mockup_simbolos import _ESPACO_REFERENCIA as _SIMBOLO_ESPACO_REFERENCIA
from .mockup_tabela import ElementoTabela
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


# ── Conexão + ponto de entrada ──────────────────────────────────────────


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
        shape = (
            _desenhar_arco_faca(app, layer, linha, altura)
            if geometria_faca.e_arco(linha)
            else layer.CreateLineSegment(linha.x1, y1, linha.x2, y2)
        )
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

# ── Helpers de geometria/cor compartilhados entre os desenhistas ───────


def _desenhar_arco_faca(app, layer, linha, altura: float):
    """Arco da faca como curva do CorelDRAW (Béziers, até 90° cada). Se a API
    de curva não responder, cai pra segmentos retos curtos."""
    try:
        curva = app.ActiveDocument.CreateCurve()
        trechos = geometria_faca.em_cubicas(linha)
        subcaminho = curva.CreateSubPath(trechos[0][0][0], altura - trechos[0][0][1])
        for _p0, c1, c2, p3 in trechos:
            subcaminho.AppendCurveSegment2(p3[0], altura - p3[1], c1[0], altura - c1[1], c2[0], altura - c2[1])
        return layer.CreateCurve(curva)
    except Exception:  # noqa: BLE001
        pontos = geometria_faca.pontos(linha, 2.0)
        formas = [layer.CreateLineSegment(a[0], altura - a[1], b[0], altura - b[1]) for a, b in zip(pontos, pontos[1:])]
        grupo = app.CreateShapeRange()
        for forma in formas:
            grupo.Add(forma)
        return grupo


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


# ── Um desenhista por tipo de ElementoMockup (dispatch abaixo) ─────────


# `Shape.Flip`/`ShapeRange.Flip` da API do CorelDRAW (cdrFlipAxes).
_CDR_ESPELHO_HORIZONTAL = 1
_CDR_ESPELHO_VERTICAL = 2


def _desenhar_elemento_mockup(app, layer, elemento: ElementoMockup, altura_total: float) -> None:
    espelho = (_CDR_ESPELHO_HORIZONTAL if elemento.espelho_h else 0) | (_CDR_ESPELHO_VERTICAL if elemento.espelho_v else 0)
    if espelho and not isinstance(elemento, GrupoMockup):
        # Espelhar = desenhar normal e virar no CorelDRAW o que acabou de
        # nascer. Shapes.Item(1) é o mais recente (topo da pilha).
        antes = layer.Shapes.Count
        _desenhar_elemento_mockup_normal(app, layer, elemento, altura_total)
        novos = layer.Shapes.Count - antes
        if novos > 0:
            intervalo = app.CreateShapeRange()
            for i in range(1, novos + 1):
                intervalo.Add(layer.Shapes.Item(i))
            intervalo.Flip(espelho)
        return
    _desenhar_elemento_mockup_normal(app, layer, elemento, altura_total)


def _desenhar_elemento_mockup_normal(app, layer, elemento: ElementoMockup, altura_total: float) -> None:
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
    elif isinstance(elemento, ElementoElipse):
        _desenhar_elipse_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, ElementoPoligono):
        _desenhar_poligono_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, ElementoLinha):
        _desenhar_linha_mockup_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, ElementoCota):
        _desenhar_cota_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, ElementoCotaAngular):
        _desenhar_cota_angular_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, ElementoCurva):
        _desenhar_curva_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, ElementoCallout):
        _desenhar_callout_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, ElementoTabela):
        _desenhar_tabela_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, ElementoAcabamento):
        _desenhar_acabamento_cdr(app, layer, elemento, altura_total)
    elif isinstance(elemento, ElementoSimbolo):
        _desenhar_simbolo_cdr(app, layer, elemento, altura_total)
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


def _desenhar_elipse_cdr(app, layer, elemento: "ElementoElipse", altura_total: float) -> None:
    # `Layer.CreateEllipse2(x1, y1, x2, y2)` — mesma família de método
    # (2 pontos opostos, não centro+raio) de `CreateRectangle2` já usado
    # acima. NÃO testado ao vivo contra o CorelDRAW nesta sessão (ao
    # contrário do resto do arquivo) — vale conferir na prática.
    x, y, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    x1, y1 = x - elemento.largura / 2, y - elemento.altura / 2
    x2, y2 = x + elemento.largura / 2, y + elemento.altura / 2
    shape = layer.CreateEllipse2(x1, y1, x2, y2)
    if elemento.preenchido:
        _aplicar_cor_preenchimento(app, shape, elemento.cor_tinta.r, elemento.cor_tinta.g, elemento.cor_tinta.b)
    else:
        shape.Fill.ApplyNoFill()
    shape.Outline.Color = _cor_rgb(app, elemento.cor_tinta)
    shape.Outline.Width = elemento.largura_traco
    if angulo:
        shape.Rotate(angulo)


def _desenhar_poligono_cdr(app, layer, elemento: "ElementoPoligono", altura_total: float) -> None:
    """Desenha aresta por aresta com `CreateLineSegment` (método já
    testado/confirmado nesta sessão, ver nota grande no topo do arquivo)
    em vez de arriscar um método de polígono nativo do CorelDRAW que não
    dá pra confirmar sem testar ao vivo — sai como N linhas soltas, não 1
    shape polígono só; agrupa/preenche manualmente no Corel se precisar
    de 1 shape única com preenchimento sólido."""
    x_centro, y_centro, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    raio_x, raio_y = elemento.largura / 2, elemento.altura / 2
    pontos = []
    for i in range(elemento.lados):
        angulo_local = math.radians(-90 + i * 360 / elemento.lados)
        # `_pintar_conteudo` (Qt, Y cresce pra baixo) usa sin(ângulo) direto
        # pro deslocamento em Y a partir do centro — o Corel cresce pra
        # CIMA, então precisa do mesmo espelho `-y` que `_desenhar_checklist_cdr`
        # já usa (`ponto_cdr` acima) pra qualquer ponto que não seja o
        # centro do próprio elemento.
        px = x_centro + math.cos(angulo_local) * raio_x
        py = y_centro - math.sin(angulo_local) * raio_y
        pontos.append((px, py))

    cor = _cor_rgb(app, elemento.cor_tinta)
    arestas = []
    for i in range(len(pontos)):
        x0, y0 = pontos[i]
        x1, y1 = pontos[(i + 1) % len(pontos)]
        shape = layer.CreateLineSegment(x0, y0, x1, y1)
        shape.Outline.Color = cor
        shape.Outline.Width = elemento.largura_traco
        arestas.append(shape)

    if angulo and arestas:
        intervalo = app.CreateShapeRange()
        for aresta in arestas:
            intervalo.Add(aresta)
        intervalo.Rotate(angulo)


def _desenhar_simbolo_cdr(app, layer, elemento: "ElementoSimbolo", altura_total: float) -> None:
    """Achata o `QPainterPath` do pictograma (que tem curva — `cubicTo`/
    `arcTo`, ver `mockup_simbolos.py`) em segmentos de reta via
    `toSubpathPolygons()`, mesma técnica/motivo de `_desenhar_poligono_cdr`
    (evita apostar num método de curva nativo do Corel sem testar ao
    vivo). Diferente de lá, cada vértice já sai direto na posição de CENA
    certa via `elemento.mapToScene()` — que já embute rotação/posição do
    próprio elemento (e de qualquer grupo pai) sozinho, sem precisar de
    um `Rotate()` em separado depois de desenhar tudo "reto"."""
    escala_x = elemento.largura / _SIMBOLO_ESPACO_REFERENCIA
    escala_y = elemento.altura / _SIMBOLO_ESPACO_REFERENCIA
    cor = _cor_rgb(app, elemento.cor_tinta)
    for poligono in elemento.caminho_normalizado().toSubpathPolygons():
        pontos_cdr = []
        for ponto_ref in poligono:
            local = QPointF(ponto_ref.x() * escala_x, ponto_ref.y() * escala_y)
            cena = elemento.mapToScene(local)
            pontos_cdr.append((cena.x(), altura_total - cena.y()))
        for i in range(len(pontos_cdr) - 1):
            x0, y0 = pontos_cdr[i]
            x1, y1 = pontos_cdr[i + 1]
            shape = layer.CreateLineSegment(x0, y0, x1, y1)
            shape.Outline.Color = cor
            shape.Outline.Width = 0.25


def _desenhar_linha_mockup_cdr(app, layer, elemento: ElementoLinha, altura_total: float) -> None:
    x, y, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    shape = layer.CreateLineSegment(x - elemento.largura / 2, y, x + elemento.largura / 2, y)
    shape.Outline.Color = _cor_rgb(app, elemento.cor_tinta)
    shape.Outline.Width = elemento.largura_traco
    if angulo:
        shape.Rotate(angulo)


def _desenhar_texto_cdr(app, layer, elemento: ElementoTexto, altura_total: float) -> None:
    if not elemento.texto.strip():
        return
    x, y, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    shape = layer.CreateArtisticText(
        # O CorelDRAW quebra linha com \r (texto artístico de várias linhas).
        0, 0, elemento.texto.replace("\n", "\r"), Font=elemento.fonte_familia, Size=_TAMANHO_FONTE_REFERENCIA_CDR
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


def _construtor_ponto_cdr(x_centro: float, y_centro: float, largura: float, altura: float):
    """Mesmo padrão de `ponto_cdr` dentro de `_desenhar_checklist_cdr`
    acima, só que fatorado pra reuso — converte um ponto LOCAL do
    elemento (0,0 = canto superior-esquerdo, Y cresce pra baixo, igual
    `_pintar_conteudo` de qualquer `ElementoMockup`) pra posição real no
    documento CorelDRAW, sem rotação (aplicada depois, numa ShapeRange)."""
    origem_x = x_centro - largura / 2
    origem_y = y_centro + altura / 2

    def ponto_cdr(x_qt: float, y_qt: float) -> tuple[float, float]:
        return origem_x + x_qt, origem_y - y_qt

    return ponto_cdr


def _desenhar_callout_cdr(app, layer, elemento: "ElementoCallout", altura_total: float) -> None:
    """Composto de retângulo (caixa) + linha (cauda) + texto — reaproveita
    só métodos já confirmados (`CreateRectangle2`/`CreateLineSegment`/
    `CreateArtisticText`), mesmo espírito de `_desenhar_checklist_cdr`.
    Cauda geometricamente igual à de `ElementoCallout._pintar_conteudo`
    (canto inferior-esquerdo, mesmo ângulo fixo)."""
    x_centro, y_centro, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    ponto_cdr = _construtor_ponto_cdr(x_centro, y_centro, elemento.largura, elemento.altura)
    cor = _cor_rgb(app, elemento.cor_tinta)

    x0, y0 = ponto_cdr(0.0, 0.0)
    x1, y1 = ponto_cdr(elemento.largura, elemento.altura)
    caixa = layer.CreateRectangle2(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
    caixa.Fill.ApplyNoFill()
    caixa.Outline.Color = cor
    caixa.Outline.Width = 0.3

    comprimento_cauda = 9.0
    base_x_qt, base_y_qt = elemento.largura * 0.18, elemento.altura
    ponta_x_qt = base_x_qt - comprimento_cauda * 0.75
    ponta_y_qt = base_y_qt + comprimento_cauda * 0.75
    bx, by = ponto_cdr(base_x_qt, base_y_qt)
    px, py = ponto_cdr(ponta_x_qt, ponta_y_qt)
    cauda = layer.CreateLineSegment(bx, by, px, py)
    cauda.Outline.Color = cor
    cauda.Outline.Width = 0.3

    margem = 3.0
    tx0, ty0 = ponto_cdr(margem, margem)
    tx1, ty1 = ponto_cdr(elemento.largura - margem, elemento.altura - margem)
    texto_shape = layer.CreateArtisticText(0, 0, elemento.texto, Size=_TAMANHO_FONTE_REFERENCIA_CDR)
    _aplicar_cor_preenchimento(app, texto_shape, elemento.cor_tinta.r, elemento.cor_tinta.g, elemento.cor_tinta.b)
    texto_shape.SetSize(max(0.1, abs(tx1 - tx0)), max(0.1, abs(ty1 - ty0)))
    texto_shape.SetPosition(min(tx0, tx1), max(ty0, ty1))

    if angulo:
        intervalo = app.CreateShapeRange()
        for forma in (caixa, cauda, texto_shape):
            intervalo.Add(forma)
        intervalo.Rotate(angulo)


def _desenhar_curva_cdr(app, layer, elemento: "ElementoCurva", altura_total: float) -> None:
    """Curva Bézier nativa do CorelDRAW (`Document.CreateCurve` +
    `SubPath.AppendCurveSegment2`), com os nós já na posição final (com
    rotação; o espelho é aplicado depois por `_desenhar_elemento_mockup`,
    igual aos outros tipos). Se a API de curva falhar nessa versão do
    CorelDRAW, cai pra um polígono de segmentos retos (aproximação fina)."""
    def cdr(q: QPointF) -> tuple[float, float]:
        return q.x(), altura_total - q.y()

    cena = elemento.sceneTransform()
    subs = elemento.subcaminhos_locais()
    try:
        curva = app.ActiveDocument.CreateCurve()
        for sub in subs:
            nos = [no.mapeado(cena.map) for no in sub.nos]
            caminho_cdr = curva.CreateSubPath(*cdr(nos[0].p))
            pares = list(zip(nos, nos[1:]))
            if sub.fechado:
                pares.append((nos[-1], nos[0]))
            for a, b in pares:
                caminho_cdr.AppendCurveSegment2(*cdr(b.p), *cdr(a.saida), *cdr(b.entrada))
            if sub.fechado:
                caminho_cdr.Closed = True
        forma = layer.CreateCurve(curva)
        formas = [forma]
    except Exception:  # noqa: BLE001 — API de curva indisponível: aproximação por segmentos
        caminho = cena.map(elemento.caminho_local())
        formas = []
        for poligono in caminho.toSubpathPolygons():
            pontos = [cdr(poligono.at(i)) for i in range(poligono.count())]
            for (xa, ya), (xb, yb) in zip(pontos, pontos[1:]):
                formas.append(layer.CreateLineSegment(xa, ya, xb, yb))
    cor = _cor_rgb(app, elemento.cor_tinta)
    for forma in formas:
        if elemento.largura_traco > 0:
            forma.Outline.Color = cor
            forma.Outline.Width = elemento.largura_traco
        else:
            forma.Outline.SetNoOutline()
    if elemento.preenchido and len(formas) == 1:
        _aplicar_cor_preenchimento(app, formas[0], elemento.cor_tinta.r, elemento.cor_tinta.g, elemento.cor_tinta.b)


def _desenhar_cota_angular_cdr(app, layer, elemento: "ElementoCotaAngular", altura_total: float) -> None:
    """Braços, arco (em segmentos curtos) e setas como linhas; o valor como
    texto. Os pontos já vão na posição final (com rotação), então não há
    giro depois."""
    cena = elemento.sceneTransform()

    def cdr(q: QPointF) -> tuple[float, float]:
        q = cena.map(q)
        return q.x(), altura_total - q.y()

    cor = _cor_rgb(app, elemento.cor_tinta)
    linhas, arco, setas, caixa = elemento.primitivas_locais()
    segmentos = list(linhas) + list(zip(arco, arco[1:]))
    for seta in setas:
        pontos = [seta.at(i) for i in range(seta.count())]
        segmentos += list(zip(pontos, pontos[1:] + pontos[:1]))
    for a, b in segmentos:
        linha = layer.CreateLineSegment(*cdr(a), *cdr(b))
        linha.Outline.Color = cor
        linha.Outline.Width = 0.25
    texto = layer.CreateArtisticText(0, 0, elemento.texto_valor(), Size=elemento.altura_texto * _FATOR_SIZE_CDR_POR_MM)
    _aplicar_cor_preenchimento(app, texto, elemento.cor_tinta.r, elemento.cor_tinta.g, elemento.cor_tinta.b)
    cx, cy = cdr(caixa.center())
    texto.SetPosition(cx - texto.SizeWidth / 2, cy + elemento.altura_texto / 2)


def _desenhar_cota_cdr(app, layer, elemento: "ElementoCota", altura_total: float) -> None:
    """Cota como linhas + setas + texto (primitivas já usadas acima), não
    como objeto de cota nativo do CorelDRAW: o valor sai fixo, igual ao
    que aparece no Autoline. Gira em torno do centro do elemento."""
    x_centro, y_centro, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    ponto_cdr = _construtor_ponto_cdr(x_centro, y_centro, elemento.largura, elemento.altura)
    cor = _cor_rgb(app, elemento.cor_tinta)
    formas = []
    for a, b in elemento.segmentos_locais():
        x0, y0 = ponto_cdr(a.x(), a.y())
        x1, y1 = ponto_cdr(b.x(), b.y())
        linha = layer.CreateLineSegment(x0, y0, x1, y1)
        linha.Outline.Color = cor
        linha.Outline.Width = 0.25
        formas.append(linha)
    for seta in elemento.setas_locais():
        pontos = [ponto_cdr(seta[i].x(), seta[i].y()) for i in range(seta.count())]
        for i, (xa, ya) in enumerate(pontos):
            xb, yb = pontos[(i + 1) % len(pontos)]
            lado = layer.CreateLineSegment(xa, ya, xb, yb)
            lado.Outline.Color = cor
            lado.Outline.Width = 0.25
            formas.append(lado)
    caixa = elemento.retangulo_texto_local()
    tx0, ty0 = ponto_cdr(caixa.left(), caixa.top())
    tx1, ty1 = ponto_cdr(caixa.right(), caixa.bottom())
    texto = layer.CreateArtisticText(0, 0, elemento.texto_valor(), Size=elemento.altura_texto * _FATOR_SIZE_CDR_POR_MM)
    _aplicar_cor_preenchimento(app, texto, elemento.cor_tinta.r, elemento.cor_tinta.g, elemento.cor_tinta.b)
    texto.SetPosition((tx0 + tx1) / 2 - texto.SizeWidth / 2, max(ty0, ty1))
    formas.append(texto)
    if angulo:
        intervalo = app.CreateShapeRange()
        for forma in formas:
            intervalo.Add(forma)
        intervalo.RotateEx(angulo, x_centro, y_centro)


def _desenhar_tabela_cdr(app, layer, elemento: "ElementoTabela", altura_total: float) -> None:
    x_centro, y_centro, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    ponto_cdr = _construtor_ponto_cdr(x_centro, y_centro, elemento.largura, elemento.altura)
    cor = _cor_rgb(app, elemento.cor_tinta)
    largura_celula = elemento.largura / elemento.colunas
    altura_celula = elemento.altura / elemento.linhas

    formas = []
    x0, y0 = ponto_cdr(0.0, 0.0)
    x1, y1 = ponto_cdr(elemento.largura, elemento.altura)
    borda = layer.CreateRectangle2(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
    borda.Fill.ApplyNoFill()
    borda.Outline.Color = cor
    borda.Outline.Width = 0.3
    formas.append(borda)

    for c in range(1, elemento.colunas):
        lx0, ly0 = ponto_cdr(c * largura_celula, 0.0)
        lx1, ly1 = ponto_cdr(c * largura_celula, elemento.altura)
        linha = layer.CreateLineSegment(lx0, ly0, lx1, ly1)
        linha.Outline.Color = cor
        linha.Outline.Width = 0.3
        formas.append(linha)
    for l in range(1, elemento.linhas):
        lx0, ly0 = ponto_cdr(0.0, l * altura_celula)
        lx1, ly1 = ponto_cdr(elemento.largura, l * altura_celula)
        linha = layer.CreateLineSegment(lx0, ly0, lx1, ly1)
        linha.Outline.Color = cor
        linha.Outline.Width = 0.3
        formas.append(linha)

    margem = min(largura_celula, altura_celula) * 0.12
    for l in range(elemento.linhas):
        for c in range(elemento.colunas):
            texto = elemento.celulas[l][c]
            if not texto:
                continue
            tx0, ty0 = ponto_cdr(c * largura_celula + margem, l * altura_celula + margem)
            tx1, ty1 = ponto_cdr(
                (c + 1) * largura_celula - margem, (l + 1) * altura_celula - margem
            )
            texto_shape = layer.CreateArtisticText(0, 0, texto, Size=_TAMANHO_FONTE_REFERENCIA_CDR)
            texto_shape.Text.Story.Bold = l == 0
            _aplicar_cor_preenchimento(app, texto_shape, elemento.cor_tinta.r, elemento.cor_tinta.g, elemento.cor_tinta.b)
            texto_shape.SetSize(max(0.1, abs(tx1 - tx0)), max(0.1, abs(ty1 - ty0)))
            texto_shape.SetPosition(min(tx0, tx1), max(ty0, ty1))
            formas.append(texto_shape)

    if angulo and formas:
        intervalo = app.CreateShapeRange()
        for forma in formas:
            intervalo.Add(forma)
        intervalo.Rotate(angulo)


def _desenhar_acabamento_cdr(app, layer, elemento: "ElementoAcabamento", altura_total: float) -> None:
    """Só o retângulo de referência + rótulo do processo — a hachura em
    si (ver `_pintar_conteudo`) é textura de tela, não precisa ir pro
    arquivo de produção; o que importa pra gráfica é a ÁREA marcada e o
    tipo de processo escrito, ambos saem aqui. Cor de marcação fixa
    (magenta), nunca uma tinta do trabalho — ver docstring do módulo."""
    x, y, angulo = _centro_e_rotacao_cdr(elemento, altura_total)
    cor_marcacao = app.CreateRGBColor(236, 0, 140)
    shape = layer.CreateRectangle2(
        x - elemento.largura / 2, y - elemento.altura / 2, elemento.largura, elemento.altura
    )
    shape.Fill.ApplyNoFill()
    shape.Outline.Color = cor_marcacao
    shape.Outline.Width = 0.3

    texto_shape = layer.CreateArtisticText(0, 0, elemento.tipo.value, Size=_TAMANHO_FONTE_REFERENCIA_CDR)
    texto_shape.Text.Story.Bold = True
    _aplicar_cor_preenchimento(app, texto_shape, 236, 0, 140)
    altura_texto = min(elemento.altura * 0.3, 6.0)
    largura_texto = min(elemento.largura * 0.9, altura_texto * len(elemento.tipo.value) * 0.6)
    texto_shape.SetSize(max(0.1, largura_texto), max(0.1, altura_texto))
    texto_shape.SetPosition(x - elemento.largura / 2 + 1.0, y + elemento.altura / 2 - 1.0)

    if angulo:
        intervalo = app.CreateShapeRange()
        intervalo.Add(shape)
        intervalo.Add(texto_shape)
        intervalo.Rotate(angulo)


# ── Legenda de cores + utilitários genéricos ────────────────────────────


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
