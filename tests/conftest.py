"""Configurações dos testes isoladas: as preferências (QSettings) vão para
um .ini temporário, não para o registro do Windows de quem roda os testes
— senão um teste mudava a configuração real do app (e a configuração real
mudava o resultado dos testes)."""

from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import QSettings

_PASTA = tempfile.mkdtemp(prefix="autoline-testes-")
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, _PASTA)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
