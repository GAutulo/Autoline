"""Cinta: uma medida só na impressora (largura total), faixas só no
riscador, recuo opcional dos dois lados em faixas escolhidas e furos de
pega (3 lados de corte + 1 de vinco) em qualquer faixa."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gerador_layout.dobra3d import montar_modelo  # noqa: E402
from gerador_layout.geometria_faca import e_arco  # noqa: E402
from gerador_layout.layout_service import ServicoLayoutCaixa  # noqa: E402
from gerador_layout.models import FuroCinta, MedidasCaixa, TipoCaixa, TipoLinha  # noqa: E402
from gerador_layout.paineis import calcular_paineis  # noqa: E402


def _cinta(largura=120.0, faixas=(30.0, 2.0, 25.0, 30.0), recuo=0.0, recuadas=(), furos=()):
    riscador = list(faixas) + [0.0] * (5 - len(faixas))
    medidas = MedidasCaixa(
        tipo=TipoCaixa.CINTA,
        comprimento=largura,
        altura=40.0,
        impressora_aba=0.0,
        impressora_largura_1=recuo,
        riscador_superior=riscador[0],
        riscador_centro=riscador[1],
        riscador_inferior=riscador[2],
        riscador_parte_4=riscador[3],
        riscador_parte_5=riscador[4],
        faixas_recuadas=tuple(recuadas),
        furos=list(furos),
    )
    return ServicoLayoutCaixa().calcular(medidas)


def _horizontais(layout, tipo, y):
    return sorted(
        (min(l.x1, l.x2), max(l.x1, l.x2))
        for l in layout.linhas
        if l.tipo == tipo and not e_arco(l) and l.y1 == pytest.approx(y) and l.y2 == pytest.approx(y)
    )


def _verticais(layout, tipo, x):
    return sorted(
        (min(l.y1, l.y2), max(l.y1, l.y2))
        for l in layout.linhas
        if l.tipo == tipo and not e_arco(l) and l.x1 == pytest.approx(x) and l.x2 == pytest.approx(x)
    )


def test_uma_medida_na_impressora_e_faixas_no_riscador():
    layout = _cinta()
    assert layout.largura_total == 120
    assert layout.altura_total == 30 + 2 + 25 + 30
    assert layout.segmentos_impressora == [120.0, 0.0]  # total | recuo
    assert layout.segmentos_riscador == [30.0, 2.0, 25.0, 30.0]
    # Vincos só no riscador: horizontais, de lado a lado, entre as faixas.
    for y in (30, 32, 57):
        assert _horizontais(layout, TipoLinha.VINCO, y) == [(0, 120)]
    assert not any(l.tipo == TipoLinha.VINCO and l.x1 != l.x2 and l.y1 != l.y2 for l in layout.linhas)
    # Contorno de corte: o retângulo da chapa.
    assert _horizontais(layout, TipoLinha.CORTE, 0) == [(0, 120)]
    assert _horizontais(layout, TipoLinha.CORTE, 87) == [(0, 120)]
    assert _verticais(layout, TipoLinha.CORTE, 0) == [(0, 87)]
    assert _verticais(layout, TipoLinha.CORTE, 120) == [(0, 87)]


def test_sem_faixas_digitadas_usa_a_altura_como_uma_faixa():
    layout = _cinta(faixas=())
    assert layout.segmentos_riscador == [40.0]
    assert layout.altura_total == 40


def test_recuo_dos_dois_lados_nas_faixas_escolhidas():
    layout = _cinta(recuo=10.0, recuadas=(2, 3))
    assert layout.segmentos_impressora == [120.0, 10.0]
    # Faixas 2 e 3 (y 30 → 57) entram 10 mm de cada lado.
    assert _verticais(layout, TipoLinha.CORTE, 10) == [(30, 57)]
    assert _verticais(layout, TipoLinha.CORTE, 110) == [(30, 57)]
    assert _verticais(layout, TipoLinha.CORTE, 0) == [(0, 30), (57, 87)]
    # Onde a largura muda, o degrau é corte e o vinco fica só na parte em comum.
    assert _horizontais(layout, TipoLinha.CORTE, 30) == [(0, 10), (110, 120)]
    assert _horizontais(layout, TipoLinha.VINCO, 30) == [(10, 110)]
    assert _horizontais(layout, TipoLinha.VINCO, 32) == [(10, 110)]  # entre duas recuadas
    assert _horizontais(layout, TipoLinha.CORTE, 57) == [(0, 10), (110, 120)]


def test_recuo_zero_ignora_as_faixas_marcadas():
    assert _verticais(_cinta(recuo=0.0, recuadas=(2,)), TipoLinha.CORTE, 0) == [(0, 87)]


def test_furo_de_pega_pela_distancia_ate_o_topo():
    # Faixa 3 (y 32 → 57, meio em 44,5), 45 mm da borda direita até o topo
    # (lado curvo); o vinco fica no lado voltado para a borda.
    furo = FuroCinta(faixa=3, borda="direita", distancia=45.0, largura=8.0, altura=9.0, raio=1.0)
    layout = _cinta(furos=[furo])
    topo, vinco = 120 - 45, 120 - 45 + 8
    assert _verticais(layout, TipoLinha.VINCO, vinco) == [(40, 49)]
    assert _verticais(layout, TipoLinha.CORTE, topo) == [(41, 48)]  # entre os arcos
    assert _horizontais(layout, TipoLinha.CORTE, 40) == [(topo + 1, vinco)]
    assert _horizontais(layout, TipoLinha.CORTE, 49) == [(topo + 1, vinco)]
    arcos = [l for l in layout.linhas if e_arco(l)]
    assert len(arcos) == 2 and all(l.tipo == TipoLinha.CORTE for l in arcos)


def test_furo_pela_borda_esquerda():
    furo = FuroCinta(faixa=1, borda="esquerda", distancia=30.0, largura=8.0, altura=10.0, raio=0.0)
    layout = _cinta(furos=[furo])
    assert _verticais(layout, TipoLinha.VINCO, 22) == [(10, 20)]  # vinco voltado para a esquerda
    assert _verticais(layout, TipoLinha.CORTE, 30) == [(10, 20)]
    assert not any(e_arco(l) for l in layout.linhas)


def test_furo_em_faixa_que_nao_existe_e_ignorado():
    furo = FuroCinta(faixa=5, borda="direita", distancia=45.0, largura=8.0, altura=9.0)
    assert len(_cinta(furos=[furo]).linhas) == len(_cinta().linhas)


def test_faces_sao_as_faixas_com_o_recuo():
    layout = _cinta(recuo=10.0, recuadas=(2,))
    assert layout.faixas_recuadas == (2,)
    paineis = calcular_paineis(
        TipoCaixa.CINTA, layout.segmentos_impressora, layout.segmentos_riscador, faixas_recuadas=layout.faixas_recuadas
    )
    assert [p.nome for p in paineis] == ["Faixa 1", "Faixa 2", "Faixa 3", "Faixa 4"]
    faixa2 = paineis[1]
    assert (faixa2.x1, faixa2.x2, faixa2.y1, faixa2.y2) == (10, 110, 30, 32)


def test_3d_da_cinta_fica_vazio_por_enquanto():
    layout = _cinta()
    assert montar_modelo(TipoCaixa.CINTA, layout.segmentos_impressora, layout.segmentos_riscador).vazio


# ── Tela ──────────────────────────────────────────────────────────────
def _janela_cinta():
    from PySide6.QtWidgets import QApplication

    from gerador_layout.ui.main_window import JanelaPrincipal

    QApplication.instance() or QApplication([])
    j = JanelaPrincipal()
    j.combo_tipo.setCurrentIndex(j.combo_tipo.findData(TipoCaixa.CINTA))
    j.spin_comprimento.setValue(120)
    j.linha_riscador.definir_valores_manuais([30, 2, 25, 30, 0])
    j.spin_recuo.setValue(10)
    j.checks_faixa_recuada[1].setChecked(True)  # faixa 2
    j.adicionar_furo_cinta(FuroCinta(faixa=3, borda="direita", distancia=45, largura=8, altura=9, raio=1))
    j._recalcular()
    return j


def test_cinta_na_tela_usa_as_faixas_o_recuo_e_os_furos():
    j = _janela_cinta()
    assert not j.grupo_cinta.isHidden()
    assert not j.spin_largura.isEnabled()  # L não vale na cinta
    medidas = j._obter_medidas()
    assert medidas.faixas_recuadas == (2,)
    assert medidas.furos == [FuroCinta(3, "direita", 45, 8, 9, 1)]
    paineis = j._paineis_disponiveis()
    assert [p.nome for p in paineis] == ["Faixa 1", "Faixa 2", "Faixa 3", "Faixa 4"]
    assert paineis[1].x1 == 10
    j.combo_tipo.setCurrentIndex(j.combo_tipo.findData(TipoCaixa.MALETA_NORMAL))
    assert j.grupo_cinta.isHidden() and j.spin_largura.isEnabled()
    j.close()


def test_recuar_so_liga_com_recuo_e_em_faixa_que_existe():
    from PySide6.QtWidgets import QApplication

    from gerador_layout.ui.main_window import JanelaPrincipal

    QApplication.instance() or QApplication([])
    j = JanelaPrincipal()
    j.combo_tipo.setCurrentIndex(j.combo_tipo.findData(TipoCaixa.CINTA))
    j.linha_riscador.definir_valores_manuais([30, 2, 25, 0, 0])
    j._recalcular()
    assert not any(c.isEnabled() for c in j.checks_faixa_recuada)  # sem recuo digitado
    j.spin_recuo.setValue(10)
    assert [c.isEnabled() for c in j.checks_faixa_recuada] == [True, True, True, False, False]
    j.checks_faixa_recuada[1].setChecked(True)
    assert j.canvas.layout_atual.faixas_recuadas == (2,)  # marcar já recorta
    j.close()


def test_cinta_volta_igual_do_projeto(tmp_path):
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = _janela_cinta()
    assert j._gravar_projeto(str(tmp_path / "riobras"))
    caminho = tmp_path / "riobras.autoline"
    j.close()
    outra = JanelaPrincipal()
    assert outra.abrir_projeto(str(caminho))
    medidas = outra._obter_medidas()
    assert medidas.tipo == TipoCaixa.CINTA
    assert medidas.faixas_recuadas == (2,)
    assert outra.spin_recuo.value() == 10
    assert medidas.furos == [FuroCinta(3, "direita", 45, 8, 9, 1)]
    assert outra.canvas.layout_atual.segmentos_riscador == [30, 2, 25, 30]
    outra.close()


def test_cinta_no_inicio():
    from PySide6.QtWidgets import QApplication

    from gerador_layout.ui.main_window import JanelaPrincipal

    QApplication.instance() or QApplication([])
    j = JanelaPrincipal()
    j.mostrar_inicio()
    j.tela_inicio.cartoes["Cinta"].click()
    assert j.tela_inicio.tipo_escolhido == TipoCaixa.CINTA
    j.close()


def test_folha_de_aprovacao_da_cinta_mostra_largura_por_altura(tmp_path):
    j = _janela_cinta()
    vistos = {}

    def preencher(janela):
        vistos["medidas"] = janela.campo_medidas.text()
        vistos["tipo"] = janela.campo_tipo.text()
        janela.check_3d.setChecked(False)  # a cinta ainda não tem 3D
        return True

    assert j.gerar_folha_aprovacao(str(tmp_path / "folha.pdf"), dialogo=preencher, abrir=False)
    assert vistos == {"medidas": "1200X870", "tipo": "CINTA"}  # medida real (× 10)
    j.close()


# ── Casos de borda (revisão do ECC) ───────────────────────────────────
def test_recuo_impossivel_e_ignorado_na_faca_e_nas_faces():
    layout = _cinta(largura=4.0, recuo=70.0, recuadas=(1,))
    assert layout.segmentos_impressora == [4.0, 0.0] and layout.faixas_recuadas == ()
    paineis = calcular_paineis(TipoCaixa.CINTA, layout.segmentos_impressora, layout.segmentos_riscador)
    assert all(p.largura > 0 for p in paineis)


def test_furo_fora_do_material_nao_e_desenhado():
    sem = len(_cinta(recuo=10.0, recuadas=(1,)).linhas)
    fora = [
        FuroCinta(faixa=1, borda="esquerda", distancia=3.0, largura=8.0, altura=9.0),  # sai da chapa
        FuroCinta(faixa=1, borda="direita", distancia=5.0, largura=2.0, altura=9.0),  # cai no recuo
        FuroCinta(faixa=1, borda="direita", distancia=45.0, largura=8.0, altura=40.0),  # mais alto que a faixa
    ]
    layout = _cinta(recuo=10.0, recuadas=(1,), furos=fora)
    assert len(layout.linhas) == sem
    assert layout.furos_ignorados == (1, 2, 3)


def test_faixa_vazia_no_meio_mantem_o_numero_das_outras():
    furo = FuroCinta(faixa=3, borda="direita", distancia=45.0, largura=8.0, altura=10.0)
    layout = _cinta(faixas=(10.0, 0.0, 20.0), recuo=5.0, recuadas=(3,), furos=[furo])
    assert layout.segmentos_riscador == [10.0, 0.0, 20.0]
    assert layout.altura_total == 30
    assert _verticais(layout, TipoLinha.CORTE, 5) == [(10, 30)]  # a "Faixa 3" é a recuada
    assert _verticais(layout, TipoLinha.VINCO, 120 - 45 + 8) == [(15, 25)]  # furo na faixa 3
    paineis = calcular_paineis(
        TipoCaixa.CINTA, layout.segmentos_impressora, layout.segmentos_riscador, faixas_recuadas=layout.faixas_recuadas
    )
    assert [p.nome for p in paineis] == ["Faixa 1", "Faixa 3"]


def test_raio_igual_a_largura_nao_gera_linha_vazia():
    furo = FuroCinta(faixa=1, borda="direita", distancia=45.0, largura=4.0, altura=10.0, raio=4.0)
    linhas = _cinta(furos=[furo]).linhas
    assert all(abs(l.x1 - l.x2) + abs(l.y1 - l.y2) > 1e-9 for l in linhas)


def test_projeto_com_furo_corrompido_abre_e_avisa(tmp_path):
    import json

    from gerador_layout.ui import projeto_arquivo
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = _janela_cinta()
    assert j._gravar_projeto(str(tmp_path / "x"))
    j.close()
    dados = projeto_arquivo.ler(str(tmp_path / "x.autoline"))
    dados["caixa"]["cinta"]["furos"].append([2, "direita"])  # incompleto
    dados["caixa"]["cinta"]["faixas_recuadas"].append("dois")
    outra = JanelaPrincipal()
    avisos = projeto_arquivo.aplicar_na_janela(outra, json.loads(json.dumps(dados)))
    assert outra._obter_medidas().furos == [FuroCinta(3, "direita", 45, 8, 9, 1)]
    assert any("furo" in a.lower() for a in avisos)
    outra.close()
