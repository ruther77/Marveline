"""Seed 20 clients fictifs réalistes pour Marveline.

Couvre les 7 départements servis : Somme (80), Oise (60), Aisne (02),
Pas-de-Calais (62), Nord (59), Seine-Maritime (76), Val-d'Oise (95).
Mix particuliers / entreprises (traiteurs, salles, associations).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db_context
from app.models.customer import Customer

TENANT_ID = 1

CUSTOMERS = [
    # --- Somme (80) ---
    {
        "customer_type": "individual",
        "first_name": "Camille",
        "last_name": "Dubois",
        "email": "camille.dubois@gmail.com",
        "phone": "06 12 34 56 78",
        "address": "14 rue de la Paix",
        "city": "Amiens",
        "postal_code": "80000",
        "country": "France",
    },
    {
        "customer_type": "individual",
        "first_name": "Thomas",
        "last_name": "Leroy",
        "email": "thomas.leroy@hotmail.fr",
        "phone": "07 23 45 67 89",
        "address": "3 allée des Lilas",
        "city": "Abbeville",
        "postal_code": "80100",
        "country": "France",
    },
    {
        "customer_type": "company",
        "first_name": "Sophie",
        "last_name": "Martin",
        "company_name": "Traiteur Martin & Fils",
        "email": "contact@traiteur-martin.fr",
        "phone": "03 22 10 20 30",
        "address": "Zone artisanale du Moulin",
        "city": "Amiens",
        "postal_code": "80080",
        "country": "France",
    },
    # --- Oise (60) ---
    {
        "customer_type": "individual",
        "first_name": "Julie",
        "last_name": "Bernard",
        "email": "julie.bernard@orange.fr",
        "phone": "06 45 67 89 01",
        "address": "7 impasse des Roses",
        "city": "Compiègne",
        "postal_code": "60200",
        "country": "France",
    },
    {
        "customer_type": "individual",
        "first_name": "Alexandre",
        "last_name": "Petit",
        "email": "alex.petit60@gmail.com",
        "phone": "07 56 78 90 12",
        "address": "22 avenue de la République",
        "city": "Beauvais",
        "postal_code": "60000",
        "country": "France",
    },
    {
        "customer_type": "company",
        "first_name": "Nathalie",
        "last_name": "Dupont",
        "company_name": "Salle des Fêtes de Senlis",
        "email": "reservation@sallesenlis.fr",
        "phone": "03 44 53 00 11",
        "address": "1 place de la Mairie",
        "city": "Senlis",
        "postal_code": "60300",
        "country": "France",
    },
    # --- Aisne (02) ---
    {
        "customer_type": "individual",
        "first_name": "Marie",
        "last_name": "Fontaine",
        "email": "marie.fontaine02@gmail.com",
        "phone": "06 67 89 01 23",
        "address": "5 rue du Château",
        "city": "Laon",
        "postal_code": "02000",
        "country": "France",
    },
    {
        "customer_type": "individual",
        "first_name": "Pierre",
        "last_name": "Garnier",
        "email": "pierre.garnier@sfr.fr",
        "phone": "07 78 90 12 34",
        "address": "18 rue des Vignes",
        "city": "Soissons",
        "postal_code": "02200",
        "country": "France",
    },
    {
        "customer_type": "company",
        "first_name": "Aurélie",
        "last_name": "Chevalier",
        "company_name": "Association Les Mariées de l'Aisne",
        "email": "lesmarieesdelaisne@gmail.com",
        "phone": "06 89 01 23 45",
        "address": "12 rue du Commerce",
        "city": "Saint-Quentin",
        "postal_code": "02100",
        "country": "France",
    },
    # --- Pas-de-Calais (62) ---
    {
        "customer_type": "individual",
        "first_name": "Lucie",
        "last_name": "Moreau",
        "email": "lucie.moreau62@gmail.com",
        "phone": "06 90 12 34 56",
        "address": "9 rue du Général de Gaulle",
        "city": "Arras",
        "postal_code": "62000",
        "country": "France",
    },
    {
        "customer_type": "individual",
        "first_name": "Maxime",
        "last_name": "Simon",
        "email": "maxime.simon@live.fr",
        "phone": "07 01 23 45 67",
        "address": "34 boulevard de la Liberté",
        "city": "Lens",
        "postal_code": "62300",
        "country": "France",
    },
    {
        "customer_type": "company",
        "first_name": "Élodie",
        "last_name": "Rousseau",
        "company_name": "Domaine de la Roseraie",
        "email": "domaine.roseraie@wanadoo.fr",
        "phone": "03 21 45 67 89",
        "address": "Route de la Roseraie",
        "city": "Béthune",
        "postal_code": "62400",
        "country": "France",
    },
    # --- Nord (59) ---
    {
        "customer_type": "individual",
        "first_name": "Hugo",
        "last_name": "Laurent",
        "email": "hugo.laurent59@gmail.com",
        "phone": "06 12 98 76 54",
        "address": "2 rue Nationale",
        "city": "Lille",
        "postal_code": "59000",
        "country": "France",
    },
    {
        "customer_type": "individual",
        "first_name": "Céline",
        "last_name": "Lecomte",
        "email": "celine.lecomte@yahoo.fr",
        "phone": "07 23 09 87 65",
        "address": "56 avenue du Peuple Belge",
        "city": "Dunkerque",
        "postal_code": "59140",
        "country": "France",
    },
    {
        "customer_type": "company",
        "first_name": "Romain",
        "last_name": "Girard",
        "company_name": "Brasserie des Flandres — Événements",
        "email": "events@brasserieflandres.fr",
        "phone": "03 20 33 44 55",
        "address": "48 Grand'Place",
        "city": "Lille",
        "postal_code": "59800",
        "country": "France",
    },
    # --- Seine-Maritime (76) ---
    {
        "customer_type": "individual",
        "first_name": "Émilie",
        "last_name": "Durand",
        "email": "emilie.durand76@gmail.com",
        "phone": "06 34 56 78 90",
        "address": "11 quai de la Bourse",
        "city": "Rouen",
        "postal_code": "76000",
        "country": "France",
    },
    {
        "customer_type": "individual",
        "first_name": "Nicolas",
        "last_name": "Blanc",
        "email": "nicolas.blanc@free.fr",
        "phone": "07 45 67 89 01",
        "address": "3 rue du Havre",
        "city": "Le Havre",
        "postal_code": "76600",
        "country": "France",
    },
    # --- Val-d'Oise (95) ---
    {
        "customer_type": "individual",
        "first_name": "Laura",
        "last_name": "Renard",
        "email": "laura.renard95@gmail.com",
        "phone": "06 56 78 90 12",
        "address": "8 rue des Ormes",
        "city": "Cergy",
        "postal_code": "95000",
        "country": "France",
    },
    {
        "customer_type": "individual",
        "first_name": "Sébastien",
        "last_name": "Morel",
        "email": "sebastien.morel@gmail.com",
        "phone": "07 67 89 01 23",
        "address": "25 avenue du Val-d'Oise",
        "city": "Pontoise",
        "postal_code": "95300",
        "country": "France",
    },
    {
        "customer_type": "company",
        "first_name": "Virginie",
        "last_name": "Caron",
        "company_name": "Château de la Vallée — Location Événementielle",
        "email": "reservation@chateauvallee95.fr",
        "phone": "01 34 21 00 00",
        "address": "1 chemin du Château",
        "city": "L'Isle-Adam",
        "postal_code": "95290",
        "country": "France",
    },
]


def seed_customers():
    with get_db_context() as db:
        existing = db.query(Customer).filter(
            Customer.tenant_id == TENANT_ID,
            Customer.email != "csrftest2@t.com",
        ).count()

        if existing > 0:
            print(f"{existing} clients métier déjà présents — skip.")
            return

        created = 0
        for data in CUSTOMERS:
            c = Customer(
                tenant_id=TENANT_ID,
                is_active=True,
                **data,
            )
            db.add(c)
            created += 1

        db.commit()
        print(f"{created} clients créés ✅")


if __name__ == "__main__":
    seed_customers()
