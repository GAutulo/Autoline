"""Catálogo de estilos paramétricos (como o Style Catalog do ArtiosCAD):
escolhe o estilo, digita as medidas olhando o diagrama da faca cotada, o
programa valida e gera. Ver `estilos.py`."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..estilos import Estilo, ErroEstilo, FacaDoEstilo, carregar_estilos
from ..models import TipoLinha
from .estilo import FONTE_MONO


def pasta_estilos_usuario() -> Path:
    """Onde ficam os estilos do usuário (um .json por estilo)."""
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base) / "estilos"


class _Diagrama(QWidget):
    """A faca do estilo nas medidas digitadas, com as cotas (C, L, A...)
    — o "diagrama de documentação" do catálogo."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(420, 380)
        self._faca: FacaDoEstilo | None = None
        self._erro = ""

    def definir(self, faca: FacaDoEstilo | None, erro: str = "") -> None:
        self._faca, self._erro = faca, erro
        self.update()

    def paintEvent(self, _evento) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(250, 250, 248))
        if self._faca is None or not self._faca.linhas:
            p.setPen(QColor(170, 40, 40))
            p.drawText(self.rect().adjusted(16, 16, -16, -16), Qt.TextFlag.TextWordWrap, self._erro or "Sem faca.")
            return
        f = self._faca
        xs = [x for l in f.linhas for x in (l.x1, l.x2)] + [x for a, b, _r in f.cotas for x in (a[0], b[0])]
        ys = [y for l in f.linhas for y in (l.y1, l.y2)] + [y for a, b, _r in f.cotas for y in (a[1], b[1])]
        caixa = QRectF(min(xs), min(ys), max(xs) - min(xs) or 1, max(ys) - min(ys) or 1)
        margem = 24
        escala = min((self.width() - 2 * margem) / caixa.width(), (self.height() - 2 * margem) / caixa.height())
        ox = (self.width() - caixa.width() * escala) / 2 - caixa.left() * escala
        oy = (self.height() - caixa.height() * escala) / 2 - caixa.top() * escala

        def tela(x: float, y: float) -> QPointF:
            return QPointF(ox + x * escala, oy + y * escala)

        corte = QPen(QColor(30, 30, 30), 1.2)
        vinco = QPen(QColor(30, 30, 30), 1.0, Qt.PenStyle.DashLine)
        for l in f.linhas:
            p.setPen(vinco if l.tipo in (TipoLinha.VINCO, TipoLinha.DOBRA, TipoLinha.MEIO_CORTE) else corte)
            p.drawLine(tela(l.x1, l.y1), tela(l.x2, l.y2))
        fonte = QFont(FONTE_MONO)
        fonte.setPixelSize(12)
        fonte.setBold(True)
        p.setFont(fonte)
        cor_cota = QColor(0, 110, 200)
        for a, b, rotulo in f.cotas:
            pa, pb = tela(*a), tela(*b)
            p.setPen(QPen(cor_cota, 1.0))
            p.drawLine(pa, pb)
            for ponta in (pa, pb):
                p.drawEllipse(ponta, 2.0, 2.0)
            valor = f.valores.get(rotulo)
            texto = f"{rotulo} = {valor:g}" if valor is not None else rotulo
            meio = (pa + pb) / 2
            largura = p.fontMetrics().horizontalAdvance(texto) + 8
            fundo = QRectF(meio.x() - largura / 2, meio.y() - 9, largura, 18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 255, 255, 235))
            p.drawRoundedRect(fundo, 3, 3)
            p.setPen(cor_cota)
            p.drawText(fundo, Qt.AlignmentFlag.AlignCenter, texto)
            p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QColor(110, 110, 110))
        fonte.setBold(False)
        p.setFont(fonte)
        p.drawText(8, self.height() - 8, f"Faca: {f.largura:.1f} × {f.altura:.1f} mm")


