# 📅 Maison Lumen : une API de rendez-vous et son site Webflow

Une API en Python (FastAPI) qui gère la prise de rendez-vous d'un salon de coiffure, branchée sur un site vitrine construit en no-code sur Webflow.

> ⚠️ **Site de démonstration.** Maison Lumen est un salon de coiffure **fictif**, créé pour mon portfolio. Aucun rendez-vous pris sur le site n'est réel.

| | |
|---|---|
| 🌐 Site | [maison-lumen-c4b75a.webflow.io](https://maison-lumen-c4b75a.webflow.io) |
| 📅 Réservation | [/reserver](https://maison-lumen-c4b75a.webflow.io/reserver) |
| 🗓️ Espace salon | [/admin](https://maison-lumen-c4b75a.webflow.io/admin) (clé admin demandée) |
| ⚙️ API en ligne | [rdv-api-awu1.onrender.com/docs](https://rdv-api-awu1.onrender.com/docs) |

L'API est hébergée sur l'offre gratuite de Render : elle s'endort après 15 minutes sans visite, la première réponse peut donc prendre jusqu'à une minute. Le site affiche un message pendant ce réveil.

---

## 🤝 Un projet Python et un projet no-code, réunis

Je voulais montrer qu'une API écrite à la main et un site construit en no-code peuvent former un vrai produit. D'un côté, cette API en Python avec FastAPI : elle calcule les créneaux libres, valide chaque réservation, refuse les doublons, applique la règle des 24 h, envoie les emails et protège les données des clientes. De l'autre, un site vitrine réalisé sur Webflow pour un salon fictif, Maison Lumen, à partir d'une inspiration Pinterest. Le lien entre les deux, c'est un module de réservation en JavaScript que j'ai intégré dans les pages Webflow : il interroge l'API en direct pour afficher les créneaux, envoie la réservation et affiche les messages d'erreur de l'API en français. Une deuxième page, l'espace salon, permet à l'administratrice de gérer le planning, les annulations et les prestations avec sa clé. Webflow s'occupe du design et de l'hébergement des pages, l'API (déployée sur Render) s'occupe de toute la logique. Ce projet m'a appris à faire dialoguer deux mondes : la rapidité du no-code pour l'interface, et la rigueur d'un back-end testé pour tout ce qui ne doit pas casser.

```
 Navigateur de la cliente
        │
        ▼
 Site Webflow (design, pages, hébergement)
   └── module JavaScript intégré (réservation / espace salon)
        │  fetch() en HTTPS
        ▼
 API FastAPI sur Render (créneaux, règles, sécurité)
   ├── base de données (SQLite, ou PostgreSQL via DATABASE_URL)
   └── relais Gmail (Google Apps Script) → emails à la cliente
```

---

## 🧭 Journal du projet, depuis le premier jour

### Partie 1 : construire l'API (13 octobre)

**1. Préparer l'environnement.**
J'ai installé Python avec Homebrew et créé un environnement virtuel (`venv`), un espace isolé pour les bibliothèques du projet. J'y ai installé FastAPI, SQLModel et pytest, puis j'ai créé `requirements.txt` (la liste des bibliothèques) et `.gitignore` (les fichiers à ne jamais mettre sur GitHub).

**2. Calculer les créneaux (`creneaux.py`).**
C'est le cœur du projet, et il ne dépend de rien : de 9 h à 18 h, par tranches de 30 minutes, sans la pause de 12 h à 13 h, fermé le dimanche. Toute l'API a été construite autour de ce module.

**3. Créer la base de données (`database.py`).**
J'ai connecté le projet à une base SQLite (`rdv.db`). Les données restent enregistrées quand on arrête le serveur : c'est la **persistance**.

**4. Décrire les données et leurs règles (`models.py`).**
Deux types de données : une **prestation** (nom, prix, description) et un **rendez-vous** (client, email, téléphone, date, prestation). J'ai ajouté des règles de **validation** : email valide, numéro de téléphone français, date dans le futur, heure qui tombe pile sur un créneau. Si une règle n'est pas respectée, l'API refuse la demande.

**5. Créer les routes (`main.py`).**
Une route, c'est une adresse de l'API associée à une action (`GET` pour lire, `POST` pour créer, `PATCH` pour modifier, `DELETE` pour supprimer). FastAPI génère tout seul la documentation interactive `/docs`.

**6. Réserver, déplacer, annuler.**
Avant d'enregistrer, l'API vérifie que le créneau est libre (sinon erreur **409**). Déplacer ou annuler est refusé moins de 24 h avant le rendez-vous (erreur **400**).

**7. Rendre les erreurs claires.**
Les erreurs de FastAPI sont en anglais par défaut. Je les ai toutes traduites en français, au même format, pour qu'un site puisse les afficher telles quelles :

```json
{
  "erreur": "Données invalides",
  "code": 422,
  "details": [{"champ": "prix", "message": "Doit être supérieur à 0."}]
}
```

**8. Tester et publier.**
13 premiers tests automatiques avec pytest, sur une base temporaire pour ne pas toucher à la vraie. Puis premier commit et publication sur GitHub.

### Partie 2 : préparer la mise en ligne (29 octobre)

**9. Sécuriser l'API.**
Un site public peut être lu par n'importe qui, donc la sécurité doit être **dans l'API**, jamais dans la page :
- une **clé admin** pour les routes du salon, lue dans une variable d'environnement, jamais écrite dans le code ;
- un **jeton secret par rendez-vous**, donné une seule fois à la cliente, pour qu'elle seule puisse voir, déplacer ou annuler le sien ;
- une **limite de requêtes** par adresse IP (`slowapi`), un **champ piège** contre les robots, des réservations limitées à 60 jours ;
- **CORS** limité au site du salon et **en-têtes de sécurité** sur chaque réponse.

**10. Déployer sur Render.**
Le fichier `render.yaml` décrit le service : commande d'installation, commande de démarrage, fuseau horaire de Paris, variables d'environnement. Les valeurs secrètes se règlent dans le tableau de bord de Render, pas dans le dépôt.

### Partie 3 : designer et développer le site sur Webflow (29 octobre)

**11. Trouver la direction artistique.**
Je suis partie d'une inspiration Pinterest pour un salon haut de gamme : tons crème et sable, grande typographie à empattements, photos en pleine largeur, beaucoup d'espace. J'ai appelé le salon **Maison Lumen**.

**12. Construire les pages.**
- **Accueil** : en-tête, présentation du salon, cartes des prestations (Coupe & brushing, Brushing & mise en forme, Coloration), appel à réserver.
- **Réserver** : la page qui accueille le module de réservation.
- **Espace salon** (`/admin`) : la page de gestion pour l'administratrice.

**13. Brancher Webflow sur l'API.**
Webflow ne sait pas parler à une API tout seul. J'ai donc écrit un module en HTML, CSS et JavaScript, intégré dans chaque page avec un bloc *Embed* (le code est dans le dossier [`webflow/`](webflow)). Il appelle l'API avec `fetch()` et affiche ses réponses dans le style du site.

Côté cliente, sur `/reserver` :
- choix de la prestation, du jour, puis d'un créneau libre chargé en direct ;
- formulaire avec un message qui dit ce qu'il manque avant de pouvoir confirmer ;
- tous les messages d'erreur de l'API affichés en français (créneau déjà pris, téléphone invalide, trop de demandes…) ;
- un onglet « Gérer mon rendez-vous » pour déplacer ou annuler avec son numéro et son code ;
- un lien depuis l'accueil qui coche directement la bonne prestation (`/reserver?prestation=coloration`).

Côté salon, sur `/admin` :
- connexion avec la clé admin, gardée seulement le temps de l'onglet ;
- planning jour par jour, liste des rendez-vous à venir ;
- ajout d'un rendez-vous pris par téléphone, déplacement, annulation avec motif ;
- gestion des prestations (ajouter, modifier le prix, supprimer).

### Partie 4 : finaliser le produit (3 novembre)

**14. Une seule clé admin, choisie par le salon.**
L'administratrice choisit elle-même sa clé et la colle dans la variable `ADMIN_API_KEY` sur Render. C'est cette clé qu'elle tape pour entrer dans l'espace salon. Elle n'apparaît nulle part dans le code, sur GitHub ou dans le site.

**15. Les mêmes critères d'annulation pour tout le monde.**
La cliente comme le salon ne peuvent annuler ou déplacer qu'un rendez-vous à venir, au moins 24 h avant. Le salon doit en plus choisir un **motif** (demande de la cliente, salon indisponible, autre avec précision), repris dans l'email envoyé à la cliente.

**16. Les emails à la cliente.**
Confirmation (avec le numéro, le code de gestion et un lien « Gérer mon rendez-vous » qui pré-remplit le formulaire), déplacement et annulation. L'offre gratuite de Render bloque l'envoi d'emails classique (SMTP) : l'API passe donc par un petit **relais Google Apps Script** ([`docs/relais-email.gs`](docs/relais-email.gs)) protégé par un secret, qui envoie depuis la boîte Gmail du salon. L'email part après la réponse : si l'envoi échoue, la réservation reste valide.

**17. Une vraie base de données.**
Sur l'offre gratuite de Render, le fichier SQLite est effacé à chaque mise en veille. L'API accepte donc une adresse PostgreSQL (Neon) dans `DATABASE_URL`, et garde SQLite pour le développement. L'espace salon affiche deux voyants : emails configurés ou non, base durable ou temporaire.

**18. Des prestations toujours présentes.**
Au démarrage, si la liste est vide, l'API crée les trois prestations des cartes de l'accueil. Sans ça, une base effacée laissait la page de réservation sans prestation, et le bouton « Confirmer » restait bloqué.

**19. Afficher que c'est une démo.**
Un bandeau sur chaque page et « (démo) » dans les titres SEO, pour que personne ne prenne Maison Lumen pour un vrai salon.

**Résultat : 50 tests automatiques réussis.**

---

## 🛠️ Technologies

| Partie | Outils |
|---|---|
| API | Python, FastAPI, SQLModel, Pydantic, slowapi |
| Base de données | SQLite en local, PostgreSQL (Neon) en ligne |
| Tests | pytest (50 tests) |
| Site | Webflow (design, pages, hébergement) |
| Module de réservation | HTML, CSS, JavaScript (`fetch`) intégrés dans Webflow |
| Emails | Google Apps Script (relais Gmail) |
| Hébergement de l'API | Render (offre gratuite) |

---

## 🚀 Lancer le projet en local

```bash
# 1. Créer et activer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# 2. Installer les bibliothèques
pip install -r requirements.txt

# 3. Copier le modèle de configuration (et choisir sa clé admin dedans)
cp .env.example .env

# 4. Lancer le serveur
uvicorn app.main:app --reload

# 5. Lancer les tests
python -m pytest -v
```

Ensuite, ouvrir **http://127.0.0.1:8000/docs** pour tester toutes les routes.

---

## 📌 Les routes de l'API

| Action                   | Méthode  | Route                       | Qui peut l'utiliser            |
|--------------------------|----------|-----------------------------|--------------------------------|
| Voir les prestations     | `GET`    | `/prestations`              | Tout le monde                  |
| Créer une prestation     | `POST`   | `/prestations`              | 🔒 Le salon (clé admin)        |
| Modifier une prestation  | `PATCH`  | `/prestations/{id}`         | 🔒 Le salon (clé admin)        |
| Supprimer une prestation | `DELETE` | `/prestations/{id}`         | 🔒 Le salon (clé admin)        |
| Voir les créneaux libres | `GET`    | `/creneaux?jour=2026-10-20` | Tout le monde                  |
| Réserver                 | `POST`   | `/rendez-vous`              | Tout le monde (5 par heure)    |
| Réserver pour un client  | `POST`   | `/salon/rendez-vous`        | 🔒 Le salon (sans limite)      |
| État de la configuration | `GET`    | `/salon/etat`               | 🔒 Le salon (clé admin)        |
| Voir les rendez-vous     | `GET`    | `/rendez-vous?jour=` ou `?depuis=` | 🔒 Le salon (clé admin) |
| Voir un rendez-vous      | `GET`    | `/rendez-vous/{id}`         | 🔑 Le client (jeton) ou le salon |
| Déplacer                 | `PATCH`  | `/rendez-vous/{id}`         | 🔑 Le client (jeton) ou le salon |
| Annuler                  | `DELETE` | `/rendez-vous/{id}`         | 🔑 Le client (jeton) ou le salon (avec motif) |

## ⚠️ Les erreurs gérées

| Code    | Signification                                      |
|---------|----------------------------------------------------|
| **400** | Rendez-vous passé, ou modification moins de 24 h avant |
| **401** | Clé admin manquante ou invalide                    |
| **404** | Rendez-vous ou prestation introuvable (ou mauvais jeton) |
| **409** | Créneau déjà réservé, ou prestation déjà existante |
| **422** | Données invalides (email, téléphone, horaire, motif…) |
| **429** | Trop de demandes depuis la même connexion          |

---

## 🔐 Sécurité, en résumé

- **Aucun secret dans le dépôt ni dans le site** : clé admin, adresse de la base et secret du relais sont dans les variables d'environnement de Render.
- **Clé admin** dans l'en-tête `X-API-Key`. Sans clé configurée, les routes du salon sont fermées à tout le monde.
- **Jeton par rendez-vous** dans l'en-tête `X-Jeton`. Un mauvais jeton renvoie 404, comme un rendez-vous inexistant.
- **Comparaisons à temps constant** (`secrets.compare_digest`) pour les clés et les jetons.
- **Limite de requêtes**, **champ piège**, **CORS** limité, **en-têtes de sécurité**.
- **Validation Pydantic** et requêtes SQLModel paramétrées (pas d'injection SQL).
- Deux réservations au même créneau à la même seconde : la contrainte d'unicité de la base garde la première (409).

---

## 📁 Organisation des fichiers

```
rdv-api/
├── app/
│   ├── creneaux.py   → calcul des créneaux
│   ├── database.py   → connexion à la base (SQLite ou PostgreSQL)
│   ├── models.py     → données et règles de validation
│   ├── securite.py   → jetons, limite de requêtes, CORS
│   ├── cles.py       → vérification de la clé admin
│   ├── emails.py     → emails de confirmation, déplacement, annulation
│   └── main.py       → routes de l'API et gestion des erreurs
├── tests/
│   └── test_api.py   → 50 tests automatiques
├── webflow/
│   ├── page-reserver.html      → module intégré à la page Réserver
│   └── page-espace-salon.html  → module intégré à l'espace salon
├── docs/
│   └── relais-email.gs → relais Gmail (Google Apps Script)
├── .env.example      → modèle des variables d'environnement
├── render.yaml       → configuration du déploiement Render
└── requirements.txt  → bibliothèques à installer
```

---

👩‍💻 Projet réalisé par **Nassima**, étudiante en Bachelor développement web à HETIC.
