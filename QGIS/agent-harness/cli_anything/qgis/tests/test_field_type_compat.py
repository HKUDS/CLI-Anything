"""Compatibility tests for field type enums across QGIS releases."""

import sys
from types import ModuleType, SimpleNamespace

import pytest

from cli_anything.qgis.core.layers import _field_type_enum


@pytest.mark.parametrize("version", [33400, 33799])
def test_pre_338_uses_qvariant_types(monkeypatch, version):
    qgis_module = ModuleType("qgis")
    core_module = ModuleType("qgis.core")
    pyqt_module = ModuleType("qgis.PyQt")
    qtcore_module = ModuleType("qgis.PyQt.QtCore")

    qgis_module.core = core_module
    qgis_module.PyQt = pyqt_module
    pyqt_module.QtCore = qtcore_module
    core_module.Qgis = SimpleNamespace(QGIS_VERSION_INT=version)
    qtcore_module.QVariant = SimpleNamespace(Int=2, Double=6, QString=10, Bool=1)

    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.core", core_module)
    monkeypatch.setitem(sys.modules, "qgis.PyQt", pyqt_module)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtCore", qtcore_module)

    assert _field_type_enum("int") == (2, "integer")


def test_338_and_later_uses_qmetatype_types(monkeypatch):
    qgis_module = ModuleType("qgis")
    core_module = ModuleType("qgis.core")
    pyqt_module = ModuleType("qgis.PyQt")
    qtcore_module = ModuleType("qgis.PyQt.QtCore")

    qgis_module.core = core_module
    qgis_module.PyQt = pyqt_module
    pyqt_module.QtCore = qtcore_module
    core_module.Qgis = SimpleNamespace(QGIS_VERSION_INT=33800)
    qtcore_module.QMetaType = SimpleNamespace(
        Type=SimpleNamespace(Int=2, Double=6, QString=10, Bool=1)
    )

    monkeypatch.setitem(sys.modules, "qgis", qgis_module)
    monkeypatch.setitem(sys.modules, "qgis.core", core_module)
    monkeypatch.setitem(sys.modules, "qgis.PyQt", pyqt_module)
    monkeypatch.setitem(sys.modules, "qgis.PyQt.QtCore", qtcore_module)

    assert _field_type_enum("int") == (2, "integer")
