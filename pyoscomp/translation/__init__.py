# pyoscomp/translation/__init__.py

"""
Translation layer submodule for PyPSA-OSeMOSYS Comparison Framework.
"""

from .osemosys_translator import OSeMOSYSInputTranslator
from .pypsa_translator import PyPSAInputTranslator

__all__ = [
    'OSeMOSYSInputTranslator',
    'PyPSAInputTranslator'
]