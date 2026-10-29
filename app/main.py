"""
L'API FastAPI de prise de rendez-vous.
Lancer le serveur :  uvicorn app.main:app --reload
Documentation      :  http://127.0.0.1:8000/docs

Qui peut faire quoi ?
- Tout le monde : voir les prestations, voir les créneaux libres, réserver.
- Le client (avec le jeton reçu à la réservation) : voir, déplacer, annuler SON rendez-vous.
- Le salon (avec la clé admin X-API-Key) : tout, y compris la liste des rendez-vous.
"""
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlmodel import Session, select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.creneaux import creneaux_libres, est_jour_ouvre
from app.database import creer_tables, get_session
from app.models import (
    Prestation,
    PrestationCreate,
    PrestationModification,
    PrestationPublic,
    RendezVous,
    RendezVousConfirmation,
    RendezVousCreate,
    RendezVousDeplacement,
    RendezVousPublic,
)
from app.securite import (
    ENTETES_SECURITE,
    LIMITE_RESERVATION,
    ORIGINES_AUTORISEES,
    entete_cle_api,
    est_admin,
    jeton_valide,
    limiter,
    lire_jeton,
    verifier_admin,
)

DELAI_MODIFICATION = timedelta(hours=24)


@asynccontextmanager
async def lifespan(app: FastAPI):
    creer_tables()  # au démarrage du serveur
    yield


app = FastAPI(
    title="API de prise de rendez-vous",
    description=(
        "Réservez, déplacez ou annulez un rendez-vous chez un professionnel.\n\n"
        "Les routes marquées d'un cadenas demandent la clé admin (bouton **Authorize**)."
    ),
    version="1.2.0",
    lifespan=lifespan,
)


# ======================= Protections globales =======================

# Limite de requêtes par adresse IP
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Seul le site du salon peut appeler l'API depuis un navigateur
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINES_AUTORISEES,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Jeton", "X-API-Key"],
)


@app.middleware("http")
async def ajouter_entetes_securite(request: Request, call_next):
    reponse = await call_next(request)
    for nom, valeur in ENTETES_SECURITE.items():
        reponse.headers.setdefault(nom, valeur)
    return reponse


# ======================= Gestion des erreurs =======================

@app.exception_handler(StarletteHTTPException)
async def gerer_erreur_http(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"erreur": exc.detail, "code": exc.status_code},
    )


@app.exception_handler(RateLimitExceeded)
async def gerer_trop_de_requetes(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"erreur": "Trop de demandes depuis votre connexion. Réessayez un peu plus tard.", "code": 429},
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

def rendez_vous_autorise(
    rdv_id: int,
    session: Session = Depends(get_session),
    jeton: str | None = Depends(lire_jeton),
    cle_api: str | None = Security(entete_cle_api),
) -> RendezVous:
    """
    Donne accès au rendez-vous seulement au client qui a le bon jeton, ou au salon.
    Même message d'erreur (404) qu'il existe ou non : on ne révèle pas quels numéros sont pris.
    """
    rdv = session.get(RendezVous, rdv_id)
    if rdv is None or not (est_admin(cle_api) or jeton_valide(rdv.jeton, jeton)):
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


def verifier_delai_24h(rdv: RendezVous, admin: bool = False):
    """La règle des 24 h protège le salon des annulations de dernière minute : elle ne s'applique pas au salon lui-même."""
    if admin:
        return
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

@app.post("/prestations", response_model=PrestationPublic, status_code=201, tags=["Prestations"],
          dependencies=[Depends(verifier_admin)])
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
    return session.exec(select(Prestation).order_by(Prestation.id)).all()


def trouver_prestation(prestation_id: int, session: Session) -> Prestation:
    prestation = session.get(Prestation, prestation_id)
    if prestation is None:
        raise HTTPException(status_code=404, detail=f"Prestation n°{prestation_id} introuvable.")
    return prestation


@app.patch("/prestations/{prestation_id}", response_model=PrestationPublic, tags=["Prestations"],
           dependencies=[Depends(verifier_admin)])
def modifier_prestation(prestation_id: int, donnees: PrestationModification,
                        session: Session = Depends(get_session)):
    prestation = trouver_prestation(prestation_id, session)
    changements = donnees.model_dump(exclude_unset=True)
    if "nom" in changements and changements["nom"] != prestation.nom:
        deja = session.exec(select(Prestation).where(Prestation.nom == changements["nom"])).first()
        if deja:
            raise HTTPException(status_code=409, detail=f"La prestation « {changements['nom']} » existe déjà.")
    for champ, valeur in changements.items():
        setattr(prestation, champ, valeur)
    session.add(prestation)
    session.commit()
    session.refresh(prestation)
    return prestation


