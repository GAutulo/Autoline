"""Elemento de logotipo vetorial (SVG) do mockup, com separação de cor
automática: detecta as cores usadas no arquivo (`svg_cores.py`) e deixa
mapear cada uma pra uma das tintas do trabalho — o resultado final só
usa as cores mapeadas, seguindo a mesma regra de no máximo poucas
tintas por caixa que o resto do app já assume (ver `DialogoSepararCoresLogo`
em `dialogo_logo.py` pra UI desse mapeamento). Sem mapeamento nenhum,
mostra o SVG com as cores originais do arquivo.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer

from . import svg_cores
from .mockup_itens import ElementoMockup

_LARGURA_PADRAO_MM = 40.0


class ElementoLogoVetorial(ElementoMockup):
    def __init__(self, caminho_arquivo: str, parent=None) -> None:
        with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:
            conteudo_original = arquivo.read()

        renderer = QSvgRenderer()
        if not renderer.load(conteudo_original.encode("utf-8")):
            raise ValueError(f"Não consegui abrir o logotipo vetorial: {caminho_arquivo}")

        largura, altura = _tamanho_inicial_mm(renderer)
        super().__init__(largura=largura, altura=altura, parent=parent)

        self._caminho_arquivo = caminho_arquivo
        self._conteudo_original = conteudo_original
        self._cores_detectadas = svg_cores.detectar_cores(conteudo_original)
        self._mapa_cores: dict[str, str] = {}
        self._renderer = renderer

    @property
    def caminho_arquivo(self) -> str:
        return self._caminho_arquivo

    @property
    def cores_detectadas(self) -> list[str]:
        """Cores originais do arquivo (`#rrggbb`) — a lista que a tela
        de separação de cor mostra pro usuário mapear."""
        return list(self._cores_detectadas)

    @property
    def mapa_cores(self) -> dict[str, str]:
        return dict(self._mapa_cores)

    def definir_mapa_cores(self, mapa: dict[str, str]) -> None:
        """`mapa`: cor original ("#rrggbb") → cor da tinta escolhida
        ("#rrggbb"). Cor fora do mapa continua com a cor original."""
        conteudo = svg_cores.aplicar_mapa_cores(self._conteudo_original, mapa)
        novo_renderer = QSvgRenderer()
        if not novo_renderer.load(conteudo.encode("utf-8")):
            raise ValueError("O mapeamento de cores gerou um SVG inválido.")
        self._mapa_cores = dict(mapa)
        self._renderer = novo_renderer
        self.update()

    def _pintar_conteudo(self, painter: QPainter) -> None:
        self._renderer.render(painter, QRectF(0, 0, self._largura, self._altura))


def _tamanho_inicial_mm(renderer: QSvgRenderer) -> tuple[float, float]:
    """Mesma lógica/motivo do PNG (ver `mockup_imagem.py`): largura
    padrão + proporção real do desenho, sem tentar adivinhar tamanho
    físico a partir de unidades do SVG (px/pt/mm variam de arquivo pra
    arquivo e não são um sinal confiável de intenção de tamanho real)."""
    tamanho = renderer.defaultSize()
    if tamanho.width() <= 0 or tamanho.height() <= 0:
        return _LARGURA_PADRAO_MM, _LARGURA_PADRAO_MM
    proporcao = tamanho.height() / tamanho.width()
    return _LARGURA_PADRAO_MM, _LARGURA_PADRAO_MM * proporcao
