#!/usr/bin/env python3
"""Seed restaurant — Peuple les tables du module restaurant avec les vraies données.

Source : MassaCorp DB (restaurant_plats) + plat_compositions_2026-01-12.json.
Restaurant camerounais, devise EUR, prix en centimes.

Usage :
    docker compose exec api python scripts/seed_restaurant.py
    docker compose exec api python scripts/seed_restaurant.py --dry-run
    docker compose exec api python scripts/seed_restaurant.py --tenant-id=3
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_context
import app.models  # noqa: F401 — charge tous les modèles pour résoudre les relations SQLAlchemy
from app.models.restaurant.categorie_ingredient import CategorieIngredient
from app.models.restaurant.ingredient_restaurant import IngredientRestaurant
from app.models.restaurant.type_preparation import TypePreparation
from app.models.restaurant.recette_type_preparation import RecetteTypePreparation
from app.models.restaurant.variante_plat import VariantePlat
from app.models.restaurant.side_restaurant import SideRestaurant
from app.models.restaurant.table_restaurant import TableRestaurant

# ── Constantes ───────────────────────────────────────────────────────────────

DEFAULT_TENANT_ID = 3
PORTIONS_PAR_BATCH = 10      # portions standard par marmite
TAUX_TVA_DEFAULT = 0         # TVA à configurer selon réglementation locale

# Catégories d'ingrédients
CATEGORIES_DATA = [
    {"nom": "Viandes",                     "is_proteine": True},
    {"nom": "Poissons et fruits de mer",   "is_proteine": True},
    {"nom": "Légumes",                     "is_proteine": False},
    {"nom": "Huiles",                      "is_proteine": False},
    {"nom": "Condiments et épices",        "is_proteine": False},
    {"nom": "Volaille",                    "is_proteine": True},
    {"nom": "Abats",                       "is_proteine": True},
    {"nom": "Féculents",                   "is_proteine": False},
    {"nom": "Fruits",                      "is_proteine": False},
    {"nom": "Produits laitiers",           "is_proteine": False},
    {"nom": "Boissons stock",             "is_proteine": False},
]

# Ingrédients — (nom, catégorie, unité, coût_achat_cts ou None)
INGREDIENTS_DATA = [
    # ── Viandes ──────────────────────────────────────────────────────────────
    ("Bœuf",                    "Viandes",  "kg",  999),
    ("Porc (filet)",            "Viandes",  "kg",  850),
    ("Bœuf brochettes",        "Viandes",  "kg",  1100),
    ("Bœuf séché (soya)",      "Viandes",  "kg",  1500),
    # ── Volaille ─────────────────────────────────────────────────────────────
    ("Poulet entier",           "Volaille", "kg",  650),
    ("Cuisses de poulet",       "Volaille", "kg",  700),
    ("Ailes de poulet",         "Volaille", "kg",  500),
    # ── Abats ────────────────────────────────────────────────────────────────
    ("Tripes",                  "Abats",    "kg",  600),
    ("Rognon",                  "Abats",    "kg",  700),
    ("Gésier",                  "Abats",    "kg",  550),
    # ── Poissons et fruits de mer ────────────────────────────────────────────
    ("Maquereau moyen",         "Poissons et fruits de mer", "kg",  282),
    ("Poisson fumé",            "Poissons et fruits de mer", "kg",  None),
    ("Crevettes",               "Poissons et fruits de mer", "kg",  749),
    ("Écrevisses séchées",      "Poissons et fruits de mer", "kg",  None),
    ("Capitaine",               "Poissons et fruits de mer", "kg",  1200),
    ("Tilapia",                 "Poissons et fruits de mer", "kg",  800),
    ("Sole",                    "Poissons et fruits de mer", "kg",  1800),
    # ── Légumes ──────────────────────────────────────────────────────────────
    ("Gombo",                   "Légumes",  "kg",  502),
    ("Feuilles Ndolé",          "Légumes",  "kg",  269),
    ("Feuilles Eru",            "Légumes",  "kg",  616),
    ("Épinards",                "Légumes",  "kg",  145),
    ("Plantain",                "Légumes",  "kg",  163),
    ("Champignons",             "Légumes",  "kg",  800),
    ("Tomates",                 "Légumes",  "kg",  None),
    ("Oignons",                 "Légumes",  "kg",  58),
    ("Ail",                     "Légumes",  "kg",  None),
    ("Gingembre",               "Légumes",  "kg",  None),
    ("Piment",                  "Légumes",  "kg",  675),
    ("Avocat",                  "Légumes",  "kg",  350),
    ("Laitue",                  "Légumes",  "kg",  200),
    ("Concombre",               "Légumes",  "kg",  150),
    ("Poivron",                 "Légumes",  "kg",  300),
    ("Carotte",                 "Légumes",  "kg",  120),
    ("Chou",                    "Légumes",  "kg",  100),
    ("Persil",                  "Légumes",  "botte", 50),
    ("Céleri",                  "Légumes",  "botte", 80),
    ("Taro (tubercule)",        "Légumes",  "kg",  250),
    ("Igname",                  "Légumes",  "kg",  200),
    ("Manioc",                  "Légumes",  "kg",  150),
    ("Haricots blancs",         "Légumes",  "kg",  180),
    ("Macabo",                  "Légumes",  "kg",  200),
    ("Banane douce",            "Légumes",  "kg",  120),
    # ── Féculents ────────────────────────────────────────────────────────────
    ("Riz blanc",               "Féculents", "kg",  200),
    ("Pommes de terre",         "Féculents", "kg",  150),
    ("Farine de blé",           "Féculents", "kg",  120),
    ("Semoule de maïs",         "Féculents", "kg",  100),
    ("Pâtes alimentaires",      "Féculents", "kg",  180),
    ("Baguette",                "Féculents", "pièce", 60),
    # ── Huiles ───────────────────────────────────────────────────────────────
    ("Huile de palme",          "Huiles",   "L",   341),
    ("Huile végétale",          "Huiles",   "L",   247),
    ("Huile d'olive",           "Huiles",   "L",   800),
    # ── Condiments et épices ─────────────────────────────────────────────────
    ("Pâte d'arachide",         "Condiments et épices", "kg",    457),
    ("Pistache pilée",          "Condiments et épices", "kg",    None),
    ("Njansang",                "Condiments et épices", "kg",    None),
    ("Sel",                     "Condiments et épices", "kg",    84),
    ("Bouillon cube",           "Condiments et épices", "pièce", None),
    ("Poivre noir",             "Condiments et épices", "kg",    1200),
    ("Muscade",                 "Condiments et épices", "kg",    2000),
    ("Curry",                   "Condiments et épices", "kg",    800),
    ("Vinaigre",                "Condiments et épices", "L",     150),
    ("Concentré de tomate",     "Condiments et épices", "kg",    300),
    ("Pâte de piment",          "Condiments et épices", "kg",    500),
    ("Sucre",                   "Condiments et épices", "kg",    100),
    ("Thym",                    "Condiments et épices", "botte", 30),
    ("Laurier",                 "Condiments et épices", "botte", 30),
    ("Ail en poudre",           "Condiments et épices", "kg",    900),
    # ── Fruits ───────────────────────────────────────────────────────────────
    ("Citron",                  "Fruits",   "kg",  250),
    ("Ananas",                  "Fruits",   "pièce", 200),
    ("Mangue",                  "Fruits",   "kg",  300),
    ("Papaye",                  "Fruits",   "kg",  200),
    # ── Produits laitiers ────────────────────────────────────────────────────
    ("Beurre",                  "Produits laitiers", "kg",  800),
    ("Fromage",                 "Produits laitiers", "kg",  1200),
    ("Crème fraîche",           "Produits laitiers", "L",   400),
    ("Lait",                    "Produits laitiers", "L",   120),
    ("Œufs",                    "Produits laitiers", "pièce", 25),
    # ── Boissons stock (suivi de l'inventaire bouteilles/canettes) ───────────
    # Bières
    ("Heineken (bouteille)",        "Boissons stock", "bouteille", 250),
    ("Guinness (bouteille)",        "Boissons stock", "bouteille", 250),
    ("Guinness grande (bouteille)", "Boissons stock", "bouteille", 300),
    ("Guinness petite (bouteille)", "Boissons stock", "bouteille", 150),
    ("Leffe (bouteille)",           "Boissons stock", "bouteille", 300),
    ("Leffe grande (bouteille)",    "Boissons stock", "bouteille", 250),
    ("Leffe petite (bouteille)",    "Boissons stock", "bouteille", 180),
    ("1664 (bouteille)",            "Boissons stock", "bouteille", 150),
    ("Desperados (bouteille)",      "Boissons stock", "bouteille", 300),
    ("Desperados grande (bouteille)", "Boissons stock", "bouteille", 250),
    ("Desperados petite (bouteille)", "Boissons stock", "bouteille", 180),
    ("Mutzig (bouteille)",          "Boissons stock", "bouteille", 180),
    ("Castel (bouteille)",          "Boissons stock", "bouteille", 180),
    ("33 Export (bouteille)",       "Boissons stock", "bouteille", 180),
    ("Pelfort (bouteille)",         "Boissons stock", "bouteille", 200),
    ("Isenbeck (bouteille)",        "Boissons stock", "bouteille", 250),
    ("Kadji Beer (bouteille)",      "Boissons stock", "bouteille", 180),
    ("Malta (bouteille)",           "Boissons stock", "bouteille", 150),
    ("Top (bouteille)",             "Boissons stock", "bouteille", 200),
    # Spiritueux (bouteille 70cl)
    ("Jack Daniel's (70cl)",        "Boissons stock", "bouteille", 2500),
    ("Chivas (70cl)",               "Boissons stock", "bouteille", 2500),
    ("Black Label (70cl)",          "Boissons stock", "bouteille", 2500),
    ("Glenfiddich (70cl)",          "Boissons stock", "bouteille", 3500),
    ("JB (70cl)",                   "Boissons stock", "bouteille", 2000),
    ("Baileys (70cl)",              "Boissons stock", "bouteille", 1500),
    ("Vodka (70cl)",                "Boissons stock", "bouteille", 1500),
    ("Cognac (70cl)",               "Boissons stock", "bouteille", 2000),
    ("Rhum (70cl)",                 "Boissons stock", "bouteille", 1200),
    ("Martini (70cl)",              "Boissons stock", "bouteille", 1000),
    ("Campari (70cl)",              "Boissons stock", "bouteille", 1000),
    # Champagnes & vins (bouteille 75cl)
    ("Moët (75cl)",                 "Boissons stock", "bouteille", 3000),
    ("Veuve Clicquot (75cl)",       "Boissons stock", "bouteille", 3500),
    ("Ruinart (75cl)",              "Boissons stock", "bouteille", 8000),
    ("Nicola (75cl)",               "Boissons stock", "bouteille", 2000),
    ("Vin blanc (75cl)",            "Boissons stock", "bouteille", 500),
    ("Bordeaux (75cl)",             "Boissons stock", "bouteille", 500),
    ("Rosé (75cl)",                 "Boissons stock", "bouteille", 500),
    ("Moelleux (75cl)",             "Boissons stock", "bouteille", 500),
    # Softs
    ("Coca-Cola (bouteille)",       "Boissons stock", "bouteille", 80),
    ("Jus de fruits (bouteille)",   "Boissons stock", "bouteille", 80),
    ("Eau minérale (bouteille)",    "Boissons stock", "bouteille", 30),
    ("Eau gazeuse (bouteille)",     "Boissons stock", "bouteille", 80),
    ("Ginger ale (bouteille)",      "Boissons stock", "bouteille", 100),
    ("Booster (canette)",           "Boissons stock", "canette",   200),
    ("Red Bull (canette)",          "Boissons stock", "canette",   150),
    ("Petit CD (bouteille)",        "Boissons stock", "bouteille", 150),
    # Café
    ("Café (grain)",                "Boissons stock", "kg",        1500),
]

# Types de préparation (recettes marmite)
# (nom, portions_par_batch, temps_cuisson_min, seuil_alerte_portions)
TYPES_PREP_DATA = [
    ("Gombo",          PORTIONS_PAR_BATCH, 60,  3),
    ("Ndolé",          PORTIONS_PAR_BATCH, 120, 3),
    ("Mafé",           PORTIONS_PAR_BATCH, 90,  3),
    ("Pistache",       PORTIONS_PAR_BATCH, 90,  3),
    ("Légumes sautés", PORTIONS_PAR_BATCH, 30,  3),
    ("Sauce jaune",    PORTIONS_PAR_BATCH, 45,  3),
    ("Sauce tomate",   PORTIONS_PAR_BATCH, 30,  3),
    ("Heru",           PORTIONS_PAR_BATCH, 45,  2),
    ("Koki",           PORTIONS_PAR_BATCH, 45,  2),
    ("Kondre",         PORTIONS_PAR_BATCH, 120, 2),
    ("Taro",           PORTIONS_PAR_BATCH, 90,  2),
]

# Recettes de base par TypePreparation — (type_prep_nom, [(ingredient_nom, qte_par_batch)])
# Quantités = qte_par_portion_json * PORTIONS_PAR_BATCH. Exclure si qte == 0.
RECETTES_BASE_DATA = [
    ("Gombo", [
        ("Gombo",           1.000),
        ("Tomates",         0.300),
        ("Oignons",         0.100),
        ("Huile de palme",  0.200),
    ]),
    ("Ndolé", [
        ("Feuilles Ndolé",  1.000),
        ("Pâte d'arachide", 0.200),
        ("Oignons",         0.100),
        ("Huile végétale",  0.100),
    ]),
    ("Mafé", [
        ("Pâte d'arachide", 0.500),
        ("Tomates",         0.200),
        ("Oignons",         0.100),
        ("Huile de palme",  0.100),
    ]),
    ("Pistache", [
        ("Pistache pilée",  0.400),
        ("Huile de palme",  0.100),
        ("Oignons",         0.100),
    ]),
    ("Légumes sautés", [
        ("Oignons",         0.500),
        ("Tomates",         0.300),
        ("Piment",          0.100),
        ("Huile végétale",  0.200),
    ]),
    ("Sauce jaune", [
        ("Pâte d'arachide", 0.400),
        ("Huile de palme",  0.200),
        ("Oignons",         0.100),
    ]),
    ("Sauce tomate", [
        ("Oignons",         0.500),
        ("Tomates",         0.300),
        ("Piment",          0.100),
        ("Huile végétale",  0.200),
    ]),
    ("Heru", [
        ("Feuilles Eru",        0.600),
        ("Épinards",            1.400),
        ("Écrevisses séchées",  0.200),
        ("Huile de palme",      0.300),
    ]),
    ("Koki", [
        ("Pâte d'arachide", 0.800),
        ("Huile de palme",  0.300),
        ("Oignons",         0.200),
    ]),
    ("Kondre", [
        ("Plantain",        3.000),
        ("Huile de palme",  0.500),
        ("Piment",          0.100),
        ("Oignons",         0.200),
    ]),
    ("Taro", [
        ("Huile de palme",  0.500),
        ("Champignons",     0.400),
        ("Njansang",        0.100),
        ("Bouillon cube",   2.500),
    ]),
]

# VariantePlat :
# (nom, type, prix_cts, categorie, type_prep_nom|None, proteine_nom|None, qte_proteine|None)
VARIANTES_DATA = [
    # ── Gombo ─────────────────────────────────────────────────────────────────
    ("GOMBO VIANDE",          "plat", 1500, "plats_sauce",  "Gombo",    "Bœuf",           0.250),
    ("GOMBO POISSON FRIT",    "plat", 1800, "plats_sauce",  "Gombo",    "Maquereau moyen",0.500),
    ("GOMBO POISSON FUMÉ",    "plat", 1800, "plats_sauce",  "Gombo",    "Poisson fumé",   0.150),
    ("GOMBO ROYAL",           "plat", 2000, "plats_sauce",  "Gombo",    "Bœuf",           0.300),
    # ── Ndolé ─────────────────────────────────────────────────────────────────
    ("NDOLE VIANDE",          "plat", 1500, "plats_sauce",  "Ndolé",    "Bœuf",           0.250),
    ("NDOLE POISSON FRIT",    "plat", 2000, "plats_sauce",  "Ndolé",    "Maquereau moyen",0.500),
    ("NDOLE POISSON FUMÉ",    "plat", 1800, "plats_sauce",  "Ndolé",    "Poisson fumé",   0.150),
    ("NDOLE CREVETTES",       "plat", 1800, "plats_sauce",  "Ndolé",    "Crevettes",      0.150),
    ("NDOLE ROYAL",           "plat", 2000, "plats_sauce",  "Ndolé",    "Bœuf",           0.300),
    # ── Mafé ──────────────────────────────────────────────────────────────────
    ("MAFE VIANDE",           "plat", 1500, "plats_sauce",  "Mafé",     "Bœuf",           0.250),
    ("MAFE POISSON FRIT",     "plat", 2000, "plats_sauce",  "Mafé",     "Maquereau moyen",0.500),
    ("MAFE POISSON FUMÉ",     "plat", 1800, "plats_sauce",  "Mafé",     "Poisson fumé",   0.150),
    # ── Pistache ──────────────────────────────────────────────────────────────
    ("PISTACHE VIANDE",       "plat", 1500, "plats_sauce",  "Pistache", "Bœuf",           0.250),
    ("PISTACHE POISSON FRIT", "plat", 2000, "plats_sauce",  "Pistache", "Maquereau moyen",0.500),
    ("PISTACHE POISSON FUMÉ", "plat", 1500, "plats_sauce",  "Pistache", "Poisson fumé",   0.150),
    ("PISTACHE ROYAL",        "plat", 2000, "plats_sauce",  "Pistache", "Bœuf",           0.300),
    # ── Légumes sautés ────────────────────────────────────────────────────────
    ("LEGUMES SAUTES VIANDE",        "plat", 1500, "plats_sauce",  "Légumes sautés", "Bœuf",           0.250),
    ("LEGUMES SAUTES CREVETTES",     "plat", 1500, "plats_sauce",  "Légumes sautés", "Crevettes",      0.150),
    ("LEGUMES SAUTES POISSON FRIT",  "plat", 2000, "plats_sauce",  "Légumes sautés", "Maquereau moyen",0.500),
    ("LEGUMES SAUTES POISSON FUMÉ",  "plat", 2000, "plats_sauce",  "Légumes sautés", "Poisson fumé",   0.150),
    ("LEGUMES ROYAL",                "plat", 2000, "plats_sauce",  "Légumes sautés", "Bœuf",           0.300),
    # ── Plats sauce uniques ───────────────────────────────────────────────────
    ("HERU",    "plat", 1800, "plats_sauce",  "Heru",   "Bœuf", 0.250),
    ("KOKI",    "plat", 1200, "plats_sauce",  "Koki",   "Bœuf", 0.250),
    ("KONDRE",  "plat", 2500, "plats_sauce",  "Kondre", "Bœuf", 0.250),
    ("TARO",    "plat", 1800, "plats_sauce",  "Taro",   "Bœuf", 0.250),
    # ── Sauce jaune ───────────────────────────────────────────────────────────
    ("SAUCE JAUNE VIANDE",        "plat", 1500, "accompagnement", "Sauce jaune",  "Bœuf",         0.250),
    ("SAUCE JAUNE POISSON FUMÉ",  "plat", 1800, "accompagnement", "Sauce jaune",  "Poisson fumé", 0.150),
    ("SAUCE JAUNE ROYAL",         "plat", 2000, "accompagnement", "Sauce jaune",  "Bœuf",         0.300),
    # ── Sauce tomate ──────────────────────────────────────────────────────────
    ("SAUCE TOMATE VIANDE",       "plat", 1500, "accompagnement", "Sauce tomate", "Bœuf",           0.250),
    ("SAUCE TOMATE POISSON FRIT", "plat", 2000, "accompagnement", "Sauce tomate", "Maquereau moyen",0.500),
    # ── Grillades (type_prep=None) ────────────────────────────────────────────
    ("AILES DE POULET",         "plat", 1000, "grillades", None, None, None),
    ("AILES DE POULET RIZ",     "plat", 1500, "grillades", None, None, None),
    ("DEMI PLAT AILES",         "plat",  500, "grillades", None, None, None),
    ("CUISSES DE POULET",       "plat", 1000, "grillades", None, None, None),
    ("COTELETTE DE PORC BRAISE","plat", 1000, "grillades", None, None, None),
    ("BROCHETTES DE VIANDES",   "plat", 1000, "grillades", None, None, None),
    ("BROCHETTES DE CREVETTES", "plat", 1000, "grillades", None, None, None),
    ("SOYA",                    "plat", 1000, "grillades", None, None, None),
    ("TRIPPES SAUTEES",         "plat", 1500, "grillades", None, None, None),
    ("PORC RIZ",                "plat", 1500, "grillades", None, None, None),
    ("Rôti porc",               "plat", 1500, "grillades", None, None, None),
    ("Rognon sautée",           "plat", 1500, "grillades", None, None, None),
    ("Gésier",                  "plat", 1500, "grillades", None, None, None),
    ("DG",                      "plat", 3000, "grillades", None, None, None),
    # ── Poissons frais ────────────────────────────────────────────────────────
    ("MAQUEREAU PM",    "plat", 1500, "poissons", None, "Maquereau moyen", 0.500),
    ("MAQUEREAU GROS",  "plat", 2000, "poissons", None, "Maquereau moyen", 0.700),
    ("CAPITAINE PM",    "plat", 2000, "poissons", None, None, None),
    ("GROS CAPTAINE",   "plat", 2500, "poissons", None, None, None),
    ("TILAPIA",         "plat", 1500, "poissons", None, None, None),
    ("SOLE PM",         "plat", 2500, "poissons", None, None, None),
    ("SOLE GROS",       "plat", 4500, "poissons", None, None, None),
    # ── Entrées ───────────────────────────────────────────────────────────────
    ("BOUILLON DE POISSON",  "plat", 2000, "entrees", None, None, None),
    ("BOUILLON QUEUE DE B",  "plat", 1500, "entrees", None, None, None),
    ("SALADE AVOCATS",       "plat", 1800, "entrees", None, None, None),
    ("SALADE MAISON",        "plat", 1500, "entrees", None, None, None),
    # ── Accompagnements ───────────────────────────────────────────────────────
    ("Oeuf",            "plat",   50, "accompagnement", None, None, None),
    ("Beignet haricot", "plat", 1000, "accompagnement", None, None, None),
    ("Supplements 10€", "plat", 1000, "accompagnement", None, None, None),
    ("Supplements 5€",  "plat",  500, "accompagnement", None, None, None),
    ("Supplements 3€",  "plat",  300, "accompagnement", None, None, None),
    # ── Bières ────────────────────────────────────────────────────────────────
    ("HEINEKEIN",           "boisson", 1200, "biere", None, None, None),
    ("GUINESS",             "boisson", 1200, "biere", None, None, None),
    ("GRANDE GUINESS",      "boisson", 1000, "biere", None, None, None),
    ("PETITE GUINESS",      "boisson",  500, "biere", None, None, None),
    ("MUTZIG",              "boisson",  600, "biere", None, None, None),
    ("33 EXPORT",           "boisson",  600, "biere", None, None, None),
    ("CASTEL",              "boisson",  600, "biere", None, None, None),
    ("LEFFE",               "boisson", 1000, "biere", None, None, None),
    ("GRANDE LEFFE",        "boisson",  700, "biere", None, None, None),
    ("PETITE LEFFE",        "boisson",  500, "biere", None, None, None),
    ("DESPERADOS",          "boisson", 1000, "biere", None, None, None),
    ("GRANDE DESPERADOS",   "boisson",  800, "biere", None, None, None),
    ("PETITE DESPERADOS",   "boisson",  500, "biere", None, None, None),
    ("1664",                "boisson",  500, "biere", None, None, None),
    ("PELFORT",             "boisson",  700, "biere", None, None, None),
    ("GRANDE PELFORT",      "boisson",  700, "biere", None, None, None),
    ("Isenbeck",            "boisson",  800, "biere", None, None, None),
    ("Kadji beer",          "boisson",  600, "biere", None, None, None),
    ("MALTA",               "boisson",  500, "biere", None, None, None),
    ("TOP",                 "boisson",  700, "biere", None, None, None),
    # ── Whiskies ──────────────────────────────────────────────────────────────
    ("JACK DANIEL",         "boisson", 6000, "whisky", None, None, None),
    ("1/2 JACK DANIEL'S",   "boisson", 3000, "whisky", None, None, None),
    ("1/4 JACK DANIEL'S",   "boisson", 1500, "whisky", None, None, None),
    ("CHIVAS",              "boisson", 6000, "whisky", None, None, None),
    ("1/2 CHIVAS",          "boisson", 3000, "whisky", None, None, None),
    ("1/4 CHIVAS",          "boisson", 1500, "whisky", None, None, None),
    ("BLACK LABEL",         "boisson", 6000, "whisky", None, None, None),
    ("1/2 BLACK LABEL",     "boisson", 3000, "whisky", None, None, None),
    ("1/4 BLACK LABEL",     "boisson", 1500, "whisky", None, None, None),
    ("Glenfiddich",         "boisson", 8000, "whisky", None, None, None),
    ("1/2 Glenfiddich",     "boisson", 4000, "whisky", None, None, None),
    ("JB",                  "boisson", 5000, "whisky", None, None, None),
    ("Conso whisky",        "boisson",  500, "whisky", None, None, None),
    # ── Digestifs / Spiritueux ────────────────────────────────────────────────
    ("BALLEYS",             "boisson", 5000, "digestif", None, None, None),
    ("BALLEYS CONSO",       "boisson",  500, "digestif", None, None, None),
    ("VODKA",               "boisson", 5000, "digestif", None, None, None),
    ("COGNAC CONSO",        "boisson",  700, "digestif", None, None, None),
    ("RHUM CONSO",          "boisson",  500, "digestif", None, None, None),
    # ── Apéritifs ─────────────────────────────────────────────────────────────
    ("MARTINI CONSO",       "boisson",  500, "aperitif", None, None, None),
    ("COMPARI CONSO",       "boisson",  500, "aperitif", None, None, None),
    # ── Champagnes ────────────────────────────────────────────────────────────
    ("MOET",                "boisson",  6000, "champagne", None, None, None),
    ("COUPE MOET",          "boisson",  1000, "champagne", None, None, None),
    ("VEUVE CLICOT",        "boisson",  7000, "champagne", None, None, None),
    ("COUPE VEUVE CLICOT",  "boisson",  1000, "champagne", None, None, None),
    ("Ruinart B2B",         "boisson", 15000, "champagne", None, None, None),
    ("Nicola",              "boisson",  5000, "champagne", None, None, None),
    # ── Vins ──────────────────────────────────────────────────────────────────
    ("VIN BLANC",   "boisson", 1500, "vin", None, None, None),
    ("BORDEAUX",    "boisson", 1500, "vin", None, None, None),
    ("ROSE",        "boisson", 1500, "vin", None, None, None),
    ("MOELLEUX",    "boisson", 1500, "vin", None, None, None),
    ("MOYEN VIN",   "boisson", 1000, "vin", None, None, None),
    ("Vin 20€",     "boisson", 2000, "vin", None, None, None),
    ("Vin 25€",     "boisson", 2500, "vin", None, None, None),
    ("Vin 30€",     "boisson", 3000, "vin", None, None, None),
    ("Vin 50€",     "boisson", 5000, "vin", None, None, None),
    # ── Softs ─────────────────────────────────────────────────────────────────
    ("Coca",        "boisson",  300, "soft", None, None, None),
    ("JUS",         "boisson",  300, "soft", None, None, None),
    ("EAU",         "boisson",  100, "soft", None, None, None),
    ("EAU GAZEUSE", "boisson",  300, "soft", None, None, None),
    ("Ginger",      "boisson",  500, "soft", None, None, None),
    ("Booster",     "boisson", 1000, "soft", None, None, None),
    ("Redbull",     "boisson",  400, "soft", None, None, None),
    ("PETIT CD",    "boisson",  500, "soft", None, None, None),
    # ── Cafés et infusions ────────────────────────────────────────────────────
    ("café",        "boisson",  150, "cafe", None, None, None),
]

# Sides — (nom, ingredient_nom|None, qte_par_portion|None)
SIDES_DATA = [
    ("Riz blanc",           "Riz blanc", 0.150),
    ("Plantain",            "Plantain",  0.150),
    ("Baguette",            None,        None),
    ("Frites",              None,        None),
    ("Salade verte",        None,        None),
    ("Sans accompagnement", None,        None),
]

# Tables — (numero, capacite)
TABLES_DATA = [
    ("1", 4), ("2", 4), ("3", 4), ("4", 4), ("5", 6),
    ("6", 6), ("7", 6), ("8", 4), ("9", 4), ("10", 4),
    ("11", 4), ("12", 4), ("13", 8), ("14", 8), ("15", 2),
    ("Terrasse 1", 4), ("Terrasse 2", 4), ("Terrasse 3", 6),
    ("Terrasse 4", 6), ("Terrasse 5", 8),
    ("Bar 1", 2), ("Bar 2", 2),
]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _exists(db, model, **filters):
    """Retourne True si un enregistrement correspondant aux filtres existe."""
    return db.query(model).filter_by(**filters).first() is not None


def _print_stats(label: str, created: int, skipped: int) -> None:
    print(f"  {label} : {created} créés, {skipped} existants ignorés")


# ── Seed functions ───────────────────────────────────────────────────────────


def seed_categories(db, tenant_id: int, dry_run: bool) -> dict:
    """Crée les catégories d'ingrédients. Retourne dict nom→id."""
    created = skipped = 0
    result: dict = {}

    for cat in CATEGORIES_DATA:
        existing = db.query(CategorieIngredient).filter_by(
            tenant_id=tenant_id, nom=cat["nom"]
        ).first()
        if existing:
            result[cat["nom"]] = existing.id
            skipped += 1
            continue
        if not dry_run:
            obj = CategorieIngredient(
                tenant_id=tenant_id,
                nom=cat["nom"],
                is_proteine=cat["is_proteine"],
            )
            db.add(obj)
            db.flush()
            result[cat["nom"]] = obj.id
        created += 1

    _print_stats("CategorieIngredient", created, skipped)
    return result


