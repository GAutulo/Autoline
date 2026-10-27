"""Linha de "trechos" (Impressora / Riscador) no estilo do sistema de
referência: um cartão compacto e denso — título, fileira de campos
numéricos e o total, tudo numa única linha (ver `_montar_painel_direito`
em main_window.py pra por que isso importa: era duas linhas por trecho
antes, e a altura extra empurrava a segunda linha pra perto/fora da
borda da janela em tamanhos menores que o maximizado).

Cada campo mostra sempre o valor real usado no desenho (nunca um texto
genérico "auto"). Enquanto o usuário não mexe num campo, ele acompanha
automaticamente o valor calculado — assim que o usuário digita algo, o
campo "trava" nesse valor manual até que o botão "Recalcular" da linha
seja usado para voltar ao automático.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from .estilo import Cor

_ESTILO_AUTOMATICO = f"color: {Cor.TEXTO_SECUNDARIO};"
_ESTILO_MANUAL = f"color: {Cor.TEXTO}; font-weight: 600;"

# Largura mínima (não fixa — texto maior em fontes/DPI diferentes só
# empurra o resto da linha, nunca corta, ver Cor.TEXTO acima) reservada
# pro título, pra "Riscador" e "Impressora" alinharem os campos na mesma
# posição horizontal nas duas linhas.
_LARGURA_MINIMA_TITULO = 76


class LinhaTrechos(QWidget):
    valor_alterado = Signal()

    def __init__(self, titulo: str, rotulos: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("linhaTrechos")

        self._spins: list[QDoubleSpinBox] = []
        self._tocados: list[bool] = []
        self._colunas: list[QWidget] = []

        self._linha = QHBoxLayout(self)
        self._linha.setContentsMargins(10, 6, 8, 6)
        self._linha.setSpacing(6)

        label_titulo = QLabel(titulo)
        label_titulo.setStyleSheet(f"font-weight: 600; color: {Cor.TEXTO};")
        label_titulo.setMinimumWidth(_LARGURA_MINIMA_TITULO)
        self._linha.addWidget(label_titulo)

        for rotulo in rotulos:
            coluna = self._criar_coluna_trecho(rotulo)
            self._linha.addWidget(coluna)

        self._linha.addSpacing(4)
        self._linha.addWidget(self._criar_coluna_total())

        # Esticar aqui (e só aqui) empurra o botão pro canto direito do
        # cartão — como o cartão ocupa a largura toda, "Recalcular" fica
        # na mesma posição em ambas as linhas (Riscador e Impressora),
        # mesmo com quantidades diferentes de campos.
        self._linha.addStretch(1)

        self.botao_recalcular = QPushButton("↻ Recalcular")
        self.botao_recalcular.setToolTip(
            "Volta todos os trechos desta linha para o valor automático."
        )
        self.botao_recalcular.setFlat(True)  # botão pequeno/secundário, mas com fundo ao passar o mouse (ver estilo.py)
        self.botao_recalcular.setStyleSheet(f"color: {Cor.PRIMARIA}; font-weight: 600;")
        self.botao_recalcular.setCursor(Qt.CursorShape.PointingHandCursor)
        self.botao_recalcular.clicked.connect(self._recalcular_tudo)
        self._linha.addWidget(self.botao_recalcular)

    # ── Construção ──────────────────────────────────────────────────
    def _criar_coluna_trecho(self, rotulo: str) -> QWidget:
        # Sem label acima do campo (pedido do usuário: "Sup"/"Centro"/
        # "Inf"/"Aba"/"L"/"C" tiravam espaço e ainda cortavam em telas com
        # DPI diferente) — o nome do trecho vira tooltip no próprio campo,
        # continua acessível, só não ocupa uma linha inteira o tempo todo.
        spin = QDoubleSpinBox()
        spin.setRange(0, 100000)
        spin.setDecimals(1)
        # Sem as setinhas de incrementar/decrementar (ninguém usa clique
        # pra ajustar essa tabela — digita o número ou deixa automático):
        # sem elas, a largura toda vai pro texto.
        spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spin.setFixedSize(64, 24)  # com folga de sobra pro texto — evita cortar em telas de DPI mais alto
        spin.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        spin.setStyleSheet(_ESTILO_AUTOMATICO + "padding: 1px 4px;")
        # `setAlignment` sozinho não é suficiente aqui — com um QSS
        # aplicado, o QDoubleSpinBox volta a centralizar o texto (bug
        # conhecido do Qt: o alinhamento "pega" no widget mas não no
        # QLineEdit interno que de fato desenha o texto). Alinhar
        # também o QLineEdit interno resolve.
        spin.lineEdit().setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        spin.setToolTip(rotulo)

        indice = len(self._spins)
        spin.valueChanged.connect(lambda _v, i=indice: self._ao_usuario_editar(i))

        self._spins.append(spin)
        self._tocados.append(False)
        self._colunas.append(spin)
        return spin

    def _criar_coluna_total(self) -> QWidget:
        self.campo_total = QLabel("0,0")
        self.campo_total.setFixedSize(80, 24)  # cabe "1004.0" com folga
        self.campo_total.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.campo_total.setToolTip("Total")
        self.campo_total.setStyleSheet(
            f"font-weight: 700; color: {Cor.BRANCO}; background: {Cor.PRIMARIA};"
            "border-radius: 4px; padding: 1px 4px;"
        )
        return self.campo_total

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

    def definir_valores_manuais(self, valores: list[float]) -> None:
        """Trechos digitados à mão (vindos de um projeto salvo): valor > 0
        fica manual; 0 continua automático. Não avisa ninguém — quem chama
        recalcula depois."""
        for i, valor in enumerate(valores[: len(self._spins)]):
            spin = self._spins[i]
            spin.blockSignals(True)
            if valor and valor > 0:
                spin.setValue(float(valor))
                self._tocados[i] = True
                spin.setStyleSheet(_ESTILO_MANUAL)
            else:
                self._tocados[i] = False
                spin.setStyleSheet(_ESTILO_AUTOMATICO)
            spin.blockSignals(False)

    def definir_visiveis(self, quantidade: int) -> None:
        """Mostra só os primeiros `quantidade` trechos (o resto do tipo
        de caixa atual não usa os campos extras) e reseta o estado."""
        for i, coluna in enumerate(self._colunas):
            coluna.setVisible(i < quantidade)
        for i in range(len(self._tocados)):
            self._tocados[i] = False
            self._spins[i].setStyleSheet(_ESTILO_AUTOMATICO)

    def definir_rotulos(self, rotulos: list[str]) -> None:
        for spin, rotulo in zip(self._spins, rotulos):
            spin.setToolTip(rotulo)

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
        self.campo_total.setText(f"{valor:.1f}".replace(".", ","))  # vírgula, como os campos ao lado
