"""
L'API FastAPI de prise de rendez-vous.
Lancer le serveur :  uvicorn app.main:app --reload
Documentation      :  http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlmodel import Session, select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.creneaux import creneaux_libres, est_jour_ouvre
from app.database import creer_tables, get_session
from app.models import (
    Prestation,
    PrestationCreate,
    PrestationPublic,
    RendezVous,
    RendezVousCreate,
    RendezVousDeplacement,
    RendezVousPublic,
)

DELAI_MODIFICATION = timedelta(hours=24)


@asynccontextmanager
async def lifespan(app: FastAPI):
    creer_tables()  # au démarrage du serveur
    yield


app = FastAPI(
    title="API de prise de rendez-vous",
    description="Réservez, déplacez ou annulez un rendez-vous chez un professionnel.",
    version="1.0.0",
    lifespan=lifespan,
)


# ======================= Gestion des erreurs =======================

@app.exception_handler(StarletteHTTPException)
async def gerer_erreur_http(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"erreur": exc.detail, "code": exc.status_code},
    )


# Traduction en français des erreurs de validation les plus courantes
MESSAGES_FR = {
    "missing": "Champ obligatoire.",
    "string_too_short": "Trop court (minimum {min_length} caractères).",
    "string_too_long": "Trop long (maximum {max_length} caractères).",
    "greater_than": "Doit être supérieur à {gt:g}.",
    "less_than_equal": "Doit être inférieur ou égal à {le:g}.",
    "int_parsing": "Doit être un nombre entier.",
    "float_parsing": "Doit être un nombre.",
    "datetime_parsing": "Date invalide (format attendu : 2026-10-20T10:00:00).",
    "datetime_from_date_parsing": "Date invalide (format attendu : 2026-10-20T10:00:00).",
    "date_from_datetime_parsing": "Date invalide (format attendu : 2026-10-20).",
    "json_invalid": "Le corps de la requête n'est pas un JSON valide.",
}


def traduire_erreur(err: dict) -> str:
    if err["type"] in MESSAGES_FR:
        return MESSAGES_FR[err["type"]].format(**err.get("ctx", {}))
    message = err["msg"].removeprefix("Value error, ")
    if "valid email address" in message:
        return "Adresse email invalide (ex : prenom@exemple.com)."
    return message


@app.exception_handler(RequestValidationError)
async def gerer_erreur_validation(request: Request, exc: RequestValidationError):
    details = []
    for err in exc.errors():
        noms = [str(x) for x in err["loc"] if x not in ("body", "query", "path") and not isinstance(x, int)]
        champ = ".".join(noms) or "requête"
        details.append({"champ": champ, "message": traduire_erreur(err)})
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"erreur": "Données invalides", "code": 422, "details": details},
    )


# ======================= Fonctions utilitaires =======================

def trouver_rendez_vous(rdv_id: int, session: Session) -> RendezVous:
    rdv = session.get(RendezVous, rdv_id)
    if rdv is None:
        raise HTTPException(status_code=404, detail=f"Rendez-vous n°{rdv_id} introuvable.")
    return rdv


def verifier_creneau_disponible(debut: datetime, session: Session, ignorer_id: int | None = None):
    requete = select(RendezVous).where(RendezVous.debut == debut)
    existant = session.exec(requete).first()
    if existant and existant.id != ignorer_id:
        raise HTTPException(
            status_code=409,
            detail=f"Le créneau du {debut:%d/%m/%Y à %H:%M} est déjà réservé.",
        )


def verifier_delai_24h(rdv: RendezVous):
    if rdv.debut - datetime.now() < DELAI_MODIFICATION:
        raise HTTPException(
            status_code=400,
            detail="Modification impossible moins de 24 h avant le rendez-vous.",
        )


# ======================= Routes =======================

@app.get("/", tags=["Accueil"])
def accueil():
    return {"message": "Bienvenue sur l'API de prise de rendez-vous. Documentation : /docs"}


# ----- Prestations -----

@app.post("/prestations", response_model=PrestationPublic, status_code=201, tags=["Prestations"])
def creer_prestation(donnees: PrestationCreate, session: Session = Depends(get_session)):
    deja = session.exec(select(Prestation).where(Prestation.nom == donnees.nom)).first()
    if deja:
        raise HTTPException(status_code=409, detail=f"La prestation « {donnees.nom} » existe déjà.")
    prestation = Prestation.model_validate(donnees)
    session.add(prestation)
    session.commit()
    session.refresh(prestation)
    return prestation


@app.get("/prestations", response_model=list[PrestationPublic], tags=["Prestations"])
def lister_prestations(session: Session = Depends(get_session)):
    return session.exec(select(Prestation)).all()


# ----- Créneaux -----

@app.get("/creneaux", tags=["Créneaux"])
def voir_creneaux_libres(jour: date, session: Session = Depends(get_session)):
    if not est_jour_ouvre(jour):
        return {"jour": jour, "message": "Le cabinet est fermé ce jour-là.", "creneaux": []}
    debut_jour = datetime.combine(jour, datetime.min.time())
    fin_jour = debut_jour + timedelta(days=1)
    reserves = session.exec(
        select(RendezVous.debut).where(RendezVous.debut >= debut_jour, RendezVous.debut < fin_jour)
    ).all()
    maintenant = datetime.now()
    libres = [c for c in creneaux_libres(jour, list(reserves)) if c > maintenant]
    return {"jour": jour, "creneaux": [c.strftime("%H:%M") for c in libres]}


# ----- Rendez-vous -----

@app.post("/rendez-vous", response_model=RendezVousPublic, status_code=201, tags=["Rendez-vous"])
def reserver(donnees: RendezVousCreate, session: Session = Depends(get_session)):
    if session.get(Prestation, donnees.prestation_id) is None:
        raise HTTPException(status_code=404, detail=f"Prestation n°{donnees.prestation_id} introuvable.")
    verifier_creneau_disponible(donnees.debut, session)
    rdv = RendezVous.model_validate(donnees)
    session.add(rdv)
    session.commit()
    session.refresh(rdv)
    return rdv


@app.get("/rendez-vous", response_model=list[RendezVousPublic], tags=["Rendez-vous"])
def lister_rendez_vous(jour: date | None = None, session: Session = Depends(get_session)):
    requete = select(RendezVous).order_by(RendezVous.debut)
    if jour:
        debut_jour = datetime.combine(jour, datetime.min.time())
        requete = requete.where(RendezVous.debut >= debut_jour,
                                RendezVous.debut < debut_jour + timedelta(days=1))
    return session.exec(requete).all()


@app.get("/rendez-vous/{rdv_id}", response_model=RendezVousPublic, tags=["Rendez-vous"])
def voir_rendez_vous(rdv_id: int, session: Session = Depends(get_session)):
    return trouver_rendez_vous(rdv_id, session)


@app.patch("/rendez-vous/{rdv_id}", response_model=RendezVousPublic, tags=["Rendez-vous"])
def deplacer_rendez_vous(rdv_id: int, donnees: RendezVousDeplacement,
                         session: Session = Depends(get_session)):
    rdv = trouver_rendez_vous(rdv_id, session)
    verifier_delai_24h(rdv)
    verifier_creneau_disponible(donnees.debut, session, ignorer_id=rdv.id)
    rdv.debut = donnees.debut
    session.add(rdv)
    session.commit()
    session.refresh(rdv)
    return rdv


@app.delete("/rendez-vous/{rdv_id}", status_code=204, tags=["Rendez-vous"])
def annuler_rendez_vous(rdv_id: int, session: Session = Depends(get_session)):
    rdv = trouver_rendez_vous(rdv_id, session)
    verifier_delai_24h(rdv)
    session.delete(rdv)
    session.commit()