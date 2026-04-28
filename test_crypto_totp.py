"""Test de réversibilité encryption/decryption TOTP secret.

Vérifie que encrypt_totp_secret() → decrypt_totp_secret() préserve le secret.
Vérifie aussi que pyotp génère les mêmes codes avec le secret original et décrypté.
"""
import pyotp
from app.core.crypto import encrypt_totp_secret, decrypt_totp_secret

def test_crypto_reversibility():
    """Test que l'encryption/decryption ne corrompt pas le secret."""
    # Générer un secret comme le fait le backend
    original_secret = pyotp.random_base32()
    print(f"✓ Secret original: {original_secret}")
    print(f"  Longueur: {len(original_secret)} caractères")

    # Encrypter
    encrypted = encrypt_totp_secret(original_secret)
    print(f"✓ Secret encrypté: {len(encrypted)} bytes")

    # Décrypter
    decrypted_secret = decrypt_totp_secret(encrypted)
    print(f"✓ Secret décrypté: {decrypted_secret}")

    # Vérifier égalité
    if original_secret == decrypted_secret:
        print("✅ Encryption/decryption réversible — secrets identiques")
    else:
        print(f"❌ ERREUR: Secrets différents!")
        print(f"   Original:  '{original_secret}'")
        print(f"   Décrypté:  '{decrypted_secret}'")
        return False

    # Générer codes TOTP avec les deux
    totp_original = pyotp.TOTP(original_secret, digits=6, interval=30)
    totp_decrypted = pyotp.TOTP(decrypted_secret, digits=6, interval=30)

    code_original = totp_original.now()
    code_decrypted = totp_decrypted.now()

    print(f"✓ Code TOTP (secret original):  {code_original}")
    print(f"✓ Code TOTP (secret décrypté):  {code_decrypted}")

    if code_original == code_decrypted:
        print("✅ Codes TOTP identiques — encryption ne corrompt pas TOTP")
        return True
    else:
        print(f"❌ ERREUR: Codes TOTP différents!")
        return False

if __name__ == "__main__":
    success = test_crypto_reversibility()
    exit(0 if success else 1)
