"""Folha de aprovação (PDF A4 deitado): campos do projeto e digitados,
datas de criação/modificação guardadas no projeto, nome do arquivo."""

from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

QApplication.instance() or QApplication([])

from gerador_layout.models import TipoCaixa  # noqa: E402
from gerador_layout.ui import projeto_arquivo  # noqa: E402
from gerador_layout.ui.folha_aprovacao import DadosFolha, datas_da_vez, nome_do_arquivo  # noqa: E402
from gerador_layout.ui.main_window import JanelaPrincipal  # noqa: E402


def test_datas_criacao_e_modificacao():
    hoje = dt.date(2026, 10, 16)
    assert datas_da_vez(None, hoje) == (hoje, None)  # primeira vez: cria hoje
    criado = dt.date(2026, 10, 13)
    assert datas_da_vez(criado, hoje) == (criado, hoje)  # outro dia: modificação, criação fica
    assert datas_da_vez(hoje, hoje) == (hoje, None)  # mesmo dia: continua a criação
    assert datas_da_vez(hoje, hoje, modificacao=True) == (hoje, hoje)  # marcado à mão


def test_nome_do_arquivo_como_o_modelo():
    d = DadosFolha(codigo="32792", referencia="CAIXA 02 - 06 LONG NECK 355ML TRADICIONAL")
    assert nome_do_arquivo(d) == "32792 CAIXA 02 - 06 LONG NECK 355ML TRADICIONAL.pdf"
    assert nome_do_arquivo(DadosFolha(codigo="1", referencia='A/B: "C"')) == "1 A-B- -C-.pdf"
    assert nome_do_arquivo(DadosFolha()) == "Aprovação.pdf"


def test_gerar_folha_pelo_programa(tmp_path):
    from PySide6.QtPdf import QPdfDocument

    j = JanelaPrincipal()
    j.combo_tipo.setCurrentIndex(j.combo_tipo.findData(TipoCaixa.MALETA_NORMAL))
    j.spin_comprimento.setValue(19)  # desenhada em 1:10
    j.spin_largura.setValue(13)
    j.spin_altura.setValue(23)
    j._gravar_projeto(str(tmp_path / "lord lion"))
    vistos = {}

    def preencher(janela):
        vistos["medidas"] = janela.campo_medidas.text()
        vistos["tipo"] = janela.campo_tipo.text()
        vistos["primeira"] = janela.check_modificacao is None
        janela.campo_cliente.setText("LORD LION")
        janela.campo_referencia.setText("CAIXA 02 - 06 LONG NECK")
        janela.campo_codigo.setText("32792")
        janela.campo_desenvolvido.setText("Guilherme A")
        assert janela.check_3d.isChecked()
        return True

    pdf = j.gerar_folha_aprovacao(str(tmp_path / "folha.pdf"), dialogo=preencher, abrir=False)
    assert vistos == {"medidas": "190X130X230", "tipo": "MALETA NORMAL", "primeira": True}  # a medida de verdade
    assert pdf is not None and pdf.is_file()
    doc = QPdfDocument()
    doc.load(str(pdf))
    tamanho = doc.pagePointSize(0)
    assert doc.pageCount() == 2  # 2ª folha: a caixa montada em 3D
    assert tamanho.width() * 25.4 / 72 == pytest.approx(297, abs=0.5)  # A4 deitado
    assert tamanho.height() * 25.4 / 72 == pytest.approx(210, abs=0.5)
    texto = doc.getAllText(0).text()
    from PySide6.QtGui import QFontDatabase

    sem_fontes = not QFontDatabase.families()  # plataforma de teste sem fontes: o PDF sai sem texto
    for parte in () if sem_fontes else ("LORD LION", "190X130X230", "MALETA NORMAL", "32792", "ATENÇÃO", "Guilherme A",
                  dt.date.today().strftime("%d/%m/%Y")):
        assert parte in texto, parte
    # as datas e os campos ficaram no projeto (salvo junto)
    assert j._aprovacao["cliente"] == "LORD LION" and j._aprovacao["criado_em"] == dt.date.today().isoformat()
    assert not j.projeto_modificado()
    dados = projeto_arquivo.ler(j.caminho_projeto)
    assert dados["aprovacao"]["codigo"] == "32792"

    # reabrindo noutro dia: os campos voltam e marca modificação
    j._aprovacao["criado_em"] = "2026-01-02"
    vistos2 = {}

    def conferir(janela):
        janela.check_3d.setChecked(False)  # sem o 3D: uma folha só
        vistos2["cliente"] = janela.campo_cliente.text()
        vistos2["modificacao"] = janela.check_modificacao.isChecked()
        return True

    pdf2 = j.gerar_folha_aprovacao(str(tmp_path / "folha2.pdf"), dialogo=conferir, abrir=False)
    doc2 = QPdfDocument()
    doc2.load(str(pdf2))
    assert doc2.pageCount() == 1
    assert vistos2 == {"cliente": "LORD LION", "modificacao": True}
    assert j._aprovacao["criado_em"] == "2026-01-02"
    assert j._aprovacao["modificado_em"] == dt.date.today().isoformat()
    j.close()


def test_medida_da_ficha_e_a_real_da_escala_1_10():
    from gerador_layout.ui.folha_aprovacao import texto_medidas

    assert texto_medidas(54, 54, 38) == "540X540X380"
    assert texto_medidas(13.6, 1.6, 0.9) == "136X16X9"
    assert texto_medidas(54.25, 30, 20.5) == "542,5X300X205"


def _travar(caminho):
    """Abre o arquivo sem deixar ninguém mais gravar (como o Foxit faz)."""
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.restype = wintypes.HANDLE
    alca = kernel.CreateFileW(str(caminho), 0x80000000, 0x00000001, None, 3, 0x80, None)  # leitura, divide só leitura
    assert alca != wintypes.HANDLE(-1).value
    return lambda: kernel.CloseHandle(wintypes.HANDLE(alca))


@pytest.mark.skipif(sys.platform != "win32", reason="trava de arquivo do Windows")
def test_pdf_aberto_no_leitor_avisa_e_salva_com_outro_nome(tmp_path):
    from gerador_layout.ui.arquivo_destino import esta_preso, proximo_nome_livre

    alvo = tmp_path / "32842 LUMINARIA VANILLA VOL 1-1.pdf"
    alvo.write_bytes(b"%PDF-1.4 antigo")
    soltar = _travar(alvo)
    try:
        assert esta_preso(alvo) and not esta_preso(tmp_path / "nao_existe.pdf")
        assert proximo_nome_livre(alvo).name == "32842 LUMINARIA VANILLA VOL 1-1 (2).pdf"
        j = JanelaPrincipal()
        j.combo_tipo.setCurrentIndex(j.combo_tipo.findData(TipoCaixa.MALETA_NORMAL))
        j._gravar_projeto(str(tmp_path / "vanilla"))
        perguntas = []
        j._perguntar_arquivo_preso = lambda c: (perguntas.append(c), "outro")[1]
        pdf = j.gerar_folha_aprovacao(str(alvo), dialogo=lambda janela: True, abrir=False)
        assert perguntas == [str(alvo)]  # avisou que estava aberto, em vez de "não consegui gerar"
        assert pdf is not None and Path(pdf).name.endswith("(2).pdf") and Path(pdf).is_file()
        # cancelar: não grava nada
        j._perguntar_arquivo_preso = lambda c: "cancelar"
        assert j._destino_livre(str(alvo)) is None
        j.close()
    finally:
        soltar()
    assert not esta_preso(alvo)
