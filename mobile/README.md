# Lantante Technologie Job — application mobile (Android et iOS)

Application React Native (Expo + TypeScript + Expo Router) qui utilise l'API du site : `https://lantantetechnologie.com/api/v1/`
(documentation : `../LucasTech/docs/API.md`).

Trois espaces, choisis à l'inscription :

| Compte | Onglets |
|---|---|
| Candidat | Offres · Candidatures · Découvrir · Messages · Profil |
| Entreprise | Accueil · Candidatures · Publier · Messages · Plus |
| Particulier | Accueil · Publier · Découvrir · Messages · Plus |

## Lancer en développement

```bash
npm install
npx expo start
```

Scannez le QR code avec l'application **Expo Go** (Android / iPhone). Pour tester contre un serveur local :
`EXPO_PUBLIC_API_URL=http://<ip-du-pc>:8000/api/v1/ npx expo start`.

Vérification du code : `npm run typecheck`.

## Publier les applications (étapes à faire par le propriétaire du compte)

1. Créer un compte gratuit sur https://expo.dev puis `npm i -g eas-cli` et `eas login`.
2. `eas init` (relie le projet à votre compte), puis `eas build:configure`.
3. **Android** : `eas build -p android --profile production` → fichier `.aab` à déposer sur Google Play Console (frais uniques ≈ 25 $).
4. **iOS** : `eas build -p ios --profile production` (la compilation se fait dans le cloud, pas besoin de Mac) →
   envoi sur App Store Connect avec `eas submit -p ios` (compte Apple Developer ≈ 99 $/an).
5. Notifications push : `eas credentials` configure les clés FCM (Android) et APNs (iOS) ; l'adresse Expo Push de chaque
   téléphone est déjà enregistrée sur le serveur (`POST /api/v1/devices`).

Identifiants de l'application : `com.lantantetechnologie.emploi` (Android et iOS), à modifier dans `app.json` si besoin.
