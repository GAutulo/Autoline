"""Ponto de entrada usado para empacotar o aplicativo com o PyInstaller.

Não é usado no dia a dia de desenvolvimento (para isso, use
`PYTHONPATH=src python -m gerador_layout.main`) — este arquivo existe só
para o PyInstaller ter um único script para apontar e gerar o .exe.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from gerador_layout.main import main  # noqa: E402

if __name__ == "__main__":
    main()