def seed_ingredients(db, tenant_id: int, cat_ids: dict, dry_run: bool) -> dict:
    """Crée les ingrédients. Retourne dict nom→id."""
    created = skipped = 0
    result: dict = {}

    for nom, cat_nom, unite, cout_cts in INGREDIENTS_DATA:
        existing = db.query(IngredientRestaurant).filter_by(
            tenant_id=tenant_id, nom=nom
        ).first()
        if existing:
            result[nom] = existing.id
            skipped += 1
            continue
        if not dry_run:
            obj = IngredientRestaurant(
                tenant_id=tenant_id,
                nom=nom,
                categorie_id=cat_ids.get(cat_nom),
                unite_stock=unite,
                cout_unitaire_cts=cout_cts,
                stock_actuel=0,
                stock_alerte=0,
            )
            db.add(obj)
            db.flush()
            result[nom] = obj.id
        created += 1

    _print_stats("IngredientRestaurant", created, skipped)
    return result


def seed_types_prep(db, tenant_id: int, dry_run: bool) -> dict:
    """Crée les TypePreparation. Retourne dict nom→id."""
    created = skipped = 0
    result: dict = {}

    for nom, portions, temps, seuil in TYPES_PREP_DATA:
        existing = db.query(TypePreparation).filter_by(
            tenant_id=tenant_id, nom=nom
        ).first()
        if existing:
            result[nom] = existing.id
            skipped += 1
            continue
        if not dry_run:
            obj = TypePreparation(
                tenant_id=tenant_id,
                nom=nom,
                portions_par_batch=portions,
                temps_cuisson_min=temps,
                seuil_alerte_portions=seuil,
            )
            db.add(obj)
            db.flush()
            result[nom] = obj.id
        created += 1

    _print_stats("TypePreparation", created, skipped)
    return result


