"""Linha de "trechos" (Impressora / Riscador) no estilo do sistema de
referência: uma fileira de campos numéricos compactos + um total em
destaque no final.

Cada campo mostra sempre o valor real usado no desenho (nunca um texto
genérico "auto"). Enquanto o usuário não mexe num campo, ele acompanha
automaticamente o valor calculado — assim que o usuário digita algo, o
campo "trava" nesse valor manual até que o botão "Recalcular" da linha
seja usado para voltar ao automático.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_ESTILO_AUTOMATICO = "color: #666;"
_ESTILO_MANUAL = "color: #111; font-weight: 600;"


class LinhaTrechos(QWidget):
    valor_alterado = Signal()

    def __init__(self, titulo: str, rotulos: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._spins: list[QDoubleSpinBox] = []
        self._tocados: list[bool] = []
        self._colunas: list[QWidget] = []

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(2)

        cabecalho = QHBoxLayout()
        label_titulo = QLabel(titulo)
        label_titulo.setStyleSheet("font-weight: 600; color: #333;")
        cabecalho.addWidget(label_titulo)
        cabecalho.addStretch(1)
        self.botao_recalcular = QPushButton("↻ Recalcular")
        self.botao_recalcular.setToolTip(
            "Volta todos os trechos desta linha para o valor automático."
        )
        self.botao_recalcular.setFlat(True)
        self.botao_recalcular.setStyleSheet("color: #1e64b4; text-align: right;")
        self.botao_recalcular.setCursor(Qt.CursorShape.PointingHandCursor)
        self.botao_recalcular.clicked.connect(self._recalcular_tudo)
        cabecalho.addWidget(self.botao_recalcular)
        raiz.addLayout(cabecalho)

        self._linha = QHBoxLayout()
        self._linha.setSpacing(6)
        raiz.addLayout(self._linha)

        for rotulo in rotulos:
            coluna = self._criar_coluna_trecho(rotulo)
            self._linha.addWidget(coluna)

        self._linha.addSpacing(8)
        self._linha.addWidget(self._criar_coluna_total())
        self._linha.addStretch(1)

    # ── Construção ──────────────────────────────────────────────────
    def _criar_coluna_trecho(self, rotulo: str) -> QWidget:
        coluna = QWidget()
        vbox = QVBoxLayout(coluna)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(1)

        lbl = QLabel(rotulo)
        lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lbl.setStyleSheet("font-size: 10px; color: #777;")

        spin = QDoubleSpinBox()
        spin.setRange(0, 100000)
        spin.setDecimals(1)
        spin.setFixedWidth(64)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setStyleSheet(_ESTILO_AUTOMATICO)

        indice = len(self._spins)
        spin.valueChanged.connect(lambda _v, i=indice: self._ao_usuario_editar(i))

        vbox.addWidget(lbl)
        vbox.addWidget(spin)

        self._spins.append(spin)
        self._tocados.append(False)
        self._colunas.append(coluna)
        return coluna

    def _criar_coluna_total(self) -> QWidget:
        coluna = QWidget()
        vbox = QVBoxLayout(coluna)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(1)

        lbl = QLabel("Total")
        lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lbl.setStyleSheet("font-size: 10px; color: #777;")

        self.campo_total = QLabel("0.0")
        self.campo_total.setFixedWidth(70)
        self.campo_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.campo_total.setStyleSheet(
            "font-weight: 700; color: white; background: #1e64b4;"
            "border-radius: 4px; padding: 4px;"
        )

        vbox.addWidget(lbl)
        vbox.addWidget(self.campo_total)
        return coluna

    # ── Interação ───────────────────────────────────────────────────
    def _ao_usuario_editar(self, indice: int) -> None:
        # Só chega aqui em edição real do usuário — atualizações programáticas
        # (ver atualizar_valores_efetivos) usam blockSignals e não disparam isso.
        self._tocados[indice] = True
        self._spins[indice].setStyleSheet(_ESTILO_MANUAL)
        self.valor_alterado.emit()

    def _recalcular_tudo(self) -> None:
        for i in range(len(self._spins)):
            self._tocados[i] = False
        self.valor_alterado.emit()

    # ── API pública ─────────────────────────────────────────────────
    def valores(self) -> list[float]:
        """Valor a enviar pro serviço de cálculo: 0.0 nos trechos que ainda
        estão automáticos (deixa o serviço decidir o padrão), e o valor
        digitado nos que foram editados manualmente."""
        return [
            spin.value() if tocado else 0.0
            for spin, tocado in zip(self._spins, self._tocados)
        ]

    def definir_visiveis(self, quantidade: int) -> None:
        """Mostra só os primeiros `quantidade` trechos (o resto do tipo
        de caixa atual não usa os campos extras) e reseta o estado."""
        for i, coluna in enumerate(self._colunas):
            coluna.setVisible(i < quantidade)
        for i in range(len(self._tocados)):
            self._tocados[i] = False
            self._spins[i].setStyleSheet(_ESTILO_AUTOMATICO)

    def definir_rotulos(self, rotulos: list[str]) -> None:
        for coluna, rotulo in zip(self._colunas, rotulos):
            label = coluna.findChild(QLabel)
            if label is not None:
                label.setText(rotulo)

    def atualizar_valores_efetivos(self, valores_efetivos: list[float]) -> None:
        """Depois de recalcular o layout, mostra o valor real em cada campo
        que ainda está automático — sem mexer nos que foram editados
        manualmente. Usa blockSignals para não confundir isso com edição do
        usuário (o que reativaria o modo manual à toa)."""
        for spin, tocado, valor in zip(self._spins, self._tocados, valores_efetivos):
            if not tocado:
                spin.blockSignals(True)
                spin.setValue(valor)
                spin.setStyleSheet(_ESTILO_AUTOMATICO)
                spin.blockSignals(False)

    def definir_total(self, valor: float) -> None:
        self.campo_total.setText(f"{valor:.1f}")
