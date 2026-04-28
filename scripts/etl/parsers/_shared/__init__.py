"""Primitives mutualisées entre parsers fournisseur.

Ce package contient la logique générique (tokenisation sémantique, nettoyage
OCR, extraction conditionnement, utilitaires colonnes PDF) utilisée par tous
les parsers (METRO, TAIYAT, ...).

Aucune dépendance à un fournisseur spécifique : toutes les fonctions qui ont
besoin d'un dictionnaire d'abréviations ou de marques le reçoivent en paramètre.
"""