def seed_recettes(
    db, tenant_id: int, type_prep_ids: dict, ingr_ids: dict, dry_run: bool
) -> int:
    """Crée les RecetteTypePreparation (lignes recette sans protéine)."""
    created = skipped = 0

    for type_prep_nom, lignes in RECETTES_BASE_DATA:
        tp_id = type_prep_ids.get(type_prep_nom)
        if tp_id is None:
            continue
        for ingr_nom, qte_batch in lignes:
            ingr_id = ingr_ids.get(ingr_nom)
            if ingr_id is None:
                continue
            if _exists(db, RecetteTypePreparation,
                       tenant_id=tenant_id,
                       type_preparation_id=tp_id,
                       ingredient_id=ingr_id):
                skipped += 1
                continue
            if not dry_run:
                obj = RecetteTypePreparation(
                    tenant_id=tenant_id,
                    type_preparation_id=tp_id,
                    ingredient_id=ingr_id,
                    quantite_par_batch=qte_batch,
                )
                db.add(obj)
            created += 1

    _print_stats("RecetteTypePreparation", created, skipped)
    return created


def seed_variantes_plat(
    db, tenant_id: int, type_prep_ids: dict, ingr_ids: dict, dry_run: bool
) -> int:
    """Crée les VariantePlat (plats, grillades, poissons, boissons)."""
    created = skipped = 0

    for row in VARIANTES_DATA:
        nom, vtype, prix_cts, categorie, tp_nom, prot_nom, qte_prot = row
        if _exists(db, VariantePlat, tenant_id=tenant_id, nom=nom):
            skipped += 1
            continue
        if not dry_run:
            obj = VariantePlat(
                tenant_id=tenant_id,
                nom=nom,
                type=vtype,
                prix_vente_cts=prix_cts,
                taux_tva=TAUX_TVA_DEFAULT,
                categorie=categorie,
                type_preparation_id=type_prep_ids.get(tp_nom) if tp_nom else None,
                ingredient_proteine_id=ingr_ids.get(prot_nom) if prot_nom else None,
                quantite_proteine=qte_prot,
            )
            db.add(obj)
        created += 1

    _print_stats("VariantePlat", created, skipped)
    return created


