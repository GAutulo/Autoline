"""Cota angular (CorelDRAW): 3 cliques — vértice, 1º braço, 2º braço."""

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
from PySide6.QtWidgets import QApplication, QGraphicsScene  # noqa: E402

from gerador_layout.ui.mockup_cota_angular import ElementoCotaAngular, geometria_arco  # noqa: E402
from gerador_layout.ui.preview_canvas import FerramentaMockup  # noqa: E402

ESQ = Qt.MouseButton.LeftButton
NENHUM = Qt.MouseButton.NoButton


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize(
    "v, a, b, graus",
    [
        ((100, 100), (160, 100), (100, 40), 90.0),
        ((100, 100), (160, 100), (160, 40), 45.0),
        ((0, 0), (50, 0), (-50, 0.0001), 180.0),
        ((0, 0), (10, 10), (10, -10), 90.0),
    ],
)
def test_valor_e_menor_angulo(app, v, a, b, graus):
    _inicio, varredura = geometria_arco(QPointF(*v), QPointF(*a), QPointF(*b))
    assert varredura == pytest.approx(graus, abs=1e-3)


def test_posicao_copia_e_esticar(app):
    cena = QGraphicsScene()
    cota = ElementoCotaAngular(QPointF(100, 100), QPointF(160, 100), QPointF(160, 40))
    cena.addItem(cota)
    cota.setPos(cota.posicao_inicial_cena)
    vertice = cota.mapToScene(cota.pontos_locais()[0])
    assert (vertice.x(), vertice.y()) == pytest.approx((100, 100))
    assert cota.texto_valor() == "45,0°"
    copia = cota.clonar()
    cena.addItem(copia)
    v2 = copia.mapToScene(copia.pontos_locais()[0])
    assert (v2.x(), v2.y()) == pytest.approx((100, 100)) and copia.texto_valor() == "45,0°"
    cota.definir_tamanho(cota.largura * 2, cota.altura)
    assert cota.valor_graus < 45.0  # esticar na horizontal fecha o ângulo


def _clique(janela, ponto):
    vista = janela.canvas
    pos = QPointF(vista.mapFromScene(QPointF(*ponto)))
    for tipo, botao, botoes in ((QEvent.Type.MouseButtonPress, ESQ, ESQ), (QEvent.Type.MouseButtonRelease, ESQ, NENHUM)):
        evento = QMouseEvent(tipo, pos, vista.viewport().mapToGlobal(pos), botao, botoes, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(vista.viewport(), evento)


def test_ferramenta_tres_cliques_e_esc(app):
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    j.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    canvas = j.canvas
    canvas.definir_ferramenta(FerramentaMockup.COTA_ANGULAR)
    antes = len(canvas.elementos_mockup)
    # Vértice no canto da faca (4, 100): gruda no nó.
    for ponto in ((4.3, 100.2), (200, 100), (4, 0)):
        _clique(j, ponto)
    assert len(canvas.elementos_mockup) == antes + 1
    cota = canvas.elementos_mockup[-1]
    assert isinstance(cota, ElementoCotaAngular) and cota.isSelected()
    assert cota.valor_graus == pytest.approx(90.0, abs=0.5)
    assert j.painel_propriedades_mockup._rotulo_tipo.text() == "Cota angular"
    assert canvas.ferramenta_ativa == FerramentaMockup.COTA_ANGULAR

    _clique(j, (300, 150))
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    _clique(j, (310, 150))
    _clique(j, (350, 150))
    assert len(canvas.elementos_mockup) == antes + 1  # o Esc zerou os pontos: ainda faltava 1 clique
    j.close()


class _Falso:
    def __init__(self, registro, nome="app"):
        object.__setattr__(self, "_registro", registro)
        object.__setattr__(self, "_nome", nome)
        object.__setattr__(self, "SizeWidth", 8.0)

    def __getattr__(self, nome):
        return _Falso(self._registro, nome)

    def __setattr__(self, nome, valor):
        self._registro.append(("set", nome))

    def __call__(self, *args, **kwargs):
        self._registro.append((self._nome, args))
        return _Falso(self._registro, self._nome)


def test_ponte_corel(app):
    from gerador_layout.ui import corel_bridge

    cena = QGraphicsScene()
    cota = ElementoCotaAngular(QPointF(0, 0), QPointF(50, 0), QPointF(0, -50))
    cena.addItem(cota)
    registro: list = []
    corel_bridge._desenhar_elemento_mockup(_Falso(registro), _Falso(registro, "layer"), cota, 350.0)
    nomes = [n for n, *_ in registro if n != "set"]
    assert nomes.count("CreateLineSegment") > 10 and "CreateArtisticText" in nomes
