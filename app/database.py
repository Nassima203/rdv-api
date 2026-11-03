"""
Connexion à la base de données.
C'est ici que se joue la PERSISTANCE : les données survivent à l'arrêt du serveur.

- En local : un fichier SQLite (rdv.db), rien à installer.
- En ligne : une base PostgreSQL, dont l'adresse arrive par la variable DATABASE_URL.
  (Sur l'offre gratuite de Render, le disque du serveur est effacé à chaque mise en veille :
  un fichier SQLite y perdrait toutes les réservations.)
"""
import os

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine

load_dotenv()


def adresse_base() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return "sqlite:///rdv.db"
    # Render et Heroku donnent "postgres://..." : SQLAlchemy veut le nom du pilote psycopg
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = adresse_base()

if DATABASE_URL.startswith("sqlite"):
    # check_same_thread=False : nécessaire avec SQLite quand FastAPI traite plusieurs requêtes
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # pool_pre_ping : vérifie la connexion avant de s'en servir (utile après une mise en veille)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def creer_tables() -> None:
    """Crée les tables si elles n'existent pas encore."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Ouvre une session (une "conversation" avec la base) le temps d'une requête."""
    with Session(engine) as session:
        yield session