class DialogoEstilos(QDialog):
    """Escolher estilo + medidas. Depois de aceito: `estilo_escolhido`,
    `valores` e `faca` (já gerada e validada)."""

    def __init__(self, parent=None, estilo_inicial: str | None = None, valores_iniciais: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Catálogo de estilos")
        self.resize(980, 600)
        self.estilo_escolhido: Estilo | None = None
        self.valores: dict[str, float] = {}
        self.faca: FacaDoEstilo | None = None
        self._spins: dict[str, QDoubleSpinBox] = {}

        raiz = QVBoxLayout(self)
        divisao = QSplitter(Qt.Orientation.Horizontal)
        raiz.addWidget(divisao, 1)

        esquerda = QWidget()
        col = QVBoxLayout(esquerda)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(QLabel("Estilos"))
        self._lista = QListWidget()
        col.addWidget(self._lista, 1)
        botao_pasta = QPushButton("Abrir pasta dos meus estilos")
        botao_pasta.setToolTip(str(pasta_estilos_usuario()))
        botao_pasta.clicked.connect(self._abrir_pasta)
        col.addWidget(botao_pasta)
        divisao.addWidget(esquerda)

        meio = QWidget()
        col_meio = QVBoxLayout(meio)
        col_meio.setContentsMargins(8, 0, 8, 0)
        self._titulo = QLabel()
        self._titulo.setStyleSheet("font-weight: 700; font-size: 14px;")
        self._titulo.setWordWrap(True)
        col_meio.addWidget(self._titulo)
        self._descricao = QLabel()
        self._descricao.setWordWrap(True)
        col_meio.addWidget(self._descricao)
        self._form = QFormLayout()
        col_meio.addLayout(self._form)
        self._problemas = QLabel()
        self._problemas.setWordWrap(True)
        self._problemas.setStyleSheet("color: rgb(190, 40, 40);")
        col_meio.addWidget(self._problemas)
        col_meio.addStretch(1)
        divisao.addWidget(meio)

        self._diagrama = _Diagrama()
        divisao.addWidget(self._diagrama)
        divisao.setSizes([270, 290, 420])

        self._botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._botoes.button(QDialogButtonBox.StandardButton.Ok).setText("Gerar faca")
        self._botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self._botoes.accepted.connect(self._aceitar)
        self._botoes.rejected.connect(self.reject)
        raiz.addWidget(self._botoes)

        self._estilos = carregar_estilos(pasta_estilos_usuario())
        indice_inicial = 0
        for i, estilo in enumerate(self._estilos):
            item = QListWidgetItem(estilo.nome_exibicao + ("" if estilo.caminho is None else "  (meu)"))
            item.setToolTip(estilo.descricao)
            self._lista.addItem(item)
            if estilo_inicial and estilo.nome_exibicao == estilo_inicial:
                indice_inicial = i
        self._valores_iniciais = dict(valores_iniciais or {})
        self._lista.currentRowChanged.connect(self._escolher)
        self._lista.setCurrentRow(indice_inicial)

    @property
    def estilos(self) -> list[Estilo]:
        return self._estilos

    def _abrir_pasta(self) -> None:
        pasta = pasta_estilos_usuario()
        pasta.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(pasta)))

    def _escolher(self, linha: int) -> None:
        if not (0 <= linha < len(self._estilos)):
            return
        estilo = self._estilos[linha]
        self.estilo_escolhido = estilo
        self._titulo.setText(estilo.nome_exibicao)
        self._descricao.setText(estilo.descricao)
        while self._form.rowCount():
            self._form.removeRow(0)
        self._spins = {}
        anteriores = self._valores_iniciais
        for v in estilo.variaveis:
            spin = QDoubleSpinBox()
            spin.setDecimals(2)
            spin.setRange(float(v.get("min", 0.0)) if "min" in v else -100000.0, float(v.get("max", 100000.0)))
            spin.setSuffix(" mm" if v.get("unidade", "mm") == "mm" else "")
            spin.setValue(float(anteriores.get(v["nome"], v.get("padrao", 0.0))))
            spin.valueChanged.connect(self._atualizar)
            self._form.addRow(v.get("rotulo", v["nome"]) + ":", spin)
            self._spins[v["nome"]] = spin
        self._valores_iniciais = {}  # só vale pro estilo que abriu primeiro
        self._atualizar()

    def _valores_atuais(self) -> dict[str, float]:
        return {nome: spin.value() for nome, spin in self._spins.items()}

    def _atualizar(self) -> None:
        estilo = self.estilo_escolhido
        if estilo is None:
            return
        valores = self._valores_atuais()
        problemas = estilo.validar(valores)
        botao = self._botoes.button(QDialogButtonBox.StandardButton.Ok)
        if problemas:
            self._problemas.setText("\n".join(problemas))
            self._diagrama.definir(None, "\n".join(problemas))
            botao.setEnabled(False)
            return
        try:
            faca = estilo.gerar(valores)
        except ErroEstilo as exc:
            self._problemas.setText(str(exc))
            self._diagrama.definir(None, str(exc))
            botao.setEnabled(False)
            return
        self._problemas.setText("")
        self._diagrama.definir(faca)
        botao.setEnabled(True)

    def _aceitar(self) -> None:
        estilo = self.estilo_escolhido
        if estilo is None:
            return
        self.valores = self._valores_atuais()
        try:
            self.faca = estilo.gerar(self.valores)
        except ErroEstilo as exc:
            self._problemas.setText(str(exc))
            return
        self.accept()
