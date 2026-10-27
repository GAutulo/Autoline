"""Revisão de interface: seleção visível, cadeado com dois estados, nome
das cores legível no tema."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtGui import QColor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QApplication.instance() or QApplication([])

from gerador_layout.ui import estilo  # noqa: E402


def _contraste(a, b):
    def lum(c):
        def canal(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

        return 0.2126 * canal(c[0]) + 0.7152 * canal(c[1]) + 0.0722 * canal(c[2])

    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _rgb(hexa):
    return tuple(int(hexa[i : i + 2], 16) for i in (1, 3, 5))


def test_cores_legiveis_nos_dois_temas():
    for fundo in ("#1E1A16", "#EAE1CC"):  # escuro e claro
        for cor in ((0, 0, 0), (0, 0, 255), (255, 0, 255), (255, 230, 0), (0, 160, 227)):
            assert _contraste(estilo.cor_legivel_sobre(*cor, fundo=fundo), _rgb(fundo)) >= 3.0
    # cor que já lê bem fica como está (vermelho continua vermelho no claro)
    assert estilo.cor_legivel_sobre(200, 0, 0, fundo="#EAE1CC") == (200, 0, 0)


def test_selecao_destaca_do_campo_e_do_cartao():
    for paleta in (estilo._PALETA_CLARA, estilo._PALETA_ESCURA):
        selecao = _rgb(paleta["SELECAO"])
        assert _contraste(selecao, _rgb(paleta["CAMPO"])) >= 1.5
        assert _contraste(selecao, _rgb(paleta["CARTAO"])) >= 1.5
        assert _contraste(_rgb(paleta["TEXTO"]), selecao) >= 3.0  # texto selecionado legível
    assert "selection-background-color: {Cor.SELECAO}".replace("{Cor.SELECAO}", estilo.Cor.SELECAO) in estilo.FOLHA_DE_ESTILO


def test_cadeado_aberto_e_fechado():
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QToolButton

    from gerador_layout.ui.main_window import JanelaPrincipal
    from gerador_layout.ui.mockup_formas import ElementoRetangulo

    j = JanelaPrincipal()
    j.show()
    j.abas_tela.setCurrentIndex(1)
    el = ElementoRetangulo()
    j.canvas.adicionar_elemento_mockup(el, QPointF(100, 100))
    j.canvas.cena.clearSelection()
    el.setSelected(True)
    QApplication.processEvents()
    trava = next(b for b in j.painel_propriedades_mockup.findChildren(QToolButton) if "Propor" in b.toolTip())
    icone_aberto = trava.icon().pixmap(18, 18).toImage()
    assert not el.proporcao_travada and "livre" in trava.toolTip()
    trava.setChecked(True)
    assert el.proporcao_travada and "travada" in trava.toolTip()
    assert trava.icon().pixmap(18, 18).toImage() != icone_aberto  # outro desenho
    j.close()


def test_mais_tintas_e_tinta_criada_pelo_usuario(tmp_path):
    from gerador_layout.ui import configuracoes, projeto_arquivo
    from gerador_layout.ui.main_window import JanelaPrincipal

    configuracoes.definir_cores_personalizadas([])
    j = JanelaPrincipal()
    nomes = list(j._chips_cor)
    assert nomes[:8] == ["Preto", "Vermelho", "Azul", "Amarelo", "Verde", "Ciano", "Magenta", "Laranja"]  # as de antes
    assert {"Azul Escuro", "Verde Escuro", "Vinho", "Marrom", "Cinza", "Branco", "Dourado"} <= set(nomes)
    # criar uma tinta: entra marcada, vai pra legenda, pra paleta e pras próximas vezes
    assert j._nova_cor_personalizada("Pantone 286", (0, 51, 160))
    assert j._chips_cor["Pantone 286"][0].isChecked()
    assert any(c.nome == "PANTONE 286" for c in j._cores_impressao_ativas())
    assert ("Pantone 286", (0, 51, 160)) in configuracoes.cores_personalizadas()
    assert not j._nova_cor_personalizada("pantone 286", (1, 2, 3))  # nome repetido não duplica
    # o projeto leva o tom junto: abre noutro computador sem a tinta cadastrada
    destino = projeto_arquivo.salvar(j, tmp_path / "x.autoline")
    j.close()
    configuracoes.definir_cores_personalizadas([])
    k = JanelaPrincipal()
    assert "Pantone 286" not in k._chips_cor
    projeto_arquivo.aplicar_na_janela(k, projeto_arquivo.ler(destino))
    assert k._chips_cor["Pantone 286"][0].isChecked() and k._chips_cor["Pantone 286"][1] == (0, 51, 160)
    # tirar a tinta criada
    assert k._remover_cor_personalizada("Pantone 286", confirmar=lambda: True)
    assert "Pantone 286" not in k._chips_cor
    k.close()
    configuracoes.definir_cores_personalizadas([])


def test_barra_de_propriedades_nao_alarga_a_janela_e_cor_embaixo():
    from PySide6.QtCore import QPointF

    from gerador_layout.ui.main_window import JanelaPrincipal
    from gerador_layout.ui.mockup_checklist import ElementoChecklistCores
    from gerador_layout.ui.preview_canvas import FerramentaMockup

    j = JanelaPrincipal()
    j.resize(1366, 700)
    j.show()
    j.abas_tela.setCurrentIndex(1)
    el = ElementoChecklistCores(["20 UN.", "30 UN."])
    j.canvas.adicionar_elemento_mockup(el, QPointF(50, 50))
    j.canvas.cena.clearSelection()
    el.setSelected(True)
    for _ in range(6):
        QApplication.processEvents()
    # a barra não exige a largura toda (antes ~1730 px) e tem altura FIXA:
    # o fixo (posição/tamanho) não sai do lugar; o resto fica em abas
    barra = j.barra_propriedades_mockup
    assert j.minimumSizeHint().width() < 1366
    painel = j.painel_propriedades_mockup
    altura = painel.height()
    x_largura = painel._spins_geometria["largura"].mapTo(painel, painel._spins_geometria["largura"].rect().topLeft()).x()
    # Letra na linha de contexto; o resto em seções do inspetor (à direita)
    assert painel.nomes_secoes() == ["Espaçamento", "Quadro", "Posição"]
    assert painel.mostrar_aba("Quadro") and j._docks["propriedades"].isVisible()
    j.canvas.cena.clearSelection()
    QApplication.processEvents()
    assert painel.height() == altura and not painel._spins_geometria["largura"].isEnabled()
    assert painel._spins_geometria["largura"].mapTo(painel, painel._spins_geometria["largura"].rect().topLeft()).x() == x_largura
    el.setSelected(True)
    QApplication.processEvents()
    assert painel.nomes_secoes() == ["Espaçamento", "Quadro", "Posição"]
    assert barra.height() <= altura + 12
    # cor embaixo: amostras clicáveis com a lista de tintas, e o conta-gotas
    status = j.painel_status
    assert status.amostra_preenchimento.isVisible() and status.botao_conta_gotas.isVisible()
    menu = j._menu_cor_status(contorno=False, executar=False)
    acao = next(a for a in menu.actions() if a.text() == "Azul Escuro")
    acao.trigger()
    assert (el.cor_tinta.r, el.cor_tinta.g, el.cor_tinta.b) == (0, 40, 110)
    status.botao_conta_gotas.click()
    assert j.canvas._ferramenta == FerramentaMockup.CONTA_GOTAS
    j.abas_tela.setCurrentIndex(0)  # fora do Layout, os controles de cor somem
    assert not status.botao_conta_gotas.isVisible()
    j.close()


def test_conta_gotas_pega_a_tinta_do_objeto_clicado():
    """Como no CorelDRAW: seleciona o que vai receber, clica com o
    conta-gotas no que tem a cor. Funciona com tinta que nem está marcada."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest

    from gerador_layout.models import CorImpressao
    from gerador_layout.ui.main_window import JanelaPrincipal
    from gerador_layout.ui.mockup_formas import ElementoRetangulo
    from gerador_layout.ui.preview_canvas import FerramentaMockup

    j = JanelaPrincipal()
    j.resize(1200, 800)
    j.show()
    j.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    azul = CorImpressao(nome="AZUL ESCURO", r=0, g=40, b=110)
    fonte = ElementoRetangulo(largura=60, altura=40, cor_tinta=azul, preenchido=True)
    alvo = ElementoRetangulo(largura=60, altura=40, preenchido=True)
    j.canvas.adicionar_elemento_mockup(fonte, QPointF(100, 100))
    j.canvas.adicionar_elemento_mockup(alvo, QPointF(250, 100))
    assert not j._chips_cor["Azul Escuro"][0].isChecked()
    j.canvas.cena.clearSelection()
    alvo.setSelected(True)
    j.canvas.definir_ferramenta(FerramentaMockup.CONTA_GOTAS)
    QApplication.processEvents()
    ponto = j.canvas.mapFromScene(fonte.sceneBoundingRect().center())
    QTest.mouseClick(j.canvas.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
    assert (alvo.cor_tinta.r, alvo.cor_tinta.g, alvo.cor_tinta.b) == (0, 40, 110)
    assert j._chips_cor["Azul Escuro"][0].isChecked()  # a tinta usada entra na legenda
    assert j.canvas._ferramenta == FerramentaMockup.SELECIONAR
    # pixel solto (sem objeto): a tinta da lista mais parecida, mesmo não marcada
    j._ao_cor_amostrada(QColor(250, 115, 5))
    assert alvo.cor_tinta.nome == "LARANJA" and j._chips_cor["Laranja"][0].isChecked()
    j.close()


def test_cursor_da_ferramenta_e_campo_de_texto_legivel():
    from PySide6.QtCore import QPointF, Qt

    from gerador_layout.ui.main_window import JanelaPrincipal
    from gerador_layout.ui.mockup_formas import ElementoRetangulo
    from gerador_layout.ui.preview_canvas import FerramentaMockup, _cursor_da_ferramenta

    j = JanelaPrincipal()
    j.show()
    j.abas_tela.setCurrentIndex(1)
    for ferramenta in (FerramentaMockup.RETANGULO, FerramentaMockup.CONTA_GOTAS, FerramentaMockup.COTA_PARALELA):
        j.canvas.definir_ferramenta(ferramenta)
        cursor = j.canvas.viewport().cursor()
        assert cursor.shape() == Qt.CursorShape.BitmapCursor  # cursor próprio, com o desenho da ferramenta
        assert not cursor.pixmap().isNull()
    assert _cursor_da_ferramenta(FerramentaMockup.CONTA_GOTAS).hotSpot().x() < 8  # ponta do conta-gotas
    # passando por cima de um objeto com outra ferramenta: não impõe a seta dele
    el = ElementoRetangulo()
    j.canvas.adicionar_elemento_mockup(el, QPointF(50, 50))
    from PySide6.QtWidgets import QGraphicsSceneHoverEvent

    evento = QGraphicsSceneHoverEvent()
    evento.setPos(QPointF(5, 5))
    el.hoverMoveEvent(evento)
    assert not el.hasCursor()
    j.canvas.definir_ferramenta(FerramentaMockup.SELECIONAR)
    el.hoverMoveEvent(evento)
    assert el.hasCursor()
    j.close()
    # campos de texto com cor de texto do tema (no escuro sumiam)
    assert "QLineEdit" in estilo.FOLHA_DE_ESTILO.split("selection-background-color")[0]


def _janela_com_dois_retangulos():
    from PySide6.QtCore import QPointF

    from gerador_layout.ui.main_window import JanelaPrincipal
    from gerador_layout.ui.mockup_formas import ElementoRetangulo

    j = JanelaPrincipal()
    j.resize(1200, 800)
    j.show()
    j.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    a, b = ElementoRetangulo(largura=40, altura=30), ElementoRetangulo(largura=40, altura=30)
    j.canvas.adicionar_elemento_mockup(a, QPointF(100, 100))
    j.canvas.adicionar_elemento_mockup(b, QPointF(200, 100))
    return j, a, b


def test_grupo_como_no_corel_clique_pega_o_grupo_ctrl_pega_um():
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from gerador_layout.ui.mockup_itens import GrupoMockup

    j, a, b = _janela_com_dois_retangulos()
    j.canvas.cena.clearSelection()
    a.setSelected(True)
    b.setSelected(True)
    grupo = j.canvas.agrupar_selecionados()
    j.canvas.cena.clearSelection()
    QApplication.processEvents()
    vp = j.canvas.viewport()
    ponto = j.canvas.mapFromScene(a.sceneBoundingRect().center())
    # clique simples num objeto do grupo: seleciona o GRUPO
    QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
    assert grupo.isSelected() and not a.isSelected()
    # arrastar move os dois juntos
    b_antes = b.scenePos()
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)
    for k in range(1, 6):
        QTest.mouseMove(vp, ponto + QPoint(10 * k, 0))
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto + QPoint(50, 0))
    assert b.scenePos().x() > b_antes.x() + 5
    # Ctrl+clique: entra no grupo e pega só um
    j.canvas.cena.clearSelection()
    ponto = j.canvas.mapFromScene(a.sceneBoundingRect().center())
    QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, ponto)
    assert a.isSelected() and not grupo.isSelected() and isinstance(a.parentItem(), GrupoMockup)
    # seleção por retângulo não pega os de dentro
    j.canvas.cena.clearSelection()
    assert not a.flags() & a.GraphicsItemFlag.ItemIsSelectable
    # barra do grupo: desagrupar
    grupo.setSelected(True)
    QApplication.processEvents()
    j.painel_propriedades_mockup.desagrupar_solicitado()
    assert a.parentItem() is None and a.flags() & a.GraphicsItemFlag.ItemIsSelectable
    j.close()


