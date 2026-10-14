"""Ferramentas de desenho da faca (ArtiosCAD/CorelDRAW): retângulo, linha
por medida, arco, paralela, aparar, estender e arredondar — a geometria pura
e o uso pela barra da tela Dieline."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout import geometria_faca as geo  # noqa: E402
from gerador_layout.dobra_generica import achar_faces  # noqa: E402
from gerador_layout.models import LinhaDesenho, TipoLinha  # noqa: E402

C, V = TipoLinha.CORTE, TipoLinha.VINCO
ESQ = Qt.MouseButton.LeftButton
NENHUM = Qt.MouseButton.NoButton
SEM = Qt.KeyboardModifier.NoModifier


# ── geometria ─────────────────────────────────────────────────────────
def test_linha_por_medida_angulo_como_no_papel():
    l = geo.linha_por_medida((10, 10), 20, 90, C)  # 90° = pra cima (y diminui)
    assert (l.x2, l.y2) == pytest.approx((10, -10))
    l = geo.linha_por_medida((0, 0), 10, 0, C)
    assert (l.x2, l.y2) == pytest.approx((10, 0))


def test_retangulo_fecha_e_vira_uma_face():
    linhas = geo.retangulo((30, 20), (0, 0), C)
    assert len(linhas) == 4
    assert linhas[0].x1 == 0 and linhas[0].y1 == 0  # normalizado
    faces = achar_faces(linhas)
    assert len(faces.faces) == 1


def test_arco_semicirculo_comprimento_e_meio():
    semi = LinhaDesenho(0, 0, 20, 0, C, 1.0)  # bojo 1 = 180°
    assert geo.comprimento(semi) == pytest.approx(math.pi * 10, rel=1e-6)
    meio = geo.meio_do_arco(semi)
    assert abs(meio[1]) == pytest.approx(10, rel=1e-6)
    pts = geo.pontos(semi)
    assert pts[0] == (0, 0) and pts[-1] == (20, 0)
    bojo = geo.bojo_por_tres_pontos((0, 0), meio, (20, 0))
    assert bojo == pytest.approx(1.0, rel=1e-6)


def test_paralela_reta_e_arco():
    l = LinhaDesenho(0, 0, 10, 0, V)
    p = geo.paralela(l, 3)
    assert abs(p.y1 - l.y1) == pytest.approx(3) and p.y1 == p.y2 and p.tipo == V
    arco = LinhaDesenho(0, 0, 20, 0, C, 1.0)
    maior = geo.paralela(arco, 5)
    assert geo.arco(maior)[1] == pytest.approx(15)
    assert maior.bojo == arco.bojo  # mesmo ângulo


def test_aparar_tira_o_trecho_entre_cruzamentos():
    horizontal = LinhaDesenho(0, 5, 30, 5, C)
    v1 = LinhaDesenho(10, 0, 10, 10, C)
    v2 = LinhaDesenho(20, 0, 20, 10, C)
    saida = geo.aparar([horizontal, v1, v2], 0, (15, 5))
    pedacos = [l for l in saida if l.y1 == 5 and l.y2 == 5]
    assert sorted((min(l.x1, l.x2), max(l.x1, l.x2)) for l in pedacos) == [(0, 10), (20, 30)]
    assert geo.aparar([horizontal], 0, (15, 5)) is None


def test_estender_ate_a_proxima_linha():
    curta = LinhaDesenho(0, 5, 8, 5, C)
    parede = LinhaDesenho(25, 0, 25, 10, C)
    saida = geo.estender([curta, parede], 0, (7, 5))
    assert saida[0].x2 == pytest.approx(25) and saida[0].x1 == 0
    assert geo.estender([curta], 0, (7, 5)) is None


def test_arredondar_canto_reto():
    a = LinhaDesenho(0, 0, 20, 0, C)
    b = LinhaDesenho(0, 0, 0, 20, C)
    saida = geo.arredondar([a, b], (0, 0), 5)
    assert len(saida) == 3
    novo = saida[2]
    assert geo.e_arco(novo)
    assert geo.arco(novo)[1] == pytest.approx(5)
    assert (saida[0].x1, saida[1].y1) == pytest.approx((5, 5))
    assert geo.arredondar([a, b], (0, 0), 50) is None  # não cabe


def test_faca_com_canto_arredondado_ainda_fecha_face():
    linhas = geo.retangulo((0, 0), (40, 30), C)
    for canto in ((0, 0), (40, 0), (40, 30), (0, 30)):
        linhas = geo.arredondar(linhas, canto, 4)
    assert len(linhas) == 8
    faces = achar_faces(linhas)
    assert len(faces.faces) == 1


# ── na tela ───────────────────────────────────────────────────────────
@pytest.fixture
def janela():
    QApplication.instance() or QApplication([])
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    j.abas_tela.setCurrentIndex(0)
    QApplication.processEvents()
    j._nova_faca_em_branco()
    j.canvas.definir_snap_ativo(False)
    QApplication.processEvents()
    yield j
    j.close()


def _mouse(janela, tipo, ponto, botao, botoes, mods=SEM):
    vista = janela.canvas
    pos = QPointF(vista.mapFromScene(QPointF(*ponto)))
    evento = QMouseEvent(tipo, pos, vista.viewport().mapToGlobal(pos), botao, botoes, mods)
    QApplication.sendEvent(vista.viewport(), evento)


def _clicar(janela, p):
    _mouse(janela, QEvent.Type.MouseButtonPress, p, ESQ, ESQ)
    _mouse(janela, QEvent.Type.MouseButtonRelease, p, ESQ, NENHUM)


def _arrastar(janela, de, ate):
    _mouse(janela, QEvent.Type.MouseButtonPress, de, ESQ, ESQ)
    _mouse(janela, QEvent.Type.MouseMove, ((de[0] + ate[0]) / 2, (de[1] + ate[1]) / 2), NENHUM, ESQ)
    _mouse(janela, QEvent.Type.MouseMove, ate, NENHUM, ESQ)
    _mouse(janela, QEvent.Type.MouseButtonRelease, ate, ESQ, NENHUM)


def _ferramenta(janela, chave):
    janela._acoes_faca[chave].trigger()
    QApplication.processEvents()


def _perto(a, b, tol=0.6):
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def test_barra_tem_as_ferramentas_novas(janela):
    for chave in ("retangulo", "medida", "arco", "aparar", "estender", "arredondar"):
        assert chave in janela._acoes_faca
    assert not janela._acao_paralela.isEnabled()


def test_retangulo_na_tela_com_tipo_novo_e_desfazer(janela):
    canvas = janela.canvas
    antes = len(canvas.linhas_faca())
    janela.combo_tipo_novo.setCurrentIndex(janela.combo_tipo_novo.findData(V))
    _ferramenta(janela, "retangulo")
    janela.combo_tipo_novo.activated.emit(janela.combo_tipo_novo.currentIndex())
    _arrastar(janela, (10, 10), (60, 40))
    linhas = canvas.linhas_faca()
    assert len(linhas) == antes + 4
    assert all(l.tipo == V for l in linhas[-4:])
    canvas._pilha_desfazer.undo()
    assert len(canvas.linhas_faca()) == antes


def test_arco_em_tres_cliques(janela):
    canvas = janela.canvas
    _ferramenta(janela, "arco")
    _arrastar(janela, (0, 50), (40, 50))
    _mouse(janela, QEvent.Type.MouseMove, (20, 30), NENHUM, NENHUM)
    _clicar(janela, (20, 30))
    novo = canvas.linhas_faca()[-1]
    assert geo.e_arco(novo)
    assert _perto(geo.meio_do_arco(novo), (20, 30), tol=1.0)


def test_linha_por_medida_encadeia(janela):
    canvas = janela.canvas
    antes = len(canvas.linhas_faca())
    _ferramenta(janela, "medida")
    _clicar(janela, (0, 0))
    origem = canvas._medida_origem
    canvas._ao_confirmar_medida(30, 0)
    canvas._ao_confirmar_medida(20, 270)  # pra baixo
    linhas = canvas.linhas_faca()
    assert len(linhas) == antes + 2
    assert (linhas[-1].x1, linhas[-1].y1) == pytest.approx((origem.x() + 30, origem.y()))
    assert (linhas[-1].x2, linhas[-1].y2) == pytest.approx((origem.x() + 30, origem.y() + 20))


def test_paralela_aparar_estender_arredondar_na_tela(janela):
    canvas = janela.canvas
    _ferramenta(janela, "corte")
    _arrastar(janela, (0, 0), (100, 0))
    _arrastar(janela, (0, 0), (0, 80))
    linhas = canvas.linhas_faca()
    base = len(linhas)
    h = base - 2

    # paralela da horizontal selecionada
    _ferramenta(janela, "forma")
    _clicar(janela, (50, 0))
    assert janela._acao_paralela.isEnabled()
    assert canvas.criar_paralela_selecionada(20)
    assert len(canvas.linhas_faca()) == base + 1
    paralela = canvas.linhas_faca()[-1]
    assert abs(abs(paralela.y1) - 20) < 1e-6

    # estender a paralela até uma linha vertical colocada à frente
    _ferramenta(janela, "corte")
    _arrastar(janela, (130, -40), (130, 40))
    parede = canvas.linhas_faca()[-1]
    xp = parede.x1  # o mouse cai no pixel mais próximo
    x_cruzamento = parede.x1 + (parede.x2 - parede.x1) * (paralela.y1 - parede.y1) / (parede.y2 - parede.y1)
    _ferramenta(janela, "estender")
    _clicar(janela, (99, paralela.y1))
    estendida = [l for l in canvas.linhas_faca() if abs(l.y1 - paralela.y1) < 1e-6 and abs(l.y2 - paralela.y1) < 1e-6]
    assert estendida and max(estendida[0].x1, estendida[0].x2) == pytest.approx(x_cruzamento, abs=1e-6)

    # aparar o pedaço da vertical que passa da paralela
    _ferramenta(janela, "aparar")
    ponta_fora = 35 if paralela.y1 > 0 else -35
    _clicar(janela, (xp, ponta_fora))
    verticais = [l for l in canvas.linhas_faca() if abs(l.x1 - xp) < 1.0 and abs(l.x2 - xp) < 1.0 and abs(l.y2 - l.y1) > 1]
    assert verticais
    assert all(not (min(l.y1, l.y2) <= ponta_fora <= max(l.y1, l.y2)) for l in verticais)

    # arredondar o canto (0, 0)
    janela.spin_raio_faca.setValue(6)
    _ferramenta(janela, "arredondar")
    _clicar(janela, (0, 0))
    arcos = [l for l in canvas.linhas_faca() if geo.e_arco(l)]
    assert arcos and geo.arco(arcos[-1])[1] == pytest.approx(6)
    assert linhas[h].tipo == TipoLinha.CORTE


def test_exportar_svg_com_arco(janela, tmp_path):
    from gerador_layout.ui.exportacao import exportar_svg

    canvas = janela.canvas
    _ferramenta(janela, "arco")
    _arrastar(janela, (0, 50), (40, 50))
    _mouse(janela, QEvent.Type.MouseMove, (20, 30), NENHUM, NENHUM)
    _clicar(janela, (20, 30))
    destino = tmp_path / "faca.svg"
    exportar_svg(canvas.scene(), canvas.layout_atual, str(destino))
    texto = destino.read_text(encoding="utf-8")
    assert "<image" not in texto
    assert " C" in texto or "C " in texto or "c " in texto  # curva, não polilinha raster
