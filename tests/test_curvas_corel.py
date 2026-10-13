"""Curvas: Bézier, Mão livre, Forma (nós), Converter/Combinar/Separar."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui.mockup_curva import ElementoCurva  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoElipse, ElementoRetangulo  # noqa: E402
from gerador_layout.ui.mockup_texto import ElementoTexto  # noqa: E402
from gerador_layout.ui.preview_canvas import FerramentaMockup  # noqa: E402

PRETO = CorImpressao("PRETO", 0, 0, 0)
ESQ = Qt.MouseButton.LeftButton
NENHUM = Qt.MouseButton.NoButton


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app):
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    j.abas_tela.setCurrentIndex(1)
    j.canvas.definir_snap_ativo(False)
    QApplication.processEvents()
    yield j
    j.close()


def _mouse(janela, tipo, ponto, botao, botoes):
    vista = janela.canvas
    pos = QPointF(vista.mapFromScene(QPointF(*ponto)))
    evento = QMouseEvent(tipo, pos, vista.viewport().mapToGlobal(pos), botao, botoes, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(vista.viewport(), evento)


def _clique(janela, ponto):
    _mouse(janela, QEvent.Type.MouseButtonPress, ponto, ESQ, ESQ)
    _mouse(janela, QEvent.Type.MouseButtonRelease, ponto, ESQ, NENHUM)


def _arrastar(janela, de, ate):
    _mouse(janela, QEvent.Type.MouseButtonPress, de, ESQ, ESQ)
    _mouse(janela, QEvent.Type.MouseMove, ((de[0] + ate[0]) / 2, (de[1] + ate[1]) / 2), NENHUM, ESQ)
    _mouse(janela, QEvent.Type.MouseMove, ate, NENHUM, ESQ)
    _mouse(janela, QEvent.Type.MouseButtonRelease, ate, ESQ, NENHUM)


def _amostras(caminho, n=24):
    return [caminho.pointAtPercent(i / n) for i in range(n + 1)]


def _diferenca(a, b):
    return max(abs(p.x() - q.x()) + abs(p.y() - q.y()) for p, q in zip(_amostras(a), _amostras(b)))


def test_bezier_fecha_no_primeiro_no(janela):
    canvas = janela.canvas
    canvas.definir_ferramenta(FerramentaMockup.BEZIER)
    antes = len(canvas.elementos_mockup)
    _clique(janela, (100, 100))
    _arrastar(janela, (200, 100), (230, 130))  # nó suave
    _clique(janela, (200, 200))
    _clique(janela, (100.3, 100.2))  # perto do 1º nó: fecha
    assert len(canvas.elementos_mockup) == antes + 1
    curva = canvas.elementos_mockup[-1]
    assert isinstance(curva, ElementoCurva)
    sub = curva.subcaminhos[0]
    assert sub.fechado and len(sub.nos) == 3 and sub.nos[1].suave
    assert canvas.ferramenta_ativa == FerramentaMockup.BEZIER  # continua na ferramenta


def test_bezier_duplo_clique_termina_aberta_e_esc_cancela(janela):
    canvas = janela.canvas
    canvas.definir_ferramenta(FerramentaMockup.BEZIER)
    antes = len(canvas.elementos_mockup)
    _clique(janela, (50, 50))
    _clique(janela, (150, 60))
    _mouse(janela, QEvent.Type.MouseButtonDblClick, (150, 60), ESQ, ESQ)
    assert len(canvas.elementos_mockup) == antes + 1
    assert not canvas.elementos_mockup[-1].subcaminhos[0].fechado
    _clique(janela, (60, 60))
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    assert len(canvas.elementos_mockup) == antes + 1


def test_mao_livre_simplifica(janela):
    canvas = janela.canvas
    canvas.definir_ferramenta(FerramentaMockup.MAO_LIVRE)
    _mouse(janela, QEvent.Type.MouseButtonPress, (10, 200), ESQ, ESQ)
    for i in range(1, 41):
        _mouse(janela, QEvent.Type.MouseMove, (10 + i * 5, 200), NENHUM, ESQ)  # reta: vira 2 nós
    _mouse(janela, QEvent.Type.MouseButtonRelease, (210, 200), ESQ, NENHUM)
    curva = canvas.elementos_mockup[-1]
    assert isinstance(curva, ElementoCurva) and len(curva.subcaminhos[0].nos) == 2


def test_converter_em_curvas_mantem_desenho_e_desfaz(janela):
    canvas = janela.canvas
    canvas.definir_ferramenta(FerramentaMockup.SELECIONAR)
    ret = ElementoRetangulo(largura=60, altura=30, cor_tinta=PRETO, preenchido=True)
    canvas.adicionar_elemento_mockup(ret, QPointF(300, 100))
    ret.setRotation(25)
    ret.definir_espelho(True, False)
    esperado = canvas._caminho_cena_de(ret)
    canvas.cena.clearSelection()
    ret.setSelected(True)
    QTest.keyClick(canvas, Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier)
    curva = canvas.selecionados_mockup()[0]
    assert isinstance(curva, ElementoCurva) and curva.preenchido
    assert ret not in canvas.elementos_mockup
    assert _diferenca(esperado, curva.caminho_cena()) < 1e-6
    canvas.pilha_desfazer.undo()
    assert ret in canvas.elementos_mockup and curva not in canvas.elementos_mockup


def test_texto_vira_curvas(janela):
    canvas = janela.canvas
    texto = ElementoTexto("OK", cor_tinta=PRETO)
    canvas.adicionar_elemento_mockup(texto, QPointF(400, 200))
    canvas.cena.clearSelection()
    texto.setSelected(True)
    assert canvas.converter_selecionados_em_curvas() == 1
    curva = canvas.selecionados_mockup()[0]
    assert curva.preenchido and curva.largura_traco == 0 and len(curva.subcaminhos) >= 2


def test_combinar_e_separar(janela):
    canvas = janela.canvas
    a = ElementoRetangulo(largura=80, altura=80, cor_tinta=PRETO, preenchido=True)
    b = ElementoElipse(largura=30, altura=30, cor_tinta=PRETO)
    canvas.adicionar_elemento_mockup(a, QPointF(100, 100))
    canvas.adicionar_elemento_mockup(b, QPointF(125, 125))
    canvas.cena.clearSelection()
    a.setSelected(True)
    b.setSelected(True)
    QTest.keyClick(canvas, Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)
    combinada = canvas.selecionados_mockup()[0]
    assert isinstance(combinada, ElementoCurva) and len(combinada.subcaminhos) == 2
    centro = combinada.mapFromScene(QPointF(140, 140))
    assert not combinada.caminho_local().contains(centro)  # furo (par/ímpar), como no CorelDRAW
    QTest.keyClick(canvas, Qt.Key.Key_K, Qt.KeyboardModifier.ControlModifier)
    partes = canvas.selecionados_mockup()
    assert len(partes) == 2 and all(isinstance(p, ElementoCurva) for p in partes)


def test_forma_arrasta_no_adiciona_remove_e_desfaz(janela):
    canvas = janela.canvas
    ret = ElementoRetangulo(largura=100, altura=50, cor_tinta=PRETO, largura_traco=0)
    canvas.adicionar_elemento_mockup(ret, QPointF(500, 100))
    canvas.cena.clearSelection()
    ret.setSelected(True)
    canvas.converter_selecionados_em_curvas()
    curva = canvas.selecionados_mockup()[0]
    canto = curva.mapToScene(curva.subcaminhos_locais()[0].nos[0].p)
    QTest.keyClick(canvas, Qt.Key.Key_F10)
    assert canvas.ferramenta_ativa == FerramentaMockup.FORMA

    _arrastar(janela, (canto.x(), canto.y()), (canto.x() - 20, canto.y() - 10))
    novo = curva.mapToScene(curva.subcaminhos_locais()[0].nos[0].p)
    # O arrasto cai em pixel inteiro da tela (~0,15 mm neste zoom).
    assert (novo.x(), novo.y()) == pytest.approx((canto.x() - 20, canto.y() - 10), abs=0.5)
    canvas.pilha_desfazer.undo()
    volta = curva.mapToScene(curva.subcaminhos_locais()[0].nos[0].p)
    assert (volta.x(), volta.y()) == pytest.approx((canto.x(), canto.y()), abs=1e-6)

    meio_topo = (550.0, 100.0)  # meio do lado de cima
    _mouse(janela, QEvent.Type.MouseButtonDblClick, meio_topo, ESQ, ESQ)
    assert len(curva.subcaminhos[0].nos) == 5
    QTest.keyClick(canvas, Qt.Key.Key_Delete)
    assert len(curva.subcaminhos[0].nos) == 4


class _Falso:
    def __init__(self, registro, nome="app", falhar=()):
        object.__setattr__(self, "_registro", registro)
        object.__setattr__(self, "_nome", nome)
        object.__setattr__(self, "_falhar", falhar)

    def __getattr__(self, nome):
        if nome in self._falhar:
            raise AttributeError(nome)
        return _Falso(self._registro, nome, self._falhar)

    def __setattr__(self, nome, valor):
        self._registro.append(("set", nome))

    def __call__(self, *args, **kwargs):
        self._registro.append((self._nome, args))
        return _Falso(self._registro, self._nome, self._falhar)


@pytest.mark.parametrize("falhar, esperado", [((), "AppendCurveSegment2"), (("CreateCurve",), "CreateLineSegment")])
def test_ponte_corel_curva_nativa_e_aproximada(app, falhar, esperado):
    from PySide6.QtGui import QPainterPath
    from PySide6.QtWidgets import QGraphicsScene

    from gerador_layout.ui import corel_bridge
    from gerador_layout.ui.mockup_curva import curva_de_caminho_cena

    caminho = QPainterPath(QPointF(0, 0))
    caminho.cubicTo(QPointF(10, -20), QPointF(40, -20), QPointF(50, 0))
    curva = curva_de_caminho_cena(caminho, cor_tinta=PRETO)
    cena = QGraphicsScene()
    cena.addItem(curva)
    registro: list = []
    corel_bridge._desenhar_elemento_mockup(_Falso(registro, falhar=falhar), _Falso(registro, "layer", falhar), curva, 350.0)
    assert esperado in [nome for nome, *_ in registro]