def test_colar_no_mesmo_lugar_e_girado_sem_escorregar():
    import pytest
    from PySide6.QtCore import QPointF

    j, a, _b = _janela_com_dois_retangulos()
    a.setRotation(30)
    centro = a.mapToScene(QPointF(a.largura / 2, a.altura / 2))
    j.canvas.cena.clearSelection()
    a.setSelected(True)
    j.canvas.copiar_selecionados()
    colado = j.canvas.colar()[0]
    assert colado.rotation() == pytest.approx(30)
    centro_colado = colado.mapToScene(QPointF(colado.largura / 2, colado.altura / 2))
    assert (centro_colado.x(), centro_colado.y()) == pytest.approx((centro.x(), centro.y()))
    # mudar a largura de um girado pela barra: o centro não anda
    for largura in (41, 42, 43):
        a.definir_largura(largura)
        novo = a.mapToScene(QPointF(a.largura / 2, a.altura / 2))
        assert (novo.x(), novo.y()) == pytest.approx((centro.x(), centro.y()))
    j.close()


def test_alinhar_varios_usa_o_primeiro_selecionado():
    import pytest

    j, a, b = _janela_com_dois_retangulos()
    j.canvas.cena.clearSelection()
    b.setSelected(True)  # o primeiro selecionado é a referência
    a.setSelected(True)
    centro_b = b.retangulo_conteudo_cena().center()
    j.canvas.alinhar_selecionados("centro_h")
    j.canvas.alinhar_selecionados("centro_v")
    assert b.retangulo_conteudo_cena().center() == centro_b  # a referência não sai do lugar
    assert a.retangulo_conteudo_cena().center().x() == pytest.approx(centro_b.x())
    assert a.retangulo_conteudo_cena().center().y() == pytest.approx(centro_b.y())
    # objeto girado: alinha pela caixa que ele ocupa na tela
    a.setRotation(45)
    j.canvas.alinhar_selecionados("esquerda")
    assert a.retangulo_conteudo_cena().left() == pytest.approx(b.retangulo_conteudo_cena().left())
    j.close()


