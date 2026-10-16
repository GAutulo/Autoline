"""Arquivo de projeto (.autoline): salvar e abrir devolve o mesmo modelo —
medidas, trechos digitados, cores, faca editada/estilo, objetos do Layout
(com logo e imagem embutidos) e o 3D."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QColor, QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

QApplication.instance() or QApplication([])

from gerador_layout.models import CorImpressao, LinhaDesenho, TipoCaixa, TipoLinha  # noqa: E402
from gerador_layout.ui import projeto_arquivo  # noqa: E402
from gerador_layout.ui.main_window import JanelaPrincipal  # noqa: E402
from gerador_layout.ui.mockup_checklist import ElementoChecklistCores  # noqa: E402
from gerador_layout.ui.mockup_curva import ElementoCurva, No, SubCaminho  # noqa: E402
from gerador_layout.ui.mockup_formas import ElementoPoligono, ElementoRetangulo  # noqa: E402
from gerador_layout.ui.mockup_imagem import ElementoImagem  # noqa: E402
from gerador_layout.ui.mockup_itens import GrupoMockup  # noqa: E402
from gerador_layout.ui.mockup_logo import ElementoLogoVetorial  # noqa: E402
from gerador_layout.ui.mockup_tabela import ElementoTabela  # noqa: E402
from gerador_layout.ui.mockup_texto import ElementoTexto  # noqa: E402

_CIANO = CorImpressao(nome="CIANO", r=0, g=160, b=227)
_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="20mm" height="10mm" viewBox="0 0 20 10"><rect width="20" height="10" fill="#ED3237"/></svg>'


def _montar(tmp_path) -> JanelaPrincipal:
    j = JanelaPrincipal()
    j.combo_tipo.setCurrentIndex(j.combo_tipo.findData(TipoCaixa.MALETA_NORMAL))
    j.spin_comprimento.setValue(605)
    j.spin_largura.setValue(400)
    j.spin_altura.setValue(300)
    j.linha_impressora._spins[0].setValue(42)  # aba digitada à mão
    j._chips_cor["Ciano"][0].setChecked(True)
    c = j.canvas
    texto = ElementoTexto("GABINETE FLORA", fonte_familia="Arial Black", cor_tinta=_CIANO)
    texto.aplicar_letra(2.0, 0.667)
    texto.definir_alinhamento("centro")
    c.adicionar_elemento_mockup(texto, QPointF(100, 120))
    texto.setRotation(15)
    checklist = ElementoChecklistCores(["OFF WHITE", "PRETO"], fonte_familia="Arial Black", largura_letra=0.667)
    checklist.definir_altura_letra_mm(2.0)
    c.adicionar_elemento_mockup(checklist, QPointF(200, 120))
    c.adicionar_elemento_mockup(ElementoTabela(linhas=2, colunas=2, celulas=[["a", "b"], ["c", "d"]]), QPointF(300, 120))
    nos = [No.canto(QPointF(0, 0)), No.canto(QPointF(10, 5)), No.canto(QPointF(0, 10))]
    c.adicionar_elemento_mockup(ElementoCurva([SubCaminho(nos, True)], _CIANO, True), QPointF(50, 50))
    # logo e imagem: o arquivo some depois de salvar — o projeto tem que bastar
    svg = tmp_path / "logo.svg"
    svg.write_text(_SVG, encoding="utf-8")
    logo = ElementoLogoVetorial(str(svg))
    logo.pintar_numa_tinta(_CIANO)
    c.adicionar_elemento_mockup(logo, QPointF(400, 100))
    png = tmp_path / "foto.png"
    img = QImage(8, 4, QImage.Format.Format_ARGB32)
    img.fill(QColor("green"))
    img.save(str(png))
    c.adicionar_elemento_mockup(ElementoImagem(str(png)), QPointF(450, 100))
    # grupo de dois objetos
    r1, r2 = ElementoRetangulo(cor_tinta=_CIANO, preenchido=True), ElementoPoligono(lados=6)
    c.adicionar_elemento_mockup(r1, QPointF(10, 200))
    c.adicionar_elemento_mockup(r2, QPointF(80, 230))
    c.cena.clearSelection()
    r1.setSelected(True)
    r2.setSelected(True)
    c.agrupar_selecionados()
    c.cena.clearSelection()
    svg.unlink()
    png.unlink()
    return j


def _resumo(j: JanelaPrincipal) -> dict:
    d = projeto_arquivo.estado_da_janela(j, com_arquivos=False)
    d.pop("arquivos")
    return json.loads(json.dumps(d), parse_float=lambda v: round(float(v), 3))


def test_salvar_e_abrir_devolve_o_mesmo_modelo(tmp_path):
    j = _montar(tmp_path)
    antes = _resumo(j)
    destino = projeto_arquivo.salvar(j, tmp_path / "Cliente X")
    assert destino.name == "Cliente X.autoline" and destino.is_file()
    dados = json.loads(destino.read_text(encoding="utf-8"))
    assert dados["formato"] == "autoline" and len(dados["arquivos"]) == 2  # logo + imagem dentro
    j.close()

    k = JanelaPrincipal()
    avisos = projeto_arquivo.aplicar_na_janela(k, projeto_arquivo.ler(destino))
    assert avisos == []
    depois = _resumo(k)
    assert depois["caixa"] == antes["caixa"] and depois["caixa"]["impressora"][0] == 42
    assert depois["cores"] == antes["cores"]
    assert len(depois["elementos"]) == len(antes["elementos"]) == 7
    assert depois["elementos"] == antes["elementos"]
    tipos = {type(e).__name__ for e in k.canvas.elementos_mockup}
    assert {"ElementoTexto", "ElementoLogoVetorial", "ElementoImagem", "GrupoMockup"} <= tipos
    texto = next(e for e in k.canvas.elementos_mockup if isinstance(e, ElementoTexto))
    assert texto.altura_letra_mm == pytest.approx(2.0) and texto.largura_letra == pytest.approx(0.667, abs=1e-3)
    assert texto.rotation() == pytest.approx(15)
    logo = next(e for e in k.canvas.elementos_mockup if isinstance(e, ElementoLogoVetorial))
    assert logo.tinta_unica.nome == "CIANO"
    grupo = next(e for e in k.canvas.elementos_mockup if isinstance(e, GrupoMockup))
    assert len(grupo.elementos) == 2
    assert k.canvas.pilha_desfazer.count() == 0  # abrir não vira passo de desfazer
    k.close()


def test_faca_editada_e_3d_voltam(tmp_path):
    j = JanelaPrincipal()
    linhas = [LinhaDesenho(0, 0, 100, 0, TipoLinha.CORTE), LinhaDesenho(0, 50, 100, 50, TipoLinha.VINCO, 0.0)]
    j.canvas._definir_linhas_editadas(linhas)
    j._angulos_dobra = {1: 120.0}
    j.visualizacao_3d.definir_espessura(0.7)
    destino = projeto_arquivo.salvar(j, tmp_path / "faca.autoline")
    j.close()
    k = JanelaPrincipal()
    projeto_arquivo.aplicar_na_janela(k, projeto_arquivo.ler(destino))
    assert k.canvas.faca_editada and k.canvas.linhas_faca() == linhas
    assert k._angulos_dobra == {1: 120.0}
    assert k.visualizacao_3d.vista.espessura == pytest.approx(0.7)
    k.close()


def test_titulo_e_salvar_marcam_alterado(tmp_path):
    j = JanelaPrincipal()
    assert not j.projeto_modificado()
    j.spin_comprimento.setValue(777)
    assert j.projeto_modificado()
    assert j._gravar_projeto(str(tmp_path / "caixa"))
    assert not j.projeto_modificado() and j.caminho_projeto.endswith("caixa.autoline")
    assert j.windowTitle().startswith("caixa —")
    j.spin_comprimento.setValue(778)
    j._atualizar_titulo()
    assert j.windowTitle().startswith("• caixa")
    # abrir de novo volta ao salvo; novo projeto zera
    assert j.abrir_projeto(j.caminho_projeto)
    assert j.spin_comprimento.value() == 777 and not j.projeto_modificado()
    assert j.novo_projeto()
    assert j.caminho_projeto is None and j.spin_comprimento.value() == 300
    j.close()


def test_arquivo_que_nao_e_projeto(tmp_path):
    ruim = tmp_path / "x.autoline"
    ruim.write_text("{}", encoding="utf-8")
    with pytest.raises(projeto_arquivo.ErroProjeto):
        projeto_arquivo.ler(ruim)
    ruim.write_text(json.dumps({"formato": "autoline", "versao": 99}), encoding="utf-8")
    with pytest.raises(projeto_arquivo.ErroProjeto, match="mais nova"):
        projeto_arquivo.ler(ruim)


def test_associacao_grava_so_no_usuario():
    from gerador_layout.ui import associacao_arquivo

    comando = '"C:\\Apps\\Autoline.exe" "%1"'
    chaves = associacao_arquivo.chaves(comando)
    assert all(c.startswith("Software\\Classes\\") for c, _v in chaves)
    assert chaves[-1][1] == comando
    with pytest.raises(associacao_arquivo.ErroAssociacao):
        associacao_arquivo.comando_de_abrir()  # rodando pelo código-fonte
