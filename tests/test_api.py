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
from app.models import RendezVous
from app.securite import limiter

CLE_ADMIN = "cle-de-test-tres-secrete"
ADMIN = {"X-API-Key": CLE_ADMIN}


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", CLE_ADMIN)
    limiter.enabled = False  # la limite de requêtes a son propre test
    limiter.reset()

    def get_session_test():
        yield session

    app.dependency_overrides[get_session] = get_session_test
    yield TestClient(app)
    app.dependency_overrides.clear()
    limiter.enabled = True


def prochain_jour_ouvre(dans_jours: int = 3) -> date:
    jour = date.today() + timedelta(days=dans_jours)
    while jour.weekday() == 6:  # on saute le dimanche
        jour += timedelta(days=1)
    return jour


def creneau(heure: int, minute: int = 0, dans_jours: int = 3) -> str:
    return datetime.combine(prochain_jour_ouvre(dans_jours),
                            datetime.min.time()).replace(hour=heure, minute=minute).isoformat()


def creer_prestation(client) -> int:
    rep = client.post("/prestations", json={"nom": "Coupe femme", "prix": 35}, headers=ADMIN)
    return rep.json()["id"]


def donnees_rdv(prestation_id: int, debut: str) -> dict:
    return {
        "prestation_id": prestation_id,
        "client_nom": "Sarah Martin",
        "client_email": "sarah@example.com",
        "client_telephone": "06 12 34 56 78",
        "debut": debut,
    }


def reserver(client, debut: str | None = None) -> dict:
    pid = creer_prestation(client)
    return client.post("/rendez-vous", json=donnees_rdv(pid, debut or creneau(10))).json()


# ---------- Cas qui fonctionnent ----------

def test_reserver_un_rendez_vous(client):
    pid = creer_prestation(client)
    rep = client.post("/rendez-vous", json=donnees_rdv(pid, creneau(10)))
    assert rep.status_code == 201
    assert rep.json()["client_nom"] == "Sarah Martin"
    assert len(rep.json()["jeton"]) >= 20  # le client reçoit son code secret


def test_creneau_reserve_disparait_des_creneaux_libres(client):
    reserver(client)
    rep = client.get("/creneaux", params={"jour": prochain_jour_ouvre().isoformat()})
    assert "10:00" not in rep.json()["creneaux"]
    assert "10:30" in rep.json()["creneaux"]


def test_deplacer_un_rendez_vous_avec_son_jeton(client):
    rdv = reserver(client)
    rep = client.patch(f"/rendez-vous/{rdv['id']}", json={"debut": creneau(15)},
                       headers={"X-Jeton": rdv["jeton"]})
    assert rep.status_code == 200
    assert rep.json()["debut"].startswith(creneau(15)[:16])
    assert "jeton" not in rep.json()  # le jeton n'est renvoyé qu'à la réservation


def test_annuler_un_rendez_vous_avec_son_jeton(client):
    rdv = reserver(client)
    jeton = {"X-Jeton": rdv["jeton"]}
    assert client.delete(f"/rendez-vous/{rdv['id']}", headers=jeton).status_code == 204
    assert client.get(f"/rendez-vous/{rdv['id']}", headers=jeton).status_code == 404


def test_voir_son_rendez_vous_avec_son_jeton(client):
    rdv = reserver(client)
    rep = client.get(f"/rendez-vous/{rdv['id']}", headers={"X-Jeton": rdv["jeton"]})
    assert rep.status_code == 200
    assert rep.json()["client_email"] == "sarah@example.com"


# ---------- Sécurité ----------

def test_401_lister_les_rendez_vous_sans_cle(client):
    reserver(client)
    rep = client.get("/rendez-vous")
    assert rep.status_code == 401
    assert "Accès réservé" in rep.json()["erreur"]


def test_401_mauvaise_cle_admin(client):
    rep = client.get("/rendez-vous", headers={"X-API-Key": "pas-la-bonne"})
    assert rep.status_code == 401


