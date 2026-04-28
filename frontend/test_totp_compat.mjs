/**
 * Test de compatibilité otpauth (JS) vs pyotp (Python)
 *
 * Génère des codes TOTP avec otpauth en utilisant les mêmes secrets
 * que ceux générés par pyotp côté backend.
 */
import * as OTPAuth from 'otpauth'

// Secret de error-context.md
const testSecrets = [
  'FZNBEFDHOIMZGKZJN35QNSBJVWCQUM7S',  // Depuis error-context.md, code entré: 243184
]

console.log('🔍 Test compatibilité otpauth (JS) vs pyotp (Python)\n')

for (const secret of testSecrets) {
  console.log(`\nSecret: ${secret}`)
  console.log(`  Longueur: ${secret.length} caractères`)

  try {
    // Créer TOTP avec otpauth (comme dans generateTOTPCode)
    const totp = new OTPAuth.TOTP({
      algorithm: 'SHA1',
      digits: 6,
      period: 30,
      secret: OTPAuth.Secret.fromBase32(secret),
    })

    // Générer code actuel
    const code = totp.generate()
    console.log(`  ✅ Code TOTP généré: ${code}`)

    // Afficher timestamp actuel pour comparaison avec Python
    const now = Math.floor(Date.now() / 1000)
    const window = Math.floor(now / 30)
    console.log(`  Timestamp: ${now} (window: ${window})`)

  } catch (error) {
    console.log(`  ❌ ERREUR: ${error.message}`)
  }
}

console.log('\n📋 Pour comparer avec pyotp, exécutez:')
console.log('docker compose run --rm --entrypoint "" api python -c "import pyotp, time; secret=\'FZNBEFDHOIMZGKZJN35QNSBJVWCQUM7S\'; totp=pyotp.TOTP(secret, digits=6, interval=30); print(f\'Code: {totp.now()}, Window: {int(time.time()) // 30}\')"')
