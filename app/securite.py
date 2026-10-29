"""
Tout ce qui protège l'API une fois en ligne.

- Les routes ADMIN (lister les rendez-vous, créer une prestation...) demandent une clé
  secrète envoyée dans l'en-tête X-API-Key. La clé vit dans une variable d'environnement,
  jamais dans le code ni dans le site.
- Chaque rendez-vous reçoit un JETON aléatoire à sa création. Sans ce jeton (ou la clé
  admin), impossible de voir, déplacer ou annuler le rendez-vous de quelqu'un d'autre.
- Une LIMITE DE REQUÊTES par adresse IP empêche un robot de réserver tout le planning.
- Le CORS n'autorise que le site du salon à appeler l'API depuis un navigateur.
"""
import os
import secrets

from dotenv import load_dotenv
from fastapi import Header, HTTPException, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address


# ---------- Configuration (variables d'environnement) ----------

load_dotenv()  # en local : lit le fichier .env s'il existe (en production, Render fournit les variables)

def cle_admin() -> str:
    """Clé admin lue à chaque appel : pratique pour les tests et pour Render."""
    return os.environ.get("ADMIN_API_KEY", "")


ORIGINES_AUTORISEES = [
    origine.strip()
    for origine in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://maison-lumen-c4b75a.webflow.io,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origine.strip()
]

LIMITE_RESERVATION = os.environ.get("LIMITE_RESERVATION", "5/hour")
LIMITE_PAR_DEFAUT = os.environ.get("LIMITE_PAR_DEFAUT", "120/minute")

# Au-delà de cette date, on refuse les réservations (évite de "remplir" l'agenda sur des années)
JOURS_RESERVABLES = int(os.environ.get("JOURS_RESERVABLES", "60"))


# ---------- Limite de requêtes ----------

limiter = Limiter(key_func=get_remote_address, default_limits=[LIMITE_PAR_DEFAUT])


# ---------- Clé admin ----------

entete_cle_api = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Clé réservée au salon (variable d'environnement ADMIN_API_KEY).",
)


def est_admin(cle_recue: str | None) -> bool:
    cle = cle_admin()
    # Sans clé configurée, personne n'est admin : on ferme par défaut.
    if not cle or not cle_recue:
        return False
    return secrets.compare_digest(cle_recue, cle)


def verifier_admin(cle_recue: str | None = Security(entete_cle_api)) -> None:
    """Dépendance FastAPI à ajouter sur les routes réservées au salon."""
    if not est_admin(cle_recue):
        raise HTTPException(status_code=401, detail="Accès réservé au salon : clé API manquante ou invalide.")


# ---------- Jeton d'un rendez-vous ----------

def generer_jeton() -> str:
    """Jeton aléatoire impossible à deviner (environ 128 bits)."""
    return secrets.token_urlsafe(16)


def jeton_valide(jeton_attendu: str, jeton_recu: str | None) -> bool:
    if not jeton_recu:
        return False
    return secrets.compare_digest(jeton_attendu, jeton_recu)


def lire_jeton(x_jeton: str | None = Header(default=None, description="Code reçu lors de la réservation.")) -> str | None:
    return x_jeton


# ---------- En-têtes de sécurité ajoutés à chaque réponse ----------

ENTETES_SECURITE = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}
