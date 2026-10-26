"""Testes da dobra 3D: plana = dieline, fechada = sólido C × L × A."""

from __future__ import annotations

import math

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
            if pp.painel.arte_de is not None:
                continue  # a outra metade da meia caixa: só existe no 3D, fora da faca
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

    # Bem de perto a face inteira não cabe na resolução pedida (lado máximo
    # em pixels): ganha uma textura de DETALHE só do pedaço visível, mais
    # nítida que a da face — era o borrão nos símbolos com zoom.
    vista._zoom = 40.0
    for _ in range(2):
        vista.grab()
        vista._gerar_texturas_pendentes()
    base = vista.textura_do_painel("frente")
    detalhe = vista._detalhes.get("frente")
    assert detalhe is not None and detalhe[0] is not None
    assert detalhe[1] > base[1] * 1.5
    assert detalhe[2].width() < base[2].width() / 3  # só o pedaço na tela
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


def test_foto_do_3d_sai_com_a_arte_mesmo_com_a_aba_fechada():
    """A arte das faces é gerada depois de pintar: a foto (folha de
    aprovação, Salvar imagem) pinta de novo quando acabou de gerar."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication

    from gerador_layout.models import CorImpressao
    from gerador_layout.ui.main_window import JanelaPrincipal
    from gerador_layout.ui.mockup_formas import ElementoRetangulo

    QApplication.instance() or QApplication([])
    j = JanelaPrincipal()
    for p in j._paineis_disponiveis():
        if not p.eh_aba:
            el = ElementoRetangulo(largura=p.largura * 0.6, altura=p.altura * 0.6, preenchido=True,
                                   cor_tinta=CorImpressao("VERMELHO", 255, 0, 0))
            j.canvas.adicionar_elemento_mockup(el, QPointF(p.x1 + p.largura * 0.2, p.y1 + p.altura * 0.2))
    imagem = j._imagem_3d_montada()  # aba 3D nunca aberta
    vermelhos = sum(
        1 for x in range(0, imagem.width(), 6) for y in range(0, imagem.height(), 6)
        if (c := imagem.pixelColor(x, y)).red() > 200 and c.green() < 60 and c.blue() < 60
    )
    assert vermelhos > 50
    j.close()


@pytest.mark.parametrize("tipo", _ENVOLTORIOS_FECHADOS)
def test_envoltorio_tem_o_prolongamento_dos_cantos_e_ele_fica_dentro_da_caixa(tipo):
    """Na faca, a coluna do canto vai da tampa até a aba de fechamento (vinco
    na altura da parede, corte-serra separando da tampa). O 3D mostrava um
    degrau no lugar desses pedaços."""
    modelo, layout = _modelo(tipo)
    xs = [sum(layout.segmentos_impressora[:i]) for i in range(6)]
    ys = [sum(layout.segmentos_riscador[:i]) for i in range(6)]
    for xa, xb in ((xs[1], xs[2]), (xs[3], xs[4])):
        for ya, yb in ((ys[0], ys[1]), (ys[4], ys[5])):
            cx, cy = (xa + xb) / 2, (ya + yb) / 2
            assert any(p.x1 < cx < p.x2 and p.y1 < cy < p.y2 for p in modelo.paineis), (cx, cy)
    fechada = posicionar(modelo, 1.0)
    paredes = [p for p in fechada if p.painel.id in {"base", "lateral1", "lateral2", "parede_sup", "parede_inf"}]
    mn, mx = caixa_envolvente(paredes)
    for pp in fechada:
        if pp.painel.id.endswith("_tampa") and pp.painel.id.startswith("canto"):
            for x, y in pp.painel.cantos:
                ponto = pp.ponto(x, y)
                for i in range(3):
                    # dobra pra dentro; só a folga de 3° do canto (que entra inclinado) sobra
                    sobra = A * math.sin(math.radians(3.0)) + 1.0
                    assert mn[i] - sobra <= ponto[i] <= mx[i] + sobra


def test_cor_do_papelao_vem_das_configuracoes():
    from PySide6.QtGui import QColor

    from gerador_layout.ui import configuracoes
    from gerador_layout.ui.visualizacao_3d import cores_papelao

    assert configuracoes.cor_papelao_3d() == "#D4B07C"  # mais claro que o kraft da marca
    configuracoes.definir_cor_papelao_3d("#E0C090")
    fora, dentro, borda = cores_papelao()
    assert fora == QColor("#E0C090") and dentro.lightness() > fora.lightness() > borda.lightness()
    configuracoes.definir_cor_papelao_3d("não é cor")
    assert configuracoes.cor_papelao_3d() == "#D4B07C"
    configuracoes.restaurar_padroes()
    assert configuracoes.cor_papelao_3d() == "#D4B07C"


@pytest.mark.parametrize("medidas", [(30, 30, 80), (54, 54, 38), (136, 16, 9), (193.5, 28.2, 8)])
def test_sombra_no_chao_e_inteira_na_foto(medidas):
    """Caixa alta: a sombra ficava no meio da altura e larga demais, cortada
    reta nas bordas da foto."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from gerador_layout.ui.main_window import JanelaPrincipal

    QApplication.instance() or QApplication([])
    j = JanelaPrincipal()
    j.combo_tipo.setCurrentIndex(j.combo_tipo.findData(TipoCaixa.MALETA_NORMAL))
    j.spin_comprimento.setValue(medidas[0])
    j.spin_largura.setValue(medidas[1])
    j.spin_altura.setValue(medidas[2])
    vista = j.visualizacao_3d.vista
    assert vista._meia_altura_montada == pytest.approx(medidas[2] / 2, rel=0.05)
    img = j._imagem_3d_montada()
    w, h = img.width(), img.height()
    borda = [(x, 0) for x in range(0, w, 9)] + [(x, h - 1) for x in range(0, w, 9)]
    borda += [(0, y) for y in range(0, h, 9)] + [(w - 1, y) for y in range(0, h, 9)]
    assert max(255 - img.pixelColor(x, y).red() for x, y in borda) <= 12  # nada de sombra cortada na borda
    # a caixa ocupa a foto (antes, numa caixa comprida, a sombra redonda abria
    # o recorte e a caixa ficava pequena na folha de aprovação)
    xs = [x for y in range(0, h, 6) for x in range(0, w, 6)
          if img.pixelColor(x, y).red() < 220 and abs(img.pixelColor(x, y).red() - img.pixelColor(x, y).blue()) > 25]
    ys = [y for y in range(0, h, 6) for x in range(0, w, 6)
          if img.pixelColor(x, y).red() < 220 and abs(img.pixelColor(x, y).red() - img.pixelColor(x, y).blue()) > 25]
    assert max((max(xs) - min(xs)) / w, (max(ys) - min(ys)) / h) > 0.7
    j.close()
