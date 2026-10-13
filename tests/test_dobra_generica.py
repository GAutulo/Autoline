"""Dobra 3D de qualquer faca (ArtiosCAD "Converter em 3D")."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gerador_layout.dobra3d import caixa_envolvente, posicionar  # noqa: E402
from gerador_layout.dobra_generica import achar_faces, montar_modelo_generico  # noqa: E402
from gerador_layout.layout_service import ServicoLayoutCaixa  # noqa: E402
from gerador_layout.models import LinhaDesenho, MedidasCaixa, TipoCaixa, TipoLinha  # noqa: E402

C, V = TipoLinha.CORTE, TipoLinha.VINCO


def _dimensoes(modelo, t=1.0):
    mn, mx = caixa_envolvente(posicionar(modelo, t))
    return sorted(round(mx[i] - mn[i], 3) for i in range(3))


def _cruz_de_cubo(lado=100.0):
    """Planificação em cruz de um cubo: bordas externas cortam, internas vincam."""
    quadrados = [(1, 0), (0, 1), (1, 1), (2, 1), (3, 1), (1, 2)]
    contagem: dict = {}
    for cx, cy in quadrados:
        x, y = cx * lado, cy * lado
        for a, b in (((x, y), (x + lado, y)), ((x + lado, y), (x + lado, y + lado)), ((x, y + lado), (x + lado, y + lado)), ((x, y), (x, y + lado))):
            contagem[(a, b)] = contagem.get((a, b), 0) + 1
    return [LinhaDesenho(a[0], a[1], b[0], b[1], V if n > 1 else C) for (a, b), n in contagem.items()]


@pytest.mark.parametrize("tipo", list(TipoCaixa))
def test_tipos_prontos_dobram_na_caixa_certa(tipo):
    layout = ServicoLayoutCaixa().calcular(MedidasCaixa(tipo=tipo, comprimento=300, largura=200, altura=150))
    modelo = montar_modelo_generico(layout.linhas)
    assert _dimensoes(modelo, 0.0)[0] == pytest.approx(0.0)  # plana
    assert _dimensoes(modelo) == pytest.approx([150.0, 200.0, 300.0], abs=1.5)
    # Nenhuma "lasca" de fenda de serra (1 mm) virou face.
    assert min(f.area for f in achar_faces(layout.linhas).faces) >= 15.0


def test_maleta_faces_e_dobradicas():
    layout = ServicoLayoutCaixa().calcular(MedidasCaixa(tipo=TipoCaixa.MALETA_NORMAL, comprimento=300, largura=200, altura=150))
    resultado = achar_faces(layout.linhas)
    assert len(resultado.faces) == 13  # aba + 4 paredes + 4 abas em cima + 4 embaixo
    assert len(resultado.dobradicas) == 12
    base = [p for p in montar_modelo_generico(layout.linhas).paineis if p.pai is None][0]
    assert (base.x2 - base.x1, base.y2 - base.y1) == pytest.approx((300.0, 150.0))  # a frente (C × A)


def test_cruz_vira_cubo_e_base_e_o_meio():
    modelo = montar_modelo_generico(_cruz_de_cubo())
    assert len(modelo.paineis) == 6
    base = [p for p in modelo.paineis if p.pai is None][0]
    assert (base.x1, base.y1) == (100.0, 100.0)
    assert _dimensoes(modelo) == pytest.approx([100.0, 100.0, 100.0])


def test_janela_vazada_vira_furo_e_corte_solto_e_ignorado():
    linhas = _cruz_de_cubo()
    hexagono = [(150 + 25 * math.cos(math.radians(60 * k)), 150 + 25 * math.sin(math.radians(60 * k))) for k in range(6)]
    linhas += [LinhaDesenho(*hexagono[k], *hexagono[(k + 1) % 6], C) for k in range(6)]
    linhas.append(LinhaDesenho(250, 120, 250, 160, C))  # corte que entra e para (não fecha face)
    modelo = montar_modelo_generico(linhas)
    base = [p for p in modelo.paineis if p.pai is None][0]
    assert len(modelo.paineis) == 6 and len(base.furos) == 1 and len(base.furos[0]) == 6


def test_angulos_por_vinco_e_face_base_escolhida():
    linhas = _cruz_de_cubo()
    plana = montar_modelo_generico(linhas, angulos={i: 0.0 for i, l in enumerate(linhas) if l.tipo == V})
    assert _dimensoes(plana)[0] == pytest.approx(0.0)
    # -90 dobra pro outro lado: a aba de cima (100..200 × 0..100) vai pra -z.
    vinco_de_cima = next(i for i, l in enumerate(linhas) if l.tipo == V and l.y1 == l.y2 == 100.0 and l.x1 == 100.0)
    modelo = montar_modelo_generico(linhas, angulos={vinco_de_cima: -90.0})
    aba = next(pp for pp in posicionar(modelo, 1.0) if pp.painel.y1 == 0.0)
    assert min(pp_z for pp_z in (aba.ponto(x, y)[2] for x, y in aba.painel.cantos)) == pytest.approx(-100.0)
    outra = montar_modelo_generico(linhas, base=0)
    assert [p for p in outra.paineis if p.pai is None][0].id == "face_0"


def test_faca_editada_usa_a_dobra_generica_no_3d():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from gerador_layout.ui.main_window import JanelaPrincipal

    QApplication.instance() or QApplication([])
    j = JanelaPrincipal()
    canvas = j.canvas
    linhas = canvas._linhas_para_editar()
    linhas.append(LinhaDesenho(4, 120, 60, 120, TipoLinha.CORTE))  # um corte solto qualquer
    canvas._aplicar_faca("teste", linhas)
    assert canvas.faca_editada
    j.abas_tela.setCurrentIndex(2)
    modelo = j.visualizacao_3d.vista._modelo
    assert modelo.descricao == "Faca editada" and not modelo.vazio
    assert not modelo.solido_fechado
    j.visualizacao_3d.vista.resize(600, 400)
    j.visualizacao_3d.vista.grab()  # desenha faces em polígono sem erro
    canvas.descartar_edicoes_faca()
    j.abas_tela.setCurrentIndex(0)
    j.abas_tela.setCurrentIndex(2)
    assert j.visualizacao_3d.vista._modelo.descricao == "Maleta normal"
    j.close()


def _janela():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from gerador_layout.ui.main_window import JanelaPrincipal

    QApplication.instance() or QApplication([])
    j = JanelaPrincipal()
    j.resize(1300, 850)
    return j


def test_faca_em_branco_desenhada_vira_3d_com_angulo_e_base():
    j = _janela()
    j._nova_faca_em_branco()
    canvas = j.canvas
    assert canvas.faca_editada and canvas.linhas_faca() == []
    assert j._acoes_faca["corte"].isChecked()
    j.abas_tela.setCurrentIndex(2)
    assert j.visualizacao_3d.vista._modelo.vazio
    j.abas_tela.setCurrentIndex(0)
    canvas._aplicar_faca("cubo", _cruz_de_cubo())
    j.abas_tela.setCurrentIndex(2)
    vista = j.visualizacao_3d.vista
    assert len(vista._modelo.paineis) == 6
    assert j.visualizacao_3d._botoes_modo["dobra"].isEnabled()

    # Modo "Ângulo da dobra": clicar num vinco alterna 90 → -90 → 0.
    j.visualizacao_3d._botoes_modo["dobra"].click()
    vista.resize(700, 500)
    vista.grab()
    a, b, linha, angulo = vista._dobradicas_tela[0]
    assert angulo == 90.0
    vista._clique((a + b) / 2)
    assert j._angulos_dobra[linha] == -90.0
    vista.grab()  # a dobradiça pode ter mudado de lugar na tela: procura de novo
    a, b, _l, angulo = next(item for item in vista._dobradicas_tela if item[2] == linha)
    assert angulo == -90.0
    vista._clique((a + b) / 2)
    assert j._angulos_dobra[linha] == 0.0
    j.visualizacao_3d.campo_angulo.setValue(45.0)  # valor exato pelo campo
    assert j._angulos_dobra[linha] == 45.0
    assert next(p for p in vista._modelo.paineis if p.linha_origem == linha).angulo_fechado == 45.0

    # Modo "Face base": clicar numa face a deixa parada.
    j.visualizacao_3d._botoes_modo["base"].click()
    vista.grab()
    _prof, poligono, painel_id = min(vista._faces_tela, key=lambda item: item[0])  # a da frente
    vista._clique(poligono.boundingRect().center())
    assert [p.id for p in vista._modelo.paineis if p.pai is None] == [painel_id]
    j.close()


def test_ferramentas_de_dobra_desligadas_no_modelo_pronto():
    j = _janela()
    j.abas_tela.setCurrentIndex(2)
    assert not j.visualizacao_3d._botoes_modo["dobra"].isEnabled()
    assert not j.visualizacao_3d.aviso_dobras.isHidden()
    j.close()
