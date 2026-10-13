# 📅 API de prise de rendez-vous

Une API en Python qui permet de prendre des rendez-vous chez un professionnel (coiffeur, kiné, professeur particulier…).

Avec cette API, on peut :
- voir les créneaux libres d'une journée ;
- réserver un rendez-vous ;
- déplacer un rendez-vous ;
- annuler un rendez-vous.

L'API refuse un créneau déjà pris, et interdit de modifier un rendez-vous moins de 24 h avant.

---

## 🛠️ Technologies

- **Python** : le langage
- **FastAPI** : pour créer l'API
- **SQLite** : la base de données
- **SQLModel** : pour lire et écrire dans la base avec Python
- **Pydantic** : pour vérifier les données reçues
- **pytest** : pour tester l'API automatiquement

---

## 🚀 Lancer le projet

```bash
# 1. Créer et activer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# 2. Installer les bibliothèques
pip install -r requirements.txt

# 3. Lancer le serveur
uvicorn app.main:app --reload
```

Ensuite, ouvrir **http://127.0.0.1:8000/docs** dans le navigateur. Cette page permet de tester toutes les routes de l'API.

---

## 🧱 Comment j'ai construit le projet, étape par étape

### Étape 1 : Préparer l'environnement
J'ai installé Python avec Homebrew. J'ai créé un environnement virtuel (`venv`) : c'est un espace isolé pour les bibliothèques du projet. J'ai ensuite installé FastAPI, SQLModel et pytest avec `pip`.

J'ai aussi créé deux fichiers :
- `requirements.txt` : la liste des bibliothèques à installer ;
- `.gitignore` : la liste des fichiers à ne pas mettre sur GitHub.

### Étape 2 : Écrire le module des créneaux (`creneaux.py`)
C'est le point de départ du projet. Ce fichier calcule les créneaux d'une journée :
- de 9h à 18h ;
- par tranches de 30 minutes ;
- sans la pause de 12h à 13h ;
- fermé le dimanche.

Ce module ne dépend de rien. L'API a ensuite été construite autour de lui.

### Étape 3 : Créer la base de données (`database.py`)
J'ai connecté le projet à une base SQLite. Les données sont enregistrées dans un fichier, `rdv.db`. Elles restent sauvegardées même quand on arrête le serveur : c'est la **persistance**.

### Étape 4 : Définir les données et leurs règles (`models.py`)
J'ai décrit deux types de données :
- une **prestation** : un nom et un prix ;
- un **rendez-vous** : un client, un email, un téléphone et une date.

J'ai ajouté des règles pour vérifier les données : c'est la **validation**. Par exemple :
- l'email doit être valide ;
- le téléphone doit être un numéro français ;
- la date ne peut pas être dans le passé ;
- l'heure doit tomber pile sur un créneau.

Si une règle n'est pas respectée, l'API refuse la demande.

### Étape 5 : Créer l'API (`main.py`)
J'ai créé l'application FastAPI et les premières routes pour les prestations. Une route, c'est une adresse de l'API associée à une action :
- `GET` pour lire ;
- `POST` pour créer.

FastAPI génère tout seul une page de documentation : `/docs`.

### Étape 6 : Réserver un rendez-vous
J'ai ajouté une route pour voir les créneaux libres, et une route pour réserver. Avant d'enregistrer, l'API vérifie que le créneau est libre. S'il est déjà pris, elle renvoie une erreur **409**.

### Étape 7 : Déplacer et annuler
J'ai ajouté deux routes :
- `PATCH` pour déplacer un rendez-vous ;
- `DELETE` pour l'annuler.

Les deux sont refusées moins de 24 h avant le rendez-vous (erreur **400**).

### Étape 8 : Rendre les erreurs claires
Par défaut, les erreurs de FastAPI sont en anglais et difficiles à lire. J'ai ajouté une gestion des erreurs pour qu'elles soient toutes **en français** et au même format :

```json
{
  "erreur": "Données invalides",
  "code": 422,
  "details": [
    {"champ": "prix", "message": "Doit être supérieur à 0."}
  ]
}
```

### Étape 9 : Écrire les tests (`tests/test_api.py`)
J'ai écrit 13 tests automatiques avec pytest. Ils vérifient que l'API fonctionne et qu'elle refuse bien les mauvaises demandes. Les tests utilisent une base de données temporaire, pour ne pas toucher à la vraie.

```bash
python -m pytest -v
```

Résultat : **13 tests réussis**.

### Étape 10 : Mettre le projet sur GitHub
J'ai enregistré le projet avec Git, puis je l'ai publié sur GitHub.

---

## 📌 Les routes de l'API

| Action | Méthode | Route |
|---|---|---|
| Voir les prestations | `GET` | `/prestations` |
| Créer une prestation | `POST` | `/prestations` |
| Voir les créneaux libres | `GET` | `/creneaux?jour=2026-10-20` |
| Voir les rendez-vous | `GET` | `/rendez-vous` |
| Voir un rendez-vous | `GET` | `/rendez-vous/{id}` |
| Réserver | `POST` | `/rendez-vous` |
| Déplacer | `PATCH` | `/rendez-vous/{id}` |
| Annuler | `DELETE` | `/rendez-vous/{id}` |

---

## ⚠️ Les erreurs gérées

| Code | Signification |
|---|---|
| **400** | Modification impossible moins de 24 h avant |
| **404** | Rendez-vous ou prestation introuvable |
| **409** | Créneau déjà réservé, ou prestation déjà existante |
| **422** | Données invalides (email, téléphone, horaire…) |

---

## 📁 Organisation des fichiers

```
rdv_api/
├── app/
│   ├── creneaux.py   → calcul des créneaux
│   ├── database.py   → connexion à la base de données
│   ├── models.py     → données et règles de validation
│   └── main.py       → routes de l'API et gestion des erreurs
├── tests/
│   └── test_api.py   → tests automatiques
└── requirements.txt  → bibliothèques à installer
```

---

👩‍💻 Projet réalisé par **Nassima**, étudiante en Bachelor développement web à HETIC.