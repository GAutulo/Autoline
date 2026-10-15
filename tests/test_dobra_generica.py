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
    assert modelo.solido_fechado  # veio da maleta: fecha como ela (sem piscar nas abas)
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


def _referencia(tipo):
    from gerador_layout.dobra3d import montar_modelo

    layout = ServicoLayoutCaixa().calcular(MedidasCaixa(tipo=tipo, comprimento=300, largura=200, altura=150))
    return layout, montar_modelo(tipo, layout.segmentos_impressora, layout.segmentos_riscador)


def _posicoes(modelo, t=1.0):
    return sorted(
        tuple(round(c, 1) for c in pp.ponto(*pp.painel.ponto_interno))
        if pp.painel.ponto_interno
        else tuple(round(c, 1) for c in pp.ponto((pp.painel.x1 + pp.painel.x2) / 2, (pp.painel.y1 + pp.painel.y2) / 2))
        for pp in posicionar(modelo, t)
    )


@pytest.mark.parametrize("tipo", list(TipoCaixa))
def test_faca_editada_herda_o_fechamento_do_tipo(tipo):
    """Mexer no corte de uma aba não pode mudar como a caixa fecha: cada
    dobra herda o ângulo e a ordem de montagem do modelo calculado."""
    layout, referencia = _referencia(tipo)
    sem_mexer = montar_modelo_generico(layout.linhas, referencia=referencia)
    base = [p for p in sem_mexer.paineis if p.pai is None][0]
    raiz = [p for p in referencia.paineis if p.pai is None][0]
    assert (base.x1, base.y1, base.x2, base.y2) == pytest.approx((raiz.x1, raiz.y1, raiz.x2, raiz.y2))
    # mesmo ângulo e mesma janela de montagem em cada dobra que existe nos dois
    por_ref = {}
    for p in sem_mexer.paineis:
        if p.pai is None:
            continue
        x, y = p.ponto_interno
        dono = min(
            (r for r in referencia.paineis if r.x1 <= x <= r.x2 and r.y1 <= y <= r.y2),
            key=lambda r: (r.x2 - r.x1) * (r.y2 - r.y1),
            default=None,
        )
        if dono is None:
            continue  # pedaço que o modelo calculado não representa: dobra padrão
        por_ref[p.id] = dono
        assert p.angulo_fechado == pytest.approx(dono.angulo_fechado)
        assert (p.inicio, p.fim) == pytest.approx((dono.inicio, dono.fim))
    if len(por_ref) == len(sem_mexer.paineis) - 1:  # todo pedaço tem par no modelo
        assert _dimensoes(sem_mexer) == pytest.approx(_dimensoes(referencia), abs=2.0)


def test_mudar_corte_da_aba_nao_muda_o_fechamento():
    layout, referencia = _referencia(TipoCaixa.MALETA_NORMAL)
    antes = montar_modelo_generico(layout.linhas, referencia=referencia)
    # chanfra a ponta de um corte de aba (o "mudar o corte das abas" relatado)
    linhas = list(layout.linhas)
    i = max(
        (k for k, l in enumerate(linhas) if l.tipo == TipoLinha.CORTE and abs(l.y1 - l.y2) < 1e-6),
        key=lambda k: linhas[k].x2 - linhas[k].x1 if linhas[k].y1 < 1 else -1,
    )
    l = linhas[i]
    linhas[i] = LinhaDesenho(l.x1 + 5, l.y1, l.x2, l.y2, l.tipo)
    linhas.append(LinhaDesenho(l.x1, l.y1 + 5, l.x1 + 5, l.y1, l.tipo))
    depois = montar_modelo_generico(linhas, referencia=referencia)
    assert len(depois.paineis) == len(antes.paineis)
    angulos = lambda m: sorted(round(p.angulo_fechado, 3) for p in m.paineis if p.pai)  # noqa: E731
    assert angulos(depois) == angulos(antes)
    assert _dimensoes(depois) == pytest.approx(_dimensoes(antes), abs=2.0)


