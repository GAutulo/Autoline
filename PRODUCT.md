# Product

<!-- impeccable:product-schema 1 -->

## Platform

desktop (Windows, Qt/PySide6)

> Nota: o schema desta skill só prevê `web`, `ios`, `android` ou `adaptive`. Este projeto é um aplicativo desktop nativo (PySide6/Qt), não nenhum desses — registrado aqui como está de fato, não forçado em "web". Isso significa que o detector mecânico web-only (`detect.mjs`) e o modo `live` (iteração em navegador) não se aplicam a este projeto; comandos de julgamento humano (`critique`, `polish`, `colorize`, `typeset`, `layout`, `clarify`, `harden` etc.) seguem aplicáveis, adaptados para convenções de UI desktop/Qt em vez de web.

## Users

Uso interno/pessoal: o próprio usuário (ou sua equipe) usa o Autoline para gerar layouts de caixas de papel para produção própria — não é, hoje, um produto vendido a terceiros.

## Product Purpose

Gera layouts de faca (dieline) para caixas de papel/embalagem e permite montar um mockup visual sobre esse layout (texto, imagens, logotipo vetorial com separação de cor, formas, checklist de cores de impressão). Exporta o resultado para SVG/PDF/JPG e, atualmente, automatiza o CorelDRAW via COM para levar o layout completo (estrutura + mockup) direto para dentro do CorelDRAW.

## Positioning

Alternativa mais acessível e barata que o ArtiosCAD (citado pelo usuário como referência) — que é caro e complexo — e mais focada especificamente em estrutura de caixas de papel do que ferramentas genéricas como o Pacdora. Direção estratégica declarada: reduzir e eventualmente eliminar a dependência do CorelDRAW, construindo nativamente no próprio Autoline as capacidades que hoje dependem da automação COM externa — a integração com CorelDRAW é uma ponte para o fluxo atual, não o destino final do produto.

## Operating Context

Fluxo de produção gráfica de embalagens no Brasil: cálculo de painéis/faces da caixa (`paineis.py`), montagem de mockup sobre o layout, legenda/checklist de cores de tinta para impressão, exportação para arquivos de produção (SVG/PDF/JPG) e, hoje, para o CorelDRAW via automação COM (Windows).

## Capabilities and Constraints

- Requer Windows (constraint de plataforma).
- Não requer CorelDRAW instalado como dependência obrigatória de longo prazo — a automação COM existente é um recurso de ponte; a intenção explícita é que o Autoline não dependa dele no futuro.
- Mercado-alvo: Brasil, interface e nomenclatura em português (PT-BR).
- Motor de mockup (Fase 2) já implementado: seleção/edição de elementos, painéis, texto, formas, imagem PNG, logotipo vetorial com separação de cor, checklist de cores — com propriedades avançadas inspiradas em ArtiosCAD (campos universais de posição/tamanho/rotação, alinhar ao painel, ordem de empilhamento, travar proporção); pendentes: zonas seguras/copy-free, biblioteca de símbolos, desfazer/refazer.

## Brand Commitments

Nome do produto: **Autoline** (rebranding já aplicado nesta sessão anterior). Paleta de marca: Carvão / Kraft / Tinta / Osso, com cor primária assimétrica por tema (kraft puro no tema escuro, kraft escuro no tema claro, ajustada para contraste WCAG). Tipografia: Big Shoulders Stencil (exibição) + IBM Plex (corpo/UI). Ícone e nome do executável já atualizados; repositório no GitHub já renomeado e privado.

## Evidence on Hand

Aplicativo funcional com motor de mockup completo (Fase 2), exportação SVG/PDF/JPG e automação CorelDRAW verificados ao vivo nesta sessão. Não há clientes, depoimentos ou material de imprensa — uso é interno, sem histórico de comercialização até o momento.

## Product Principles

1. Estrutura (dieline) e visual (mockup) vivem na mesma ferramenta, em vez de exigir dois softwares separados (um tipo ArtiosCAD para estrutura, outro tipo Pacdora/CorelDRAW para o visual).
2. Acessibilidade de custo/complexidade é o diferencial central frente ao ArtiosCAD.
3. Independência de software proprietário de terceiros (CorelDRAW) é uma meta de produto de longo prazo, não um detalhe de implementação — funcionalidades novas devem, quando possível, reduzir essa dependência em vez de aprofundá-la.
4. Foco no mercado brasileiro de embalagens de papel, com interface em português.
