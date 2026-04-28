# Démo Le Splendid Events — Script Loom 90s

**Cible** : Le Splendid Events (prospect Facebook, frustré Lokki, RDV mardi 28/04).
**Durée** : 90s strict (au-delà = perte d'attention, cf ux-strategy §13).
**Halo effect** : la première impression compte sur les 10 premières secondes.

## Promesse d'ouverture (0:00 → 0:05)

**À l'écran** : page de connexion Marveline avec brand Le Splendid (or/sombre).
**Voix** : "En 90 secondes, je vous montre comment votre devis devient une
réservation, pilote votre stock, et trace chaque changement jusqu'à la
restitution. Sans Excel, sans relances oubliées, sans surprises au retour."

> Hook = bénéfice utilisateur immédiat (Call-to-Value §6), pas "voici les
> fonctionnalités".

---

## Acte 1 — Le devis vivant (0:05 → 0:25)

**À l'écran** :
1. `/devis/new` — wizard 5 étapes
2. Sélection client "Mariage Caroline & Thomas"
3. Ajout 2 lignes : `100 × Chaise Tiffany or` + `10 × Nappe satin blanc`
4. Étape 5 : aperçu PDF généré → envoi par mail
5. Toast "Devis envoyé"

**Voix** : "Vous créez un devis en 5 étapes. Le PDF part au client tout de
suite, signé, avec vos CGV à jour. Le client clique sur le lien et accepte
en ligne — vous voyez l'acceptation arriver dans votre app."

**Différenciateur Lokki** : Lokki ne génère pas de PDF en marque blanche
avec CGV personnalisées par tenant.

---

## Acte 2 — Le devis devient réservation (0:25 → 0:45)

**À l'écran** :
1. Bandeau "Devis accepté" sur la fiche
2. Bouton **"Convertir en réservation"** → 1 clic
3. Vue Réservation détaillée :
   - Statut `confirmée`
   - Cards : caution `1 200 €`, équipe assignée, pré-check matériel
   - Mini-timeline livraison/événement/retour
4. Notification email arrivée client

**Voix** : "Quand le client accepte, le devis devient automatiquement une
réservation. Le stock est verrouillé, la caution est demandée, votre équipe
est notifiée. Vous n'avez rien à ressaisir."

**Point clé à la voix** : "Et si à J-7 la caution n'est toujours pas
encaissée, l'app crée une alerte automatique sur la fiche. Vous ne courrez
plus après les acomptes."

> **Ce qu'on montre vite** : la pastille "Risque : caution manquante J-7" sur
> la fiche, créée par la tâche Celery quotidienne (P8).

---

## Acte 3 — Le scénario que vous redoutez (0:45 → 1:10)

**À l'écran** :
1. Mail simulé du client : "Finalement, on sera 120 invités, il me faut
   20 chaises de plus."
2. Sur la fiche résa convertie : bouton **"Modifier le périmètre (avenant)"**
3. Modale qui s'ouvre :
   - Raison : "Client : 120 invités au lieu de 100"
   - Nouvelle date événement (si décalage) — ici on change juste les lignes
4. Validation → toast "Avenant créé : nouvelle version du devis générée"
5. Onglet "Versions" du devis : v1 (snapshot pré-avenant) + v2 (active)
   avec le nom de l'utilisateur qui a fait le changement

**Voix** : "Le client change d'avis trois jours avant ? Un clic sur
'Modifier le périmètre'. L'ancienne version du devis reste figée pour la
trace contractuelle, la nouvelle est active. Le stock est recalculé.
Le client reçoit la nouvelle version. Tout est tracé, vous n'oubliez rien."

**Différenciateur Lokki** : c'est le moment où Lokki perd ses utilisateurs
(devis figé après envoi, pas de versioning, modifs manuelles dans Excel).

---

## Acte 4 — Le différenciateur invisible : le retour (1:10 → 1:30)

**À l'écran** :
1. Statut résa = `livrée`
2. Bouton **"Constater le retour"**
3. Modale d'inspection :
   - 100 chaises Tiffany : 97 retournées, **3 endommagées** (rayures)
   - 10 nappes : 10 retournées, état OK
   - Charge à imputer : `60 €` (3 × 20 €)
4. Validation → la résa bascule en `litige` automatiquement
5. Section "Journal du litige" qui apparaît en bas avec timeline :
   - 🟡 **Litige ouvert** — 3 items endommagés, 60 € imputés
6. Plus tard : ajout d'une note "Client conteste, accord à 30 €"
7. Bouton "Clôturer le litige" → entrée ✅ **Litige résolu**

**Voix** : "Au retour, vous constatez le matériel ligne par ligne. S'il y
a de la casse, l'app ouvre automatiquement un litige tracé, calcule la
charge, et vous donne un journal append-only que vous pouvez sortir en
audit. Vous savez quoi facturer, et pourquoi."

**Différenciateur Lokki absolu** : aucun outil grand public ne fait ça.
C'est le moment "ah ouais, ok" du prospect.

---

## Closing (1:30 → 1:35)

**À l'écran** : retour sur la fiche résa, statut `terminée`, montant
finalisé, lien fiche client (avec son segment RFM "VIP").

**Voix** : "Tout est tracé, du devis au retour. Tout est dans une seule
app. RDV mardi."

---

## Notes de tournage

- **Ordre filmage** : on tourne acte 1 → 4 dans l'ordre, puis on cut à 90s
  net en post.
- **Souris** : déplacements lents et nets (zoom natif Loom suffit).
- **Audio** : intro/outro punchy, milieu plus posé.
- **Pas de bug visible** : si le seed plante, on relance avant de filmer.
- **Pas de mention IA** dans la voix-off (règle A7).

## Pre-flight (avant Loom)

1. URL : `https://everette-unattacked-genna.ngrok-free.dev/`
2. Login : `demo@lesplendidevent.fr` / `DemoSplendid2026!`
3. Tenant id 5 — vérifier brand or/sombre rendu correctement
4. Vérifier qu'au moins **1 devis non-converti** existe (sinon en créer un)
5. Vérifier qu'au moins **1 résa convertie en statut `delivered`** existe
   (sinon basculer une résa pour acte 4)
6. Désactiver les notifs système macOS pendant le tournage

## Si vivant (RDV mardi en visio)

Même structure mais on commente en réagissant aux questions. Garder l'acte
4 pour la fin = le prospect s'accroche jusqu'au bout.
