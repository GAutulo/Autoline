"""Gera o ícone do aplicativo (assets/icon.ico) — logotipo "Dobra"
(REDESIGN.md, seção 3): quadrado arredondado #1D2125 com borda #3A4048 e o
símbolo dentro. Abaixo de 64 px a travessa vira traço cheio (mais grosso),
como no resto da marca (ver src/gerador_layout/ui/marca.py).

Não faz parte do app em si — é só uma ferramenta de build:
    .venv/Scripts/python.exe assets/gerar_icone.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

_FUNDO = (0x1D, 0x21, 0x25, 255)
_BORDA = (0x3A, 0x40, 0x48, 255)
_CLARA = (0xE7, 0xE9, 0xEB, 255)
_AMBAR = (0xF0, 0xA0, 0x4B, 255)
_FACE_ESQUERDA = ((12, 106), (48, 14), (60, 14), (60, 44), (34, 106))
_FACE_DIREITA = ((108, 106), (72, 14), (60, 14), (60, 44), (86, 106))
_SUPERAMOSTRA = 8  # desenha grande e reduz: borda lisa em qualquer tamanho


def desenhar_icone(tamanho: int) -> Image.Image:
    lado = tamanho * _SUPERAMOSTRA
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Cartão: raio ~22% (96 px → 22 px na referência); borda de 1 px no tamanho final.
    borda = round(max(1.0, tamanho / 96) * _SUPERAMOSTRA) if tamanho >= 24 else 0  # 16 px: sem borda (referência)
    d.rounded_rectangle([0, 0, lado - 1, lado - 1], radius=round(lado * 0.22), fill=_FUNDO,
                        outline=_BORDA if borda else None, width=borda)

    # Símbolo: 2/3 do cartão, centralizado (64 em 96 na referência).
    simbolo = lado * (64 / 96 if tamanho >= 32 else 13 / 16)
    origem = (lado - simbolo) / 2
    k = simbolo / 120.0

    def ponto(x, y):
        return (origem + x * k, origem + y * k)

    d.polygon([ponto(x, y) for x, y in _FACE_ESQUERDA], fill=_CLARA)
    d.polygon([ponto(x, y) for x, y in _FACE_DIREITA], fill=_AMBAR)
    if tamanho >= 64:
        # Travessa tracejada "8 3", espessura 8 (assinatura grande).
        y = origem + 80 * k
        x, fim, traco, vao = 45.0, 75.0, 8.0, 3.0
        while x < fim:
            d.rectangle([origem + x * k, y - 4 * k, origem + min(x + traco, fim) * k, y + 4 * k], fill=_CLARA)
            x += traco + vao
    else:
        espessura = 12 if tamanho <= 16 else (10 if tamanho <= 32 else 9)
        d.rectangle([*ponto(44, 80 - espessura / 2), *ponto(76, 80 + espessura / 2)], fill=_CLARA)
    return img.resize((tamanho, tamanho), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    tamanhos = [16, 24, 32, 48, 64, 128, 256]
    imagens = [desenhar_icone(t) for t in tamanhos]
    destino = Path(__file__).resolve().parent / "icon.ico"
    imagens[-1].save(destino, format="ICO", sizes=[(t, t) for t in tamanhos], append_images=imagens[:-1])
    print(f"Ícone gerado: {destino}")
