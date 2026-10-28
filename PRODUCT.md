# Product

<!-- impeccable:product-schema 1 -->

## Platform

desktop (Windows, Qt/PySide6)

> Nota: o schema desta skill só prevê `web`, `ios`, `android` ou `adaptive`. Este projeto é um aplicativo desktop nativo (PySide6/Qt), não nenhum desses — registrado aqui como está de fato, não forçado em "web". Isso significa que o detector mecânico web-only (`detect.mjs`) e o modo `live` (iteração em navegador) não se aplicam a este projeto; comandos de julgamento humano (`critique`, `polish`, `colorize`, `typeset`, `layout`, `clarify`, `harden` etc.) seguem aplicáveis, adaptados para convenções de UI desktop/Qt em vez de web.

## Users

Hoje, uso interno: eu e a equipe da Bacaro usamos o Autoline para gerar os layouts das caixas, mandar a folha de aprovação ao cliente e levar o trabalho à produção. O plano comercial é licenciá-lo para gráficas de embalagem de papelão ondulado quando o produto estiver completo; até lá, não é vendido a terceiros.

## Product Purpose

Gera a faca (dieline) de caixas de papelão ondulado: 9 tipos prontos, estilos paramétricos FEFCO, construtor por trechos e faca editável. Sobre ela, monta a arte: texto, checklist e tabela no padrão da máquina, formas, curvas, cotas, imagens, logotipo vetorial com separação de cor e banco de simbologias. Mostra a caixa montada em 3D com a arte e o papelão. Gera as saídas:
- JPG, SVG e PDF;
- a folha de aprovação em PDF, que vai para o cliente;
- o arquivo de projeto `.autoline`.

A ponte COM com o CorelDRAW continua disponível, mas não é mais necessária para fechar um trabalho.

## Positioning

Alternativa mais acessível e barata que o ArtiosCAD (citado pelo usuário como referência) — que é caro e complexo — e mais focada especificamente em estrutura de caixas de papel do que ferramentas genéricas como o Pacdora. Direção estratégica declarada: reduzir e eventualmente eliminar a dependência do CorelDRAW, construindo nativamente no próprio Autoline as capacidades que hoje dependem da automação COM externa — a integração com CorelDRAW é uma ponte para o fluxo atual, não o destino final do produto.

## Operating Context

Fluxo de produção gráfica de embalagens no Brasil. O fluxo é este:
1. Tipo e medidas (em escala 1:10).
2. Faca.
3. Arte por face, com as tintas do trabalho.
4. Conferência no 3D.
5. Folha de aprovação para o cliente.
6. A cada alteração pedida pelo cliente, "Salvar e exportar tudo": projeto, JPG do layout e foto 3D nas pastas da empresa.

Telas usadas numa tela de notebook comum (1366 px), nos temas claro e escuro.

## Capabilities and Constraints

- Requer Windows (constraint de plataforma).
- Não requer CorelDRAW instalado como dependência obrigatória de longo prazo — a automação COM existente é um recurso de ponte; a intenção explícita é que o Autoline não dependa dele no futuro.
- Mercado-alvo: Brasil, interface e nomenclatura em português (PT-BR).
- Caixas desenhadas em escala 1:10. Padrões e mínimos novos têm que caber nessa escala; só a folha de aprovação mostra a medida real.
- Texto novo no padrão da máquina da fábrica: Arial Black, letra de 2 mm, 66,7% de largura.
- O que já foi pendente e hoje existe: zonas seguras (recuo do vinco), banco de simbologias, desfazer/refazer completo, 3D com qualquer faca, arquivo de projeto com recuperação automática.
- Ainda não coberto: cores CMYK/Pantone com separação (hoje são tintas com nome) e mais estilos FEFCO/ECMA.

## Brand Commitments

Nome do produto: **Autoline**. Logotipo "Dobra": o A de duas faces de uma caixa dobrada, com a travessa tracejada como um vinco. Paleta do redesign: grafite em degraus com um único acento âmbar, que é também a face kraft do logotipo; o âmbar muda de tom entre os temas para manter o contraste WCAG. Tipografia: Archivo 700 semi-expandida só na marca e nos títulos de tela, IBM Plex Sans na interface e IBM Plex Mono nas medidas. Detalhes em `DESIGN.md`. O repositório no GitHub é privado.

## Evidence on Hand

Em uso na produção da Bacaro. As folhas de aprovação já saem do Autoline em vez de serem montadas à mão no Corel. Até 27/10/2026 foram 80 PRs e há 344 testes automatizados. Não há clientes externos, depoimentos nem material de imprensa: o uso é interno, sem histórico de comercialização.

## Product Principles

1. Estrutura (dieline) e visual (mockup) vivem na mesma ferramenta, em vez de exigir dois softwares separados (um tipo ArtiosCAD para estrutura, outro tipo Pacdora/CorelDRAW para o visual).
2. Acessibilidade de custo/complexidade é o diferencial central frente ao ArtiosCAD.
3. Independência de software proprietário de terceiros (CorelDRAW) é uma meta de produto de longo prazo, não um detalhe de implementação — funcionalidades novas devem, quando possível, reduzir essa dependência em vez de aprofundá-la.
4. Foco no mercado brasileiro de embalagens de papel, com interface em português.
