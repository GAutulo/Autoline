"""Ponte de automação COM com o CorelDRAW — desenha o layout técnico
diretamente num documento do CorelDRAW, do jeito que o sistema original em
C# fazia (em vez de só exportar um arquivo à parte).

Só funciona no Windows, com o CorelDRAW instalado (usa win32com/pywin32).
CorelDRAW é servidor COM single-instance: `Dispatch` sozinho já resolve
tanto "conectar numa instância aberta" quanto "abrir uma nova se não
tiver nenhuma rodando" — não precisa de `GetActiveObject`.
"""

from __future__ import annotations

from ..models import LayoutCaixa, TipoLinha
from . import configuracoes

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


def desenhar_layout(app, layout: LayoutCaixa) -> None:
    """Desenha as linhas técnicas do layout num documento NOVO do
    CorelDRAW — sempre cria um documento, nunca reaproveita um que já
    esteja aberto (senão a automação desenha por cima de um arquivo que
    pode estar em edição)."""
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

    doc.ActiveWindow.Refresh()


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
