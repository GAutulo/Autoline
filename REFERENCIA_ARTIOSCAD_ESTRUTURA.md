# Referência ArtiosCAD — estrutura, faca livre e 3D

Complementa `REFERENCIA_FERRAMENTAS_ARTIOSCAD.md` (que cobre as ferramentas
de desenho pontuais). Aqui o foco é o que o usuário pediu: **criar a própria
faca sem ficar preso aos modelos prontos** e **o 3D**.

**Método (sala limpa):** só documentação pública da Esko e material de
divulgação — nada de código, binário, arquivo `.ARD` ou recurso do ArtiosCAD
(a licença proíbe engenharia reversa do programa, e o ArtiosCAD nem está
instalado nesta máquina). Texto resumido com palavras próprias.

**Fontes:**
- [Descrição dos módulos do ArtiosCAD (Esko, 2015)](https://www.bgt.com.ua/resources/PDF/ArtiosCAD_Modules_Description.pdf)
- [Manual 14.1 — Ferramentas do 3D](https://docs.esko.com/docs/en-us/artioscad/14.1/userguide/en-us/common/ac/topic/UG5_Artios-3D_id873224U3D24.html) e [Mudar a face base](https://docs.esko.com/docs/en-us/artioscad/14.1/userguide/en-us/common/ac/topic/UG5_Artios-3D_id873365U3D24.html)
- [Studio Toolkit for Boxes — dobrar arquivo ArtiosCAD](https://docs.esko.com/docs/fr-fr/studiotoolkitforboxes/12/userguide/fr-fr/common/stb/task/ta_fold_artioscad_file.html)
- [Notas de versão 25.07](https://docs.esko.com/docs/en-us/artioscad/25.07/whatsnew/ArtiosCAD%2025.07%20Release%20Notes.pdf), [18.1.1](https://docs.esko.com/docs/en-us/artioscad/18.1/otherdocs/ArtiosCAD%2018.1.1%20Release%20Notes.pdf) e [Novidades 23.07](https://docs.esko.com/docs/en-us/artioscad/23.07/whatsnew/ArtiosCAD%2023.07%20Whats%20New.pdf)
- [Guia de instalação do ArtiosCAD Enterprise 14.1 — design paramétrico](https://docs.esko.com/docs/en-us/artioscadenterprise/14.1/userguide/en-us/common/ac/topic/UG1_Introduction_id307051UON27.html)

---

## 1. Como o ArtiosCAD vira 3D

- **Um clique do 2D pro 3D.** A faca (cortes e vincos) já define tudo: as
  regiões fechadas entre as linhas são as **faces**, e os **vincos são as
  dobradiças** entre faces vizinhas.
- **Face base:** a face que fica parada; todas as outras dobram em volta
  dela. Dá pra trocar ("Change Base Face").
- **Ângulo por vinco:** o ângulo fica guardado em cada vinco da faca. Sem
  ângulo definido, assume **90°** em todos. Ferramentas: *Fold Angle* (um
  vinco), *Fold All* (todos), *Fold 1/2 to Meet* (calcula o ângulo pra duas
  faces se encontrarem). Na 18.1, **duplo clique num vinco dobra 90° / −90°**.
- **Ângulos são lembrados** — alternar entre plano e dobrado é instantâneo,
  e um estilo já dobrado gera faces novas com os ângulos pré-definidos.
- **Medir no dobrado** (folgas e sobreposições), **montagens** de várias
  peças, **animação** gravada passo a passo, exportação (3D PDF, Collada,
  VRML, vídeo). Fibra/onda e lado de dentro/fora são rastreados.
- **Arte no 3D:** a arte registrada na estrutura vai junto pro 3D.

## 2. Desenhar a faca do zero (Designer)

- Geometria com várias ferramentas: linha (com ângulo, comprimento e
  deslocamentos digitados), arco, retângulo; copiar, mover, **aparar,
  dividir, ajustar e esticar**; **linhas de construção** (não cortam nem
  imprimem; estender linha ao infinito e arco em círculo pra ter pontos de
  referência); expressões num teclado na tela.
- **Tipos de linha** (corte, vinco, meio corte, perfurado...), **pontes**
  (bridges) automáticas por fórmula.
- Seleção por atributo e ferramenta *Change* aplicada a toda a seleção;
  cotas e detalhe ampliado.

## 3. Modelos paramétricos (Style Catalog / StyleMaker)

- **Catálogo de estilos** (FEFCO e ECMA — o ECMA completo tem 254 estilos):
  escolhe o estilo, digita as medidas com um **diagrama de documentação**
  na tela, o programa **valida** os valores e gera a faca.
- **Refazer (rebuild)** com outras medidas, papelão ou parâmetros.
- **Criar o próprio estilo:** variáveis com expressões que dependem de
  outras variáveis, condições de validação, variáveis de escolha de estilo
  (lista de opções), menus com diagramas, unidades mm/pol automáticas,
  "Rebuild Playback" pra conferir a construção.

---

## O que o Autoline tem e o plano (um PR por etapa)

| # | Etapa | Situação |
|---|---|---|
| A | **Dobra 3D de qualquer faca**: faces achadas pelas linhas, vincos como dobradiças, face base, 90° padrão, faca editada no 3D | Feito — PR #13 |
| B | **Ângulo por vinco e face base no 3D**: clicar no vinco (90° / −90° / 0°), clicar numa face pra ser a base | Feito — PR #14 |
| C | **Faca livre**: "Faca em branco" começa vazia e é desenhada com as ferramentas da Faca | Feito — PR #14 |
| D | Ferramentas de desenho da faca: retângulo, linha com ângulo/comprimento digitados, paralela (offset), aparar/estender, arco | Depois |
| E | **Estilos paramétricos**: faca definida por variáveis/expressões (C, L, A, espessura), salvar a própria faca como estilo, catálogo FEFCO básico (0201, 0427...) | Depois |
| F | Espessura do papelão no 3D (folga de vinco), fibra/onda | Depois |

Os 6 tipos atuais continuam com a dobra própria deles (sequência de
montagem e abas por baixo), que é melhor que a genérica pra eles; a dobra
genérica entra quando a faca é editada à mão ou desenhada livre.
