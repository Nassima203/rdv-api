/**
 * Relais email de Maison Lumen (Google Apps Script).
 *
 * Pourquoi ? L'offre gratuite de Render bloque l'envoi d'emails en SMTP.
 * L'API envoie donc chaque email ici, en HTTPS, et ce script l'envoie depuis votre Gmail.
 *
 * Installation (une seule fois) :
 * 1. Ouvrir https://script.google.com > Nouveau projet, coller ce fichier à la place du code.
 * 2. Paramètres du projet (roue dentée) > Propriétés du script > Ajouter :
 *      SECRET = une longue phrase secrète (la même que MAIL_RELAY_SECRET sur Render)
 * 3. Déployer > Nouveau déploiement > Type : Application Web
 *      Exécuter en tant que : Moi    |    Qui a accès : Tout le monde
 *    Autoriser l'accès à Gmail quand Google le demande.
 * 4. Copier l'URL qui finit par /exec : c'est MAIL_RELAY_URL sur Render.
 *
 * Limite Gmail gratuite : environ 100 destinataires par jour.
 */
function doPost(e) {
  var secret = PropertiesService.getScriptProperties().getProperty('SECRET');
  var donnees;
  try {
    donnees = JSON.parse(e.postData.contents);
  } catch (err) {
    return reponse({ ok: false, erreur: 'json' });
  }
  // Sans le bon secret, on n'envoie rien : personne d'autre ne peut se servir de ce relais
  if (!secret || donnees.secret !== secret) return reponse({ ok: false, erreur: 'secret' });
  if (!donnees.to || !donnees.subject || !donnees.html) return reponse({ ok: false, erreur: 'champs' });

  GmailApp.sendEmail(donnees.to, donnees.subject,
    'Votre messagerie n\'affiche pas ce message. Contactez le salon Maison Lumen.',
    { htmlBody: donnees.html, name: 'Maison Lumen' });
  return reponse({ ok: true });
}

function reponse(objet) {
  return ContentService.createTextOutput(JSON.stringify(objet)).setMimeType(ContentService.MimeType.JSON);
}
