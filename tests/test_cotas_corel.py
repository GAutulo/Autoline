"""Cotas persistentes (paralela, horizontal, vertical) — ver mockup_cota.py."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication, QGraphicsScene  # noqa: E402

from gerador_layout.ui.mockup_cota import ElementoCota, criar_cota  # noqa: E402
from gerador_layout.ui.preview_canvas import FerramentaMockup  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _pontos_medidos(cota: ElementoCota):
    a = cota.mapToScene(QPointF(0.0, cota.altura - cota._ya))
    b = cota.mapToScene(QPointF(cota.largura, cota.altura - cota._yb))
    return (round(a.x(), 6), round(a.y(), 6)), (round(b.x(), 6), round(b.y(), 6))


@pytest.mark.parametrize(
    "tipo, p1, p2, valor",
    [
        ("paralela", (10, 10), (110, 10), 100.0),
        ("paralela", (10, 10), (40, 50), 50.0),
        ("paralela", (110, 50), (10, 50), 100.0),
        ("horizontal", (10, 40), (110, 10), 100.0),
        ("vertical", (10, 10), (60, 90), 80.0),
    ],
)
def test_cota_mede_e_encosta_nos_pontos(app, tipo, p1, p2, valor):
    cena = QGraphicsScene()
    cota = criar_cota(QPointF(*p1), QPointF(*p2), tipo)
    cena.addItem(cota)
    assert cota.valor_mm == pytest.approx(valor)
    a, b = _pontos_medidos(cota)
    if tipo == "paralela":
        assert {a, b} == {tuple(map(float, p1)), tuple(map(float, p2))}
    else:
        assert sorted([a, b]) == sorted([tuple(map(float, p1)), tuple(map(float, p2))])
    assert not cota.texto_de_cabeca_pra_baixo()


def test_valor_acompanha_redimensionar_e_afastamento_preserva_pontos(app):
    cena = QGraphicsScene()
    cota = criar_cota(QPointF(0, 50), QPointF(100, 50), "paralela")
    cena.addItem(cota)
    cota.definir_tamanho(120.0, cota.altura)
    assert cota.texto_valor() == "120,0 mm"
    antes = cota.mapToScene(QPointF(0.0, cota.altura))
    cota.definir_afastamento(25.0)
    assert cota.afastamento == pytest.approx(25.0)
    depois = cota.mapToScene(QPointF(0.0, cota.altura))
    assert (depois.x(), depois.y()) == pytest.approx((antes.x(), antes.y()))
    copia = cota.clonar()
    assert copia.valor_mm == pytest.approx(120.0) and copia.afastamento == pytest.approx(25.0)


def test_ferramenta_cria_cota_grudada_na_faca(app):
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.abas_tela.setCurrentIndex(1)
    canvas = j.canvas
    canvas.definir_snap_ativo(True)
    linha = canvas.layout_atual.linhas[0]
    perto = QPointF(linha.x1 + 0.4, linha.y1 - 0.3)
    assert canvas.encaixar_ponto(perto) == QPointF(linha.x1, linha.y1)

    canvas.definir_ferramenta(FerramentaMockup.COTA_HORIZONTAL)
    antes = len(canvas.elementos_mockup)
    canvas.cota_desenhada.emit(QPointF(0, 0), QPointF(300, 0), "horizontal")
    assert len(canvas.elementos_mockup) == antes + 1
    cota = canvas.elementos_mockup[-1]
    assert isinstance(cota, ElementoCota) and cota.isSelected()
    assert canvas.ferramenta_ativa == FerramentaMockup.COTA_HORIZONTAL  # continua cotando
    assert "Cota" in j.painel_status.rotulo_objeto.text() or j.painel_propriedades_mockup._rotulo_tipo.text() == "Cota"
    j.close()


class _Falso:
    """Objeto COM de mentira: aceita qualquer atributo/chamada e registra."""

    def __init__(self, registro, nome="app"):
        object.__setattr__(self, "_registro", registro)
        object.__setattr__(self, "_nome", nome)
        object.__setattr__(self, "SizeWidth", 10.0)

    def __getattr__(self, nome):
        return _Falso(self._registro, nome)

    def __setattr__(self, nome, valor):
        self._registro.append(("set", nome))

    def __call__(self, *args, **kwargs):
        self._registro.append((self._nome, args))
        return _Falso(self._registro, self._nome)


def test_ponte_corel_desenha_cota_com_primitivas(app):
    from gerador_layout.ui import corel_bridge

    cena = QGraphicsScene()
    cota = criar_cota(QPointF(0, 0), QPointF(50, 50), "paralela")
    cena.addItem(cota)
    registro: list = []
    corel_bridge._desenhar_elemento_mockup(_Falso(registro), _Falso(registro, "layer"), cota, 350.0)
    chamadas = [nome for nome, *_ in registro if nome != "set"]
    assert chamadas.count("CreateLineSegment") == 3 + 6  # 2 chamadas + linha + 2 setas de 3 lados
    assert "CreateArtisticText" in chamadas
    assert "RotateEx" in chamadas
