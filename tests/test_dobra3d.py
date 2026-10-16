"""Testes da dobra 3D: plana = dieline, fechada = sólido C × L × A."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gerador_layout.dobra3d import caixa_envolvente, montar_modelo, posicionar, produto_escalar
from gerador_layout.layout_service import ServicoLayoutCaixa
from gerador_layout.models import MedidasCaixa, TipoCaixa

C, L, A = 300.0, 200.0, 150.0
TOLERANCIA = 1e-6


def _modelo(tipo: TipoCaixa):
    layout = ServicoLayoutCaixa().calcular(MedidasCaixa(tipo=tipo, comprimento=C, largura=L, altura=A))
    return montar_modelo(tipo, layout.segmentos_impressora, layout.segmentos_riscador), layout


def _dimensoes(posicionados, ids):
    mn, mx = caixa_envolvente([p for p in posicionados if p.painel.id in ids])
    return sorted(round(mx[i] - mn[i], 6) for i in range(3))


@pytest.mark.parametrize("tipo", list(TipoCaixa))
def test_planificada_e_a_propria_dieline(tipo):
    modelo, layout = _modelo(tipo)
    assert not modelo.vazio
    for pp in posicionar(modelo, 0.0):
        for x, y in pp.painel.cantos:
            px, py, pz = pp.ponto(x, y)
            assert (px, py, pz) == pytest.approx((x, y, 0.0), abs=TOLERANCIA)
            assert -TOLERANCIA <= px <= layout.largura_total + TOLERANCIA
            assert -TOLERANCIA <= py <= layout.altura_total + TOLERANCIA


@pytest.mark.parametrize("tipo", [TipoCaixa.MALETA_NORMAL, TipoCaixa.MALETA_TRANSPASSADA])
def test_maleta_fechada_tem_as_medidas_da_caixa(tipo):
    modelo, _ = _modelo(tipo)
    fechada = posicionar(modelo, 1.0)
    paredes = {"frente", "verso", "lateral1", "lateral2"}
    assert _dimensoes(fechada, paredes) == sorted([C, L, A])
    # O verso fecha o anel: fica paralelo à frente, a uma Largura de distância.
    por_id = {p.painel.id: p for p in fechada}
    n_frente, n_verso = por_id["frente"].normal_externa, por_id["verso"].normal_externa
    assert produto_escalar(n_frente, n_verso) == pytest.approx(-1.0)


_ENVOLTORIOS_FECHADOS = [
    TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_SEM_CORTE,
    TipoCaixa.ENVOLTORIO_FECHAMENTO_MEIO_COM_CORTE,
    TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_SEM_CORTE,
    TipoCaixa.ENVOLTORIO_FECHAMENTO_NORMAL_COM_CORTE,
]


@pytest.mark.parametrize("tipo", _ENVOLTORIOS_FECHADOS)
def test_envoltorio_fechado_tem_as_medidas_da_caixa(tipo):
    modelo, _ = _modelo(tipo)
    fechada = posicionar(modelo, 1.0)
    assert _dimensoes(fechada, {"base", "lateral1", "lateral2", "parede_sup", "parede_inf"}) == sorted([C, L, A])


@pytest.mark.parametrize("tipo", list(TipoCaixa))
def test_caixa_fechada_tem_faces_impressas_para_fora(tipo):
    """Toda parede termina com o lado impresso apontando pra longe do centro."""
    modelo, _ = _modelo(tipo)
    fechada = posicionar(modelo, 1.0)
    paredes = [p for p in fechada if p.painel.id in {"frente", "verso", "lateral1", "lateral2", "base", "centro", "parede_sup", "parede_inf"}]
    mn, mx = caixa_envolvente(paredes)
    centro = tuple((mn[i] + mx[i]) / 2 for i in range(3))
    for pp in paredes:
        p = pp.painel
        cx, cy, cz = pp.ponto((p.x1 + p.x2) / 2, (p.y1 + p.y2) / 2)
        para_fora = (cx - centro[0], cy - centro[1], cz - centro[2])
        assert produto_escalar(pp.normal_externa, para_fora) > 0, p.id


def test_tampa_da_maleta_fecha_no_plano_do_topo():
    modelo, _ = _modelo(TipoCaixa.MALETA_NORMAL)
    fechada = {p.painel.id: p for p in posicionar(modelo, 1.0)}
    tampa = fechada["tampa_frente"]
    p = tampa.painel
    # Aba maior fecha a 90° exatos: todos os cantos no plano da aresta de cima da frente.
    alturas = {round(tampa.ponto(x, y)[1], 6) for x, y in p.cantos}
    assert alturas == {round(p.y2, 6)}


def test_medidas_invalidas_geram_modelo_vazio():
    assert montar_modelo(TipoCaixa.MALETA_NORMAL, [4, 0, 300, 200, 300], [100, 150, 100]).vazio


def test_aba_3d_leva_a_arte_do_layout():
    """Regressão: entrar na aba 3D com arte no Layout renderizava a arte
    com um parâmetro inválido e quebrava."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication

    from gerador_layout.models import CorImpressao
    from gerador_layout.ui.main_window import JanelaPrincipal
    from gerador_layout.ui.mockup_formas import ElementoRetangulo

    QApplication.instance() or QApplication([])
    j = JanelaPrincipal()
    j.abas_tela.setCurrentIndex(1)
    vermelho = CorImpressao("VERMELHO", 255, 0, 0)
    j.canvas.adicionar_elemento_mockup(ElementoRetangulo(largura=50, altura=30, cor_tinta=vermelho, preenchido=True), QPointF(250, 120))
    j.abas_tela.setCurrentIndex(2)
    vista = j.visualizacao_3d.vista
    vista.resize(800, 600)
    vista.grab()  # pinta: as faces visíveis pedem a textura
    imagem, k, retangulo = vista.textura_do_painel("frente")
    assert imagem is not None
    cor = imagem.pixelColor(int((275 - retangulo.left()) * k), int((135 - retangulo.top()) * k))
    assert (cor.red(), cor.green(), cor.blue(), cor.alpha()) == (255, 0, 0, 255)
    assert imagem.pixelColor(2, 2).alpha() == 0  # sem faca nem fundo na textura

    # Aproximar a câmera pede a face de novo, mais nítida.
    vista._zoom = 4.0
    vista.grab()
    vista._gerar_texturas_pendentes()
    _imagem, k_perto, _r = vista.textura_do_painel("frente")
    assert k_perto > k * 2
    j.close()


def test_giro_livre_olha_por_baixo():
    """O giro vertical não trava em 90°: dá pra olhar a caixa por baixo."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    from gerador_layout.ui.main_window import JanelaPrincipal

    QApplication.instance() or QApplication([])
    j = JanelaPrincipal()
    j.abas_tela.setCurrentIndex(2)
    vista = j.visualizacao_3d.vista
    vista.resize(600, 400)
    cima = vista._modelo.cima
    olho_antes = vista._camera()[0]
    vista._arrasto = (QPointF(0, 0), 0.0, 0.0)
    ponto = QPointF(0, -500)
    vista.mouseMoveEvent(QMouseEvent(QMouseEvent.Type.MouseMove, ponto, ponto, Qt.MouseButton.NoButton,
                                     Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
    assert vista._pitch_usuario == -200.0  # passou dos 90°, sem trava
    olho = vista._camera()[0]
    centro = vista._centro_montado
    altura = lambda o: sum((o[i] - centro[i]) * cima[i] for i in range(3))  # noqa: E731
    assert altura(olho_antes) > 0 and altura(olho) < 0  # foi pra baixo da caixa
    vista.grab()  # pinta sem erro vista de baixo (sem a sombra do chão)
    j.close()
