# Gerador de Layout de Caixas

Aplicativo desktop (Python + PySide6) para gerar automaticamente o layout
técnico de corte de caixas de papelão — sem depender de nenhum programa
externo (CorelDRAW, Illustrator etc.) para visualizar o resultado.

Este projeto é a reescrita, em Python, de um sistema originalmente feito em
C#/.NET que enviava as linhas técnicas por automação COM para o CorelDRAW.
A lógica de cálculo das medidas foi portada 1:1 (ver `tests/`), e a
visualização agora é nativa do próprio aplicativo.

## Status atual

- [x] Cálculo das medidas técnicas (impressora/riscador) para os 6 tipos de
      caixa suportados (maleta normal, maleta transpassada, envoltórios).
- [x] Pré-visualização 2D nativa, com zoom (roda do mouse) e pan (arrastar) —
      não depende mais de nenhum programa externo para conferir o desenho.
- [x] Legenda de cores de impressão (em tela e nos arquivos exportados).
- [x] Exportação própria em SVG/PDF vetorial e JPG raster (elimina de vez
      a necessidade de qualquer programa de desenho externo).
- [x] Envio do layout pro CorelDRAW por automação COM (igual ao sistema
      original em C#) — conecta numa instância aberta ou abre uma nova,
      e desenha as linhas técnicas direto no documento ativo.
- [x] Interface das telas Dieline e Layout no padrão do CorelDRAW: atalhos
      e gestos, caixa de ferramentas com flyouts, paleta de cores, barra de
      status, "Ajustar a", dockers (Objetos, Alinhar e distribuir,
      Transformações), cotas persistentes e curvas Bézier editáveis por nós
      (ver `REFERENCIA_CORELDRAW.md`).
- [ ] Camada de elementos gráficos (textos, símbolos, logos) posicionáveis
      sobre o layout.
- [ ] Visualização 3D da caixa montada, a partir do mesmo layout 2D.

## Rodando localmente

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

python -m gerador_layout.main       # roda o aplicativo (a partir de src/)
pytest                              # roda os testes
```

> Se `python -m gerador_layout.main` não encontrar o pacote, rode a partir
> da raiz do projeto com `PYTHONPATH=src python -m gerador_layout.main`
> (ou instale o projeto em modo editável: `pip install -e .`).

## Estrutura

```
src/gerador_layout/
├── models.py            # modelos de dados (MedidasCaixa, LayoutCaixa, ...)
├── layout_service.py    # cálculo das linhas técnicas por tipo de caixa
├── main.py               # ponto de entrada do aplicativo
└── ui/
    ├── main_window.py    # janela principal (formulário de medidas)
    ├── preview_canvas.py # canvas 2D (QGraphicsView) com zoom/pan + legenda de cores
    ├── exportacao.py     # exportação para SVG/PDF/JPG
    └── corel_bridge.py   # automação COM com o CorelDRAW (só Windows)
tests/
└── test_layout_service.py
```

## Regras do domínio

- Estrutura da **maleta normal**:
  - Impressora, esquerda → direita: `Aba × L × C × L × C`
  - Riscador, cima → baixo: `(L/2) × A × (L/2)`
- Exemplo para caixa **300 × 200 × 150**:
  - Impressora: `4 × 200 × 300 × 200 × 300`
  - Riscador: `100 × 150 × 100`
- As "medidas geradas/ajustáveis" podem ser alteradas manualmente sem
  alterar as medidas finais **C × L × A** da caixa — isso é regra de UI,
  não do cálculo em si.

## Licença

Ver [LICENSE](LICENSE).
