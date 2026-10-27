"""Janelas de encaixe (dockers) do CorelDRAW na tela de Layout — ver
REFERENCIA_CORELDRAW.md, plano etapa 5:

- **Objetos**: as "camadas" (Arte e Faca) e cada elemento, com
  visibilidade; clicar na lista seleciona no desenho e vice-versa.
- **Alinhar e distribuir**: alinhar entre os selecionados, na face de
  cada um ou na página (chapa); distribuir centros ou espaços.
- **Transformações**: posição, rotação, escala/espelho e tamanho, com o
  campo **Cópias** do CorelDRAW (aplica numa cópia, cumulativamente).

O comportamento segue o CorelDRAW; o desenho dos controles é do Autoline.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .estilo import Cor
from .mockup_icones import construir_icone
from .mockup_itens import ElementoMockup, GrupoMockup
from .mockup_texto import ElementoTexto
from .painel_propriedades_mockup import NOME_TIPO_ELEMENTO

_PAPEL_ELEMENTO = Qt.ItemDataRole.UserRole


def _nome_elemento(el: ElementoMockup) -> str:
    nome = NOME_TIPO_ELEMENTO.get(type(el), "Objeto")
    if isinstance(el, ElementoTexto):
        trecho = el.texto.strip()
        if trecho:
            nome += f" “{trecho[:24]}{'…' if len(trecho) > 24 else ''}”"
    return nome


class DockerObjetos(QWidget):
    """Lista de objetos por camada, de cima (frente) pra baixo (trás),
    como o docker Objetos do CorelDRAW."""

    def __init__(self, canvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._canvas = canvas
        self._sincronizando = False

        self.arvore = QTreeWidget()
        self.arvore.setHeaderHidden(True)
        self.arvore.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.arvore.itemSelectionChanged.connect(self._ao_selecionar_na_lista)
        self.arvore.itemChanged.connect(self._ao_mudar_visibilidade)

        dica = QLabel("Desmarque pra ocultar. Oculto não sai na exportação.")
        dica.setWordWrap(True)
        dica.setStyleSheet(f"color: {Cor.TEXTO_TERCIARIO};")

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(6, 6, 6, 6)
        vbox.addWidget(self.arvore, 1)
        vbox.addWidget(dica)

        # Várias mudanças seguidas (desfazer de um macro, agrupar...)
        # viram uma reconstrução só.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self.reconstruir)
        # Métodos do próprio docker (não lambdas): o Qt desliga sozinho
        # quando o docker é destruído, então nada dispara depois disso.
        canvas.elementos_alterados.connect(self._agendar_reconstrucao)
        canvas.pilha_desfazer.indexChanged.connect(self._agendar_reconstrucao)
        canvas.cena.selectionChanged.connect(self._ao_selecionar_no_desenho)
        self.reconstruir()

    def _agendar_reconstrucao(self, *_args) -> None:
        self._timer.start()

    def reconstruir(self) -> None:
        self._sincronizando = True
        try:
            self.arvore.clear()
            arte = QTreeWidgetItem(["Arte (layout)"])
            arte.setIcon(0, construir_icone("ferramenta_retangulo"))
            arte.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.arvore.addTopLevelItem(arte)
            elementos = sorted(self._canvas.elementos_mockup, key=lambda el: el.zValue(), reverse=True)
            for el in elementos:
                self._adicionar(arte, el)
            faca = QTreeWidgetItem(["Faca (dieline) — travada"])
            faca.setIcon(0, construir_icone("trava"))
            faca.setFlags(Qt.ItemFlag.ItemIsEnabled)
            faca.setToolTip(0, "Corte e vinco vêm das medidas da tela Dieline e não são editáveis aqui.")
            self.arvore.addTopLevelItem(faca)
            self.arvore.expandAll()
        finally:
            self._sincronizando = False
        self._ao_selecionar_no_desenho()

    def _adicionar(self, pai: QTreeWidgetItem, el: ElementoMockup) -> None:
        item = QTreeWidgetItem([_nome_elemento(el)])
        item.setData(0, _PAPEL_ELEMENTO, el)
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
        if el.parentItem() is None:
            flags |= Qt.ItemFlag.ItemIsSelectable  # filho de grupo seleciona pelo grupo
        item.setFlags(flags)
        item.setCheckState(0, Qt.CheckState.Checked if el.isVisible() else Qt.CheckState.Unchecked)
        pai.addChild(item)
        if isinstance(el, GrupoMockup):
            for filho in sorted(el.elementos, key=lambda f: f.zValue(), reverse=True):
                self._adicionar(item, filho)

    def _itens(self):
        pilha = [self.arvore.topLevelItem(i) for i in range(self.arvore.topLevelItemCount())]
        while pilha:
            item = pilha.pop()
            yield item
            pilha.extend(item.child(i) for i in range(item.childCount()))

    def _ao_selecionar_na_lista(self) -> None:
        if self._sincronizando:
            return
        self._sincronizando = True
        try:
            escolhidos = {id(it.data(0, _PAPEL_ELEMENTO)) for it in self.arvore.selectedItems()}
            for el in self._canvas.elementos_mockup:
                el.setSelected(id(el) in escolhidos)
        finally:
            self._sincronizando = False

    def _ao_selecionar_no_desenho(self) -> None:
        if self._sincronizando:
            return
        self._sincronizando = True
        try:
            for item in self._itens():
                el = item.data(0, _PAPEL_ELEMENTO)
                if el is not None and el.parentItem() is None:
                    item.setSelected(el.isSelected())
        finally:
            self._sincronizando = False

    def _ao_mudar_visibilidade(self, item: QTreeWidgetItem, _coluna: int) -> None:
        if self._sincronizando:
            return
        el = item.data(0, _PAPEL_ELEMENTO)
        if el is None:
            return
        visivel = item.checkState(0) == Qt.CheckState.Checked
        el.setVisible(visivel)
        if not visivel:
            el.setSelected(False)


_ALINHAMENTOS = (
    ("alinhar_esquerda", "esquerda", "Esquerda (L)"),
    ("alinhar_centro_h", "centro_h", "Centros na vertical (C)"),
    ("alinhar_direita", "direita", "Direita (R)"),
    ("alinhar_topo", "topo", "Topo (T)"),
    ("alinhar_centro_v", "centro_v", "Centros na horizontal (E)"),
    ("alinhar_base", "base", "Base (B)"),
)


class DockerAlinhar(QWidget):
    """Alinhar e distribuir (Ctrl+Shift+A no CorelDRAW). Uma linha de
    botões por referência — entre os selecionados, na face de cada um, na
    página — em vez de escolher a referência num rádio e depois o botão
    (com um objeto só e "Seleção" marcada, nada acontecia, sem aviso)."""

    REFERENCIAS = (
        ("selecao", "Entre os selecionados", "Selecione 2 ou mais objetos."),
        ("face", "Na face", "Cada objeto na face da caixa em que está."),
        ("pagina", "Na página", "Na chapa inteira."),
    )

    def __init__(self, canvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._canvas = canvas
        self._referencia = "selecao"
        self.setObjectName("conteudoInspetor")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(8)

        self._botoes: dict[str, list[QToolButton]] = {}
        self._dicas: dict[str, QLabel] = {}
        for chave, titulo, dica in self.REFERENCIAS:
            rotulo = QLabel(titulo.upper())
            rotulo.setObjectName("tituloSecaoInspetor")
            vbox.addWidget(rotulo)
            linha = QHBoxLayout()
            linha.setSpacing(4)
            botoes = []
            for icone, alinhamento, texto in _ALINHAMENTOS:
                botao = QToolButton()
                botao.setObjectName("botaoAlinharFace")
                botao.setIcon(construir_icone(icone))
                botao.setToolTip(f"{texto} — {titulo.lower()}")
                botao.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
                botao.clicked.connect(lambda _c=False, r=chave, a=alinhamento: self._alinhar_com(r, a))
                linha.addWidget(botao)
                botoes.append(botao)
            vbox.addLayout(linha)
            self._botoes[chave] = botoes
            texto_dica = QLabel(dica)
            texto_dica.setObjectName("legendaMuted")
            texto_dica.setWordWrap(True)
            vbox.addWidget(texto_dica)
            self._dicas[chave] = texto_dica
            vbox.addSpacing(10)

        rotulo = QLabel("DISTRIBUIR")
        rotulo.setObjectName("tituloSecaoInspetor")
        vbox.addWidget(rotulo)
        grade_dist = QGridLayout()
        grade_dist.setHorizontalSpacing(6)
        grade_dist.setVerticalSpacing(6)
        self._botoes_distribuir: list[QPushButton] = []
        for linha_g, (eixo, rotulo_eixo) in enumerate((("h", "Horizontal"), ("v", "Vertical"))):
            grade_dist.addWidget(QLabel(rotulo_eixo), linha_g, 0)
            for coluna, (modo, texto) in enumerate((("centros", "Centros"), ("espacos", "Espaços")), start=1):
                botao = QPushButton(texto)
                botao.setObjectName(f"distribuir_{eixo}_{modo}")
                botao.clicked.connect(lambda _c=False, e=eixo, m=modo: self._canvas.distribuir(e, m))
                grade_dist.addWidget(botao, linha_g, coluna)
                self._botoes_distribuir.append(botao)
        vbox.addLayout(grade_dist)
        self._dica_distribuir = QLabel("Selecione 3 ou mais objetos.")
        self._dica_distribuir.setObjectName("legendaMuted")
        vbox.addWidget(self._dica_distribuir)
        vbox.addStretch(1)

        canvas.cena.selectionChanged.connect(self._atualizar_estado)
        self._atualizar_estado()

    def _atualizar_estado(self) -> None:
        try:
            n = len([it for it in self._canvas.cena.selectedItems() if isinstance(it, ElementoMockup)])
        except RuntimeError:  # cena já destruída ao fechar
            return
        for chave, botoes in self._botoes.items():
            ativo = n >= 2 if chave == "selecao" else n >= 1
            for botao in botoes:
                botao.setEnabled(ativo)
        self._dicas["selecao"].setVisible(n < 2)
        for botao in self._botoes_distribuir:
            botao.setEnabled(n >= 3)
        self._dica_distribuir.setVisible(n < 3)

    def referencia(self) -> str:
        return self._referencia

    def definir_referencia(self, chave: str) -> None:
        self._referencia = chave

    def _alinhar(self, alinhamento: str) -> None:
        self._alinhar_com(self._referencia, alinhamento)

    def _alinhar_com(self, referencia: str, alinhamento: str) -> None:
        self._referencia = referencia
        self._canvas.alinhar_a(referencia, alinhamento)


def _spin(minimo: float, maximo: float, valor: float, sufixo: str, decimais: int = 2) -> QDoubleSpinBox:
    campo = QDoubleSpinBox()
    campo.setRange(minimo, maximo)
    campo.setDecimals(decimais)
    campo.setValue(valor)
    campo.setSuffix(sufixo)
    return campo


def _escalar_no_centro(el: ElementoMockup, largura: float, altura: float) -> None:
    """Muda o tamanho mantendo o centro parado (a origem de transformação
    do elemento é o centro)."""
    l0, a0 = el.largura, el.altura
    pos = el.pos()
    el.definir_tamanho(largura, altura)
    el.setPos(pos.x() + (l0 - el.largura) / 2, pos.y() + (a0 - el.altura) / 2)


class DockerTransformacoes(QWidget):
    """Transformações (Alt+F7..F10 no CorelDRAW): uma aba por tipo e o
    campo Cópias em todas."""

    ABAS = ("posicao", "rotacao", "escala", "tamanho")

    def __init__(self, canvas, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._canvas = canvas
        self.abas = QTabWidget()

        # Posição: deslocamento relativo, como o padrão do CorelDRAW.
        self.dx = _spin(-10000, 10000, 10.0, " mm")
        self.dy = _spin(-10000, 10000, 0.0, " mm")
        self.abas.addTab(self._form(("Horizontal", self.dx), ("Vertical", self.dy)), "Posição")

        self.angulo = _spin(-360, 360, 90.0, " °")
        self.abas.addTab(self._form(("Ângulo", self.angulo)), "Rotação")

        self.escala_h = _spin(1, 10000, 100.0, " %", 1)
        self.escala_v = _spin(1, 10000, 100.0, " %", 1)
        self.espelhar_h = QCheckBox("Espelhar na horizontal")
        self.espelhar_v = QCheckBox("Espelhar na vertical")
        self.abas.addTab(
            self._form(("Largura", self.escala_h), ("Altura", self.escala_v), ("", self.espelhar_h), ("", self.espelhar_v)),
            "Escala e espelho",
        )

        self.largura = _spin(0.1, 10000, 50.0, " mm")
        self.altura = _spin(0.1, 10000, 50.0, " mm")
        self.abas.addTab(self._form(("Largura", self.largura), ("Altura", self.altura)), "Tamanho")

        self.copias = QSpinBox()
        self.copias.setRange(0, 200)
        self.copias.setToolTip("0 = transforma o próprio objeto; N = cria N cópias, cada uma transformada a partir da anterior")
        botao_aplicar = QPushButton("Aplicar")
        botao_aplicar.setProperty("primario", True)
        botao_aplicar.clicked.connect(self.aplicar)

        rodape = QHBoxLayout()
        rodape.addWidget(QLabel("Cópias"))
        rodape.addWidget(self.copias)
        rodape.addStretch(1)
        rodape.addWidget(botao_aplicar)

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.addWidget(self.abas)
        vbox.addLayout(rodape)
        vbox.addStretch(1)

        canvas.cena.selectionChanged.connect(self._preencher_tamanho)

    @staticmethod
    def _form(*linhas) -> QWidget:
        pagina = QWidget()
        form = QFormLayout(pagina)
        for rotulo, campo in linhas:
            form.addRow(rotulo, campo)
        return pagina

    def mostrar_aba(self, chave: str) -> None:
        self.abas.setCurrentIndex(self.ABAS.index(chave))

    def _preencher_tamanho(self) -> None:
        try:
            selecionados = self._canvas.selecionados_mockup()
        except RuntimeError:
            return  # cena já destruída (fechando a janela)
        if len(selecionados) == 1:
            self.largura.setValue(selecionados[0].largura)
            self.altura.setValue(selecionados[0].altura)

    def aplicar(self) -> None:
        aba = self.ABAS[self.abas.currentIndex()]
        copias = self.copias.value()
        if aba == "posicao":
            dx, dy = self.dx.value(), self.dy.value()
            self._canvas.transformar("Mover", lambda el: el.setPos(el.pos().x() + dx, el.pos().y() + dy), copias)
        elif aba == "rotacao":
            angulo = self.angulo.value()
            self._canvas.transformar("Girar", lambda el: el.setRotation(el.rotation() + angulo), copias)
        elif aba == "escala":
            fh, fv = self.escala_h.value() / 100.0, self.escala_v.value() / 100.0
            esp_h, esp_v = self.espelhar_h.isChecked(), self.espelhar_v.isChecked()

            def escalar(el: ElementoMockup) -> None:
                _escalar_no_centro(el, el.largura * fh, el.altura * fv)
                if esp_h or esp_v:
                    el.definir_espelho(el.espelho_h ^ esp_h, el.espelho_v ^ esp_v)

            self._canvas.transformar("Escalar", escalar, copias)
        else:
            largura, altura = self.largura.value(), self.altura.value()
            self._canvas.transformar("Tamanho", lambda el: _escalar_no_centro(el, largura, altura), copias)
