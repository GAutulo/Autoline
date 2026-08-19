"""Diálogo de separação de cor automática pro logotipo vetorial — mostra
cada cor detectada no arquivo (`ElementoLogoVetorial.cores_detectadas`)
e deixa escolher pra qual tinta do trabalho ela vai, ou manter a cor
original."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout

from ..models import CorImpressao

_ROTULO_MANTER_ORIGINAL = "Manter cor original"


class DialogoSepararCoresLogo(QDialog):
    def __init__(
        self, cores_detectadas: list[str], tintas_disponiveis: list[CorImpressao], parent=None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Separação de cor do logotipo")
        self.setMinimumWidth(360)

        vbox = QVBoxLayout(self)
        if not tintas_disponiveis:
            aviso = QLabel(
                "Nenhuma cor de impressão marcada na legenda ainda — marque pelo "
                "menos uma antes de mapear o logotipo, ou deixe tudo na cor original."
            )
            aviso.setWordWrap(True)
            vbox.addWidget(aviso)

        if not cores_detectadas:
            vbox.addWidget(QLabel("Não encontrei nenhuma cor mapeável nesse arquivo."))

        form = QFormLayout()
        self._combos: dict[str, QComboBox] = {}
        for cor_hex in cores_detectadas:
            combo = QComboBox()
            combo.addItem(_ROTULO_MANTER_ORIGINAL, None)
            for tinta in tintas_disponiveis:
                combo.addItem(tinta.nome, tinta)
            amostra = QLabel(cor_hex)
            amostra.setStyleSheet(
                f"background: {cor_hex}; border: 1px solid rgba(0,0,0,60); "
                "border-radius: 3px; padding: 2px 10px; font-family: monospace;"
            )
            self._combos[cor_hex] = combo
            form.addRow(amostra, combo)
        vbox.addLayout(form)

        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botoes.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        vbox.addWidget(botoes)

    def mapa_escolhido(self) -> dict[str, str]:
        """Cor original ("#rrggbb") → cor da tinta escolhida
        ("#rrggbb") — só as cores que o usuário efetivamente mapeou
        (não deixou em "Manter cor original")."""
        mapa: dict[str, str] = {}
        for cor_hex, combo in self._combos.items():
            tinta: CorImpressao | None = combo.currentData()
            if tinta is not None:
                mapa[cor_hex] = QColor(tinta.r, tinta.g, tinta.b).name()
        return mapa
