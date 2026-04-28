"""Test du flow complet MFA setup → verify.

Simule exactement ce que font les tests E2E:
1. setup_totp() → retourne secret_plaintext
2. Stocker device avec encrypted_secret en DB
3. Générer code TOTP avec pyotp en utilisant secret_plaintext
4. verify_setup() → décrypte encrypted_secret et vérifie code
5. Comparer secret_plaintext vs secret_decrypted
"""
import asyncio
import time
import pyotp
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.account import Account
from app.models.tenant_membership import TenantMembership
from app.models.mfa import MFADevice
from app.services.mfa import mfa_service
from app.core.crypto import decrypt_totp_secret

TEST_EMAIL = "test@carocorp.com"
TEST_TENANT_ID = 1


async def test_mfa_setup_verify_flow() -> bool:
    """Test complet setup → verify."""
    async with AsyncSessionLocal() as db:
        # Récupérer utilisateur de test existant (IAM v2 : Account + TenantMembership)
        account_row = await db.execute(
            select(Account).where(Account.email == TEST_EMAIL)
        )
        account = account_row.scalar_one_or_none()
        if not account:
            print(f"❌ Account {TEST_EMAIL} non trouvé en DB")
            return False

        membership_row = await db.execute(
            select(TenantMembership).where(
                TenantMembership.account_id == account.id,
                TenantMembership.tenant_id == TEST_TENANT_ID,
                TenantMembership.status == "active",
            )
        )
        membership = membership_row.scalar_one_or_none()
        if not membership:
            print(f"❌ TenantMembership non trouvée (account_id={account.id}, tenant_id={TEST_TENANT_ID})")
            return False

        user_id = account.id
        tenant_id = membership.tenant_id
        email = account.email

        print(f"✓ Utilisateur de test: {email} (account_id={user_id}, tenant={tenant_id})")

        # Nettoyer device existant si présent
        existing_row = await db.execute(
            select(MFADevice).where(MFADevice.membership_id == membership.id)
        )
        existing = existing_row.scalar_one_or_none()
        if existing:
            await db.delete(existing)
            await db.commit()

        print("=" * 70)
        print("ÉTAPE 1: Setup MFA (comme POST /mfa/setup)")
        print("=" * 70)

        # Setup MFA (retourne secret en clair)
        secret_plaintext, provisioning_uri, recovery_codes = await mfa_service.setup_totp(
            db=db,
            user_id=user_id,
            tenant_id=tenant_id,
            email=email
        )
        await db.commit()

        print(f"✓ Secret retourné (plaintext): {secret_plaintext}")
        print(f"  Longueur: {len(secret_plaintext)} caractères")
        print(f"✓ Provisioning URI: {provisioning_uri[:50]}...")
        print(f"✓ Recovery codes: {len(recovery_codes)} codes générés")

        print("\n" + "=" * 70)
        print("ÉTAPE 2: Vérifier secret stocké en DB")
        print("=" * 70)

        # Récupérer device de la DB
        device_row = await db.execute(
            select(MFADevice).where(
                MFADevice.membership_id == membership.id,
                MFADevice.is_enabled == False,  # noqa: E712
            )
        )
        device = device_row.scalar_one_or_none()

        if not device:
            print("❌ ERREUR: Device MFA non trouvé en DB!")
            return False

        print(f"✓ Device trouvé: ID={device.id}, enabled={device.is_enabled}")
        print(f"  Encrypted secret: {len(device.encrypted_secret)} bytes")

        # Décrypter le secret stocké
        secret_decrypted = decrypt_totp_secret(device.encrypted_secret)
        print(f"✓ Secret décrypté: {secret_decrypted}")

        # Comparer plaintext vs decrypted
        if secret_plaintext != secret_decrypted:
            print(f"❌ ERREUR: Secrets différents!")
            print(f"   Plaintext:  '{secret_plaintext}'")
            print(f"   Décrypté:   '{secret_decrypted}'")
            return False

        print("✅ Secret plaintext == secret décrypté")

        print("\n" + "=" * 70)
        print("ÉTAPE 3: Générer code TOTP (comme otpauth côté frontend)")
        print("=" * 70)

        # Générer code TOTP avec le secret plaintext (comme le frontend)
        totp = pyotp.TOTP(secret_plaintext, digits=6, interval=30)
        totp_code = totp.now()
        current_window = int(time.time()) // 30

        print(f"✓ Code TOTP généré: {totp_code}")
        print(f"  Window actuel: {current_window}")

        print("\n" + "=" * 70)
        print("ÉTAPE 4: Vérifier setup (comme POST /mfa/verify-setup)")
        print("=" * 70)

        # Vérifier le code (comme verify_setup)
        try:
            result = await mfa_service.verify_setup(
                db=db,
                user_id=user_id,
                tenant_id=tenant_id,
                totp_code=totp_code
            )
            await db.commit()

            if result:
                print("✅ verify_setup() SUCCÈS — Code TOTP accepté")

                # Vérifier que le device est maintenant enabled
                await db.refresh(device)
                if device.is_enabled:
                    print(f"✅ Device enabled: {device.is_enabled}")
                    print(f"  Last window: {device.last_totp_window}")
                else:
                    print(f"⚠️  Device.is_enabled={device.is_enabled} (devrait être True)")

                return True
            else:
                print("❌ verify_setup() retourné False")
                return False

        except ValueError as e:
            print(f"❌ verify_setup() ÉCHEC: {e}")
            print("\nDÉBUG: Vérifions manuellement la vérification TOTP...")

            # Vérifier manuellement
            totp_manual = pyotp.TOTP(secret_decrypted, digits=6, interval=30)
            is_valid = totp_manual.verify(totp_code, valid_window=1)
            print(f"  Code {totp_code} valide avec valid_window=1: {is_valid}")

            if is_valid:
                print("  ⚠️  Le code est VALIDE mais verify_setup() l'a rejeté!")
                print("  Cela indique un bug dans la logique de vérification.")
            else:
                print("  Le code est INVALIDE (probablement expiré ou timing issue)")
                new_code = totp.now()
                new_window = int(time.time()) // 30
                print(f"\nRé-essai avec nouveau code: {new_code} (window: {new_window})")

                try:
                    result2 = await mfa_service.verify_setup(db, user_id, tenant_id, new_code)
                    await db.commit()
                    if result2:
                        print("✅ SUCCÈS avec nouveau code")
                        return True
                except ValueError as e2:
                    print(f"❌ ÉCHEC avec nouveau code: {e2}")

            return False

        finally:
            # Nettoyer
            cleanup_row = await db.execute(
                select(MFADevice).where(MFADevice.membership_id == membership.id)
            )
            cleanup_device = cleanup_row.scalar_one_or_none()
            if cleanup_device:
                await db.delete(cleanup_device)
            await db.commit()


if __name__ == "__main__":
    success = asyncio.run(test_mfa_setup_verify_flow())
    print("\n" + "=" * 70)
    if success:
        print("✅ FLOW COMPLET RÉUSSI")
        exit(0)
    else:
        print("❌ FLOW COMPLET ÉCHOUÉ")
        exit(1)
