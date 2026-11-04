"""Cotas automáticas também medem os objetos impressos: a distância até o
vizinho e até a borda da caixa. E o tamanho delas se ajusta de uma vez."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.models import TipoCaixa  # noqa: E402
from gerador_layout.paineis import Painel, distancias_dos_objetos  # noqa: E402
from gerador_layout.ui.mockup_cota import ElementoCota, criar_cota  # noqa: E402


def _face(y1, y2):
    return Painel("f", "F", 0.0, y1, 100.0, y2, eh_aba=False)


def test_objeto_sozinho_mede_ate_as_quatro_bordas():
    medidas = distancias_dos_objetos([(10.0, 20.0, 30.0, 40.0)], [], (0.0, 0.0, 100.0, 100.0))
    assert sorted(medidas) == sorted([
        (0.0, 30.0, 10.0, 30.0), (30.0, 30.0, 100.0, 30.0),
        (20.0, 0.0, 20.0, 20.0), (20.0, 40.0, 20.0, 100.0),
    ])


def test_dois_objetos_medem_entre_si_uma_vez_so():
    medidas = distancias_dos_objetos(
        [(10.0, 20.0, 30.0, 40.0), (50.0, 20.0, 70.0, 40.0)], [], (0.0, 0.0, 100.0, 100.0)
    )
    horizontais = [m for m in medidas if m[1] == m[3]]
    assert sorted(horizontais) == [(0.0, 30.0, 10.0, 30.0), (30.0, 30.0, 50.0, 30.0), (70.0, 30.0, 100.0, 30.0)]


def test_mede_so_ate_o_vizinho_mais_perto():
    medidas = distancias_dos_objetos(
        [(0.0, 0.0, 10.0, 10.0), (20.0, 0.0, 30.0, 10.0), (40.0, 0.0, 50.0, 10.0)], [], (0.0, 0.0, 60.0, 10.0)
    )
    assert (10.0, 5.0, 20.0, 5.0) in medidas and (30.0, 5.0, 40.0, 5.0) in medidas
    assert not any(a == 10.0 and b == 40.0 for a, _, b, _ in medidas)


def test_outra_face_para_na_borda_da_face():
    faces = [_face(0.0, 50.0), _face(50.0, 100.0)]
    medidas = distancias_dos_objetos(
        [(10.0, 10.0, 30.0, 30.0), (10.0, 60.0, 30.0, 80.0)], faces, (0.0, 0.0, 100.0, 100.0)
    )
    assert (20.0, 30.0, 20.0, 50.0) in medidas and (20.0, 50.0, 20.0, 60.0) in medidas


def test_encostado_na_borda_nao_gera_medida_zero():
    medidas = distancias_dos_objetos([(0.0, 0.0, 100.0, 100.0)], [], (0.0, 0.0, 100.0, 100.0))
    assert medidas == []


@pytest.fixture
def janela():
    QApplication.instance() or QApplication([])
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    j.combo_tipo.setCurrentIndex(j.combo_tipo.findData(TipoCaixa.CINTA))
    j.spin_comprimento.setValue(600.0)
    j.spin_largura.setValue(90.0)
    j.spin_altura.setValue(128.0)
    QApplication.processEvents()
    yield j
    j.canvas.pilha_desfazer.clear()
    j.close()


def _cotas(canvas):
    return [e for e in canvas.elementos_mockup if isinstance(e, ElementoCota)]


def _objeto_em(janela, x, y):
    from gerador_layout.ui.mockup_formas import ElementoRetangulo

    el = ElementoRetangulo(largura=40.0, altura=20.0)
    el.setPos(x, y)
    janela.canvas.adicionar_elemento_mockup(el)
    return el


def test_gerar_cotas_inclui_os_objetos_e_nao_mede_cota(janela):
    canvas = janela.canvas
    sem_objetos = canvas.gerar_cotas_automaticas()
    _objeto_em(janela, 100.0, 20.0)
    com_um = canvas.gerar_cotas_automaticas()
    assert com_um == sem_objetos + 4
    assert canvas.gerar_cotas_automaticas() == com_um  # as cotas não viram objeto medido


def test_cota_do_objeto_mede_a_distancia_real(janela):
    _objeto_em(janela, 100.0, 20.0)
    janela.canvas.gerar_cotas_automaticas()
    assert any(c.valor_mm == pytest.approx(100.0) and c.afastamento <= 2.0 for c in _cotas(janela.canvas))


def test_campo_de_tamanho_muda_todas_e_as_proximas(janela):
    canvas = janela.canvas
    manual = criar_cota(QPointF(0, 0), QPointF(100, 0), "horizontal", 10.0)
    canvas.adicionar_elemento_mockup(manual)
    canvas.gerar_cotas_automaticas()
    janela.spin_tamanho_cotas.setValue(2.0)
    assert {c.altura_texto for c in _cotas(canvas)} == {2.0}
    janela._gerar_cotas_automaticas()
    assert {c.altura_texto for c in _cotas(canvas)} == {2.0}
    assert janela.spin_tamanho_cotas.value() == 2.0


def test_campo_mostra_o_tamanho_usado_ao_gerar(janela):
    janela._gerar_cotas_automaticas()
    assert janela.spin_tamanho_cotas.value() == pytest.approx(_cotas(janela.canvas)[0].altura_texto, abs=0.05)


def test_seta_acompanha_o_tamanho_do_texto():
    cota = criar_cota(QPointF(0, 0), QPointF(100, 0), "horizontal", 10.0)
    cota.definir_altura_texto(1.0)
    pequena = cota.setas_locais()[0].boundingRect().width()
    cota.definir_altura_texto(7.0)
    assert cota.setas_locais()[0].boundingRect().width() > pequena * 2


def test_objeto_que_cruza_o_vinco_nao_some_com_a_cota_do_vizinho():
    faces = [Painel("a", "A", 0.0, 0.0, 50.0, 100.0, eh_aba=False), Painel("b", "B", 50.0, 0.0, 100.0, 100.0, eh_aba=False)]
    medidas = distancias_dos_objetos(
        [(10.0, 10.0, 20.0, 30.0), (45.0, 10.0, 90.0, 30.0)], faces, (0.0, 0.0, 100.0, 100.0)
    )
    assert (20.0, 20.0, 50.0, 20.0) in medidas  # o da esquerda mede até a borda da face dele


def test_tamanho_das_cotas_nao_passa_pro_proximo_projeto(janela):
    janela.spin_tamanho_cotas.setValue(2.0)
    janela.novo_projeto()
    janela.spin_comprimento.setValue(900.0)
    assert janela.canvas._altura_cotas is None