def test_conta_gotas_dentro_de_grupo_e_sem_selecao():
    """Pega a cor do objeto de dentro do grupo; aplica num grupo inteiro;
    sem nada selecionado, pega a cor e o próximo clique aplica (CorelDRAW)."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest

    from gerador_layout.models import CorImpressao
    from gerador_layout.ui.mockup_formas import ElementoRetangulo
    from gerador_layout.ui.preview_canvas import FerramentaMockup

    j, a, b = _janela_com_dois_retangulos()
    verde = CorImpressao(nome="VERDE", r=0, g=150, b=60)
    a.definir_cor_tinta(verde)
    a.definir_preenchido(True)
    j.canvas.cena.clearSelection()
    a.setSelected(True)
    b.setSelected(True)
    j.canvas.agrupar_selecionados()
    alvo = ElementoRetangulo(largura=40, altura=30, preenchido=True)
    j.canvas.adicionar_elemento_mockup(alvo, QPointF(100, 250))
    vp = j.canvas.viewport()

    def clicar(el):
        QApplication.processEvents()
        ponto = j.canvas.mapFromScene(el.sceneBoundingRect().center())
        QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ponto)

    # alvo selecionado, conta-gotas no objeto verde DENTRO do grupo
    j.canvas.cena.clearSelection()
    alvo.setSelected(True)
    j.canvas.definir_ferramenta(FerramentaMockup.CONTA_GOTAS)
    clicar(a)
    assert alvo.cor_tinta.nome == "VERDE"
    # sem nada selecionado: pega no alvo (verde), depois clica no b (dentro do grupo) -> o grupo todo
    j.canvas.cena.clearSelection()
    b.definir_cor_tinta(CorImpressao(nome="PRETO", r=0, g=0, b=0))
    a.definir_cor_tinta(CorImpressao(nome="PRETO", r=0, g=0, b=0))
    j.canvas.definir_ferramenta(FerramentaMockup.CONTA_GOTAS)
    clicar(alvo)
    assert j.canvas.tinta_carregada is not None
    clicar(b)
    assert a.cor_tinta.nome == "VERDE" and b.cor_tinta.nome == "VERDE"
    assert j.canvas.tinta_carregada is None
    j.canvas.pilha_desfazer.undo()
    assert a.cor_tinta.nome == "PRETO" and b.cor_tinta.nome == "PRETO"
    j.close()


def test_mensagem_longa_da_barra_de_status_corta_com_reticencias():
    from gerador_layout.ui.main_window import JanelaPrincipal

    j = JanelaPrincipal()
    j.resize(1800, 700)
    j.show()
    QApplication.processEvents()
    barra = j.statusBar()
    assert barra._area_mensagem().width() > 100
    frase = "Envoltório fechamento normal — com corte " * 6
    barra.showMessage(frase)
    QApplication.processEvents()
    visivel = barra._mensagem_visivel()
    assert visivel.endswith("…") and len(visivel) < len(frase)
    assert barra.currentMessage() == frase  # a frase inteira continua lá (dica)
    barra.showMessage("Curta")
    assert barra._mensagem_visivel() == "Curta"
    j.close()
