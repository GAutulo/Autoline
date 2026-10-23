"""Arquivo de destino de uma exportação que está aberto em outro programa.

O leitor de PDF (Foxit, Acrobat) e alguns visualizadores de imagem
travam o arquivo aberto: gravar por cima falha, e o Qt só diz "não
consegui criar o PDF". Aqui dá pra saber ANTES de gravar e oferecer
tentar de novo (depois de fechar) ou salvar com outro nome.
"""

from __future__ import annotations

import os
from pathlib import Path


def esta_preso(caminho: str | os.PathLike) -> bool:
    """True se o arquivo existe e outro programa não deixa gravar nele."""
    caminho = Path(caminho)
    if not caminho.is_file():
        return False
    try:
        descritor = os.open(caminho, os.O_RDWR | getattr(os, "O_BINARY", 0))
    except PermissionError:
        return True
    except OSError:
        return False  # outro problema (rede, disco): o próprio gravador avisa
    os.close(descritor)
    return False


def proximo_nome_livre(caminho: str | os.PathLike) -> Path:
    """"FOLHA.pdf" → "FOLHA (2).pdf" (ou o próximo que não existe e não está preso)."""
    caminho = Path(caminho)
    n = 2
    while True:
        candidato = caminho.with_name(f"{caminho.stem} ({n}){caminho.suffix}")
        if not candidato.exists() or not esta_preso(candidato):
            return candidato
        n += 1
