"""Tela do construtor de dieline (ver `construtor_dieline.py`): as medidas,
os trechos da impressora (colunas) e do riscador (linhas) à esquerda; a
faca no meio, onde um clique numa divisa escolhe o tipo dela (vinco, corte,
fenda...) e um clique numa peça escolhe se ela existe; o resumo embaixo
(quantos vincos/cortes/fendas e os metros de cada um)."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..construtor_dieline import MODELOS, TIPOS_DIVISA, Projeto, Trecho, resumir
from ..estilos import Estilo, ErroEstilo, FacaDoEstilo, salvar_estilo
from ..models import TipoLinha
from .dialogo_estilos import pasta_estilos_usuario
from .estilo import FONTE_MONO

_TOLERANCIA_PX = 7.0
_COR_SELECAO = QColor(0, 120, 215)


class _Grade(QWidget):
    """A faca do projeto com a grade por trás; clique escolhe divisa ou peça."""

    escolheu = Signal(object)  # ("divisa", chave) | ("peca", (linha, coluna)) | None

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 380)
        self.setMouseTracking(True)
        self.projeto: Projeto | None = None
        self.faca: FacaDoEstilo | None = None
        self.erro = ""
        self.selecao = None
        self._sobre = None
        self._xs: list[float] = []
        self._ys: list[float] = []
        self._escala = 1.0
        self._origem = QPointF()

    def definir(self, projeto: Projeto, faca: FacaDoEstilo | None, erro: str = "") -> None:
        self.projeto, self.faca, self.erro = projeto, faca, erro
        self._xs, self._ys = [], []
        if faca is not None:
            v = faca.valores
            xs = [0.0] + [v[f"X{i}"] for i in range(1, len(projeto.colunas) + 1)]
            ys = [0.0] + [v[f"Y{j}"] for j in range(1, len(projeto.linhas) + 1)]
            pecas = [(l, c) for l in range(len(ys) - 1) for c in range(len(xs) - 1) if projeto.tem_peca(l, c)]
            # `Estilo.gerar` encosta a faca em (0, 0): a grade anda junto.
            dx = -min((xs[c] for _l, c in pecas), default=0.0)
            dy = -min((ys[l] for l, _c in pecas), default=0.0)
            self._xs = [x + dx for x in xs]
            self._ys = [y + dy for y in ys]
        self.update()

    # ── Coordenadas ──────────────────────────────────────────────────
    def _ajustar_escala(self) -> None:
        if not self._xs:
            return
        largura, altura = self._xs[-1] - self._xs[0] or 1, self._ys[-1] - self._ys[0] or 1
        margem_esq, margem_topo, margem = 70, 34, 20
        self._escala = min((self.width() - margem_esq - margem) / largura, (self.height() - margem_topo - margem) / altura)
        self._origem = QPointF(
            margem_esq + (self.width() - margem_esq - margem - largura * self._escala) / 2 - self._xs[0] * self._escala,
            margem_topo + (self.height() - margem_topo - margem - altura * self._escala) / 2 - self._ys[0] * self._escala,
        )

    def _tela(self, x: float, y: float) -> QPointF:
        return QPointF(self._origem.x() + x * self._escala, self._origem.y() + y * self._escala)

    def item_em(self, pos: QPointF):
        """Divisa entre duas peças mais perto do ponto, ou a peça debaixo dele."""
        if self.projeto is None or not self._xs:
            return None
        self._ajustar_escala()
        x = (pos.x() - self._origem.x()) / self._escala
        y = (pos.y() - self._origem.y()) / self._escala
        tol = _TOLERANCIA_PX / self._escala
        melhor, dist = None, tol
        n, m = len(self._xs) - 1, len(self._ys) - 1
        for i in range(1, n):
            for l in range(m):
                if self._ys[l] <= y <= self._ys[l + 1] and abs(x - self._xs[i]) < dist and self.projeto.divisa_entre_pecas(("v", i, l)):
                    melhor, dist = ("divisa", ("v", i, l)), abs(x - self._xs[i])
        for j in range(1, m):
            for c in range(n):
                if self._xs[c] <= x <= self._xs[c + 1] and abs(y - self._ys[j]) < dist and self.projeto.divisa_entre_pecas(("h", j, c)):
                    melhor, dist = ("divisa", ("h", j, c)), abs(y - self._ys[j])
        if melhor is not None:
            return melhor
        for l in range(m):
            for c in range(n):
                if self._xs[c] <= x <= self._xs[c + 1] and self._ys[l] <= y <= self._ys[l + 1]:
                    return ("peca", (l, c))
        return None

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.LeftButton:
            self.selecao = self.item_em(evento.position())
            self.escolheu.emit(self.selecao)
            self.update()

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802
        sobre = self.item_em(evento.position())
        if sobre != self._sobre:
            self._sobre = sobre
            self.setCursor(Qt.CursorShape.PointingHandCursor if sobre else Qt.CursorShape.ArrowCursor)
            self.update()

    def leaveEvent(self, _evento) -> None:  # noqa: N802
        self._sobre = None
        self.update()

    # ── Desenho ──────────────────────────────────────────────────────
    def _segmento(self, item) -> tuple[QPointF, QPointF] | None:
        if not item or item[0] != "divisa":
            return None
        orient, k, outro = item[1]
        if orient == "v":
            return self._tela(self._xs[k], self._ys[outro]), self._tela(self._xs[k], self._ys[outro + 1])
        return self._tela(self._xs[outro], self._ys[k]), self._tela(self._xs[outro + 1], self._ys[k])

    def _retangulo(self, peca) -> QRectF:
        l, c = peca
        return QRectF(self._tela(self._xs[c], self._ys[l]), self._tela(self._xs[c + 1], self._ys[l + 1]))

    def paintEvent(self, _evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(250, 250, 248))
        if self.faca is None or self.projeto is None or not self._xs:
            p.setPen(QColor(170, 40, 40))
            p.drawText(self.rect().adjusted(16, 16, -16, -16), Qt.TextFlag.TextWordWrap, self.erro or "Sem faca.")
            return
        self._ajustar_escala()
        projeto = self.projeto
        fonte = QFont(FONTE_MONO)
        fonte.setPixelSize(11)
        p.setFont(fonte)

        # Peças: papel; refugo: hachurado.
        for l in range(len(self._ys) - 1):
            for c in range(len(self._xs) - 1):
                r = self._retangulo((l, c))
                if projeto.tem_peca(l, c):
                    p.fillRect(r, QColor(236, 222, 198))
                else:
                    p.fillRect(r, QBrush(QColor(200, 200, 200), Qt.BrushStyle.BDiagPattern))
        base = projeto.base if projeto.base is not None and projeto.tem_peca(*projeto.base) else projeto._base_padrao()
        if base is not None:
            r = self._retangulo(base)
            p.setPen(QColor(120, 95, 60))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "base (3D)")

        # A grade inteira, fininha, pra ver onde cada trecho começa.
        p.setPen(QPen(QColor(0, 0, 0, 28), 1, Qt.PenStyle.DotLine))
        for x in self._xs:
            p.drawLine(self._tela(x, self._ys[0]), self._tela(x, self._ys[-1]))
        for y in self._ys:
            p.drawLine(self._tela(self._xs[0], y), self._tela(self._xs[-1], y))

        # A faca de verdade.
        corte = QPen(QColor(25, 25, 25), 1.6)
        vinco = QPen(QColor(200, 30, 30), 1.4, Qt.PenStyle.DashLine)
        outra = QPen(QColor(30, 110, 200), 1.4, Qt.PenStyle.DashDotLine)
        for linha in self.faca.linhas:
            p.setPen(vinco if linha.tipo == TipoLinha.VINCO else corte if linha.tipo == TipoLinha.CORTE else outra)
            p.drawLine(self._tela(linha.x1, linha.y1), self._tela(linha.x2, linha.y2))

        # Nomes e medidas dos trechos: colunas em cima, linhas à esquerda.
        p.setPen(QColor(60, 60, 60))
        for c, trecho in enumerate(projeto.colunas):
            a, b = self._tela(self._xs[c], self._ys[0]), self._tela(self._xs[c + 1], self._ys[0])
            texto = f"{trecho.nome} {self._xs[c + 1] - self._xs[c]:g}"
            p.drawText(QRectF(a.x(), a.y() - 26, b.x() - a.x(), 20), Qt.AlignmentFlag.AlignCenter, texto)
        for l, trecho in enumerate(projeto.linhas):
            a, b = self._tela(self._xs[0], self._ys[l]), self._tela(self._xs[0], self._ys[l + 1])
            texto = f"{trecho.nome}\n{self._ys[l + 1] - self._ys[l]:g}"
            p.drawText(QRectF(a.x() - 66, a.y(), 60, b.y() - a.y()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, texto)

        # Seleção e o que está sob o mouse.
        for item, cor, largura in ((self._sobre, QColor(0, 120, 215, 90), 6), (self.selecao, _COR_SELECAO, 4)):
            if not item:
                continue
            seg = self._segmento(item)
            if seg:
                p.setPen(QPen(cor, largura, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(*seg)
            elif item[0] == "peca":
                p.setPen(QPen(cor, 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(self._retangulo(item[1]).adjusted(2, 2, -2, -2))


class _TabelaTrechos(QTableWidget):
    def __init__(self, cabecalhos: list[str], parent=None) -> None:
        super().__init__(0, len(cabecalhos), parent)
        self.setHorizontalHeaderLabels(cabecalhos)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setMinimumHeight(110)


class DialogoConstrutorDieline(QDialog):
    """Depois de "Usar na faca": `estilo`, `valores` e `faca` prontos pra
    `JanelaPrincipal.aplicar_estilo`."""

    def __init__(self, parent=None, projeto: Projeto | None = None, pasta_estilos: Path | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Construtor de dieline")
        self.resize(1240, 720)
        self.pasta_estilos = pasta_estilos or pasta_estilos_usuario()
        self.projeto = projeto or MODELOS["Maleta (Aba | L | C | L | C)"]()
        self.caminho: Path | None = None  # arquivo do estilo, quando veio do catálogo
        self.estilo: Estilo | None = None
        self.valores: dict[str, float] = {}
        self.faca: FacaDoEstilo | None = None
        self._montando = False

        raiz = QVBoxLayout(self)
        divisao = QSplitter(Qt.Orientation.Horizontal)
        raiz.addWidget(divisao, 1)

        # ── Esquerda: nome, modelo, medidas, trechos ──
        esquerda = QWidget()
        col = QVBoxLayout(esquerda)
        col.setContentsMargins(0, 0, 6, 0)
        linha_inicio = QHBoxLayout()
        self.combo_inicio = QComboBox()
        self._preencher_inicios()
        self.combo_inicio.setCurrentIndex(max(0, self.combo_inicio.findData(("modelo", "Maleta (Aba | L | C | L | C)"))))
        botao_inicio = QPushButton("Começar deste")
        botao_inicio.clicked.connect(self._comecar_de)
        linha_inicio.addWidget(self.combo_inicio, 1)
        linha_inicio.addWidget(botao_inicio)
        col.addLayout(linha_inicio)
        self.campo_nome = QLineEdit()
        self.campo_nome.setPlaceholderText("Nome da faca")
        self.campo_nome.textEdited.connect(lambda t: setattr(self.projeto, "nome", t))
        form_nome = QFormLayout()
        form_nome.addRow("Nome:", self.campo_nome)
        col.addLayout(form_nome)

        caixa_medidas = QGroupBox("Medidas (variáveis das fórmulas)")
        lay = QVBoxLayout(caixa_medidas)
        self.tabela_medidas = _TabelaTrechos(["Nome", "Descrição", "Valor"])
        self.tabela_medidas.setToolTip("Os nomes valem nas fórmulas dos trechos (C, L, A, E...). O valor é o padrão da faca.")
        self.tabela_medidas.itemChanged.connect(self._medidas_editadas)
        lay.addWidget(self.tabela_medidas)
        lay.addLayout(self._botoes_tabela(self._nova_medida, self._remover_medida))
        col.addWidget(caixa_medidas)

        caixa_colunas = QGroupBox("Impressora (colunas, da esquerda pra direita)")
        lay = QVBoxLayout(caixa_colunas)
        self.tabela_colunas = _TabelaTrechos(["Trecho", "Medida (fórmula)"])
        self.tabela_colunas.itemChanged.connect(lambda _i: self._trechos_editados(self.tabela_colunas, self.projeto.colunas))
        lay.addWidget(self.tabela_colunas)
        lay.addLayout(self._botoes_tabela(lambda: self._novo_trecho("coluna"), lambda: self._remover_trecho("coluna")))
        col.addWidget(caixa_colunas)

        caixa_linhas = QGroupBox("Riscador (linhas, de cima pra baixo)")
        lay = QVBoxLayout(caixa_linhas)
        self.tabela_linhas = _TabelaTrechos(["Trecho", "Medida (fórmula)"])
        self.tabela_linhas.itemChanged.connect(lambda _i: self._trechos_editados(self.tabela_linhas, self.projeto.linhas))
        lay.addWidget(self.tabela_linhas)
        lay.addLayout(self._botoes_tabela(lambda: self._novo_trecho("linha"), lambda: self._remover_trecho("linha")))
        col.addWidget(caixa_linhas)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setWidget(esquerda)
        rolagem.setMinimumWidth(340)
        divisao.addWidget(rolagem)

        # ── Meio: a faca ──
        meio = QWidget()
        col_meio = QVBoxLayout(meio)
        col_meio.setContentsMargins(6, 0, 6, 0)
        dica = QLabel("Clique numa divisa pra escolher vinco, corte, fenda… · clique numa peça pra tirar ou pôr")
        dica.setWordWrap(True)
        col_meio.addWidget(dica)
        self.grade = _Grade()
        self.grade.escolheu.connect(self._mostrar_selecao)
        col_meio.addWidget(self.grade, 1)
        self.resumo = QLabel()
        self.resumo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.resumo.setWordWrap(True)
        col_meio.addWidget(self.resumo)
        divisao.addWidget(meio)

        # ── Direita: o que está selecionado ──
        direita = QWidget()
        self.col_selecao = QVBoxLayout(direita)
        self.col_selecao.setContentsMargins(6, 0, 0, 0)
        self.titulo_selecao = QLabel()
        self.titulo_selecao.setStyleSheet("font-weight: 700;")
        self.titulo_selecao.setWordWrap(True)
        self.col_selecao.addWidget(self.titulo_selecao)
        self.form_selecao = QFormLayout()
        self.col_selecao.addLayout(self.form_selecao)
        self.col_selecao.addStretch(1)
        direita.setMinimumWidth(240)
        divisao.addWidget(direita)
        divisao.setSizes([360, 640, 240])

        # ── Botões ──
        botoes = QHBoxLayout()
        self.aviso = QLabel()
        self.aviso.setStyleSheet("color: #b02020;")
        self.aviso.setWordWrap(True)
        botoes.addWidget(self.aviso, 1)
        self.botao_salvar = QPushButton("Salvar no catálogo")
        self.botao_salvar.setToolTip("Guarda como estilo: aparece no catálogo (Ctrl+Shift+N) e reabre aqui pra editar")
        self.botao_salvar.clicked.connect(self.salvar)
        self.botao_usar = QPushButton("Usar na faca")
        self.botao_usar.setDefault(True)
        self.botao_usar.clicked.connect(self._usar)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.reject)
        for b in (self.botao_salvar, self.botao_usar, fechar):
            botoes.addWidget(b)
        raiz.addLayout(botoes)

        self._carregar_projeto(self.projeto)

    # ── Montagem das tabelas ─────────────────────────────────────────
    def _botoes_tabela(self, ao_mais, ao_menos) -> QHBoxLayout:
        linha = QHBoxLayout()
        mais, menos = QPushButton("+ Adicionar"), QPushButton("− Tirar")
        mais.setToolTip("Entra depois da linha selecionada (ou no fim)")
        mais.clicked.connect(ao_mais)
        menos.clicked.connect(ao_menos)
        linha.addWidget(mais)
        linha.addWidget(menos)
        linha.addStretch(1)
        return linha

    def _preencher_inicios(self) -> None:
        self.combo_inicio.clear()
        for nome in MODELOS:
            self.combo_inicio.addItem(f"Modelo: {nome}", ("modelo", nome))
        if self.pasta_estilos.is_dir():
            for arquivo in sorted(self.pasta_estilos.glob("*.json")):
                try:
                    dados = json.loads(arquivo.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(dados, dict) and "construtor" in dados:
                    self.combo_inicio.addItem(f"Meu: {dados.get('nome', arquivo.stem)}", ("arquivo", str(arquivo)))

    def _comecar_de(self) -> None:
        tipo, valor = self.combo_inicio.currentData()
        if tipo == "modelo":
            self.caminho = None
            self._carregar_projeto(MODELOS[valor]())
        else:
            self.abrir_arquivo(Path(valor))

    def abrir_arquivo(self, caminho: Path) -> None:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        self.caminho = caminho
        self._carregar_projeto(Projeto.de_dict(dados["construtor"]))

    def _carregar_projeto(self, projeto: Projeto) -> None:
        self.projeto = projeto
        self._montando = True
        self.campo_nome.setText(projeto.nome)
        self.tabela_medidas.setRowCount(0)
        for v in projeto.variaveis:
            self._linha_tabela(self.tabela_medidas, [v["nome"], v.get("rotulo", v["nome"]), f"{float(v.get('padrao', 0)):g}"])
        for tabela, trechos in ((self.tabela_colunas, projeto.colunas), (self.tabela_linhas, projeto.linhas)):
            tabela.setRowCount(0)
            for t in trechos:
                self._linha_tabela(tabela, [t.nome, t.medida])
        self._montando = False
        self.grade.selecao = None
        self._mostrar_selecao(None)
        self.atualizar()

    @staticmethod
    def _linha_tabela(tabela: QTableWidget, textos: list[str], indice: int | None = None) -> None:
        linha = tabela.rowCount() if indice is None else indice
        tabela.insertRow(linha)
        for c, texto in enumerate(textos):
            tabela.setItem(linha, c, QTableWidgetItem(texto))

    # ── Edição das tabelas ───────────────────────────────────────────
    def _medidas_editadas(self, _item=None) -> None:
        if self._montando:
            return
        variaveis = []
        for r in range(self.tabela_medidas.rowCount()):
            nome = (self.tabela_medidas.item(r, 0).text() if self.tabela_medidas.item(r, 0) else "").strip()
            if not nome:
                continue
            rotulo = self.tabela_medidas.item(r, 1).text() if self.tabela_medidas.item(r, 1) else nome
            try:
                valor = float((self.tabela_medidas.item(r, 2).text() if self.tabela_medidas.item(r, 2) else "0").replace(",", "."))
            except ValueError:
                valor = 0.0
            anterior = next((v for v in self.projeto.variaveis if v["nome"] == nome), {})
            variaveis.append({**anterior, "nome": nome, "rotulo": rotulo, "padrao": valor})
        self.projeto.variaveis = variaveis
        self.atualizar()

    def _nova_medida(self) -> None:
        nome, ok = QInputDialog.getText(self, "Nova medida", "Nome (uma letra ou palavra, sem espaço — ex.: G, Aba, Fenda):")
        nome = nome.strip()
        if not ok or not nome:
            return
        if not nome.isidentifier():
            QMessageBox.warning(self, "Nova medida", "Use só letras, números e _ (começando com letra).")
            return
        self._montando = True
        self._linha_tabela(self.tabela_medidas, [nome, nome, "10"])
        self._montando = False
        self._medidas_editadas()

    def _remover_medida(self) -> None:
        linha = self.tabela_medidas.currentRow()
        if linha >= 0:
            self.tabela_medidas.removeRow(linha)
            self._medidas_editadas()

    def _trechos_editados(self, tabela: QTableWidget, trechos: list[Trecho]) -> None:
        if self._montando:
            return
        for r in range(tabela.rowCount()):
            nome = tabela.item(r, 0).text() if tabela.item(r, 0) else ""
            medida = (tabela.item(r, 1).text() if tabela.item(r, 1) else "0").strip().replace(",", ".") or "0"
            if r < len(trechos):
                trechos[r].nome, trechos[r].medida = nome, medida
        self.atualizar()

    def _novo_trecho(self, eixo: str) -> None:
        tabela = self.tabela_colunas if eixo == "coluna" else self.tabela_linhas
        atual = tabela.currentRow()
        indice = (atual + 1) if atual >= 0 else tabela.rowCount()
        trecho = Trecho("Novo", "50")
        if eixo == "coluna":
            self.projeto.inserir_coluna(indice, trecho)
        else:
            self.projeto.inserir_linha(indice, trecho)
        self._montando = True
        self._linha_tabela(tabela, [trecho.nome, trecho.medida], indice)
        self._montando = False
        tabela.setCurrentCell(indice, 1)
        self.grade.selecao = None
        self._mostrar_selecao(None)
        self.atualizar()

    def _remover_trecho(self, eixo: str) -> None:
        tabela = self.tabela_colunas if eixo == "coluna" else self.tabela_linhas
        indice = tabela.currentRow()
        if indice < 0 or tabela.rowCount() <= 1:
            return
        if eixo == "coluna":
            self.projeto.remover_coluna(indice)
        else:
            self.projeto.remover_linha(indice)
        tabela.removeRow(indice)
        self.grade.selecao = None
        self._mostrar_selecao(None)
        self.atualizar()

    # ── Faca e resumo ────────────────────────────────────────────────
    def atualizar(self) -> None:
        try:
            faca = self.projeto.gerar()
        except (ErroEstilo, KeyError, ValueError) as exc:
            self.faca = None
            self.grade.definir(self.projeto, None, str(exc))
            self.aviso.setStyleSheet("color: #b02020;")
            self.aviso.setText(str(exc))
            self.resumo.setText("")
            self.botao_usar.setEnabled(False)
            self.botao_salvar.setEnabled(False)
            return
        self.faca = faca
        self.aviso.setText("")
        self.botao_usar.setEnabled(True)
        self.botao_salvar.setEnabled(True)
        self.grade.definir(self.projeto, faca)
        r = resumir(self.projeto, faca)
        self.resumo.setText(
            f"<b>Chapa {r.largura:.1f} × {r.altura:.1f} mm</b> · "
            f"<span style='color:#c81e1e'>{r.vincos} vincos ({r.metros_vinco:.2f} m)</span> · "
            f"{r.cortes} cortes ({r.metros_corte:.2f} m) · {r.fendas} fendas"
            + (f" · {r.outros} outras linhas" if r.outros else "")
        )

    # ── Seleção (painel da direita) ──────────────────────────────────
    def _limpar_form(self) -> None:
        while self.form_selecao.rowCount():
            self.form_selecao.removeRow(0)

    def _mostrar_selecao(self, item) -> None:
        self._limpar_form()
        if not item:
            self.titulo_selecao.setText("Clique numa divisa ou numa peça da faca.")
            return
        if item[0] == "divisa":
            self._form_divisa(item[1])
        else:
            self._form_peca(item[1])

    def _form_divisa(self, chave) -> None:
        orient, k, outro = chave
        p = self.projeto
        if orient == "v":
            nome = f"Entre {p.colunas[k - 1].nome} e {p.colunas[k].nome} (no trecho {p.linhas[outro].nome})"
        else:
            nome = f"Entre {p.linhas[k - 1].nome} e {p.linhas[k].nome} (no trecho {p.colunas[outro].nome})"
        self.titulo_selecao.setText(nome)
        d = p.divisa(chave)
        combo = QComboBox()
        for tipo, rotulo in TIPOS_DIVISA.items():
            if tipo == "fenda" and orient == "h":
                continue  # fenda separa abas lado a lado
            combo.addItem(rotulo, tipo)
        combo.setCurrentIndex(max(0, combo.findData(d.tipo)))
        self.form_selecao.addRow("Tipo:", combo)

        angulo = QDoubleSpinBox()
        angulo.setRange(-180, 180)
        angulo.setSuffix("°")
        angulo.setValue(d.angulo)
        angulo.setToolTip("Quanto dobra no 3D (90° = parede em pé; 180° = dobra de volta, como parede dupla)")
        ordem = QSpinBox()
        ordem.setRange(1, 20)
        ordem.setValue(d.ordem)
        ordem.setToolTip("Ordem de montagem: os vincos de ordem 1 dobram primeiro, depois os de 2…")
        largura = QLineEdit(d.largura)
        largura.setToolTip("Largura da fenda em mm (pode ser fórmula, ex.: E + 2)")
        self.form_selecao.addRow("Dobra:", angulo)
        self.form_selecao.addRow("Ordem:", ordem)
        self.form_selecao.addRow("Largura da fenda:", largura)
        replicar = QCheckBox("Aplicar nas iguais desta linha")
        replicar.setToolTip(
            "Vale também pras outras divisas desta mesma linha (entre os mesmos dois trechos) que eram do mesmo tipo "
            "— ex.: todas as fendas entre L e C, sem mexer no vinco da parede"
        )
        grupo = {"tipo": d.tipo}  # o tipo que as "iguais" têm agora
        self.form_selecao.addRow(replicar)

        def visiveis() -> None:
            tipo = combo.currentData()
            for campo, mostrar in ((angulo, tipo == "vinco"), (ordem, tipo == "vinco"), (largura, tipo == "fenda")):
                campo.setVisible(mostrar)
                self.form_selecao.labelForField(campo).setVisible(mostrar)

        def aplicar() -> None:
            chaves = [chave]
            if replicar.isChecked():
                total = len(p.linhas) if orient == "v" else len(p.colunas)
                chaves = [
                    (orient, k, o) for o in range(total)
                    if p.divisa_entre_pecas((orient, k, o)) and ((orient, k, o) == chave or p.divisa((orient, k, o)).tipo == grupo["tipo"])
                ]
            for ch in chaves:
                alvo = p.divisa(ch)
                alvo.tipo = combo.currentData()
                alvo.angulo = angulo.value()
                alvo.ordem = ordem.value()
                alvo.largura = largura.text().strip().replace(",", ".") or "5"
            grupo["tipo"] = combo.currentData()
            visiveis()
            self.atualizar()

        combo.currentIndexChanged.connect(lambda _i: aplicar())
        angulo.valueChanged.connect(lambda _v: aplicar())
        ordem.valueChanged.connect(lambda _v: aplicar())
        largura.editingFinished.connect(aplicar)
        replicar.toggled.connect(lambda marcado: marcado and aplicar())
        visiveis()

    def _form_peca(self, peca) -> None:
        l, c = peca
        p = self.projeto
        self.titulo_selecao.setText(f"Peça {p.colunas[c].nome} × {p.linhas[l].nome}")
        existe = QCheckBox("Tem peça aqui (desmarcado = refugo)")
        existe.setChecked(p.tem_peca(l, c))
        self.form_selecao.addRow(existe)

        def trocar(marcado: bool) -> None:
            if marcado:
                p.refugo.discard(peca)
            else:
                p.refugo.add(peca)
                if p.base == peca:
                    p.base = None
            self.atualizar()
            self._mostrar_selecao(("peca", peca))

        existe.toggled.connect(trocar)
        if not p.tem_peca(l, c):
            return
        base = QPushButton("Esta fica parada no 3D" if p.base != peca else "✓ Base do 3D")
        base.setEnabled(p.base != peca)
        base.clicked.connect(lambda: (setattr(p, "base", peca), self.atualizar(), self._mostrar_selecao(("peca", peca))))
        self.form_selecao.addRow(base)
        if c in (0, len(p.colunas) - 1):
            chanfro = QLineEdit(p.chanfros.get(peca, ""))
            chanfro.setPlaceholderText("0")
            chanfro.setToolTip("Corta as quinas de fora em diagonal (aba de cola) — mm ou fórmula, ex.: G / 3")

            def mudar_chanfro() -> None:
                texto = chanfro.text().strip().replace(",", ".")
                if texto and texto != "0":
                    p.chanfros[peca] = texto
                else:
                    p.chanfros.pop(peca, None)
                self.atualizar()

            chanfro.editingFinished.connect(mudar_chanfro)
            self.form_selecao.addRow("Chanfro nas pontas:", chanfro)

    # ── Saída ────────────────────────────────────────────────────────
    def _estilo_pronto(self) -> Estilo | None:
        self.projeto.nome = self.campo_nome.text().strip() or "Minha faca"
        try:
            dados = self.projeto.para_estilo()
            Estilo(dados).gerar()
        except (ErroEstilo, KeyError, ValueError) as exc:
            QMessageBox.warning(self, "Construtor de dieline", f"A faca ainda tem problema:\n{exc}")
            return None
        return Estilo(dados)

    def salvar(self) -> Path | None:
        estilo = self._estilo_pronto()
        if estilo is None:
            return None
        if self.caminho is not None and self.caminho.is_file():
            self.caminho.write_text(json.dumps(estilo.dados, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            self.caminho = salvar_estilo(estilo.dados, self.pasta_estilos)
        self.aviso.setStyleSheet("color: #207020;")
        self.aviso.setText(f"Salvo no catálogo: {self.caminho.name}")
        return self.caminho

    def _usar(self) -> None:
        estilo = self._estilo_pronto()
        if estilo is None:
            return
        self.estilo = estilo
        self.valores = estilo.valores_padrao()
        self.faca = estilo.gerar(self.valores)
        self.accept()
