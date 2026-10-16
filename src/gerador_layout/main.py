"""Ponto de entrada do aplicativo."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFontDatabase, QIcon, QPixmapCache
from PySide6.QtWidgets import QApplication

from .ui.estilo import FOLHA_DE_ESTILO
from .ui.main_window import JanelaPrincipal


def _pasta_assets() -> Path:
    """Onde os arquivos de dado (fontes, ícone) ficam — muda conforme
    rodando do código-fonte ou do `.exe` empacotado. O PyInstaller
    extrai tudo que está em `datas` (ver Autoline.spec) pra uma pasta
    temporária, exposta em `sys._MEIPASS`; rodando do código-fonte, é só
    a pasta `assets/` na raiz do projeto."""
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return Path(base) / "assets"
    return Path(__file__).resolve().parent.parent.parent / "assets"


def _carregar_fontes() -> None:
    """Carrega as fontes da marca (ver `estilo.FONTE_*`) do arquivo —
    sem isso o Qt cai pra fonte do sistema mais parecida, silenciosamente
    (nunca quebra o app), então isso aqui só é uma melhoria visual, não
    uma dependência dura."""
    pasta = _pasta_assets() / "fonts"
    if not pasta.is_dir():
        return
    for arquivo in pasta.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(arquivo))


def _carregar_icone() -> QIcon:
    """O `icon=` do Autoline.spec só define o ícone do arquivo `.exe`
    em si (Explorer, barra de tarefas antes de abrir) — sem chamar
    `setWindowIcon`, a janela em si (barra de título, Alt+Tab) usa o
    ícone genérico padrão do Qt. Mesmo arquivo `.ico`, só que carregado
    em tempo de execução (por isso também precisa estar em `datas` no
    spec, não só no parâmetro `icon=`)."""
    caminho = _pasta_assets() / "icon.ico"
    return QIcon(str(caminho)) if caminho.is_file() else QIcon()


def main() -> None:
    app = QApplication(sys.argv)
    _carregar_fontes()
    app.setWindowIcon(_carregar_icone())
    app.setStyleSheet(FOLHA_DE_ESTILO)
    # O cache de desenho de cada elemento (ver ElementoMockup) mora no
    # QPixmapCache, que por padrão tem só 10 MB — pouco pra um layout com
    # logos grandes em zoom alto.
    QPixmapCache.setCacheLimit(256 * 1024)  # KB
    janela = JanelaPrincipal()
    # Maximizado, não só .show(): o tamanho padrão da janela (ver
    # JanelaPrincipal.__init__) é só o tamanho de fallback pra quando o
    # usuário restaurar a janela — abrir maximizado garante que o app usa
    # o espaço real da tela (uma tela de notebook comum tem só 768px de
    # altura útil, bem menos do que os ~820-880px que o app assumia),
    # em vez de depender de adivinhar a resolução de antemão.
    janela.showMaximized()
    projeto = next((a for a in sys.argv[1:] if a.lower().endswith(".autoline")), None)
    if projeto and Path(projeto).is_file():
        janela.abrir_projeto(projeto)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
