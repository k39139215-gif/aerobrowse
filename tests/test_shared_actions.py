"""Rust crate and Python wheel package one identical action runtime."""

from pathlib import Path

from aerobrowse.actions import INSTALL


def test_native_and_python_package_identical_runtime():
    native = Path(__file__).resolve().parents[1] / "rust_core/src/action_runtime.js"
    assert native.read_text(encoding="utf-8") == INSTALL
