"""
Clé admin du salon.

La clé que l'admin tape sur l'écran de connexion de l'espace salon (/admin) est la valeur de la
variable d'environnement ADMIN_API_KEY, choisie par le salon sur Render. Elle n'est jamais dans le
code du site ni sur GitHub. Le site l'envoie dans l'en-tête X-API-Key.
"""
import os
import secrets

from fastapi import HTTPException, Security

from app.securite import entete_cle_api


def est_admin(cle: str | None) -> bool:
    attendue = os.environ.get("ADMIN_API_KEY", "")
    # Sans clé configurée, personne n'est admin : on ferme par défaut
    return bool(attendue and cle and secrets.compare_digest(cle, attendue))


def verifier_admin(cle: str | None = Security(entete_cle_api)) -> None:
    """Dépendance FastAPI à ajouter sur les routes réservées au salon."""
    if not est_admin(cle):
        raise HTTPException(status_code=401, detail="Accès réservé au salon : clé admin manquante ou invalide.")
