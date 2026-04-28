"""Valide l'intégrité de la chaîne Alembic.

Vérifie que :
1. Toutes les révisions référencées comme down_revision existent
2. Il n'y a pas de tête multiple non intentionnelle (merge manquant)
3. La chaîne est linéaire (ou les branches sont explicitement mergées)

Usage :
    python scripts/check_migrations.py          # exit 0 si OK, 1 si erreur
    docker compose run --rm api python scripts/check_migrations.py
    make migration-check
"""
import sys
import os

# IMPORTANT : ne PAS sys.path.insert(0, project_root) car le dossier `alembic/` du projet
# contient un __init__.py qui shadow le package PyPI `alembic` (rendant `alembic.config`
# introuvable). Le script doit s'exécuter avec le package PyPI prioritaire.
# Si besoin du root projet : append (low-priority) au lieu d'insert.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic.config import Config
from alembic.script import ScriptDirectory

EXIT_OK = 0
EXIT_ERROR = 1


def check_migrations() -> int:
    cfg = Config("alembic.ini")
    scripts = ScriptDirectory.from_config(cfg)

    errors = []
    all_revs: dict[str, object] = {}

    # Indexer toutes les révisions connues
    for script in scripts.walk_revisions():
        all_revs[script.revision] = script

    # Vérifier que chaque down_revision pointe vers une révision existante
    for rev_id, script in all_revs.items():
        down = script.down_revision
        if down is None:
            continue  # base de la chaîne
        if isinstance(down, (list, tuple)):
            parents = down  # merge commit
        else:
            parents = [down]

        for parent in parents:
            if parent not in all_revs:
                errors.append(
                    f"  ❌  {rev_id} ({script.doc}) → down_revision '{parent}' introuvable"
                )

    # Vérifier les têtes multiples (branches non mergées)
    heads = scripts.get_heads()
    if len(heads) > 1:
        head_details = [
            f"    • {h} ({all_revs[h].doc})" for h in heads if h in all_revs
        ]
        errors.append(
            "  ⚠️  Têtes multiples détectées (branches non mergées) :\n"
            + "\n".join(head_details)
            + "\n  → Créer une migration de merge : "
            "make new-migration MSG=\"merge heads\""
        )

    if errors:
        print("❌  Problèmes détectés dans la chaîne Alembic :\n")
        for e in errors:
            print(e)
        return EXIT_ERROR

    print(f"✅  Chaîne Alembic valide — {len(all_revs)} révisions, 1 tête ({heads[0]})")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(check_migrations())