@app.delete("/prestations/{prestation_id}", status_code=204, tags=["Prestations"],
            dependencies=[Depends(verifier_admin)])
def supprimer_prestation(prestation_id: int, session: Session = Depends(get_session)):
    prestation = trouver_prestation(prestation_id, session)
    a_venir = session.exec(
        select(RendezVous).where(RendezVous.prestation_id == prestation_id, RendezVous.debut >= datetime.now())
    ).first()
    if a_venir:
        raise HTTPException(
            status_code=409,
            detail="Des rendez-vous à venir utilisent cette prestation : annulez-les ou attendez qu'ils soient passés.",
        )
    session.delete(prestation)
    session.commit()


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

def enregistrer_rendez_vous(donnees: RendezVousCreate, session: Session) -> RendezVous:
    trouver_prestation(donnees.prestation_id, session)
    verifier_creneau_disponible(donnees.debut, session)
    rdv = RendezVous.model_validate(donnees.model_dump(exclude={"site_web"}))
    session.add(rdv)
    session.commit()
    session.refresh(rdv)
    return rdv


@app.post("/rendez-vous", response_model=RendezVousConfirmation, status_code=201, tags=["Rendez-vous"])
@limiter.limit(LIMITE_RESERVATION)
def reserver(request: Request, donnees: RendezVousCreate, session: Session = Depends(get_session)):
    if donnees.site_web:  # champ piège rempli : c'est un robot
        raise HTTPException(status_code=400, detail="Demande refusée.")
    return enregistrer_rendez_vous(donnees, session)


@app.post("/salon/rendez-vous", response_model=RendezVousConfirmation, status_code=201,
          tags=["Rendez-vous (salon)"], dependencies=[Depends(verifier_admin)])
def reserver_pour_un_client(donnees: RendezVousCreate, session: Session = Depends(get_session)):
    """Rendez-vous pris par le salon (au téléphone, au comptoir) : pas de limite de requêtes."""
    return enregistrer_rendez_vous(donnees, session)


@app.get("/rendez-vous", response_model=list[RendezVousPublic], tags=["Rendez-vous (salon)"],
         dependencies=[Depends(verifier_admin)])
def lister_rendez_vous(jour: date | None = None, depuis: date | None = None,
                       session: Session = Depends(get_session)):
    """`jour` : les rendez-vous d'une journée. `depuis` : tous les rendez-vous à partir d'une date."""
    requete = select(RendezVous).order_by(RendezVous.debut)
    if jour:
        debut_jour = datetime.combine(jour, datetime.min.time())
        requete = requete.where(RendezVous.debut >= debut_jour,
                                RendezVous.debut < debut_jour + timedelta(days=1))
    elif depuis:
        requete = requete.where(RendezVous.debut >= datetime.combine(depuis, datetime.min.time()))
    return session.exec(requete).all()


@app.get("/rendez-vous/{rdv_id}", response_model=RendezVousPublic, tags=["Rendez-vous"])
def voir_rendez_vous(rdv: RendezVous = Depends(rendez_vous_autorise)):
    return rdv


@app.patch("/rendez-vous/{rdv_id}", response_model=RendezVousPublic, tags=["Rendez-vous"])
def deplacer_rendez_vous(donnees: RendezVousDeplacement,
                         rdv: RendezVous = Depends(rendez_vous_autorise),
                         session: Session = Depends(get_session),
                         cle_api: str | None = Security(entete_cle_api)):
    verifier_delai_24h(rdv, admin=est_admin(cle_api))
    verifier_creneau_disponible(donnees.debut, session, ignorer_id=rdv.id)
    rdv.debut = donnees.debut
    session.add(rdv)
    session.commit()
    session.refresh(rdv)
    return rdv


@app.delete("/rendez-vous/{rdv_id}", status_code=204, tags=["Rendez-vous"])
def annuler_rendez_vous(rdv: RendezVous = Depends(rendez_vous_autorise),
                        session: Session = Depends(get_session),
                        cle_api: str | None = Security(entete_cle_api)):
    verifier_delai_24h(rdv, admin=est_admin(cle_api))
    session.delete(rdv)
    session.commit()
