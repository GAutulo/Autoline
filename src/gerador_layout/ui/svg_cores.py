"""Detecção e substituição de cores num arquivo SVG — base da separação
de cor automática de logotipo vetorial (ver `ElementoLogoVetorial` em
`mockup_logo.py`).

Escopo deliberadamente conservador: lida com `fill`/`stroke` em
atributo direto, dentro do atributo `style` de cada elemento, e nas
regras de classe do bloco `<style>` (o que o CorelDRAW exporta:
`.fil0 {fill:#ED3237}` + `class="fil0"`) — só contam as classes que algum
elemento usa. Não resolve gradiente (`url(#...)`) nem seletor CSS
complexo; esses casos simplesmente não aparecem na lista de cores
detectadas, em vez de arriscar um mapeamento errado.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from PySide6.QtGui import QColor

_ATRIBUTOS_COR = ("fill", "stroke")
_VALORES_IGNORADOS = {"none", "transparent", "currentcolor"}

ET.register_namespace("", "http://www.w3.org/2000/svg")

_REGRA_CSS = re.compile(r"([^{}]+)\{([^{}]*)\}")
_COR_CSS = re.compile(r"\b(fill|stroke)(\s*:\s*)([^;}\s]+)")


def _local(tag) -> str:
    return tag.split("}", 1)[1] if isinstance(tag, str) and "}" in tag else str(tag)


def _cores_por_classe(raiz: ET.Element) -> dict[str, list[str]]:
    """Classe CSS ("fil0") → cores de fill/stroke das regras `.fil0 {…}`
    dos blocos `<style>` (regras com vários seletores simples valem pra cada um)."""
    por_classe: dict[str, list[str]] = {}
    for estilo in raiz.iter():
        if _local(estilo.tag) != "style" or not estilo.text:
            continue
        for seletores, corpo in _REGRA_CSS.findall(estilo.text):
            cores = [c for _p, _s, v in _COR_CSS.findall(corpo) if (c := _normalizar_cor(v))]
            for seletor in seletores.split(","):
                seletor = seletor.strip()
                if re.fullmatch(r"\.[\w-]+", seletor):
                    por_classe.setdefault(seletor[1:], []).extend(cores)
    return por_classe


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
    por_classe = _cores_por_classe(raiz)

    for elemento in raiz.iter():
        valores = []
        for classe in elemento.attrib.get("class", "").split():
            valores += por_classe.get(classe, [])
        valores += [elemento.attrib[a] for a in _ATRIBUTOS_COR if a in elemento.attrib]
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

        if _local(elemento.tag) == "style" and elemento.text:

            def trocar(m: re.Match) -> str:
                cor = _normalizar_cor(m.group(3))
                if cor and cor.lower() in mapa_normalizado:
                    return f"{m.group(1)}{m.group(2)}{mapa_normalizado[cor.lower()]}"
                return m.group(0)

            elemento.text = _REGRA_CSS.sub(lambda r: r.group(1) + "{" + _COR_CSS.sub(trocar, r.group(2)) + "}", elemento.text)

    return ET.tostring(raiz, encoding="unicode")
