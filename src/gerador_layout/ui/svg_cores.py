"""Detecção e substituição de cores num arquivo SVG — base da separação
de cor automática de logotipo vetorial (ver `ElementoLogoVetorial` em
`mockup_logo.py`).

Escopo deliberadamente conservador: só lida com `fill`/`stroke` em
atributo direto ou dentro do atributo `style` de cada elemento — não
resolve cor vinda de bloco `<style>` CSS externo com classe, nem
gradiente (`url(#...)`). Cobre a grande maioria dos logotipos
exportados de um programa gráfico (Illustrator/CorelDRAW/Inkscape
"Salvar como SVG" usa fill/stroke direto no elemento); os casos fora
disso simplesmente não aparecem na lista de cores detectadas, em vez de
arriscar um mapeamento errado.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from PySide6.QtGui import QColor

_ATRIBUTOS_COR = ("fill", "stroke")
_VALORES_IGNORADOS = {"none", "transparent", "currentcolor"}

ET.register_namespace("", "http://www.w3.org/2000/svg")


def _normalizar_cor(valor: str) -> str | None:
    valor = valor.strip()
    if not valor or valor.lower() in _VALORES_IGNORADOS or valor.lower().startswith("url("):
        return None
    cor = QColor(valor)
    if not cor.isValid():
        return None
    return cor.name()  # sempre "#rrggbb"


def _parsear_style(style: str) -> dict[str, str]:
    propriedades = {}
    for parte in style.split(";"):
        if ":" not in parte:
            continue
        chave, _, valor = parte.partition(":")
        propriedades[chave.strip()] = valor.strip()
    return propriedades


def _serializar_style(propriedades: dict[str, str]) -> str:
    return ";".join(f"{k}:{v}" for k, v in propriedades.items())


def detectar_cores(conteudo_svg: str) -> list[str]:
    """Lista de cores (`#rrggbb`) usadas em fill/stroke no arquivo, sem
    repetição, na ordem em que aparecem."""
    raiz = ET.fromstring(conteudo_svg)
    encontradas: list[str] = []
    vistas: set[str] = set()

    for elemento in raiz.iter():
        valores = [elemento.attrib[a] for a in _ATRIBUTOS_COR if a in elemento.attrib]
        if "style" in elemento.attrib:
            propriedades = _parsear_style(elemento.attrib["style"])
            valores += [propriedades[a] for a in _ATRIBUTOS_COR if a in propriedades]

        for valor in valores:
            cor = _normalizar_cor(valor)
            if cor and cor not in vistas:
                vistas.add(cor)
                encontradas.append(cor)

    return encontradas


def aplicar_mapa_cores(conteudo_svg: str, mapa: dict[str, str]) -> str:
    """`mapa`: cor original ("#rrggbb", como devolvido por
    `detectar_cores`) → cor nova ("#rrggbb"). Cores fora do mapa ficam
    como estavam no arquivo original."""
    if not mapa:
        return conteudo_svg

    raiz = ET.fromstring(conteudo_svg)
    mapa_normalizado = {k.lower(): v for k, v in mapa.items()}

    for elemento in raiz.iter():
        for atributo in _ATRIBUTOS_COR:
            if atributo in elemento.attrib:
                cor = _normalizar_cor(elemento.attrib[atributo])
                if cor and cor.lower() in mapa_normalizado:
                    elemento.attrib[atributo] = mapa_normalizado[cor.lower()]

        if "style" in elemento.attrib:
            propriedades = _parsear_style(elemento.attrib["style"])
            mudou = False
            for atributo in _ATRIBUTOS_COR:
                if atributo in propriedades:
                    cor = _normalizar_cor(propriedades[atributo])
                    if cor and cor.lower() in mapa_normalizado:
                        propriedades[atributo] = mapa_normalizado[cor.lower()]
                        mudou = True
            if mudou:
                elemento.attrib["style"] = _serializar_style(propriedades)

    return ET.tostring(raiz, encoding="unicode")
