"""Coisas de tela (alças, grade, encaixe) acompanham o zoom e a escala do
desenho; ir pro 3D e voltar não perde o enquadramento."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from gerador_layout.models import CorImpressao  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoRetangulo  # noqa: E402
from gerador_layout.ui.mockup_itens import ElementoMockup  # noqa: E402


@pytest.fixture
def janela():
    QApplication.instance() or QApplication([])
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1400, 900)
    j.show()
    QApplication.processEvents()
    yield j
    j.close()


def _processar():
    for _ in range(5):
        QApplication.processEvents()


def test_ir_pro_3d_e_voltar_mantem_o_desenho_na_tela(janela):
    canvas = janela.canvas
    for medidas in ((300, 200, 150), (80.5, 55, 6)):  # tamanho normal e escala reduzida
        janela.spin_comprimento.setValue(medidas[0])
        janela.spin_largura.setValue(medidas[1])
        janela.spin_altura.setValue(medidas[2])
        for aba in (2, 0, 1, 2, 1, 0):
            janela.abas_tela.setCurrentIndex(aba)
            _processar()
        pagina = canvas.retangulo_pagina()
        centro = canvas.mapFromScene(pagina.center())
        assert canvas.viewport().rect().contains(centro)
        largura_na_tela = pagina.width() * canvas.transform().m11()
        assert largura_na_tela > canvas.viewport().width() * 0.5  # ocupa a tela, não virou um ponto


def test_alcas_em_pixels_acompanham_o_zoom(janela):
    canvas = janela.canvas
    janela.spin_comprimento.setValue(30)
    janela.spin_largura.setValue(20)
    janela.spin_altura.setValue(15)
    janela.abas_tela.setCurrentIndex(1)
    _processar()
    el = ElementoRetangulo(largura=3, altura=2, cor_tinta=CorImpressao("PRETO", 0, 0, 0))
    canvas.adicionar_elemento_mockup(el, QPointF(10, 10))
    canvas.ajustar_a_tela()
    zoom = canvas.transform().m11()
    assert ElementoMockup.mm_por_px == pytest.approx(1.0 / zoom)
    margem_px = (el.boundingRect().width() - el.largura) / 2 * zoom
    assert 20 < margem_px < 60  # a alça de rotação fica a ~24 px, em qualquer escala
    canvas.scale(2, 2)
    canvas._zoom_atual *= 2
    canvas.zoom_alterado.emit(canvas._zoom_atual)
    margem_px_2 = (el.boundingRect().width() - el.largura) / 2 * canvas.transform().m11()
    assert margem_px_2 == pytest.approx(margem_px, rel=0.01)


def test_grade_e_encaixe_acompanham_a_escala(janela):
    canvas = janela.canvas
    janela.spin_comprimento.setValue(30)
    janela.spin_largura.setValue(20)
    janela.spin_altura.setValue(15)
    _processar()
    canvas.ajustar_a_tela()
    px_por_mm = canvas.transform().m11()
    passo = canvas.passo_grade()
    assert 12 <= passo * px_por_mm <= 120  # a grade aparece com espaçamento legível
    assert canvas.limiar_snap() <= 10.0 / px_por_mm + 1e-9


def test_guia_nao_estraga_o_ajustar_a_tela(janela):
    canvas = janela.canvas
    canvas.ajustar_a_tela()
    zoom = canvas.transform().m11()
    canvas.adicionar_guia("v", 500)
    canvas.adicionar_guia("h", 100)
    for aba in (2, 0):  # o caso relatado: ir pro 3D e voltar
        janela.abas_tela.setCurrentIndex(aba)
        _processar()
    canvas.ajustar_a_tela()
    assert canvas.transform().m11() == pytest.approx(zoom, rel=0.05)


def test_zoom_nao_prende_o_desenho_no_canto(janela):
    canvas = janela.canvas
    janela.spin_comprimento.setValue(80)
    janela.spin_largura.setValue(50)
    janela.spin_altura.setValue(30)
    _processar()
    canvas.ajustar_a_tela()
    canvas.scale(3, 3)
    pagina = canvas.retangulo_pagina()
    for alvo in (pagina.topLeft(), pagina.bottomRight(), pagina.center()):
        canvas.centerOn(alvo)
        centro_tela = canvas.mapToScene(canvas.viewport().rect().center())
        # dá pra centralizar qualquer canto da chapa na tela (a mesa vai além)
        assert abs(centro_tela.x() - alvo.x()) < 2 and abs(centro_tela.y() - alvo.y()) < 2


def test_redimensionar_janela_reajusta_ate_o_usuario_mexer_no_zoom(janela):
    canvas = janela.canvas
    canvas.ajustar_a_tela()
    _processar()
    zoom_grande = canvas.transform().m11()
    janela.resize(900, 650)
    _processar()
    pagina = canvas.retangulo_pagina()
    assert canvas.transform().m11() < zoom_grande  # reajustou pra caber
    assert pagina.width() * canvas.transform().m11() <= canvas.viewport().width()
    canvas.scale(2, 2)  # o usuário deu zoom
    zoom_usuario = canvas.transform().m11()
    janela.resize(1300, 850)
    _processar()
    assert canvas.transform().m11() == pytest.approx(zoom_usuario)


def test_barra_da_faca_em_linha_propria(janela):
    janela.resize(1000, 700)
    janela.abas_tela.setCurrentIndex(0)
    _processar()
    assert janela.toolBarBreak(janela.barra_faca)


def test_selecionar_objeto_nao_mexe_no_zoom_nem_desloca(janela):
    """Bug relatado: selecionar o texto mexia a barra de status, o canvas
    reajustava o zoom no meio do clique e o objeto pulava pra direita."""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest

    from gerador_layout.ui.mockup_texto import ElementoTexto

    canvas = janela.canvas
    janela.spin_comprimento.setValue(30)
    janela.spin_largura.setValue(20)
    janela.spin_altura.setValue(15)
    janela.abas_tela.setCurrentIndex(1)
    _processar()
    canvas.ajustar_a_tela()
    _processar()
    pagina = canvas.retangulo_pagina()
    janela._criar_texto_por_clique(pagina.center())
    QTest.keyClicks(canvas.viewport(), "GABINETE FLORA")
    QTest.keyClick(canvas.viewport(), Qt.Key.Key_Escape)
    _processar()
    texto = next(e for e in canvas._elementos_mockup if isinstance(e, ElementoTexto))

    def mouse(tipo, p, botao, botoes):
        pos = QPointF(canvas.mapFromScene(p))
        QApplication.sendEvent(
            canvas.viewport(),
            QMouseEvent(tipo, pos, canvas.viewport().mapToGlobal(pos), botao, botoes, Qt.KeyboardModifier.NoModifier),
        )

    esq, nada = Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton
    QTest.qWait(250)  # deixa passar o ajuste agendado pela troca de aba
    zoom = canvas.transform().m11()
    for _ in range(4):
        antes = QPointF(texto.pos())
        p = texto.mapToScene(texto.largura * 0.3, texto.altura / 2)
        mouse(QEvent.Type.MouseButtonPress, p, esq, esq)
        mouse(QEvent.Type.MouseButtonRelease, p, esq, nada)
        _processar()
        fora = pagina.topLeft() - QPointF(3, 3)
        mouse(QEvent.Type.MouseButtonPress, fora, esq, esq)
        mouse(QEvent.Type.MouseButtonRelease, fora, esq, nada)
        _processar()
        assert texto.pos() == antes
    assert canvas.transform().m11() == pytest.approx(zoom)


def test_aviso_do_3d_nao_alarga_a_janela(janela):
    """O aviso longo da barra do 3D, junto com o seletor de papelão, fazia a
    janela pedir 1303 px no Windows (não cabia num notebook). Ele precisa
    poder encolher. (A largura em pixels depende da plataforma: no modo
    offscreen dos testes as fontes medem bem maior, então o teste olha o
    aviso, não o total.)"""
    aviso = janela.visualizacao_3d.aviso_dobras
    assert aviso.minimumSizeHint().width() < 100 or aviso.sizePolicy().horizontalPolicy() == aviso.sizePolicy().Policy.Ignored
    sem_aviso = janela.visualizacao_3d.minimumSizeHint().width()
    aviso.setText(aviso.text() * 3)  # mesmo um aviso enorme não muda a largura mínima
    assert janela.visualizacao_3d.minimumSizeHint().width() == sem_aviso
