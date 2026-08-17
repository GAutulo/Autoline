"""Ponto de entrada do aplicativo."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import JanelaPrincipal


def main() -> None:
    app = QApplication(sys.argv)
    janela = JanelaPrincipal()
    janela.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
