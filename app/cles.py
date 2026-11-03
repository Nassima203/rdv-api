"""
Vérification des clés d'accès APTX.

- Clé SECRÈTE (APTX_sk_...) : donne accès à tout (espace salon). Elle peut venir de la base
  (créée depuis l'espace salon) ou de la variable ADMIN_API_KEY, la clé de secours de Render.
- Clé PUBLIQUE (APTX_pk_...) : obligatoire pour les routes du site (prestations, créneaux,
  réservation, gestion par le client). Elle est visible dans le code du site : elle identifie
  le site mais ne donne aucun droit d'administration. Les vraies protections du client restent
  le jeton de son rendez-vous, la limite de requêtes et le CORS.
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, Header, HTTPException, Security
from sqlmodel import Session, select

from app.database import get_session
from app.models import CleApi
from app.securite import entete_cle_api

PREFIXES = {"publique": "APTX_pk_", "secrete": "APTX_sk_"}


def empreinte(cle: str) -> str:
    return hashlib.sha256(cle.encode()).hexdigest()


def generer_cle(type_cle: str) -> str:
    longueur = 24 if type_cle == "publique" else 32
    return PREFIXES[type_cle] + secrets.token_urlsafe(longueur)


def trouver_cle(cle: str | None, session: Session, type_cle: str) -> CleApi | None:
    if not cle or not cle.startswith(PREFIXES[type_cle]):
        return None
    trouvee = session.exec(select(CleApi).where(CleApi.empreinte == empreinte(cle))).first()
    if trouvee is None or trouvee.revoquee_le is not None or trouvee.type != type_cle:
        return None
    # On note la dernière utilisation (au plus une écriture toutes les 5 minutes)
    if trouvee.derniere_utilisation is None or datetime.now() - trouvee.derniere_utilisation > timedelta(minutes=5):
        trouvee.derniere_utilisation = datetime.now()
        session.add(trouvee)
        session.commit()
    return trouvee


def cle_de_secours_valide(cle: str | None) -> bool:
    secours = os.environ.get("ADMIN_API_KEY", "")
    # Sans clé configurée, la clé de secours n'existe pas : on ferme par défaut
    return bool(secours and cle and secrets.compare_digest(cle, secours))


def est_admin(cle: str | None, session: Session) -> bool:
    return cle_de_secours_valide(cle) or trouver_cle(cle, session, "secrete") is not None


def verifier_admin(cle: str | None = Security(entete_cle_api), session: Session = Depends(get_session)) -> None:
    """Dépendance FastAPI à ajouter sur les routes réservées au salon."""
    if not est_admin(cle, session):
        raise HTTPException(status_code=401, detail="Accès réservé au salon : clé API manquante ou invalide.")


def verifier_cle_site(
    x_cle_site: str | None = Header(default=None, description="Clé publique du site (APTX_pk_...)."),
    cle_admin: str | None = Security(entete_cle_api),
    session: Session = Depends(get_session),
) -> None:
    """Routes du site : il faut la clé publique du site, ou une clé admin (pour l'espace salon)."""
    if trouver_cle(x_cle_site, session, "publique") is not None or est_admin(cle_admin, session):
        return
    raise HTTPException(
        status_code=401,
        detail="Clé du site manquante ou invalide : la réservation en ligne est momentanément indisponible.",
    )
