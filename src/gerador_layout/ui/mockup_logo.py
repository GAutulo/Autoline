"""Elemento de logotipo vetorial (SVG) do mockup, com separação de cor
automática: detecta as cores usadas no arquivo (`svg_cores.py`) e deixa
mapear cada uma pra uma das tintas do trabalho — o resultado final só
usa as cores mapeadas, seguindo a mesma regra de no máximo poucas
tintas por caixa que o resto do app já assume (ver `DialogoSepararCoresLogo`
em `dialogo_logo.py` pra UI desse mapeamento). Sem mapeamento nenhum,
mostra o SVG com as cores originais do arquivo.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtSvg import QSvgRenderer

from ..models import CorImpressao
from . import svg_cores
from .mockup_itens import ElementoMockup

_LARGURA_PADRAO_MM = 40.0
_PADRAO_ENCODING_XML = re.compile(rb'encoding=["\']([\w-]+)["\']')


def _ler_conteudo_svg(caminho_arquivo: str) -> str:
    """Lê o arquivo tentando, em ordem: UTF-8 (o padrão de verdade pra
    SVG, cobre a maioria), o encoding que o próprio cabeçalho `<?xml?>`
    declara (comum em arquivo mais antigo ou exportado por ferramenta
    que não usa UTF-8 por padrão — ex.: `ISO-8859-1`), e por último
    Latin-1 como rede de segurança (Latin-1 nunca falha ao decodificar
    nenhuma sequência de bytes, então garante que pelo menos abre — na
    pior hipótese um acento sai errado num comentário do arquivo, mas
    isso não impede o logotipo de aparecer).

    Faltava isso: um SVG de verdade com encoding diferente de UTF-8
    derrubava o app inteiro com `UnicodeDecodeError` direto no
    `open().read()`, antes até de chegar no `try/except` que já existia
    (esse só pega `ValueError`)."""
    with open(caminho_arquivo, "rb") as arquivo:
        bruto = arquivo.read()

    declarado = _PADRAO_ENCODING_XML.search(bruto[:200])
    candidatos = ["utf-8-sig", declarado.group(1).decode("ascii") if declarado else None, "latin-1"]
    for codificacao in candidatos:
        if not codificacao:
            continue
        try:
            return bruto.decode(codificacao)
        except (UnicodeDecodeError, LookupError):
            continue
    return bruto.decode("latin-1", errors="replace")  # nunca deveria chegar aqui — latin-1 sozinho já não falha


class ElementoLogoVetorial(ElementoMockup):
    def __init__(self, caminho_arquivo: str, parent=None) -> None:
        try:
            conteudo_original = _ler_conteudo_svg(caminho_arquivo)
        except OSError as exc:
            raise ValueError(f"Não consegui ler o arquivo: {caminho_arquivo}") from exc

        renderer = QSvgRenderer()
        if not renderer.load(conteudo_original.encode("utf-8")):
            raise ValueError(f"Não consegui abrir o logotipo vetorial: {caminho_arquivo}")

        largura, altura = _tamanho_inicial_mm(renderer)
        super().__init__(largura=largura, altura=altura, parent=parent)

        self._caminho_arquivo = caminho_arquivo
        self._conteudo_original = conteudo_original
        try:
            self._cores_detectadas = svg_cores.detectar_cores(conteudo_original)
        except Exception:  # noqa: BLE001 — XML malformado não pode derrubar o app, só perde a separação de cor
            self._cores_detectadas = []
        self._mapa_cores: dict[str, str] = {}
        self._tinta_unica: CorImpressao | None = None
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
        self._tinta_unica = None
        self._renderer = novo_renderer
        self.update()

    @property
    def tinta_unica(self) -> CorImpressao | None:
        """A tinta em que o desenho todo foi pintado (`pintar_numa_tinta`),
        ou None (cores originais ou separação cor a cor)."""
        return self._tinta_unica

    def pintar_numa_tinta(self, tinta: CorImpressao | None) -> None:
        """Pinta o desenho todo numa tinta só — o caso de símbolo de
        manuseio, que sai numa cor do trabalho. O branco (vazado, miolo
        dos ícones) continua branco. None volta às cores originais."""
        if tinta is None:
            self.definir_mapa_cores({})
            return
        nova = QColor(tinta.r, tinta.g, tinta.b).name()
        self.definir_mapa_cores({c: nova for c in self._cores_detectadas if not _quase_branca(c)})
        self._tinta_unica = tinta

    def conteudo_svg(self) -> str:
        """O SVG como aparece na tela (com as cores trocadas)."""
        if not self._mapa_cores:
            return self._conteudo_original
        return svg_cores.aplicar_mapa_cores(self._conteudo_original, self._mapa_cores)

    def _pintar_conteudo(self, painter: QPainter) -> None:
        self._renderer.render(painter, QRectF(0, 0, self._largura, self._altura))

    def clonar(self) -> "ElementoLogoVetorial":
        novo = ElementoLogoVetorial(self._caminho_arquivo)
        if self._mapa_cores:
            novo.definir_mapa_cores(self._mapa_cores)
            novo._tinta_unica = self._tinta_unica
        self._copiar_geometria_para(novo)
        return novo


def _quase_branca(cor: str) -> bool:
    return QColor(cor).lightnessF() >= 0.94


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
