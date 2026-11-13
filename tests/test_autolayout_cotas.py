"""Autolayout (etapa 1): a arte acompanha a face quando as medidas mudam.
Cotas automáticas: um clique cota a faca; saem na folha de aprovação."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.models import CorImpressao, TipoCaixa  # noqa: E402
from gerador_layout.paineis import Painel, deslocamento_na_face  # noqa: E402
from gerador_layout.ui.mockup_cota import ElementoCota  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402


def _face(x1, y1, x2, y2):
    return Painel("f", "F", x1, y1, x2, y2, eh_aba=False)


def test_mantem_a_distancia_da_borda_mais_proxima():
    velha, nova = _face(0, 0, 100, 100), _face(10, 0, 210, 150)
    assert deslocamento_na_face(5, 5, 15, 15, velha, nova) == pytest.approx((10, 0))  # perto da esquerda e do topo
    assert deslocamento_na_face(80, 80, 95, 95, velha, nova) == pytest.approx((110, 50))  # direita e base
    assert deslocamento_na_face(40, 40, 60, 60, velha, nova) == pytest.approx((60, 25))  # centralizado continua


@pytest.fixture
def janela():
    QApplication.instance() or QApplication([])
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    j.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    yield j
    j.close()


def _ret(j, x, y):
    el = ElementoRetangulo(largura=20, altura=10, cor_tinta=CorImpressao("PRETO", 0, 0, 0))
    j.canvas.adicionar_elemento_mockup(el, QPointF(x, y))
    return el


def _frente(j):
    return next(p for p in j._paineis_disponiveis() if p.id == "frente")


def test_arte_acompanha_a_face_quando_o_comprimento_muda(janela):
    f = _frente(janela)
    direita = _ret(janela, f.x2 - 25, f.y1 + 20)  # 5 mm da borda direita
    meio = _ret(janela, (f.x1 + f.x2) / 2 - 10, f.y1 + 60)
    fora = _ret(janela, -100, -100)
    janela.spin_comprimento.setValue(400)
    QApplication.processEvents()
    g = _frente(janela)
    assert g.x2 - (direita.pos().x() + 20) == pytest.approx(5)
    assert meio.pos().x() + 10 == pytest.approx((g.x1 + g.x2) / 2)
    assert (fora.pos().x(), fora.pos().y()) == (-100, -100)


def test_cotas_automaticas_pelos_vincos_e_apagaveis(janela):
    canvas = janela.canvas
    assert canvas.gerar_cotas_automaticas() == 10  # 5 colunas + total, 3 linhas + total
    cotas = [e for e in canvas.elementos_mockup if isinstance(e, ElementoCota)]
    assert len(cotas) == 10
    assert canvas.gerar_cotas_automaticas() == 10  # gerar de novo não duplica
    assert len([e for e in canvas.elementos_mockup if isinstance(e, ElementoCota)]) == 10
    canvas.pilha_desfazer.undo()
    canvas.pilha_desfazer.undo()
    assert not [e for e in canvas.elementos_mockup if isinstance(e, ElementoCota)]


def test_folha_inclui_as_cotas(janela, tmp_path, monkeypatch):
    from gerador_layout.ui import folha_aprovacao

    canvas = janela.canvas
    pagina = canvas.retangulo_pagina()
    canvas.gerar_cotas_automaticas()
    area = canvas.retangulo_com_cotas()
    assert area.top() < pagina.top() and area.left() < pagina.left()
    visto = {}
    original = folha_aprovacao.gerar_pdf

    def espiao(*args, **kwargs):
        visto.update(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(folha_aprovacao, "gerar_pdf", espiao)

    def preencher(dialogo):
        dialogo.check_3d.setChecked(False)
        return True

    assert janela.gerar_folha_aprovacao(str(tmp_path / "f.pdf"), dialogo=preencher, abrir=False)
    assert visto["area_desenho"] == area


def test_centro_da_face_e_alvo_de_encaixe_mesmo_em_automatica(janela):
    canvas = janela.canvas
    f = _frente(janela)
    el = _ret(janela, f.x1 + 5, f.y1 + 5)
    el.definir_painel(None)
    assert (f.x1 + f.x2) / 2 in canvas._alvos_snap_x(el)
    assert (f.y1 + f.y2) / 2 in canvas._alvos_snap_y(el)
    rotulos = [nome for _p, nome in canvas.nos_de_encaixe_com_tipo()]
    assert "centro da face" in rotulos


def _objeto_na_face(janela, face_id, y=15.0):
    from gerador_layout.ui.mockup_formas import ElementoRetangulo

    face = next(p for p in janela._paineis_atuais if p.id == face_id)
    el = ElementoRetangulo(largura=60.0, altura=12.0)
    el.setPos(face.x1 + 30.0, face.y1 + y)
    janela.canvas.adicionar_elemento_mockup(el)
    return el


def _dentro(janela, face_id, el):
    from PySide6.QtCore import QRectF

    face = next(p for p in janela._paineis_atuais if p.id == face_id)
    area = QRectF(face.x1, face.y1, face.x2 - face.x1, face.y2 - face.y1)
    return area.contains(el.retangulo_conteudo_cena())


def _digitar(spin, texto):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    spin.setFocus()
    spin.selectAll()
    QTest.keyClicks(spin, texto)
    QTest.keyClick(spin, Qt.Key.Key_Tab)


def _maleta(janela):
    from gerador_layout.models import TipoCaixa

    janela.combo_tipo.setCurrentIndex(janela.combo_tipo.findData(TipoCaixa.MALETA_NORMAL))
    janela.spin_comprimento.setValue(600)
    janela.spin_largura.setValue(400)
    janela.spin_altura.setValue(300)


def test_digitar_a_medida_nao_tira_a_arte_da_face(janela):
    _maleta(janela)
    objetos = {f: _objeto_na_face(janela, f) for f in ("frente", "tampa_frente", "lateral1")}
    _digitar(janela.spin_largura, "150")
    _digitar(janela.spin_altura, "500")
    assert janela.spin_largura.value() == 150
    assert all(_dentro(janela, f, el) for f, el in objetos.items())


def test_digitar_no_riscador_nao_tira_a_arte_da_face(janela):
    _maleta(janela)
    objeto = _objeto_na_face(janela, "tampa_frente")
    _digitar(janela.linha_riscador._spins[0], "150")
    assert _dentro(janela, "tampa_frente", objeto)


def test_objeto_lembra_a_face_quando_ela_encolhe_e_volta(janela):
    _maleta(janela)
    objeto = _objeto_na_face(janela, "lateral1")
    janela.spin_largura.setValue(5)
    janela.spin_largura.setValue(400)
    assert _dentro(janela, "lateral1", objeto)


def test_objeto_redimensionado_volta_a_escolher_a_borda(janela):
    _maleta(janela)
    objeto = _objeto_na_face(janela, "frente")
    janela.spin_comprimento.setValue(620)  # a memória nasce presa à esquerda
    face = next(p for p in janela._paineis_atuais if p.id == "frente")
    objeto.setPos(face.x1 + 20.0, objeto.pos().y())
    objeto.definir_tamanho(face.x2 - face.x1 - 40.0, objeto.altura)  # agora centralizado
    centro = objeto.retangulo_conteudo_cena().center().x()
    assert centro == pytest.approx((face.x1 + face.x2) / 2)
    janela.spin_comprimento.setValue(700)
    nova = next(p for p in janela._paineis_atuais if p.id == "frente")
    assert objeto.retangulo_conteudo_cena().center().x() == pytest.approx((nova.x1 + nova.x2) / 2)


def test_jpg_inclui_as_cotas_por_fora_da_chapa(janela, monkeypatch):
    """O JPG cortava no tamanho da chapa: as cotas, por fora dela, sumiam.
    E o número saía em branco (drawText com escala some na exportação)."""
    from gerador_layout.ui import exportacao

    canvas = janela.canvas
    canvas.gerar_cotas_automaticas()
    cotas = [e for e in canvas.elementos_mockup if isinstance(e, ElementoCota)]

    def vermelhos():
        imagem = exportacao.imagem_do_layout(canvas.cena, canvas.layout_efetivo, dpi=40)
        return sum(
            1
            for y in range(imagem.height())
            for x in range(imagem.width())
            if imagem.pixelColor(x, y).red() > 150 and imagem.pixelColor(x, y).green() < 90
        )

    com_numero = vermelhos()
    assert com_numero > 50  # as cotas (vermelhas) saem na imagem
    monkeypatch.setattr(ElementoCota, "texto_valor", lambda self: "")
    assert com_numero > vermelhos() * 1.2  # e o número delas também

    rect, legenda = exportacao._rect_com_legenda(canvas.cena, canvas.layout_efetivo)
    try:
        for cota in cotas:
            assert rect.contains(cota.retangulo_conteudo_cena())
        topo_cotas = min(c.retangulo_conteudo_cena().top() for c in cotas)
        assert legenda._itens  # a caixa padrão tem legenda de cores
        assert max(i.sceneBoundingRect().bottom() for i in legenda._itens) <= topo_cotas  # acima de tudo
    finally:
        legenda.remover()