def test_vinco_novo_dobra_e_vinco_virado_corte_solta_a_aba():
    layout, referencia = _referencia(TipoCaixa.MALETA_NORMAL)
    antes = montar_modelo_generico(layout.linhas, referencia=referencia)
    linhas = list(layout.linhas)
    # vinco horizontal mais alto (aba de cima) vira corte: a aba solta some
    k = min((k for k, l in enumerate(linhas) if l.tipo == TipoLinha.VINCO and abs(l.y1 - l.y2) < 1e-6), key=lambda k: linhas[k].y1)
    cortado = list(linhas)
    l = cortado[k]
    cortado[k] = LinhaDesenho(l.x1, l.y1, l.x2, l.y2, TipoLinha.CORTE)
    sem_aba = montar_modelo_generico(cortado, referencia=referencia)
    assert len(sem_aba.paineis) < len(antes.paineis)
    # vinco novo no meio da face base: ela vira duas e a nova dobra fecha a 90°
    base = [p for p in antes.paineis if p.pai is None][0]
    meio = (base.y1 + base.y2) / 2
    com_vinco = linhas + [LinhaDesenho(base.x1, meio, base.x2, meio, TipoLinha.VINCO)]
    novo = montar_modelo_generico(com_vinco, referencia=referencia)
    assert len(novo.paineis) == len(antes.paineis) + 1
    nova = [p for p in novo.paineis if p.linha_origem == len(com_vinco) - 1]
    assert nova and nova[0].angulo_fechado == pytest.approx(90.0)


