"""Banco de simbologias (manuseio, transporte, "cuidado frágil"...): os
símbolos prontos que vêm com o app, os do usuário, e o separador que
transforma uma folha de símbolos exportada do CorelDRAW (vários símbolos
num SVG só) num arquivo SVG por símbolo.

Como a folha é separada: cada GRUPO (ou objeto solto) de primeiro nível da
folha é um símbolo, inteiro — do jeito que foi agrupado no CorelDRAW (uma
fileira de ícones agrupada é uma simbologia só).

Cada símbolo sai como um SVG mínimo (só as peças dele + as definições do
arquivo, como fontes e gradientes), com o viewBox justo em volta.
"""

from __future__ import annotations

import copy
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

_NS = "http://www.w3.org/2000/svg"
_Q = "{" + _NS + "}"
_FOLHAS = {"path", "polygon", "polyline", "rect", "ellipse", "circle", "line", "text", "image", "use"}

ET.register_namespace("", _NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


@dataclass
class Simbolo:
    nome: str
    caminho: Path
    categoria: str = ""
    do_usuario: bool = False


def pasta_embutida() -> Path:
    return Path(__file__).resolve().parent / "simbolos"


def carregar_banco(pasta_usuario: Path | None = None) -> list[Simbolo]:
    """Os símbolos que vêm com o app (na ordem do catálogo) e os da pasta
    do usuário (um .svg por símbolo, nome = nome do arquivo)."""
    simbolos: list[Simbolo] = []
    catalogo = pasta_embutida() / "catalogo.json"
    if catalogo.is_file():
        for item in json.loads(catalogo.read_text(encoding="utf-8")):
            caminho = pasta_embutida() / item["arquivo"]
            if caminho.is_file():
                simbolos.append(Simbolo(item["nome"], caminho, item.get("categoria", "")))
    if pasta_usuario is not None and pasta_usuario.is_dir():
        for caminho in sorted(pasta_usuario.glob("*.svg"), key=lambda p: p.name.lower()):
            simbolos.append(Simbolo(caminho.stem, caminho, "Meus símbolos", do_usuario=True))
    return simbolos


_MM_POR_UNIDADE = {"mm": 1.0, "cm": 10.0, "in": 25.4, "pt": 25.4 / 72, "pc": 25.4 / 6, "px": 25.4 / 96, "": 25.4 / 96}


def tamanho_mm(caminho: Path) -> tuple[float, float] | None:
    """Largura × altura reais do SVG (pelos atributos width/height), em mm;
    None se o arquivo não diz (ex.: só viewBox, ou em %)."""
    try:
        raiz = ET.parse(caminho).getroot()
    except (ET.ParseError, OSError):
        return None
    return _tamanho_mm_raiz(raiz)


def _tamanho_mm_raiz(raiz: ET.Element) -> tuple[float, float] | None:
    medidas = []
    for atributo in ("width", "height"):
        m = re.fullmatch(r"\s*([\d.]+)\s*(mm|cm|in|pt|pc|px|)\s*", raiz.get(atributo, ""))
        if not m:
            return None
        medidas.append(float(m.group(1)) * _MM_POR_UNIDADE[m.group(2)])
    if medidas[0] <= 0 or medidas[1] <= 0:
        return None
    return medidas[0], medidas[1]


def enquadrar_no_desenho(conteudo: str) -> tuple[str, tuple[float, float] | None]:
    """O SVG com a "página" (viewBox) justa em volta do desenho, e o tamanho
    real dele em mm (None se o arquivo não diz a unidade).

    O CorelDRAW exporta a página, não o desenho: o que passa da borda da
    página era cortado reto (o bico do pássaro do Blue Moby) e a sobra de
    página em volta deixava a caixa do logotipo maior que ele."""
    from PySide6.QtCore import QByteArray, QRectF
    from PySide6.QtSvg import QSvgRenderer

    try:
        raiz = ET.fromstring(conteudo)
    except ET.ParseError:
        return conteudo, None
    caixa_antes = _caixa_da_pagina(raiz)
    tamanho_antes = _tamanho_mm_raiz(raiz)
    if caixa_antes is None:
        return conteudo, tamanho_antes
    pais = {filho: pai for pai in raiz.iter() for filho in pai}
    folhas = [el for el in raiz.iter() if _local(el.tag) in _FOLHAS and not _dentro_de_defs(el, pais)]
    ids_novos = []
    for k, el in enumerate(folhas):
        if not el.get("id"):
            el.set("id", f"_enq{k}")
            ids_novos.append(el)
    renderer = QSvgRenderer(QByteArray(ET.tostring(raiz)))
    if not renderer.isValid():
        return conteudo, tamanho_antes
    area = QRectF()
    for el in folhas:
        i = el.get("id")
        if renderer.elementExists(i):
            area = area.united(renderer.transformForElement(i).mapRect(renderer.boundsOnElement(i)))
    for el in ids_novos:
        del el.attrib["id"]
    if area.isEmpty():
        return conteudo, tamanho_antes
    margem = max(area.width(), area.height()) * 0.01  # traço grosso fica um pouco pra fora da geometria
    area = area.adjusted(-margem, -margem, margem, margem)
    x, y, w, h = caixa_antes
    if abs(area.left() - x) < 1e-6 * w and abs(area.width() - w) < 1e-6 * w and abs(area.top() - y) < 1e-6 * h and abs(area.height() - h) < 1e-6 * h:
        return conteudo, tamanho_antes
    raiz.set("viewBox", f"{area.x():.4f} {area.y():.4f} {area.width():.4f} {area.height():.4f}")
    tamanho = None
    if tamanho_antes is not None:
        mm_por_unidade = tamanho_antes[0] / w
        tamanho = (area.width() * mm_por_unidade, area.height() * mm_por_unidade)
        raiz.set("width", f"{tamanho[0]:.3f}mm")
        raiz.set("height", f"{tamanho[1]:.3f}mm")
    else:
        for atributo in ("width", "height"):
            raiz.attrib.pop(atributo, None)
    return ET.tostring(raiz, encoding="unicode"), tamanho


def _caixa_da_pagina(raiz: ET.Element) -> tuple[float, float, float, float] | None:
    numeros = re.split(r"[\s,]+", (raiz.get("viewBox") or "").strip())
    if len(numeros) == 4:
        try:
            x, y, w, h = map(float, numeros)
        except ValueError:
            return None
        return (x, y, w, h) if w > 0 and h > 0 else None
    medidas = []
    for atributo in ("width", "height"):
        m = re.fullmatch(r"\s*([\d.]+)\s*(px|)\s*", raiz.get(atributo, ""))
        if not m:
            return None
        medidas.append(float(m.group(1)))
    return (0.0, 0.0, medidas[0], medidas[1])


# ── Separar uma folha ────────────────────────────────────────────────
def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _unidades_por_mm(raiz: ET.Element) -> float:
    """Quantas unidades do viewBox valem 1 mm (Corel exporta 210mm com
    viewBox 0 0 21000 ...: 100 por mm). Sem medida em mm, chuta 1."""
    caixa = raiz.get("viewBox")
    largura = raiz.get("width", "")
    m = re.match(r"([\d.]+)\s*mm", largura)
    if caixa and m:
        return float(caixa.split()[2]) / float(m.group(1))
    return 1.0


def _itens_de_primeiro_nivel(raiz: ET.Element) -> list[ET.Element]:
    """Desce pelos grupos que só embrulham (uma camada, um grupo único) até
    achar o nível com vários objetos — cada um é um candidato a símbolo."""
    no = raiz
    while True:
        filhos = [f for f in no if _local(f.tag) not in ("defs", "style", "metadata", "title", "desc", "font")]
        if len(filhos) == 1 and _local(filhos[0].tag) == "g":
            no = filhos[0]
            continue
        return filhos


def separar_folha_svg(conteudo: str) -> list[str]:
    """Um SVG por símbolo da folha (ver docstring do módulo)."""
    from PySide6.QtCore import QByteArray, QRectF
    from PySide6.QtSvg import QSvgRenderer

    raiz = ET.fromstring(conteudo)
    contador = 0
    for el in raiz.iter():
        if _local(el.tag) in _FOLHAS | {"g"} and not el.get("id"):
            el.set("id", f"_peca{contador}")
            contador += 1
    renderer = QSvgRenderer(QByteArray(ET.tostring(raiz)))
    if not renderer.isValid():
        raise ValueError("SVG inválido.")

    def caixa(el: ET.Element) -> QRectF:
        i = el.get("id")
        return renderer.transformForElement(i).mapRect(renderer.boundsOnElement(i))

    grupos_de_pecas: list[list[ET.Element]] = []
    for item in _itens_de_primeiro_nivel(raiz):
        pecas = [el for el in item.iter() if _local(el.tag) in _FOLHAS]
        pecas = [p for p in pecas if not caixa(p).isEmpty() or _local(p.tag) == "line"]
        if pecas:
            grupos_de_pecas.append(pecas)

    # Ordem de leitura: de cima pra baixo, da esquerda pra direita.
    def topo_esquerda(pecas):
        r = QRectF()
        for p in pecas:
            r = r.united(caixa(p))
        return r

    caixas_grupo = [(topo_esquerda(g), g) for g in grupos_de_pecas]
    linha = 10.0 * _unidades_por_mm(raiz)  # mesma "linha" se o topo difere menos de 1 cm
    caixas_grupo.sort(key=lambda item: (round(item[0].top() / linha), item[0].left()))

    saida = []
    for area, pecas in caixas_grupo:
        copia_raiz = copy.deepcopy(raiz)
        # mapeia elementos da cópia pelos ids que demos
        ids_manter = {p.get("id") for p in pecas}
        pais_copia = {filho: pai for pai in copia_raiz.iter() for filho in pai}
        for el in list(copia_raiz.iter()):
            if _local(el.tag) in _FOLHAS and el.get("id") not in ids_manter and not _dentro_de_defs(el, pais_copia):
                pais_copia[el].remove(el)
        _tirar_grupos_vazios(copia_raiz)
        margem = max(area.width(), area.height()) * 0.02
        area = area.adjusted(-margem, -margem, margem, margem)
        copia_raiz.set("viewBox", f"{area.x():.2f} {area.y():.2f} {area.width():.2f} {area.height():.2f}")
        upm = _unidades_por_mm(raiz)
        copia_raiz.set("width", f"{area.width() / upm:.2f}mm")
        copia_raiz.set("height", f"{area.height() / upm:.2f}mm")
        _tirar_ids_automaticos(copia_raiz)
        saida.append(ET.tostring(copia_raiz, encoding="unicode"))
    return saida


def _dentro_de_defs(el: ET.Element, pais: dict) -> bool:
    while el in pais:
        el = pais[el]
        if _local(el.tag) in ("defs", "font", "symbol", "clipPath", "mask", "pattern"):
            return True
    return False


def _tirar_grupos_vazios(raiz: ET.Element) -> None:
    mudou = True
    while mudou:
        mudou = False
        for pai in list(raiz.iter()):
            for filho in list(pai):
                if _local(filho.tag) == "g" and not any(_local(n.tag) in _FOLHAS for n in filho.iter()):
                    pai.remove(filho)
                    mudou = True


def _tirar_ids_automaticos(raiz: ET.Element) -> None:
    for el in raiz.iter():
        if (el.get("id") or "").startswith("_peca"):
            del el.attrib["id"]


def salvar_simbolos(svgs: list[str], pasta: Path, prefixo: str = "Símbolo") -> list[Path]:
    """Grava cada SVG como um arquivo (sem sobrescrever os que já existem)."""
    pasta.mkdir(parents=True, exist_ok=True)
    caminhos = []
    n = 1
    for svg in svgs:
        while (pasta / f"{prefixo} {n}.svg").exists():
            n += 1
        destino = pasta / f"{prefixo} {n}.svg"
        destino.write_text(svg, encoding="utf-8")
        caminhos.append(destino)
    return caminhos
