"""Ponto de entrada do aplicativo."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .ui.estilo import FOLHA_DE_ESTILO
from .ui.main_window import JanelaPrincipal


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(FOLHA_DE_ESTILO)
    janela = JanelaPrincipal()
    # Maximizado, não só .show(): o tamanho padrão da janela (ver
    # JanelaPrincipal.__init__) é só o tamanho de fallback pra quando o
    # usuário restaurar a janela — abrir maximizado garante que o app usa
    # o espaço real da tela (uma tela de notebook comum tem só 768px de
    # altura útil, bem menos do que os ~820-880px que o app assumia),
    # em vez de depender de adivinhar a resolução de antemão.
    janela.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
