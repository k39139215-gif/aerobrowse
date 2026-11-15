"""
AeroBrowse — The Featherweight AI Browser Engine
100% Web Compatibility at 30MB Memory with 90% Fewer Tokens.
"""

from aerobrowse.engine import AeroBrowser
from aerobrowse.pruner import SemanticPruner
from aerobrowse.turbo import TurboEngine
from aerobrowse.fidelity import FidelityEngine

__version__ = "0.2.0"
__all__ = ["AeroBrowser", "SemanticPruner", "TurboEngine", "FidelityEngine"]