def seed_sides(db, tenant_id: int, ingr_ids: dict, dry_run: bool) -> int:
    """Crée les SideRestaurant (accompagnements)."""
    created = skipped = 0

    for nom, ingr_nom, qte in SIDES_DATA:
        if _exists(db, SideRestaurant, tenant_id=tenant_id, nom=nom):
            skipped += 1
            continue
        if not dry_run:
            obj = SideRestaurant(
                tenant_id=tenant_id,
                nom=nom,
                ingredient_id=ingr_ids.get(ingr_nom) if ingr_nom else None,
                quantite_par_portion=qte,
            )
            db.add(obj)
        created += 1

    _print_stats("SideRestaurant", created, skipped)
    return created


def seed_tables(db, tenant_id: int, dry_run: bool) -> int:
    """Crée les TableRestaurant."""
    created = skipped = 0

    for numero, capacite in TABLES_DATA:
        if _exists(db, TableRestaurant, tenant_id=tenant_id, numero=numero):
            skipped += 1
            continue
        if not dry_run:
            obj = TableRestaurant(
                tenant_id=tenant_id,
                numero=numero,
                capacite=capacite,
            )
            db.add(obj)
        created += 1

    _print_stats("TableRestaurant", created, skipped)
    return created


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed restaurant — données réelles")
    parser.add_argument("--tenant-id", type=int, default=DEFAULT_TENANT_ID)
    parser.add_argument("--dry-run", action="store_true",
                        help="Simulation : aucune écriture en base")
    args = parser.parse_args()

    tenant_id = args.tenant_id
    dry_run = args.dry_run

    print(f"=== Seed restaurant (tenant_id={tenant_id})"
          f"{' [DRY-RUN]' if dry_run else ''} ===\n")

    with get_db_context() as db:
        cat_ids   = seed_categories(db, tenant_id, dry_run)
        ingr_ids  = seed_ingredients(db, tenant_id, cat_ids, dry_run)
        tp_ids    = seed_types_prep(db, tenant_id, dry_run)
        seed_recettes(db, tenant_id, tp_ids, ingr_ids, dry_run)
        seed_variantes_plat(db, tenant_id, tp_ids, ingr_ids, dry_run)
        seed_sides(db, tenant_id, ingr_ids, dry_run)
        seed_tables(db, tenant_id, dry_run)

        if not dry_run:
            db.commit()
            print("\n✓ Commit effectué.")
        else:
            print("\n[DRY-RUN] Aucune écriture effectuée.")

    total_variantes = len(VARIANTES_DATA)
    total_recettes = sum(len(r) for _, r in RECETTES_BASE_DATA)
    print(f"\n=== Totaux attendus ===")
    print(f"  Catégories        : {len(CATEGORIES_DATA)}")
    print(f"  Ingrédients       : {len(INGREDIENTS_DATA)}")
    print(f"  TypesPreparation  : {len(TYPES_PREP_DATA)}")
    print(f"  Lignes recette    : {total_recettes}")
    print(f"  VariantesPlat     : {total_variantes}")
    print(f"  Sides             : {len(SIDES_DATA)}")
    print(f"  Tables            : {len(TABLES_DATA)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
