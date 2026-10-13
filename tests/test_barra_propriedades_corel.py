"""Barra de propriedades no padrão do CorelDRAW: escala em %, espelhar e
estado sem seleção (ver REFERENCIA_CORELDRAW.md)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QDoubleSpinBox, QLabel  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui import configuracoes  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoPoligono, ElementoRetangulo  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def janela(app):
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.abas_tela.setCurrentIndex(1)
    yield j
    j.close()


def _spin_com_dica(barra, trecho):
    return next(s for s in barra.findChildren(QDoubleSpinBox) if trecho in s.toolTip())


def test_escala_percentual_em_torno_do_centro(janela):
    el = ElementoRetangulo(largura=40, altura=20, cor_tinta=CorImpressao("PRETO", 0, 0, 0))
    janela.canvas.adicionar_elemento_mockup(el, QPointF(100, 100))
    janela.canvas.cena.clearSelection()
    el.setSelected(True)
    centro_antes = el.retangulo_conteudo_cena().center()
    spin = _spin_com_dica(janela.painel_propriedades_mockup, "Escala da largura")
    spin.setValue(150.0)
    assert el.largura == pytest.approx(60) and el.altura == pytest.approx(20)
    assert spin.value() == pytest.approx(100.0)
    centro = el.retangulo_conteudo_cena().center()
    assert (centro.x(), centro.y()) == pytest.approx((centro_antes.x(), centro_antes.y()))


def test_espelhar_desenha_o_conteudo_invertido_e_copia_herda(janela):
    el = ElementoPoligono(largura=40, altura=40, cor_tinta=CorImpressao("PRETO", 0, 0, 0), lados=3)
    el.definir_preenchido(True)

    def render(item):
        img = QImage(40, 40, QImage.Format.Format_ARGB32)
        img.fill(0)
        p = QPainter(img)
        item.paint(p, None)
        p.end()
        return img

    normal = render(el)
    el.definir_espelho(False, True)
    invertido = render(el)
    # Antialiasing deixa diferença de borda — compara o "peso" de tinta
    # por linha: a do espelhado é a do normal de baixo pra cima.
    def peso_por_linha(img):
        return [sum(img.pixelColor(x, y).alpha() for x in range(40)) for y in range(40)]

    linhas_normal, linhas_invertido = peso_por_linha(normal), peso_por_linha(invertido)
    assert linhas_normal != linhas_invertido  # triângulo não é simétrico na vertical
    diferenca = sum(abs(a - b) for a, b in zip(linhas_normal[::-1], linhas_invertido))
    assert diferenca <= 0.05 * sum(linhas_normal)
    assert el.clonar().espelho_v


def test_estado_sem_selecao_mostra_chapa_e_distancias(janela):
    janela.canvas.cena.clearSelection()
    barra = janela.painel_propriedades_mockup
    barra.definir_elemento(None)
    rotulo = next(r for r in barra.findChildren(QLabel) if r.objectName() == "rotuloPaginaPropriedade")
    layout = janela.canvas.layout_atual
    assert f"{layout.largura_total:.1f}".replace(".", ",") in rotulo.text()
    antes = configuracoes.passo_duplicar_mm()
    try:
        spin = next(s for s in barra.findChildren(QDoubleSpinBox) if s.objectName() == "spinDistanciaDuplicar")
        spin.setValue(antes + 1.0)
        assert configuracoes.passo_duplicar_mm() == pytest.approx(antes + 1.0)
    finally:
        configuracoes.definir_passo_duplicar_mm(antes)
