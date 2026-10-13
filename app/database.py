"""
Connexion à la base de données SQLite.
C'est ici que se joue la PERSISTANCE : les données sont écrites dans le fichier rdv.db
et survivent à l'arrêt du serveur.
"""
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///rdv.db"

# check_same_thread=False : nécessaire avec SQLite quand FastAPI traite plusieurs requêtes
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def creer_tables() -> None:
    """Crée les tables dans rdv.db si elles n'existent pas encore."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Ouvre une session (une "conversation" avec la base) le temps d'une requête."""
    with Session(engine) as session:
        yield session