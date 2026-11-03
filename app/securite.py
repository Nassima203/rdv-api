"""
Tout ce qui protège l'API une fois en ligne.

- Les routes ADMIN demandent une clé secrète APTX_sk_ dans l'en-tête X-API-Key (voir app/cles.py).
- Les routes du site demandent la clé publique APTX_pk_ dans l'en-tête X-Cle-Site.
- Chaque rendez-vous reçoit un JETON aléatoire à sa création. Sans ce jeton (ou la clé
  admin), impossible de voir, déplacer ou annuler le rendez-vous de quelqu'un d'autre.
- Une LIMITE DE REQUÊTES par adresse IP empêche un robot de réserver tout le planning.
- Le CORS n'autorise que le site du salon à appeler l'API depuis un navigateur.
"""
import os
import secrets

from dotenv import load_dotenv
from fastapi import Header
from fastapi.security import APIKeyHeader
from slowapi import Limiter
from slowapi.util import get_remote_address


# ---------- Configuration (variables d'environnement) ----------

load_dotenv()  # en local : lit le fichier .env s'il existe (en production, Render fournit les variables)

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


# ---------- En-tête de la clé secrète du salon ----------
# (la vérification elle-même est dans app/cles.py, car elle a besoin de la base)

entete_cle_api = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="Clé secrète du salon (APTX_sk_...), ou la clé de secours ADMIN_API_KEY.",
)


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