def test_admin_peut_lister_sans_voir_les_jetons(client):
    reserver(client)
    rep = client.get("/rendez-vous", headers=ADMIN)
    assert rep.status_code == 200
    assert len(rep.json()) == 1
    assert "jeton" not in rep.json()[0]


def test_401_creer_une_prestation_sans_cle(client):
    rep = client.post("/prestations", json={"nom": "Coupe homme", "prix": 25})
    assert rep.status_code == 401


def test_aucune_cle_configuree_ferme_l_admin(client, monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY")
    assert client.get("/rendez-vous", headers={"X-API-Key": ""}).status_code == 401
    assert client.get("/rendez-vous", headers=ADMIN).status_code == 401


def test_impossible_d_annuler_le_rendez_vous_d_un_autre(client):
    rdv = reserver(client)
    sans_jeton = client.delete(f"/rendez-vous/{rdv['id']}")
    mauvais_jeton = client.delete(f"/rendez-vous/{rdv['id']}", headers={"X-Jeton": "devine"})
    assert sans_jeton.status_code == 404
    assert mauvais_jeton.status_code == 404
    # le rendez-vous est toujours là
    assert client.get(f"/rendez-vous/{rdv['id']}", headers=ADMIN).status_code == 200


def test_impossible_de_lire_le_rendez_vous_d_un_autre(client):
    rdv = reserver(client)
    rep = client.get(f"/rendez-vous/{rdv['id']}")
    assert rep.status_code == 404
    assert "sarah" not in rep.text


def test_admin_peut_annuler_sans_jeton(client):
    rdv = reserver(client)
    assert client.delete(f"/rendez-vous/{rdv['id']}", headers=ADMIN).status_code == 204


def test_champ_piege_bloque_les_robots(client):
    pid = creer_prestation(client)
    donnees = donnees_rdv(pid, creneau(10))
    donnees["site_web"] = "http://spam.example"
    rep = client.post("/rendez-vous", json=donnees)
    assert rep.status_code == 400
    assert client.get("/rendez-vous", headers=ADMIN).json() == []


def test_429_trop_de_reservations(client):
    limiter.enabled = True
    limiter.reset()
    pid = creer_prestation(client)
    codes = [
        client.post("/rendez-vous", json=donnees_rdv(pid, creneau(heure))).status_code
        for heure in (9, 10, 11, 13, 14, 15)
    ]
    assert codes[:5] == [201] * 5
    assert codes[5] == 429


def test_cors_autorise_seulement_le_site_du_salon(client):
    bon = client.options("/prestations", headers={
        "Origin": "https://maison-lumen-c4b75a.webflow.io",
        "Access-Control-Request-Method": "GET",
    })
    mauvais = client.options("/prestations", headers={
        "Origin": "https://site-pirate.example",
        "Access-Control-Request-Method": "GET",
    })
    assert bon.headers.get("access-control-allow-origin") == "https://maison-lumen-c4b75a.webflow.io"
    assert "access-control-allow-origin" not in mauvais.headers


def test_entetes_de_securite_presents(client):
    rep = client.get("/prestations")
    assert rep.headers["X-Content-Type-Options"] == "nosniff"
    assert rep.headers["X-Frame-Options"] == "DENY"


# ---------- Gestion des erreurs ----------

def test_409_creneau_deja_pris(client):
    pid = creer_prestation(client)
    client.post("/rendez-vous", json=donnees_rdv(pid, creneau(10)))
    rep = client.post("/rendez-vous", json=donnees_rdv(pid, creneau(10)))
    assert rep.status_code == 409
    assert "déjà réservé" in rep.json()["erreur"]


def test_409_prestation_en_double(client):
    creer_prestation(client)
    rep = client.post("/prestations", json={"nom": "Coupe femme", "prix": 35}, headers=ADMIN)
    assert rep.status_code == 409


def test_404_rendez_vous_inexistant(client):
    rep = client.get("/rendez-vous/999", headers=ADMIN)
    assert rep.status_code == 404
    assert rep.json()["erreur"] == "Rendez-vous n°999 introuvable."


def test_404_prestation_inexistante(client):
    rep = client.post("/rendez-vous", json=donnees_rdv(999, creneau(10)))
    assert rep.status_code == 404


def test_400_annulation_moins_de_24h(client, session):
    pid = creer_prestation(client)
    # on insère directement un rendez-vous dans moins de 24 h
    rdv = RendezVous(prestation_id=pid, client_nom="Test", client_email="t@example.com",
                     client_telephone="0612345678",
                     debut=datetime.now().replace(second=0, microsecond=0) + timedelta(hours=2))
    session.add(rdv)
    session.commit()
    session.refresh(rdv)
    rep = client.delete(f"/rendez-vous/{rdv.id}", headers={"X-Jeton": rdv.jeton})
    assert rep.status_code == 400
    assert "24 h" in rep.json()["erreur"]


# ---------- Validation ----------

def test_422_rendez_vous_dans_le_passe(client):
    pid = creer_prestation(client)
    hier = (datetime.now() - timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    rep = client.post("/rendez-vous", json=donnees_rdv(pid, hier.isoformat()))
    assert rep.status_code == 422


def test_422_rendez_vous_trop_lointain(client):
    pid = creer_prestation(client)
    rep = client.post("/rendez-vous", json=donnees_rdv(pid, creneau(10, dans_jours=400)))
    assert rep.status_code == 422
    assert "jours maximum" in rep.json()["details"][0]["message"]


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


# ---------- Espace salon ----------

def test_salon_annule_moins_de_24h_avant(client, session):
    pid = creer_prestation(client)
    rdv = RendezVous(prestation_id=pid, client_nom="Test", client_email="t@example.com",
                     client_telephone="0612345678",
                     debut=datetime.now().replace(second=0, microsecond=0) + timedelta(hours=2))
    session.add(rdv)
    session.commit()
    session.refresh(rdv)
    assert client.delete(f"/rendez-vous/{rdv.id}", headers=ADMIN).status_code == 204


def test_salon_deplace_un_rendez_vous(client):
    rdv = reserver(client)
    rep = client.patch(f"/rendez-vous/{rdv['id']}", json={"debut": creneau(16)}, headers=ADMIN)
    assert rep.status_code == 200


def test_salon_reserve_pour_un_client(client):
    pid = creer_prestation(client)
    rep = client.post("/salon/rendez-vous", json=donnees_rdv(pid, creneau(11)), headers=ADMIN)
    assert rep.status_code == 201
    assert client.post("/salon/rendez-vous", json=donnees_rdv(pid, creneau(13))).status_code == 401


def test_lister_les_rendez_vous_a_venir(client):
    reserver(client, creneau(10, dans_jours=3))
    rep = client.get("/rendez-vous", params={"depuis": date.today().isoformat()}, headers=ADMIN)
    assert len(rep.json()) == 1
    loin = (date.today() + timedelta(days=30)).isoformat()
    assert client.get("/rendez-vous", params={"depuis": loin}, headers=ADMIN).json() == []


def test_modifier_une_prestation(client):
    pid = creer_prestation(client)
    rep = client.patch(f"/prestations/{pid}", json={"prix": 40}, headers=ADMIN)
    assert rep.status_code == 200
    assert rep.json()["prix"] == 40 and rep.json()["nom"] == "Coupe femme"
    assert client.patch(f"/prestations/{pid}", json={"prix": 50}).status_code == 401


def test_supprimer_une_prestation(client):
    pid = creer_prestation(client)
    assert client.delete(f"/prestations/{pid}").status_code == 401
    assert client.delete(f"/prestations/{pid}", headers=ADMIN).status_code == 204
    assert client.get("/prestations").json() == []


def test_impossible_de_supprimer_une_prestation_reservee(client):
    rdv = reserver(client)
    rep = client.delete(f"/prestations/{rdv['prestation_id']}", headers=ADMIN)
    assert rep.status_code == 409