def test_3d_mover_a_vista_e_aproximar_onde_esta_o_mouse():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent, QWheelEvent
    from PySide6.QtWidgets import QApplication

    from gerador_layout.ui.main_window import JanelaPrincipal

    QApplication.instance() or QApplication([])
    j = JanelaPrincipal()
    j.abas_tela.setCurrentIndex(2)
    vista = j.visualizacao_3d.vista
    vista.resize(800, 600)

    def mouse(tipo, x, y, botao, botoes):
        p = QPointF(x, y)
        QApplication.sendEvent(vista, QMouseEvent(tipo, p, vista.mapToGlobal(p), botao, botoes, Qt.KeyboardModifier.NoModifier))

    meio = Qt.MouseButton.MiddleButton
    mouse(QEvent.Type.MouseButtonPress, 400, 300, meio, meio)
    mouse(QEvent.Type.MouseMove, 450, 280, Qt.MouseButton.NoButton, meio)
    mouse(QEvent.Type.MouseButtonRelease, 450, 280, meio, Qt.MouseButton.NoButton)
    assert vista._pan == QPointF(50, -20)
    yaw = vista._yaw_usuario
    assert yaw == 0.0  # mover não gira

    cursor = QPointF(600, 150)
    roda = QWheelEvent(cursor, vista.mapToGlobal(cursor), QPoint(), QPoint(0, 120), Qt.MouseButton.NoButton,
                       Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    antes = cursor - QPointF(400, 300) - vista._pan
    QApplication.sendEvent(vista, roda)
    depois = cursor - QPointF(400, 300) - vista._pan
    assert depois.x() == pytest.approx(antes.x() * 1.12) and depois.y() == pytest.approx(antes.y() * 1.12)
    vista.grab()
    vista.vista_inicial()
    assert vista._pan == QPointF(0, 0) and vista._zoom == 1.0


def test_espessura_do_papelao_no_3d():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from gerador_layout.estilos import Estilo
    from gerador_layout.estilos_catalogo import CATALOGO
    from gerador_layout.ui.main_window import JanelaPrincipal

    from gerador_layout.ui import configuracoes

    QApplication.instance() or QApplication([])
    configuracoes.definir_espessura_papelao_mm(0.0)  # outro teste pode ter deixado outra
    j = JanelaPrincipal()
    j.abas_tela.setCurrentIndex(2)
    vista = j.visualizacao_3d.vista
    vista.resize(800, 600)
    assert vista.espessura == 0.0  # padrão: folha fina, como antes
    j.visualizacao_3d.combo_papelao.activated.emit(3)  # escolher "Onda B" na lista
    assert vista.espessura == 3.0 and j.visualizacao_3d.campo_espessura.value() == 3.0
    vista._progresso = 0.5
    vista.grab()  # aberta: desenha as faixas da borda sem erro
    vista._progresso = 1.0
    vista.grab()
    j.visualizacao_3d.campo_espessura.setValue(2.2)  # digitado: fora da lista
    assert vista.espessura == 2.2 and j.visualizacao_3d.combo_papelao.currentText() == "Personalizado"
    # fica guardado: uma janela nova abre com 2,2 mm
    assert configuracoes.espessura_papelao_mm() == pytest.approx(2.2)
    outra = JanelaPrincipal()
    assert outra.visualizacao_3d.vista.espessura == pytest.approx(2.2)
    outra.close()
    # estilo com E = 4 mm: o 3D passa a mostrar Onda C
    estilo = next(Estilo(d) for d in CATALOGO if d["codigo"] == "FEFCO 0201")
    valores = {"C": 300, "L": 200, "A": 150, "E": 4, "G": 30}
    j.aplicar_estilo(estilo, valores, estilo.gerar(valores))
    assert vista.espessura == 4.0 and "Onda C" in j.visualizacao_3d.combo_papelao.currentText()


def test_giro_sozinho_desligado_por_padrao_e_respeita_o_tempo_do_quadro():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from gerador_layout.ui import configuracoes
    from gerador_layout.ui.main_window import JanelaPrincipal

    QApplication.instance() or QApplication([])
    configuracoes.definir_giro_automatico_3d(False)
    j = JanelaPrincipal()
    j.show()
    j.abas_tela.setCurrentIndex(2)
    QApplication.processEvents()
    vista = j.visualizacao_3d.vista
    assert not vista.girar_sozinho and not vista._timer_giro.isActive()  # parado: app livre
    j.visualizacao_3d.botao_girar.setChecked(True)
    assert vista._timer_giro.isActive() and configuracoes.giro_automatico_3d()
    vista._ultimo_quadro_ms = 60.0  # quadro pesado: espera o dobro antes do próximo
    vista._passo_giro()
    assert vista._timer_giro.interval() == 120
    j.visualizacao_3d.botao_girar.setChecked(False)
    assert not vista._timer_giro.isActive()
    j.close()


def test_ondas_do_papelao_na_borda():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor, QImage, QPainter, QPolygonF
    from PySide6.QtWidgets import QApplication

    from gerador_layout.ui.visualizacao_3d import VistaCaixa3D, miolo_do_papelao

    QApplication.instance() or QApplication([])
    assert miolo_do_papelao(0.0) == () and miolo_do_papelao(0.5) == ()  # fino e cartão: sem onda
    assert miolo_do_papelao(3.0) == (6.5,)  # onda B: uma ondulação
    assert miolo_do_papelao(7.0) == (6.5, 8.0)  # onda dupla BC: duas
    assert len(miolo_do_papelao(2.2)) == 1 and len(miolo_do_papelao(6.0)) == 2  # digitado

    vista = VistaCaixa3D()
    quad = QPolygonF([QPointF(10, 10), QPointF(890, 10), QPointF(890, 90), QPointF(10, 90)])

    def desenhar(mm, atravessado, quad=quad):
        img = QImage(900, 100, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        p = QPainter(img)
        vista._desenhar_miolo(p, quad, (0.0, 60.0, mm, miolo_do_papelao(mm), atravessado), QColor(150, 110, 60))
        p.end()
        # cores na coluna do meio: a onda cruza a faixa em alturas diferentes
        return {img.pixel(x, y) for x in range(200, 700, 7) for y in range(20, 80)}

    assert len(desenhar(3.0, True)) > len(desenhar(3.0, False))  # a onda só no corte atravessado
    longe = QPolygonF([QPointF(10, 10), QPointF(890, 10), QPointF(890, 12), QPointF(10, 12)])
    assert len(desenhar(7.0, True, longe)) <= 1  # faixa de 2 px: nada de camada
