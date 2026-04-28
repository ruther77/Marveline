"""Extraction conditionnement — façade METRO.

Délégue à `_shared/conditionnement.py`. Interface publique préservée :
`extract_conditionnement`.
"""
from scripts.etl.parsers._shared.conditionnement import extract_conditionnement

__all__ = ["extract_conditionnement"]
