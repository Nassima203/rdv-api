"""
Les modèles de données et leurs règles de VALIDATION.
- Les classes avec table=True deviennent des tables dans la base.
- Les autres décrivent ce que l'API accepte en entrée ou renvoie en sortie.
"""
import re
from datetime import datetime, timedelta
from typing import Literal, Optional

from pydantic import EmailStr, NaiveDatetime, field_validator
from sqlmodel import Field, SQLModel

from app.creneaux import est_creneau_valide, est_jour_ouvre
from app.securite import JOURS_RESERVABLES, generer_jeton


# ---------- Prestations (coupe, séance de kiné, cours...) ----------

class PrestationBase(SQLModel):
    nom: str = Field(min_length=2, max_length=100)
    prix: float = Field(gt=0, le=1000)
    description: Optional[str] = Field(default=None, max_length=300)


class Prestation(PrestationBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(min_length=2, max_length=100, unique=True)


class PrestationCreate(PrestationBase):
    pass


class PrestationPublic(PrestationBase):
    id: int


class PrestationModification(SQLModel):
    """Pour l'espace salon : on ne change que les champs envoyés."""
    nom: Optional[str] = Field(default=None, min_length=2, max_length=100)
    prix: Optional[float] = Field(default=None, gt=0, le=1000)
    description: Optional[str] = Field(default=None, max_length=300)


# ---------- Règle commune : un horaire de rendez-vous valide ----------

TELEPHONE_FR = re.compile(r"^(?:\+33|0)[1-9](?:[ .-]?\d{2}){4}$")


def valider_horaire(debut: datetime) -> datetime:
    if debut <= datetime.now():
        raise ValueError("Impossible de prendre un rendez-vous dans le passé.")
    if debut > datetime.now() + timedelta(days=JOURS_RESERVABLES):
        raise ValueError(f"Les réservations sont ouvertes sur {JOURS_RESERVABLES} jours maximum.")
    if not est_jour_ouvre(debut.date()):
        raise ValueError("Le cabinet est fermé ce jour-là (dimanche).")
    if not est_creneau_valide(debut):
        raise ValueError(
            "Horaire invalide : choisissez un créneau de 30 min entre 9h et 18h "
            "(hors pause 12h-13h), par exemple 10:00 ou 14:30."
        )
    return debut


# ---------- Rendez-vous ----------

class RendezVousBase(SQLModel):
    prestation_id: int = Field(foreign_key="prestation.id")
    client_nom: str = Field(min_length=2, max_length=100)
    client_email: EmailStr
    client_telephone: str = Field(description="Numéro français, ex : 06 12 34 56 78")
    debut: NaiveDatetime


class RendezVous(RendezVousBase, table=True):
    __tablename__ = "rendez_vous"
    id: Optional[int] = Field(default=None, primary_key=True)
    debut: NaiveDatetime = Field(index=True, unique=True)
    cree_le: NaiveDatetime = Field(default_factory=datetime.now)
    # Code secret remis au client : sans lui, impossible de voir, déplacer ou annuler ce rendez-vous
    jeton: str = Field(default_factory=generer_jeton, index=True)


class RendezVousCreate(RendezVousBase):
    # Champ "piège" : invisible pour un humain sur le site, seuls les robots le remplissent
    site_web: Optional[str] = Field(default=None, max_length=200)

    @field_validator("client_telephone")
    @classmethod
    def verifier_telephone(cls, v: str) -> str:
        if not TELEPHONE_FR.match(v):
            raise ValueError("Numéro de téléphone invalide (ex : 06 12 34 56 78).")
        return v

    @field_validator("debut")
    @classmethod
    def verifier_debut(cls, v: datetime) -> datetime:
        return valider_horaire(v)


class RendezVousDeplacement(SQLModel):
    debut: NaiveDatetime

    @field_validator("debut")
    @classmethod
    def verifier_debut(cls, v: datetime) -> datetime:
        return valider_horaire(v)


class RendezVousPublic(RendezVousBase):
    id: int
    cree_le: NaiveDatetime


class RendezVousConfirmation(RendezVousPublic):
    """Renvoyé UNE seule fois, à la réservation : c'est la seule fois où le jeton est visible."""
    jeton: str

# ---------- Clés d'accès APTX ----------
# Deux sortes de clés, comme chez Stripe :
# - "publique" (APTX_pk_...) : mise dans le code du site, elle identifie le site. Elle n'ouvre
#   que ce qu'un client peut déjà faire (voir les créneaux, réserver).
# - "secrete"  (APTX_sk_...) : tapée par l'admin sur la page /admin, jamais dans le code du site.
# La clé complète n'est montrée qu'une fois, à sa création : la base n'en garde qu'une empreinte.

class CleApiCreate(SQLModel):
    nom: str = Field(min_length=2, max_length=60)
    type: Literal["publique", "secrete"]


class CleApi(SQLModel, table=True):
    __tablename__ = "cle_api"
    id: Optional[int] = Field(default=None, primary_key=True)
    nom: str = Field(max_length=60)
    type: str = Field(max_length=10)
    apercu: str = Field(max_length=20)              # ex. "APTX_pk_3fQ9…" pour la reconnaître
    empreinte: str = Field(max_length=64, unique=True, index=True)  # SHA-256 de la clé
    cree_le: NaiveDatetime = Field(default_factory=datetime.now)
    derniere_utilisation: Optional[NaiveDatetime] = None
    revoquee_le: Optional[NaiveDatetime] = None


class CleApiPublic(SQLModel):
    id: int
    nom: str
    type: str
    apercu: str
    cree_le: NaiveDatetime
    derniere_utilisation: Optional[NaiveDatetime]
    revoquee_le: Optional[NaiveDatetime]


class CleApiCreee(CleApiPublic):
    """Renvoyée UNE seule fois, à la création : c'est la seule fois où la clé complète est visible."""
    cle: str
