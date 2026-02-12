#!/usr/bin/env python3
"""Script de refactoring : remplace les strings par des constantes Enum.

Usage:
    python scripts/refactor_constants.py --dry-run  # Preview
    python scripts/refactor_constants.py            # Apply
"""

import re
import argparse
from pathlib import Path
from typing import Dict, List, Tuple

# ═══════════════════════════════════════════════════════════════════════════
# Définitions des Enums à créer
# ═══════════════════════════════════════════════════════════════════════════

ENUMS_TO_CREATE = {
    "ProductCategory": {
        "ASSIETTE": "assiette",
        "VERRE": "verre",
        "COUVERT": "couvert",
        "NAPPE": "nappe",
        "DECO": "deco",
        "AUTRE": "autre",
    },
    "ProductCondition": {
        "NEUF": "neuf",
        "BON": "bon",
        "USE": "use",
        "HORS_SERVICE": "hors_service",
    },
    "CustomerType": {
        "INDIVIDUAL": "individual",
        "COMPANY": "company",
    },
    "ReservationStatus": {
        "DRAFT": "draft",
        "CONFIRMED": "confirmed",
        "DELIVERED": "delivered",
        "RETURNED": "returned",
        "CANCELLED": "cancelled",
    },
    "InvoiceStatus": {
        "DRAFT": "draft",
        "SENT": "sent",
        "PAID": "paid",
        "OVERDUE": "overdue",
        "CANCELLED": "cancelled",
    },
    "PaymentMethod": {
        "CASH": "cash",
        "CARD": "card",
        "TRANSFER": "transfer",
        "CHECK": "check",
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Génération du fichier constants.py
# ═══════════════════════════════════════════════════════════════════════════

def generate_constants_file() -> str:
    """Génère le contenu du fichier app/constants.py."""
    lines = [
        '"""Constantes globales de l\'application."""',
        "from enum import Enum",
        "",
        "",
    ]

    for enum_name, values in ENUMS_TO_CREATE.items():
        lines.append(f"class {enum_name}(str, Enum):")
        lines.append(f'    """Valeurs valides pour {enum_name}."""')
        lines.append("")

        for key, value in values.items():
            lines.append(f'    {key} = "{value}"')

        lines.append("")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Patterns de remplacement
# ═══════════════════════════════════════════════════════════════════════════

def build_replacement_patterns() -> List[Tuple[str, str, str]]:
    """Construit la liste des patterns à remplacer.

    Returns:
        List de (pattern_regex, replacement, enum_import)
    """
    patterns = []

    for enum_name, values in ENUMS_TO_CREATE.items():
        for key, value in values.items():
            # Pattern : category="assiette" → category=ProductCategory.ASSIETTE
            # Gère : param="value", param = "value", param='value'
            pattern = rf'(\w+)\s*=\s*["\']({re.escape(value)})["\']'
            replacement = rf'\1={enum_name}.{key}'
            patterns.append((pattern, replacement, enum_name))

    return patterns


# ═══════════════════════════════════════════════════════════════════════════
# Refactoring des fichiers
# ═══════════════════════════════════════════════════════════════════════════

def refactor_file(file_path: Path, patterns: List[Tuple[str, str, str]], dry_run: bool = False) -> Dict:
    """Refactorise un fichier Python.

    Args:
        file_path: Chemin du fichier
        patterns: Liste des (pattern, replacement, enum_name)
        dry_run: Si True, ne modifie pas le fichier

    Returns:
        Dict avec statistiques : {replacements: int, enums_needed: set}
    """
    content = file_path.read_text(encoding="utf-8")
    original_content = content

    enums_needed = set()
    total_replacements = 0

    for pattern, replacement, enum_name in patterns:
        matches = re.findall(pattern, content)
        if matches:
            enums_needed.add(enum_name)
            content = re.sub(pattern, replacement, content)
            total_replacements += len(matches)

    # Ajouter imports si nécessaire
    if enums_needed and content != original_content:
        # Vérifier si app.constants est déjà importé
        if "from app.constants import" not in content and "import app.constants" not in content:
            # Trouver la dernière ligne d'import
            lines = content.split("\n")
            last_import_idx = 0

            for i, line in enumerate(lines):
                if line.startswith("import ") or line.startswith("from "):
                    last_import_idx = i

            # Insérer l'import après le dernier import existant
            import_line = f"from app.constants import {', '.join(sorted(enums_needed))}"
            lines.insert(last_import_idx + 1, import_line)
            content = "\n".join(lines)

    # Écrire le fichier si pas dry-run et changements
    if not dry_run and content != original_content:
        file_path.write_text(content, encoding="utf-8")

    return {
        "replacements": total_replacements,
        "enums_needed": enums_needed,
        "modified": content != original_content,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Fonction principale
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Point d'entrée du script."""
    parser = argparse.ArgumentParser(description="Refactoring automatique des constantes")
    parser.add_argument("--dry-run", action="store_true", help="Preview sans modifier les fichiers")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent

    print("🔧 Refactoring des constantes")
    print("=" * 60)

    # 1. Créer app/constants.py
    constants_file = project_root / "app" / "constants.py"

    if not args.dry_run:
        constants_content = generate_constants_file()
        constants_file.write_text(constants_content, encoding="utf-8")
        print(f"✅ Créé : {constants_file}")
    else:
        print(f"[DRY-RUN] Créerait : {constants_file}")

    # 2. Scanner tous les fichiers Python
    patterns = build_replacement_patterns()

    files_to_refactor = []
    for pattern in ["app/**/*.py", "tests/**/*.py"]:
        files_to_refactor.extend(project_root.glob(pattern))

    # Exclure __pycache__ et constants.py lui-même
    files_to_refactor = [
        f for f in files_to_refactor
        if "__pycache__" not in str(f) and f.name != "constants.py"
    ]

    print(f"\n📁 Fichiers à scanner : {len(files_to_refactor)}")
    print("-" * 60)

    # 3. Refactoriser chaque fichier
    total_replacements = 0
    modified_files = 0

    for file_path in sorted(files_to_refactor):
        result = refactor_file(file_path, patterns, dry_run=args.dry_run)

        if result["modified"]:
            modified_files += 1
            total_replacements += result["replacements"]

            status = "[DRY-RUN]" if args.dry_run else "✅"
            relative_path = file_path.relative_to(project_root)
            enums = ", ".join(sorted(result["enums_needed"]))

            print(f"{status} {relative_path}")
            print(f"   └─ {result['replacements']} remplacements ({enums})")

    # 4. Résumé
    print("\n" + "=" * 60)
    print(f"📊 Résumé :")
    print(f"   - Fichiers modifiés : {modified_files}")
    print(f"   - Remplacements totaux : {total_replacements}")

    if args.dry_run:
        print("\n💡 Lancez sans --dry-run pour appliquer les changements")
    else:
        print("\n✅ Refactoring terminé !")
        print("\n📝 Prochaines étapes :")
        print("   1. Vérifier les fichiers modifiés avec git diff")
        print("   2. Lancer les tests : poetry run pytest")
        print("   3. Commit : git add -A && git commit -m 'refactor: Use Enum constants'")


if __name__ == "__main__":
    main()
