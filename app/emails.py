"""
Emails envoyés au client : confirmation, déplacement, annulation.

Pourquoi un "relais" ? L'offre gratuite de Render bloque l'envoi d'emails en SMTP.
On passe donc par un petit script Google Apps Script (voir docs/relais-email.gs) :
l'API lui envoie le message en HTTPS, et le script l'envoie depuis la boîte Gmail du salon.
Avantage : les emails partent d'une vraie adresse Gmail et arrivent en boîte de réception.

Variables d'environnement :
- MAIL_RELAY_URL    : l'adresse du script déployé (https://script.google.com/macros/s/.../exec)
- MAIL_RELAY_SECRET : le mot de passe partagé entre l'API et le script
- SITE_URL          : l'adresse du site, pour le lien "gérer mon rendez-vous"

Si le relais n'est pas configuré, la réservation fonctionne quand même : l'email est simplement ignoré.
Un email qui échoue ne fait jamais échouer une réservation.
"""
import html
import logging
import os
from datetime import datetime

import httpx

log = logging.getLogger("rdv.emails")

NOM_SALON = "Maison Lumen"
ADRESSE_SALON = "12 rue des Lumières, 75011 Paris"

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
        "août", "septembre", "octobre", "novembre", "décembre"]


def relais_configure() -> bool:
    return bool(os.environ.get("MAIL_RELAY_URL") and os.environ.get("MAIL_RELAY_SECRET"))


def date_lisible(moment: datetime) -> str:
    return f"{JOURS[moment.weekday()]} {moment.day} {MOIS[moment.month - 1]} à {moment:%H} h {moment:%M}"


def lien_gestion(rdv_id: int, jeton: str) -> str:
    site = os.environ.get("SITE_URL", "https://maison-lumen-c4b75a.webflow.io").rstrip("/")
    # Le code est dans la partie "#" de l'adresse : le navigateur ne l'envoie jamais à un serveur
    return f"{site}/reserver#gerer={rdv_id}-{jeton}"


def gabarit(titre: str, paragraphes: list[str], bouton: tuple[str, str] | None = None) -> str:
    """Email HTML simple, aux couleurs du site. Tout ce qui vient du client est échappé avant."""
    corps = "".join(f'<p style="margin:0 0 14px;font-size:15px;line-height:1.6;color:#3d3630">{p}</p>' for p in paragraphes)
    lien = ""
    if bouton:
        texte, url = bouton
        lien = (f'<p style="margin:24px 0"><a href="{html.escape(url)}" style="display:inline-block;background:#2a1d14;'
                f'color:#ffffff;text-decoration:none;padding:13px 28px;border-radius:999px;font-size:14px">{texte}</a></p>')
    return f"""<div style="background:#f5f1ec;padding:32px 16px;font-family:Arial,sans-serif">
  <div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:18px;padding:32px">
    <p style="margin:0 0 24px;font-family:Georgia,serif;letter-spacing:5px;font-size:15px;color:#2a1d14">MAISON LUMEN</p>
    <h1 style="margin:0 0 18px;font-family:Georgia,serif;font-weight:400;font-size:26px;color:#2a1d14">{titre}</h1>
    {corps}{lien}
    <p style="margin:24px 0 0;font-size:12px;color:#8a8178">{NOM_SALON}, {ADRESSE_SALON}. Cet email vous est envoyé suite à votre réservation en ligne.</p>
  </div>
</div>"""


def message_confirmation(rdv, prestation) -> dict:
    prenom = html.escape(rdv.client_nom.split(" ")[0])
    quand = date_lisible(rdv.debut)
    return {
        "to": rdv.client_email,
        "subject": f"Votre rendez-vous du {quand} est confirmé",
        "html": gabarit(
            f"C'est confirmé, {prenom}",
            [
                (f"Nous vous attendons le <strong>{quand}</strong> pour : "
                 f"<strong>{html.escape(prestation.nom)}</strong> ({format_prix(prestation.prix)}).")
                if prestation else f"Nous vous attendons le <strong>{quand}</strong>.",
                f"Rendez-vous n°{rdv.id}. Votre code de gestion : "
                f'<span style="font-family:Courier New,monospace;background:#f5f1ec;padding:3px 6px;border-radius:6px">{html.escape(rdv.jeton)}</span>',
                "Vous pouvez déplacer ou annuler votre rendez-vous en ligne jusqu'à 24 h avant. "
                "Passé ce délai, contactez directement le salon.",
            ],
            ("Gérer mon rendez-vous", lien_gestion(rdv.id, rdv.jeton)),
        ),
    }


def message_deplacement(rdv, prestation) -> dict:
    quand = date_lisible(rdv.debut)
    return {
        "to": rdv.client_email,
        "subject": f"Votre rendez-vous est déplacé au {quand}",
        "html": gabarit(
            "Votre rendez-vous est déplacé",
            [
                f"Nouvel horaire : <strong>{quand}</strong>" + (f", pour {html.escape(prestation.nom)}" if prestation else "") + ".",
                f"Rendez-vous n°{rdv.id}. Votre code de gestion reste le même.",
            ],
            ("Gérer mon rendez-vous", lien_gestion(rdv.id, rdv.jeton)),
        ),
    }


def message_annulation(rdv, prestation, par_le_salon: bool, motif: str | None = None) -> dict:
    quand = date_lisible(rdv.debut)
    qui = "Le salon a annulé" if par_le_salon else "Vous avez annulé"
    raison = [f"Motif : {html.escape(motif)}."] if motif else []
    site = os.environ.get("SITE_URL", "https://maison-lumen-c4b75a.webflow.io").rstrip("/")
    return {
        "to": rdv.client_email,
        "subject": f"Rendez-vous du {quand} annulé",
        "html": gabarit(
            "Votre rendez-vous est annulé",
            [
                f"{qui} votre rendez-vous du <strong>{quand}</strong>"
                f"{' (' + html.escape(prestation.nom) + ')' if prestation else ''}.",
                *raison,
                "Vous pouvez reprendre un rendez-vous en ligne quand vous le souhaitez.",
            ],
            ("Reprendre rendez-vous", f"{site}/reserver"),
        ),
    }


def format_prix(prix: float) -> str:
    texte = f"{prix:.2f}".replace(".", ",")
    return texte.removesuffix(",00") + " €"


def envoyer(message: dict) -> bool:
    """Appelée en tâche de fond, après la réponse au client : ne lève jamais d'exception."""
    if not relais_configure():
        log.info("Relais email non configuré : email « %s » non envoyé.", message.get("subject"))
        return False
    try:
        reponse = httpx.post(
            os.environ["MAIL_RELAY_URL"],
            json={"secret": os.environ["MAIL_RELAY_SECRET"], **message},
            follow_redirects=True,  # Apps Script répond par une redirection
            timeout=20,
        )
        ok = reponse.status_code == 200 and '"ok":true' in reponse.text.replace(" ", "")
        if not ok:
            log.warning("Le relais email a refusé le message (%s) : %s", reponse.status_code, reponse.text[:200])
        return ok
    except httpx.HTTPError as erreur:
        log.warning("Relais email injoignable : %s", erreur)
        return False
