"""Gera o ícone do aplicativo (assets/icon.ico) a partir de formas simples.
Não faz parte do app em si — é só uma ferramenta de build.
"""
from PIL import Image, ImageDraw

def desenhar_icone(tamanho: int) -> Image.Image:
    img = Image.new("RGBA", (tamanho, tamanho), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Paleta Autoline (ver estilo.py): carvão de fundo, painéis em osso,
    # contorno em kraft escuro, vinco tracejado em kraft — mesma lógica
    # de cores do resto do rebranding, não uma paleta só do ícone.
    cor_fundo = (30, 26, 22, 255)     # carvão
    cor_caixa = (237, 230, 216, 255)  # osso
    cor_linha = (140, 106, 59, 255)   # kraft escuro
    cor_vinco = (199, 154, 93, 255)   # kraft

    pad = int(tamanho * 0.08)
    d.rounded_rectangle([pad, pad, tamanho - pad, tamanho - pad], radius=int(tamanho * 0.14), fill=cor_fundo)

    # "planificação" de caixa simplificada: cruz de painéis
    cx, cy = tamanho / 2, tamanho / 2
    lado = tamanho * 0.20
    largura_linha = max(1, int(tamanho * 0.02))

    painel_w = lado
    painel_h = lado

    retangulos = [
        (cx - painel_w * 1.5, cy - painel_h / 2, cx - painel_w / 2, cy + painel_h / 2),  # esquerda
        (cx - painel_w / 2, cy - painel_h * 1.5, cx + painel_w / 2, cy - painel_h / 2),  # cima
        (cx - painel_w / 2, cy - painel_h / 2, cx + painel_w / 2, cy + painel_h / 2),    # centro
        (cx - painel_w / 2, cy + painel_h / 2, cx + painel_w / 2, cy + painel_h * 1.5),  # baixo
        (cx + painel_w / 2, cy - painel_h / 2, cx + painel_w * 1.5, cy + painel_h / 2),  # direita
    ]
    for r in retangulos:
        d.rectangle(r, fill=cor_caixa, outline=cor_linha, width=largura_linha)

    # vincos (linhas tracejadas simplificadas como pontilhado) entre painel central e os 4 ao redor
    def linha_tracejada(p1, p2, cor, largura):
        import math
        x1, y1 = p1
        x2, y2 = p2
        dist = math.hypot(x2 - x1, y2 - y1)
        passos = max(2, int(dist / (tamanho * 0.025)))
        for i in range(passos):
            if i % 2 == 0:
                t0 = i / passos
                t1 = (i + 0.6) / passos
                d.line([
                    (x1 + (x2 - x1) * t0, y1 + (y2 - y1) * t0),
                    (x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1),
                ], fill=cor, width=largura)

    linha_tracejada((cx - painel_w / 2, cy - painel_h / 2), (cx - painel_w / 2, cy + painel_h / 2), cor_vinco, largura_linha)
    linha_tracejada((cx + painel_w / 2, cy - painel_h / 2), (cx + painel_w / 2, cy + painel_h / 2), cor_vinco, largura_linha)
    linha_tracejada((cx - painel_w / 2, cy - painel_h / 2), (cx + painel_w / 2, cy - painel_h / 2), cor_vinco, largura_linha)
    linha_tracejada((cx - painel_w / 2, cy + painel_h / 2), (cx + painel_w / 2, cy + painel_h / 2), cor_vinco, largura_linha)

    return img

tamanhos = [16, 24, 32, 48, 64, 128, 256]
imagens = [desenhar_icone(t) for t in tamanhos]
imagens[-1].save(
    "icon.ico",
    format="ICO",
    sizes=[(t, t) for t in tamanhos],
)
print("Ícone gerado: icon.ico")
