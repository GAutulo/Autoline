"""Banco de simbologias: separar uma folha (um símbolo por grupo), os
símbolos que vêm com o app e o docker que insere no layout."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

QApplication.instance() or QApplication([])

from gerador_layout.simbologias import carregar_banco, separar_folha_svg, tamanho_mm  # noqa: E402

# Folha como o CorelDRAW exporta: 100 unidades por mm, uma camada, e os
# símbolos como grupos de primeiro nível (um deles com várias peças soltas).
_FOLHA = """<svg xmlns="http://www.w3.org/2000/svg" width="200mm" height="100mm" viewBox="0 0 20000 10000">
 <defs><style>.v{fill:red}</style></defs>
 <g id="Camada_1">
  <g id="fileira">
   <rect class="v" x="1000" y="1000" width="1000" height="1000"/>
   <rect class="v" x="3000" y="1000" width="1000" height="1000"/>
   <rect class="v" x="5000" y="1000" width="1000" height="1000"/>
  </g>
  <g id="seta">
   <polygon points="10000,1000 11000,3000 9000,3000"/>
   <rect x="9800" y="3000" width="400" height="2000"/>
  </g>
  <circle cx="3000" cy="7000" r="1000"/>
 </g>
</svg>"""


def test_cada_grupo_de_primeiro_nivel_e_um_simbolo(tmp_path):
    svgs = separar_folha_svg(_FOLHA)
    assert len(svgs) == 3  # a fileira de 3 quadrados é UM símbolo
    medidas = []
    for i, svg in enumerate(svgs):
        caminho = tmp_path / f"s{i}.svg"
        caminho.write_text(svg, encoding="utf-8")
        medidas.append(tamanho_mm(caminho))
        assert "_peca" not in svg
        assert ".v{fill:red}" in svg  # as definições (estilos) vão junto
    # ordem de leitura (de cima pra baixo, da esquerda pra direita) e o
    # tamanho real em mm (com 2% de margem)
    assert medidas[0] == pytest.approx((52.0, 12.0), abs=0.01)  # 50 × 10 + 1 mm de margem
    assert medidas[1] == pytest.approx((21.6, 41.6), abs=0.01)
    assert medidas[2] == pytest.approx((20.8, 20.8), abs=0.1)


@pytest.mark.parametrize(
    ("largura", "esperado"), [("90mm", 90.0), ("9cm", 90.0), ("1in", 25.4), ("96px", 25.4), ("96", 25.4), ("72pt", 25.4)]
)
def test_tamanho_mm_unidades(tmp_path, largura, esperado):
    caminho = tmp_path / "a.svg"
    caminho.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{largura}"/>', encoding="utf-8")
    assert tamanho_mm(caminho) == pytest.approx((esperado, esperado))


def test_tamanho_mm_desconhecido(tmp_path):
    caminho = tmp_path / "a.svg"
    caminho.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 10 10"/>', encoding="utf-8")
    assert tamanho_mm(caminho) is None


def test_simbolos_que_vem_com_o_app():
    from PySide6.QtSvg import QSvgRenderer

    banco = carregar_banco(None)
    assert len(banco) == 4
    for simbolo in banco:
        assert QSvgRenderer(str(simbolo.caminho)).isValid(), simbolo.nome
        assert tamanho_mm(simbolo.caminho) is not None
        assert not simbolo.do_usuario


def test_docker_adiciona_importa_renomeia_e_insere(tmp_path):
    from gerador_layout.ui.docker_simbologias import DockerSimbologias

    docker = DockerSimbologias(pasta_usuario=tmp_path / "meus")
    assert len(docker.simbolos()) == 4

    folha = tmp_path / "folha teste.svg"
    folha.write_text(_FOLHA, encoding="utf-8")
    novos = docker.importar_folha(str(folha))
    assert [p.name for p in novos] == ["folha teste 1.svg", "folha teste 2.svg", "folha teste 3.svg"]

    avulso = tmp_path / "Reciclável.svg"
    avulso.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm"><rect width="5" height="5"/></svg>', encoding="utf-8")
    docker.adicionar_svgs([str(avulso), str(avulso)])
    nomes = [s.nome for s in docker.simbolos()]
    assert len(nomes) == 4 + 3 + 2 and "Reciclável" in nomes and "Reciclável 2" in nomes

    meu = next(s for s in docker.simbolos() if s.nome == "folha teste 2")
    docker.renomear(meu, "Seta pra cima")
    assert "Seta pra cima" in [s.nome for s in docker.simbolos()]

    docker.busca.setText("seta")
    visiveis = [docker.lista.item(i).text() for i in range(docker.lista.count()) if not docker.lista.item(i).isHidden()]
    assert "Seta pra cima" in visiveis and not any(n.startswith("Ícones") for n in visiveis)

    emitidos = []
    docker.inserir_simbolo.connect(lambda caminho, nome: emitidos.append((caminho, nome)))
    docker.busca.clear()
    docker._inserir_item(docker.lista.item(0))
    assert emitidos == [(str(docker.simbolos()[0].caminho), "Cuidado frágil (setas)")]


def test_inserir_no_layout_no_tamanho_real():
    from gerador_layout.ui.main_window import JanelaPrincipal
    from gerador_layout.ui.mockup_logo import ElementoLogoVetorial

    j = JanelaPrincipal()
    j.show()
    j.abas_tela.setCurrentIndex(1)
    QApplication.processEvents()
    assert "simbologias" in j._docks
    simbolo = carregar_banco(None)[0]
    antes = len(j.canvas.elementos_mockup)
    elemento = j.inserir_simbolo(str(simbolo.caminho))
    assert isinstance(elemento, ElementoLogoVetorial)
    assert len(j.canvas.elementos_mockup) == antes + 1 and elemento.isSelected()
    assert (elemento.largura, elemento.altura) == pytest.approx(tamanho_mm(simbolo.caminho))
    assert "#ed3237" in elemento.cores_detectadas  # dá pra trocar as cores como num logotipo (classes do Corel)
    outro = j.inserir_simbolo(str(simbolo.caminho), simbolo.nome)
    assert outro.pos() != elemento.pos()  # o segundo não cai exatamente em cima do primeiro
    assert simbolo.nome in j.statusBar().currentMessage()
    j.close()


def test_cores_de_classe_css_do_corel():
    from gerador_layout.ui import svg_cores

    svg = """<svg xmlns="http://www.w3.org/2000/svg"><defs><style type="text/css"><![CDATA[
    .str0 {stroke:#201E1E;stroke-width:35}
    .fil1 {fill:#ED3237}
    .fil9 {fill:#00FF00}
    .fil0, .fil2 {fill:#FEFEFE}
    ]]></style></defs><path class="fil1 str0" d="M0 0h10v10z"/><rect class="fil0" width="2" height="2"/></svg>"""
    assert svg_cores.detectar_cores(svg) == ["#ed3237", "#201e1e", "#fefefe"]  # .fil9 não é usada
    novo = svg_cores.aplicar_mapa_cores(svg, {"#ed3237": "#000000"})
    assert svg_cores.detectar_cores(novo) == ["#000000", "#201e1e", "#fefefe"]
    assert "stroke-width:35" in novo
