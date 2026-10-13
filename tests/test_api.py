"""
Tests automatiques de l'API.
Lancer :  pytest -v
Chaque test utilise une base de données en mémoire, vide et jetable.
"""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.database import get_session
from app.main import app


@pytest.fixture(name="client")
def client_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def get_session_test():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_test
    yield TestClient(app)
    app.dependency_overrides.clear()


def prochain_jour_ouvre(dans_jours: int = 3) -> date:
    jour = date.today() + timedelta(days=dans_jours)
    while jour.weekday() == 6:  # on saute le dimanche
        jour += timedelta(days=1)
    return jour


def creneau(heure: int, minute: int = 0, dans_jours: int = 3) -> str:
    return datetime.combine(prochain_jour_ouvre(dans_jours),
                            datetime.min.time()).replace(hour=heure, minute=minute).isoformat()


def creer_prestation(client) -> int:
    rep = client.post("/prestations", json={"nom": "Coupe femme", "prix": 35})
    return rep.json()["id"]


def donnees_rdv(prestation_id: int, debut: str) -> dict:
    return {
        "prestation_id": prestation_id,
        "client_nom": "Sarah Martin",
        "client_email": "sarah@example.com",
        "client_telephone": "06 12 34 56 78",
        "debut": debut,
    }


# ---------- Cas qui fonctionnent ----------

def test_reserver_un_rendez_vous(client):
    pid = creer_prestation(client)
    rep = client.post("/rendez-vous", json=donnees_rdv(pid, creneau(10)))
    assert rep.status_code == 201
    assert rep.json()["client_nom"] == "Sarah Martin"


def test_creneau_reserve_disparait_des_creneaux_libres(client):
    pid = creer_prestation(client)
    client.post("/rendez-vous", json=donnees_rdv(pid, creneau(10)))
    rep = client.get("/creneaux", params={"jour": prochain_jour_ouvre().isoformat()})
    assert "10:00" not in rep.json()["creneaux"]
    assert "10:30" in rep.json()["creneaux"]


def test_deplacer_un_rendez_vous(client):
    pid = creer_prestation(client)
    rdv_id = client.post("/rendez-vous", json=donnees_rdv(pid, creneau(10))).json()["id"]
    rep = client.patch(f"/rendez-vous/{rdv_id}", json={"debut": creneau(15)})
    assert rep.status_code == 200
    assert rep.json()["debut"].startswith(creneau(15)[:16])


def test_annuler_un_rendez_vous(client):
    pid = creer_prestation(client)
    rdv_id = client.post("/rendez-vous", json=donnees_rdv(pid, creneau(10))).json()["id"]
    assert client.delete(f"/rendez-vous/{rdv_id}").status_code == 204
    assert client.get(f"/rendez-vous/{rdv_id}").status_code == 404


# ---------- Gestion des erreurs ----------

def test_409_creneau_deja_pris(client):
    pid = creer_prestation(client)
    client.post("/rendez-vous", json=donnees_rdv(pid, creneau(10)))
    rep = client.post("/rendez-vous", json=donnees_rdv(pid, creneau(10)))
    assert rep.status_code == 409
    assert "déjà réservé" in rep.json()["erreur"]


def test_409_prestation_en_double(client):
    creer_prestation(client)
    rep = client.post("/prestations", json={"nom": "Coupe femme", "prix": 35})
    assert rep.status_code == 409


def test_404_rendez_vous_inexistant(client):
    rep = client.get("/rendez-vous/999")
    assert rep.status_code == 404
    assert rep.json()["erreur"] == "Rendez-vous n°999 introuvable."


def test_404_prestation_inexistante(client):
    rep = client.post("/rendez-vous", json=donnees_rdv(999, creneau(10)))
    assert rep.status_code == 404


def test_400_annulation_moins_de_24h(client):
    pid = creer_prestation(client)
    # on insère directement un rendez-vous dans moins de 24 h
    from app.models import RendezVous
    session = next(app.dependency_overrides[get_session]())
    rdv = RendezVous(prestation_id=pid, client_nom="Test", client_email="t@example.com",
                     client_telephone="0612345678",
                     debut=datetime.now().replace(second=0, microsecond=0) + timedelta(hours=2))
    session.add(rdv)
    session.commit()
    session.refresh(rdv)
    rep = client.delete(f"/rendez-vous/{rdv.id}")
    assert rep.status_code == 400
    assert "24 h" in rep.json()["erreur"]


# ---------- Validation ----------

def test_422_rendez_vous_dans_le_passe(client):
    pid = creer_prestation(client)
    hier = (datetime.now() - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    rep = client.post("/rendez-vous", json=donnees_rdv(pid, hier.isoformat()))
    assert rep.status_code == 422


def test_422_horaire_hors_creneau(client):
    pid = creer_prestation(client)
    rep = client.post("/rendez-vous", json=donnees_rdv(pid, creneau(10, 15)))
    assert rep.status_code == 422
    assert "Horaire invalide" in rep.json()["details"][0]["message"]


def test_422_pendant_la_pause(client):
    pid = creer_prestation(client)
    rep = client.post("/rendez-vous", json=donnees_rdv(pid, creneau(12, 30)))
    assert rep.status_code == 422


def test_422_email_et_telephone_invalides(client):
    pid = creer_prestation(client)
    donnees = donnees_rdv(pid, creneau(10))
    donnees["client_email"] = "pas-un-email"
    donnees["client_telephone"] = "123"
    rep = client.post("/rendez-vous", json=donnees)
    assert rep.status_code == 422
    champs = [d["champ"] for d in rep.json()["details"]]
    assert "client_email" in champs and "client_telephone" in champs