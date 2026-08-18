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

_CDR_MILLIMETER = 3

# Mesmas cores usadas na pré-visualização em tela (ver `_ESTILO_POR_TIPO`
# em `preview_canvas.py`) — assim o arquivo aberto no CorelDRAW é
# reconhecível na hora, com o tipo de linha diferenciado por cor.
_COR_POR_TIPO: dict[TipoLinha, tuple[int, int, int]] = {
    TipoLinha.CORTE: (20, 20, 25),
    TipoLinha.VINCO: (40, 100, 220),
    TipoLinha.CORTE_SERRA: (230, 110, 20),
    TipoLinha.MEIO_CORTE: (30, 160, 90),
    TipoLinha.DOBRA: (150, 150, 160),
}

# Padrão da gráfica: linhas em 1pt. Outline.Width usa a unidade do
# documento (mm — ver `doc.Unit` em `desenhar_layout`), então convertemos
# pt → mm aqui (1pt = 1/72 pol = 25,4/72 mm) em vez de guardar o valor já
# convertido, pra facilitar ajustar no futuro em pt.
_LARGURA_LINHA_PT = 1.0
_LARGURA_LINHA_MM = _LARGURA_LINHA_PT * 25.4 / 72

# Padrões de traço por tipo de linha (mm), espelhando o estilo em tela
# (`_ESTILO_POR_TIPO` em `preview_canvas.py`). None = linha contínua.
# IMPORTANTE: um array com período 2 (ex.: [6,3] ou [6,3,6,3]) renderiza
# como linha SÓLIDA no CorelDRAW — quirk observado empiricamente nesta
# automação. Por isso usa 4 valores levemente assimétricos (não
# periódicos) em vez do par dash/gap "limpo".
_TRACO_POR_TIPO: dict[TipoLinha, list[float] | None] = {
    TipoLinha.CORTE: None,
    TipoLinha.VINCO: [6.0, 3.0, 5.9, 3.1],
    TipoLinha.CORTE_SERRA: [6.0, 3.0, 1.0, 3.0],
    TipoLinha.MEIO_CORTE: [2.0, 2.0, 1.9, 2.1],
    TipoLinha.DOBRA: [1.5, 1.5, 1.4, 1.6],
}

_FONTE_LEGENDA = "Arial"
_TAMANHO_FONTE_LEGENDA = 10.0
_MARGEM_LEGENDA_MM = 6.0
_RAIO_BOLINHA_MM = 1.5


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
    """Desenha as linhas técnicas do layout no documento ativo do
    CorelDRAW — cria um documento novo se não houver nenhum aberto."""
    try:
        doc = app.ActiveDocument
    except Exception:  # noqa: BLE001
        doc = None
    if doc is None:
        doc = app.CreateDocument()
    doc.Unit = _CDR_MILLIMETER

    layer = doc.ActiveLayer
    altura = layout.altura_total

    for linha in layout.linhas:
        # CorelDRAW usa eixo Y crescendo pra cima; nosso layout usa Y
        # crescendo pra baixo (mesma convenção da pré-visualização e do
        # SVG/PDF/JPG) — espelha verticalmente pra sair com a mesma
        # orientação que já aparece no app.
        y1 = altura - linha.y1
        y2 = altura - linha.y2
        shape = layer.CreateLineSegment(linha.x1, y1, linha.x2, y2)
        r, g, b = _COR_POR_TIPO.get(linha.tipo, (0, 0, 0))
        shape.Outline.Color = app.CreateRGBColor(r, g, b)
        shape.Outline.Width = _LARGURA_LINHA_MM

        padrao = _TRACO_POR_TIPO.get(linha.tipo)
        if padrao:
            shape.Outline.Style = app.CreateOutlineStyle(len(padrao), padrao)

    _desenhar_legenda(app, layer, layout)

    doc.ActiveWindow.Refresh()


def _desenhar_legenda(app, layer, layout: LayoutCaixa) -> None:
    """Desenha a legenda de cores de impressão (nome + bolinha) acima do
    layout — mesmo conteúdo que já vai pro SVG/PDF/JPG (ver
    `_LegendaExportacao` em `exportacao.py`), só que direto no documento
    do CorelDRAW."""
    if not layout.cores_legenda:
        return

    # CorelDRAW usa Y crescendo pra cima (mesma convenção do loop de
    # linhas acima) — "acima do desenho" é y > altura_total.
    y = layout.altura_total + _MARGEM_LEGENDA_MM
    x = 0.0

    titulo = layer.CreateArtisticText(x, y, "CORES:", Font=_FONTE_LEGENDA, Size=_TAMANHO_FONTE_LEGENDA)
    x += titulo.SizeWidth + 4.0

    for cor in layout.cores_legenda:
        bolinha = layer.CreateEllipse2(x + _RAIO_BOLINHA_MM, y + 1.5, _RAIO_BOLINHA_MM)
        _aplicar_cor_preenchimento(app, bolinha, cor.r, cor.g, cor.b)
        x += _RAIO_BOLINHA_MM * 2 + 3.0

        texto = layer.CreateArtisticText(x, y, cor.nome, Font=_FONTE_LEGENDA, Size=_TAMANHO_FONTE_LEGENDA)
        x += texto.SizeWidth + 8.0


def _aplicar_cor_preenchimento(app, shape, r: int, g: int, b: int) -> None:
    cor = app.CreateRGBColor(r, g, b)
    try:
        shape.Fill.UniformColor = cor
    except Exception:  # noqa: BLE001
        shape.Fill.ApplyUniformFill(cor)
