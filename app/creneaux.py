"""
Module de calcul des créneaux d'un professionnel.
C'est le "projet Python existant" autour duquel on construira l'API.
Il ne dépend de rien d'autre que la bibliothèque standard de Python.
"""
from datetime import date, datetime, time, timedelta

# --- Configuration du planning ---
HEURE_OUVERTURE = time(9, 0)
HEURE_FERMETURE = time(18, 0)
PAUSE_DEBUT = time(12, 0)
PAUSE_FIN = time(13, 0)
DUREE_CRENEAU = timedelta(minutes=30)
JOURS_FERMES = {6}  # 0 = lundi ... 6 = dimanche


def est_jour_ouvre(jour: date) -> bool:
    """Renvoie True si le professionnel travaille ce jour-là."""
    return jour.weekday() not in JOURS_FERMES


def generer_creneaux(jour: date) -> list[datetime]:
    """Renvoie tous les créneaux d'une journée (pause déjeuner exclue)."""
    if not est_jour_ouvre(jour):
        return []

    debut = datetime.combine(jour, HEURE_OUVERTURE)
    fin = datetime.combine(jour, HEURE_FERMETURE)
    pause_debut = datetime.combine(jour, PAUSE_DEBUT)
    pause_fin = datetime.combine(jour, PAUSE_FIN)

    creneaux = []
    courant = debut
    while courant + DUREE_CRENEAU <= fin:
        if not (pause_debut <= courant < pause_fin):
            creneaux.append(courant)
        courant += DUREE_CRENEAU
    return creneaux


def est_creneau_valide(moment: datetime) -> bool:
    """Vérifie qu'une date/heure correspond exactement à un créneau du planning."""
    return moment in generer_creneaux(moment.date())


def creneaux_libres(jour: date, deja_reserves: list[datetime]) -> list[datetime]:
    """Renvoie les créneaux de la journée qui ne sont pas encore réservés."""
    return [c for c in generer_creneaux(jour) if c not in deja_reserves]


# --- Petite démo quand on lance le fichier directement ---
if __name__ == "__main__":
    jour_test = date(2026, 10, 14)  # un mercredi
    print(f"Créneaux du {jour_test} :")
    for c in generer_creneaux(jour_test):
        print("  -", c.strftime("%H:%M"))

    reserves = [datetime(2026, 10, 14, 9, 0), datetime(2026, 10, 14, 14, 30)]
    libres = creneaux_libres(jour_test, reserves)
    print(f"\n{len(libres)} créneaux libres après 2 réservations")

    print("\n10h00 valide ?", est_creneau_valide(datetime(2026, 10, 14, 10, 0)))
    print("10h15 valide ?", est_creneau_valide(datetime(2026, 10, 14, 10, 15)))
    print("12h30 valide ?", est_creneau_valide(datetime(2026, 10, 14, 12, 30)))
    print("Dimanche ouvré ?", est_jour_ouvre(date(2026, 10, 18)))