# API mobile Lantante Technologie (v1)

Base : `https://lantantetechnologie.com/api/v1/` — JSON (envoi de fichiers en `multipart/form-data`).

## Authentification
`Authorization: Token <jeton>` sur tous les appels sauf ceux marqués *public*.
Le jeton est renvoyé par `auth/register` et `auth/login` ; `auth/logout` le supprime.
Connexion et inscription : 10 essais par minute et par adresse IP (réponse `429` au-delà).

## Format des réponses
- Succès : l'objet, ou `{count, page, pages, results}` pour les listes (`?page=2`).
- Erreur : `{ "detail": "message lisible en français", "code": "invalid|no_cv|wrong_account_type|…", "errors": { champ: ["…"] } }`.
- `401` pas connecté · `403` mauvais type de compte ou accès interdit · `404` introuvable · `400` données à corriger.

## Trois types de comptes
`kind` vaut `candidate` (cherche un emploi), `employer` (entreprise), `member` (particulier), `undefined` (à choisir) ou `anonymous`.
Un endpoint réservé à un autre type répond `403` avec `code: "wrong_account_type"`.

## Compte
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `config` *(public)* | Listes de choix (domaines, contrats, durées…), numéros de paiement |
| POST | `auth/register` *(public)* | `email, password, account_type, first_name, last_name, phone?, city?` → `{token, user}` |
| POST | `auth/login` *(public)* | `email, password` → `{token, user}` |
| POST | `auth/logout` | Supprime le jeton |
| GET/PATCH | `me` | Profil du compte + compteurs (`unread_notifications`, `unread_messages`, `new_applications`) ; PATCH multipart pour `avatar` |
| POST | `me/account-type` | Compte sans type : `{account_type}` (une seule fois) |
| POST/DELETE | `devices` | Enregistre / retire le téléphone pour les notifications push : `{token, platform}` |
| GET | `dashboard` | Synthèse de l'écran d'accueil selon le type de compte |

## Offres, entreprises, partenaires, actualités
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `offers` *(public)* | Offres ouvertes ; `q, domain, contract, city, page`. Réservé aux candidats et visiteurs |
| GET | `offers/<slug>` *(public)* | Détail + `applied`, `can_apply`, entreprise |
| GET | `companies`, `companies/<id>` *(public)* | Entreprises acceptées ; le détail contient offres et publications |
| GET | `partners`, `partners/<id>` *(public)* | Partenaires (visibles par tous) |
| GET | `feed` *(public)* | Actualités (mises en avant d'abord) |
| POST | `feed/<id>/like`, `feed/<id>/comments` | J'aime (bascule), commentaire `{text}` |

## Candidat
| Méthode | Chemin | Rôle |
|---|---|---|
| GET/POST/PATCH | `candidate/profile` | Profil (multipart pour `cv` PDF). `POST` crée ou met à jour ; `PATCH` ne change que les champs envoyés. Contient la lettre de motivation par défaut (`cover_letter`) |
| GET/POST | `candidate/documents` | Diplômes (PDF, JPG, PNG, 5 Mo) ; `DELETE candidate/documents/<id>` |
| POST | `offers/<slug>/apply` | `{text, internship_duration?, available_from?}` — envoie CV, profil et lettre **directement à l'entreprise**. Exige un CV (`code: no_cv`) |
| GET | `candidate/applications` | Mes candidatures et leur étape |
| POST | `candidate/applications/<id>/availability` | `{slots: [ISO, …max 3], note}` (candidature présélectionnée) |
| POST | `candidate/applications/<id>/consent` | `{answer: accept|decline}` (opportunité proposée par Lantante) |
| GET/POST | `candidate/requests` | Demandes spontanées ; `PATCH/DELETE candidate/requests/<id>` (modifier / retirer) |
| GET | `appointments`, POST `appointments/<id>/respond` | `{action: confirm|decline}` |

## Entreprise
| Méthode | Chemin | Rôle |
|---|---|---|
| GET/POST/PATCH | `employer/profile` | Fiche entreprise (multipart pour `logo`, `document`). Statut : `pending`, `approved`, `rejected` |
| GET | `employer/applications` | Candidatures reçues ; `tab=new|progress|hired|refused|all`, `offer=<id>` ; chaque candidat contient `email`, `phone`, `cv_url`, `documents` |
| GET | `employer/applications/<id>` | Une candidature reçue (même contenu que la liste) |
| POST | `employer/applications/<id>/decide` | `{action: shortlist|accept|refuse, message?}` |
| POST | `employer/applications/<id>/schedule` | `{when: ISO, place, notes}` — fixe l'entretien |
| GET | `employer/offers`, POST `employer/offers/<slug>/filled` | Mes offres en cours ; « poste pourvu » |
| GET | `candidates/<id>` | Profil d'un candidat **qui a postulé** chez moi (sinon `403 masked`) |

Les profils des candidats sont masqués : une entreprise ne voit que ceux qui ont postulé à ses offres.

## Publier et payer (entreprise et particulier)
| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `publish/plans` | Services et tarifs selon le compte (`exempt: true` pour un partenaire) |
| GET/POST | `orders` | Mes commandes ; création `{plan: <code>, …}` : actualité/mise en avant/publicité (`text, post_kind, title?, image?, link_url?`), offre (`title, domain, contract, description…`), mise en avant d'offre (`offer: <id>`), accompagnement (`title, domain, positions…`) |
| GET/PATCH | `orders/<id>` | Détail (étapes, statut) ; correction possible tant que le statut le permet |
| POST | `orders/<id>/pay` | `{payment_method: flooz|tmoney, payer_phone, payment_reference}` — Lantante confirme ensuite le paiement |
| POST | `orders/<id>/cancel` | Annule une commande non payée |
| GET | `orders/<id>/receipt` | Reçu après confirmation du paiement |

Parcours : paiement avant validation → Lantante vérifie → publication ou demande de correction.

## Messagerie, notifications, fichiers privés
| Méthode | Chemin | Rôle |
|---|---|---|
| GET/POST | `conversations` | Liste ; `POST {user_id, subject?, body}` ou `{support: true, body}` (service client, accusé automatique une seule fois) |
| GET | `conversations/<id>` | Messages (marque comme lus) ; `POST conversations/<id>/messages {body}` |
| GET/POST | `notifications` | Liste ; `POST` marque tout comme lu |
| GET | `candidates/<id>/cv`, `documents/<id>/file` | Fichiers privés (jeton obligatoire, droits contrôlés) |

## Notifications push
Chaque notification du site est aussi envoyée sur le téléphone (Expo Push). Le champ `data.url` contient le chemin du site correspondant (`/emploi/mon-espace/`, `/emploi/messages/12/`, `/emploi/rendez-vous/`, `/emploi/candidatures-recues/`…) pour ouvrir le bon écran.
