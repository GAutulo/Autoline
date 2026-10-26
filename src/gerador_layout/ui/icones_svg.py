"""Conjunto único de ícones do redesign (REDESIGN.md, seção 2.5): grade
24 × 24, traço 1.5, pontas e junções arredondadas, `currentColor`.

Os desenhos com nome da prancheta vêm das pranchetas Dieline e Layout do
canvas de referência (pelo `aria-label` de cada botão); os demais seguem a
mesma grade e o mesmo traço, pra o conjunto ficar uniforme. Quem não está
aqui continua com o desenho de `mockup_icones.py` (ícones dos campos da
barra de propriedades: X, Y, largura, trava…).
"""

from __future__ import annotations

# chave do app → conteúdo do <svg> (sem a tag de fora)
CORPOS: dict[str, str] = {
    # ── Barra de título ─────────────────────────────────────────────
    "desfazer": '<path d="M9 14 L4 9 L9 4"/><path d="M4 9 H14.5 A5.5 5.5 0 0 1 14.5 20 H11"/>',
    "refazer": '<path d="M15 14 L20 9 L15 4"/><path d="M20 9 H9.5 A5.5 5.5 0 0 0 9.5 20 H13"/>',
    # ── Dieline (prancheta "Dieline") ───────────────────────────────
    "navegar": '<path d="M12 3 V21 M3 12 H21 M9.5 5.5 L12 3 L14.5 5.5 M9.5 18.5 L12 21 L14.5 18.5 '
               'M5.5 9.5 L3 12 L5.5 14.5 M18.5 9.5 L21 12 L18.5 14.5"/>',
    "editar_faca": '<path d="M4 20 L11 6 L20 4"/><rect x="9.5" y="4.5" width="3" height="3"/>'
                   '<rect x="2.5" y="18.5" width="3" height="3"/><rect x="18.5" y="2.5" width="3" height="3"/>',
    "linha_corte": '<path d="M6 18 L18 6"/><circle cx="5" cy="19" r="1.5"/><circle cx="19" cy="5" r="1.5"/>',
    "linha_vinco": '<path d="M6 18 L18 6" stroke-dasharray="2 3"/><circle cx="5" cy="19" r="1.5"/><circle cx="19" cy="5" r="1.5"/>',
    "ferramenta_retangulo": '<rect x="4" y="6" width="16" height="12" rx="1.5"/>',
    "linha_medida": '<path d="M4 19 H20"/><path d="M4 19 L17 6"/><path d="M10.5 19 A6.5 6.5 0 0 0 8.6 14.4"/>',
    "faca_arco": '<path d="M5 17 Q12 4 19 17"/><circle cx="5" cy="18" r="1.5"/><circle cx="19" cy="18" r="1.5"/>',
    "faca_aparar": '<path d="M3 12 H12"/><path d="M15 12 H21" stroke-dasharray="1.5 2.5" opacity="0.6"/><path d="M12 4 V20"/>',
    "faca_estender": '<path d="M3 12 H10"/><path d="M10 12 H17" stroke-dasharray="1.5 2.5"/>'
                     '<path d="M14.5 9.5 L17 12 L14.5 14.5"/><path d="M20 4 V20"/>',
    "faca_arredondar": '<path d="M5 20 V13 A8 8 0 0 1 13 5 H20"/><path d="M5 9 V5 H9" stroke-dasharray="1.5 2.5" opacity="0.6"/>',
    "faca_paralela": '<path d="M4 7 H20"/><path d="M4 17 H20" stroke-dasharray="2 3"/><path d="M12 9.5 V14.5 M10.5 13 L12 14.5 L13.5 13"/>',
    "remover": '<path d="M4 7 H20 M9 7 V4.5 H15 V7 M6.5 7 L7.5 20 H16.5 L17.5 7"/>',
    "catalogo": '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/>'
                '<rect x="4" y="13" width="7" height="7" rx="1.5"/><path d="M13 14.5 H20 M13 18.5 H18"/>',  # catálogo de estilos
    "lista": '<rect x="4" y="5" width="4.5" height="4.5" rx="1"/><rect x="4" y="14.5" width="4.5" height="4.5" rx="1"/>'
             '<path d="M11.5 7.25 H20 M11.5 16.75 H20"/>',  # checklist de cores
    "medida": '<rect x="3" y="8" width="18" height="8" rx="1.5"/><path d="M7 8 V11 M11 8 V12 M15 8 V11 M19 8 V10"/>',  # régua
    "mais": '<path d="M12 5 V19 M5 12 H19"/>',
    # ── Layout (prancheta "Layout") ─────────────────────────────────
    "selecionar": '<path d="M5.5 3.5 L18.5 10.5 L12.5 12.5 L10 18.5 Z"/>',
    "ferramenta_laco": '<path d="M7 16 C 2 13, 4 5, 12 5 C 19 5, 21 11, 16 14 C 13 16, 9 15, 9 18 C 9 20, 11 21, 12 21"/>',
    "ferramenta_mover_preciso": '<path d="M12 3 V21 M3 12 H21"/><circle cx="12" cy="12" r="3"/>'
                                '<path d="M9.5 5.5 L12 3 L14.5 5.5 M18.5 9.5 L21 12 L18.5 14.5"/>',
    "ferramenta_forma": '<path d="M5 18 C 5 9, 19 15, 19 6"/><path d="M12 12 L17 9" opacity="0.6"/>'
                        '<circle cx="17.5" cy="8.5" r="1.2"/><rect x="3.5" y="17.5" width="3" height="3"/>'
                        '<rect x="17.5" y="3.5" width="3" height="3"/>',
    "ferramenta_bezier": '<path d="M4 20 C 9 20, 9 9, 13 9 S 17 4, 20 4"/><path d="M14.5 19.5 L19.5 14.5 L18 13 L13 18 L12.5 20 Z"/>',
    "ferramenta_linha": '<path d="M5 19 L19 5"/><circle cx="5" cy="19" r="1.5"/><circle cx="19" cy="5" r="1.5"/>',
    "ferramenta_mao_livre": '<path d="M4 17 C 6 9, 9 9, 10 13 S 14 18, 16 12 S 19 6, 20 6"/>',
    "ferramenta_elipse": '<ellipse cx="12" cy="12" rx="8" ry="6.5"/>',
    "ferramenta_poligono": '<path d="M12 3.5 L19.5 8 V16 L12 20.5 L4.5 16 V8 Z"/>',
    "ferramenta_texto": '<path d="M5 7 V5 H19 V7 M12 5 V19 M9.5 19 H14.5"/>',
    "ferramenta_tabela": '<rect x="3.5" y="4.5" width="17" height="15" rx="1.5"/><path d="M3.5 9.5 H20.5 M3.5 14.5 H20.5 M9.5 4.5 V19.5"/>',
    "ferramenta_simbolo": '<path d="M8.5 18 V6 M5.5 9 L8.5 6 L11.5 9 M15.5 18 V6 M12.5 9 L15.5 6 L18.5 9 M4 20.5 H20"/>',
    "cota_horizontal": '<path d="M4 7 V17 M20 7 V17 M4 12 H20 M6.5 9.5 L4 12 L6.5 14.5 M17.5 9.5 L20 12 L17.5 14.5"/>',
    "cota_vertical": '<path d="M7 4 H17 M7 20 H17 M12 4 V20 M9.5 6.5 L12 4 L14.5 6.5 M9.5 17.5 L12 20 L14.5 17.5"/>',
    "cota_paralela": '<path d="M5 15 L15 5 M9 19 L19 9 M7 17 L17 7"/><path d="M7.5 14 L7 17 L10 16.5 M14 7.5 L17 7 L16.5 10"/>',
    "cota_angular": '<path d="M4 20 H20 M4 20 L16 6"/><path d="M12 20 A8 8 0 0 0 9.4 13.8"/>',
    "ferramenta_callout": '<path d="M5 4.5 H19 A1.5 1.5 0 0 1 20.5 6 V14 A1.5 1.5 0 0 1 19 15.5 H11 L7 19.5 V15.5 H5 '
                          'A1.5 1.5 0 0 1 3.5 14 V6 A1.5 1.5 0 0 1 5 4.5 Z"/><path d="M8 9 H16 M8 12 H13"/>',
    "ferramenta_transparencia": '<path d="M12 4 L20 8 L12 12 L4 8 Z"/><path d="M4 12 L12 16 L20 12"/><path d="M4 16 L12 20 L20 16"/>',
    "conta_gotas": '<path d="M13.5 7.5 L16.5 4.5 A2.1 2.1 0 0 1 19.5 7.5 L16.5 10.5"/><path d="M12 6 L18 12"/>'
                   '<path d="M15 9 L7 17 L5 17.5 L4 20 L6.5 19 L7 17"/>',
    "ferramenta_imagem": '<rect x="3.5" y="4.5" width="17" height="15" rx="1.5"/><circle cx="9" cy="9.5" r="1.8"/>'
                         '<path d="M3.5 17 L9 12.5 L13 15.5 L16 13 L20.5 16.5"/>',
    "ferramenta_logo": '<path d="M4.5 19.5 L10 5 H14 L19.5 19.5"/><path d="M7.5 13.5 H16.5"/><path d="M12 5 V9"/>',
    # ── Cartões de estilo da tela de Início ─────────────────────────
    "caixa_maleta": '<path d="M4 8 L12 4 L20 8 V16 L12 20 L4 16 Z"/><path d="M4 8 L12 12 L20 8 M12 12 V20"/>',
    "caixa_transpassada": '<path d="M4 8 L12 4 L20 8 V16 L12 20 L4 16 Z"/><path d="M4 8 L12 12 L20 8 M12 12 V20"/>'
                          '<path d="M8 6 L16 10" stroke-dasharray="2 2"/>',
    "caixa_envoltorio": '<rect x="3" y="7" width="18" height="10" rx="1"/><path d="M8 7 V17 M16 7 V17" stroke-dasharray="2 2"/>',
    "caixa_capa": '<path d="M3 9 H21 L19 17 H5 Z"/><path d="M3 9 L5 7 H19 L21 9"/>',
    # ── Organizar ───────────────────────────────────────────────────
    "agrupar": '<path d="M3 7 V3 H7 M17 3 H21 V7 M21 17 V21 H17 M7 21 H3 V17"/>'
               '<rect x="7" y="7" width="6" height="6" rx="1"/><rect x="11" y="11" width="6" height="6" rx="1"/>',
    "desagrupar": '<rect x="4" y="4" width="7" height="7" rx="1"/><rect x="13" y="13" width="7" height="7" rx="1"/>'
                  '<path d="M15 4 H20 V9 M4 15 V20 H9" stroke-dasharray="2 2.5"/>',
    "converter_curvas": '<path d="M5 18 C 5 9, 19 15, 19 6"/><rect x="3.5" y="17.5" width="3" height="3"/><rect x="17.5" y="3.5" width="3" height="3"/>',
    "combinar": '<rect x="3.5" y="3.5" width="10" height="10" rx="1.5"/><rect x="10.5" y="10.5" width="10" height="10" rx="1.5"/>',
    "separar": '<rect x="3.5" y="3.5" width="8" height="8" rx="1.5"/><rect x="12.5" y="12.5" width="8" height="8" rx="1.5"/>'
               '<path d="M14 6 H18 M16 4 V8" opacity="0.6"/>',
    "trazer_frente": '<rect x="9" y="9" width="11" height="11" rx="1.5"/>'
                     '<path d="M15 5 V4 A1 1 0 0 0 14 3 H4 A1 1 0 0 0 3 4 V14 A1 1 0 0 0 4 15 H5" stroke-dasharray="2 2.5"/>',
    "enviar_tras": '<rect x="4" y="4" width="11" height="11" rx="1.5"/>'
                   '<path d="M9 19 V20 A1 1 0 0 0 10 21 H20 A1 1 0 0 0 21 20 V10 A1 1 0 0 0 20 9 H19" stroke-dasharray="2 2.5"/>',
    # Alinhar objetos (Alinhar e distribuir, alinhar na face, vários selecionados)
    "alinhar_esquerda": '<path d="M4 3 V21"/><rect x="7" y="6" width="12" height="4" rx="1"/><rect x="7" y="14" width="7" height="4" rx="1"/>',
    "alinhar_centro_h": '<path d="M12 3 V21"/><rect x="5" y="6" width="14" height="4" rx="1"/><rect x="8" y="14" width="8" height="4" rx="1"/>',
    "alinhar_direita": '<path d="M20 3 V21"/><rect x="5" y="6" width="12" height="4" rx="1"/><rect x="10" y="14" width="7" height="4" rx="1"/>',
    "alinhar_topo": '<path d="M3 4 H21"/><rect x="6" y="7" width="4" height="12" rx="1"/><rect x="14" y="7" width="4" height="7" rx="1"/>',
    "alinhar_centro_v": '<path d="M3 12 H21"/><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="8" width="4" height="8" rx="1"/>',
    "alinhar_base": '<path d="M3 20 H21"/><rect x="6" y="5" width="4" height="12" rx="1"/><rect x="14" y="10" width="4" height="7" rx="1"/>',
    # Alinhar as linhas de um texto
    "texto_esquerda": '<path d="M4 6 H20 M4 12 H14 M4 18 H18"/>',
    "texto_centro": '<path d="M4 6 H20 M7 12 H17 M5 18 H19"/>',
    "texto_direita": '<path d="M4 6 H20 M10 12 H20 M6 18 H20"/>',
}


def svg(chave: str, cor: str) -> str | None:
    corpo = CORPOS.get(chave)
    if corpo is None:
        return None
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{cor}" '
        f'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">{corpo}</svg>'
    )
