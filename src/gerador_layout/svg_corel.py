"""Correção dos SVGs exportados pelo CorelDRAW.

O exportador do CorelDRAW escreve o ``m`` relativo que vem logo depois de um
``z`` contando a partir do ÚLTIMO ponto desenhado — a especificação do SVG
manda contar a partir do COMEÇO do subcaminho que o ``z`` fechou. Quando o
subcaminho fechado termina onde começou (o normal) dá no mesmo; quando não
termina (uma tira aberta, por exemplo), tudo o que vem depois no mesmo path
sai deslocado em qualquer programa que siga a especificação — navegador,
Autoline… (o bico do pássaro do Blue Moby subia ~4 cm).

`corrigir_svg_corel` reescreve esses ``m`` em absoluto (``M``) do jeito que o
Corel quis dizer. Só mexe em arquivo do CorelDRAW (pela marca que ele deixa);
SVG de outro programa segue a especificação e fica como está.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_ARGS = {"m": 2, "l": 2, "h": 1, "v": 1, "c": 6, "s": 4, "q": 4, "t": 2, "a": 7, "z": 0}
_D = re.compile(r'(\sd\s*=\s*)(["\'])(.*?)\2', re.DOTALL)


def e_do_corel(conteudo: str) -> bool:
    return "CorelDRAW" in conteudo[:2000] or "corel.com/coreldraw" in conteudo


def corrigir_svg_corel(conteudo: str) -> str:
    if not e_do_corel(conteudo):
        return conteudo
    return _D.sub(lambda m: m.group(1) + m.group(2) + corrigir_caminho(m.group(3)) + m.group(2), conteudo)


def _num(valor: float) -> str:
    return f"{valor:.4f}".rstrip("0").rstrip(".")


def corrigir_caminho(d: str) -> str:
    """O mesmo caminho, com cada ``m`` logo depois de ``z`` em absoluto,
    contado do último ponto desenhado (a regra do CorelDRAW)."""
    tokens = _TOKEN.findall(d)
    if not any(t in "Zz" for t in tokens if t.isalpha()):
        return d
    saida: list[str] = []
    x = y = 0.0
    cmd = ""
    depois_do_z = False
    mudou = False
    i = 0
    try:
        while i < len(tokens):
            t = tokens[i]
            if t.isalpha():
                cmd = t
                i += 1
                if cmd in "Zz":
                    saida.append(t)
                    depois_do_z = True  # o ponto atual fica onde estava (regra do Corel)
                    continue
                if cmd == "m" and depois_do_z:
                    dx, dy = float(tokens[i]), float(tokens[i + 1])
                    x, y = x + dx, y + dy
                    saida += ["M", _num(x), _num(y)]
                    i += 2
                    cmd = "l"  # pares seguintes do mesmo m são lineto relativos
                    if i < len(tokens) and not tokens[i].isalpha():
                        saida.append("l")
                    depois_do_z = False
                    mudou = True
                    continue
                saida.append(t)
                depois_do_z = False
            if not cmd:
                return d
            c = cmd.lower()
            n = _ARGS[c]
            if n == 0:
                continue
            args = [float(v) for v in tokens[i : i + n]]
            if len(args) < n:
                return d
            saida += tokens[i : i + n]
            i += n
            rel = cmd.islower()
            if c == "h":
                x = x + args[0] if rel else args[0]
            elif c == "v":
                y = y + args[0] if rel else args[0]
            else:
                ex, ey = args[-2], args[-1]
                x, y = (x + ex, y + ey) if rel else (ex, ey)
            if c == "m":
                cmd = "l" if rel else "L"  # pares implícitos depois de m
            depois_do_z = False
    except (ValueError, IndexError):
        return d
    return " ".join(saida) if mudou else d
