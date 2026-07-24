/**
 * Gabarits HTML des emails transactionnels ChurnGuard (bienvenue, code de
 * vérification). CSS inline uniquement : les clients email n'appliquent pas
 * les feuilles de style externes/`<style>` de façon fiable.
 */

const COULEUR_PRIMAIRE = '#4F46E5'
const COULEUR_TEXTE = '#1f2937'
const COULEUR_TEXTE_ATTENUE = '#6b7280'
const COULEUR_FOND = '#f3f4f6'
const COULEUR_CARTE = '#ffffff'
const COULEUR_BORDURE = '#e5e7eb'

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? 'http://127.0.0.1:3000'

function enveloppe(titre: string, contenu: string): string {
  return `<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${titre}</title>
  </head>
  <body style="margin:0;padding:0;background-color:${COULEUR_FOND};font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:${COULEUR_FOND};padding:32px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;background-color:${COULEUR_CARTE};border-radius:12px;overflow:hidden;border:1px solid ${COULEUR_BORDURE};">
            <tr>
              <td style="background-color:${COULEUR_PRIMAIRE};padding:24px 32px;">
                <span style="color:#ffffff;font-size:20px;font-weight:700;letter-spacing:-0.02em;">ChurnGuard</span>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">
                ${contenu}
              </td>
            </tr>
            <tr>
              <td style="padding:20px 32px;border-top:1px solid ${COULEUR_BORDURE};">
                <p style="margin:0;font-size:12px;color:${COULEUR_TEXTE_ATTENUE};">
                  Cet email vous a été envoyé automatiquement par ChurnGuard. Si vous n'êtes pas à l'origine de cette action, contactez votre administrateur.
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>`
}

export function gabaritBienvenue(params: {
  nomComplet: string
  motDePasse: string
  email: string
}): { sujet: string; html: string; texte: string } {
  const { nomComplet, motDePasse, email } = params
  const sujet = 'Bienvenue sur ChurnGuard — votre compte a été créé'
  const html = enveloppe(
    sujet,
    `
    <h1 style="margin:0 0 8px;font-size:20px;color:${COULEUR_TEXTE};">Bienvenue, ${nomComplet}</h1>
    <p style="margin:0 0 24px;font-size:14px;line-height:1.6;color:${COULEUR_TEXTE_ATTENUE};">
      Un compte ChurnGuard vient d'être créé pour vous par votre administrateur. Connectez-vous avec votre adresse email :
    </p>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:${COULEUR_FOND};border-radius:8px;margin-bottom:24px;">
      <tr>
        <td style="padding:16px 20px;">
          <p style="margin:0 0 10px;font-size:13px;color:${COULEUR_TEXTE_ATTENUE};">Email</p>
          <p style="margin:0 0 16px;font-size:15px;font-weight:600;color:${COULEUR_TEXTE};font-family:monospace;">${email}</p>
          <p style="margin:0 0 10px;font-size:13px;color:${COULEUR_TEXTE_ATTENUE};">Mot de passe temporaire</p>
          <p style="margin:0;font-size:15px;font-weight:600;color:${COULEUR_TEXTE};font-family:monospace;">${motDePasse}</p>
        </td>
      </tr>
    </table>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#fffbeb;border:1px solid #fde68a;border-radius:8px;margin-bottom:24px;">
      <tr>
        <td style="padding:14px 18px;">
          <p style="margin:0;font-size:13px;line-height:1.5;color:#92400e;">
            Ce mot de passe est <strong>temporaire</strong> : dès votre première connexion, vous serez automatiquement invité à en choisir un nouveau.
          </p>
        </td>
      </tr>
    </table>
    <table role="presentation" cellpadding="0" cellspacing="0">
      <tr>
        <td style="border-radius:8px;background-color:${COULEUR_PRIMAIRE};">
          <a href="${APP_URL}/login" style="display:inline-block;padding:12px 24px;font-size:14px;font-weight:600;color:#ffffff;text-decoration:none;">
            Se connecter et choisir mon mot de passe
          </a>
        </td>
      </tr>
    </table>
    `,
  )
  const texte = `Bienvenue ${nomComplet},\n\nVotre compte ChurnGuard a été créé.\nEmail : ${email}\nMot de passe temporaire : ${motDePasse}\n\nCe mot de passe est temporaire : dès votre première connexion, vous serez automatiquement invité à en choisir un nouveau.\nConnexion : ${APP_URL}/login`
  return { sujet, html, texte }
}

export function gabaritReinitialisation(params: {
  nomComplet: string
  motDePasse: string
  email: string
}): { sujet: string; html: string; texte: string } {
  const { nomComplet, motDePasse, email } = params
  const sujet = 'Votre mot de passe ChurnGuard a été réinitialisé'
  const html = enveloppe(
    sujet,
    `
    <h1 style="margin:0 0 8px;font-size:20px;color:${COULEUR_TEXTE};">Bonjour ${nomComplet}</h1>
    <p style="margin:0 0 24px;font-size:14px;line-height:1.6;color:${COULEUR_TEXTE_ATTENUE};">
      Votre administrateur a réinitialisé le mot de passe de votre compte ChurnGuard. Voici votre nouveau mot de passe :
    </p>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:${COULEUR_FOND};border-radius:8px;margin-bottom:24px;">
      <tr>
        <td style="padding:16px 20px;">
          <p style="margin:0 0 10px;font-size:13px;color:${COULEUR_TEXTE_ATTENUE};">Email</p>
          <p style="margin:0 0 16px;font-size:15px;font-weight:600;color:${COULEUR_TEXTE};font-family:monospace;">${email}</p>
          <p style="margin:0 0 10px;font-size:13px;color:${COULEUR_TEXTE_ATTENUE};">Nouveau mot de passe</p>
          <p style="margin:0;font-size:15px;font-weight:600;color:${COULEUR_TEXTE};font-family:monospace;">${motDePasse}</p>
        </td>
      </tr>
    </table>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#fffbeb;border:1px solid #fde68a;border-radius:8px;margin-bottom:24px;">
      <tr>
        <td style="padding:14px 18px;">
          <p style="margin:0;font-size:13px;line-height:1.5;color:#92400e;">
            Pour votre sécurité, changez ce mot de passe dès votre prochaine connexion. Si vous n'êtes pas à l'origine de cette réinitialisation, contactez votre administrateur immédiatement.
          </p>
        </td>
      </tr>
    </table>
    <table role="presentation" cellpadding="0" cellspacing="0">
      <tr>
        <td style="border-radius:8px;background-color:${COULEUR_PRIMAIRE};">
          <a href="${APP_URL}/login" style="display:inline-block;padding:12px 24px;font-size:14px;font-weight:600;color:#ffffff;text-decoration:none;">
            Se connecter
          </a>
        </td>
      </tr>
    </table>
    `,
  )
  const texte = `Bonjour ${nomComplet},\n\nVotre mot de passe ChurnGuard a été réinitialisé par votre administrateur.\nEmail : ${email}\nNouveau mot de passe : ${motDePasse}\n\nChangez ce mot de passe dès votre prochaine connexion. Si vous n'êtes pas à l'origine de cette action, contactez votre administrateur.\nConnexion : ${APP_URL}/login`
  return { sujet, html, texte }
}

export function gabaritConfirmationCreation(params: {
  nomAdmin: string
  nomNouvelUtilisateur: string
  emailNouvelUtilisateur: string
  role: string
  dateCreation: string
}): { sujet: string; html: string; texte: string } {
  const { nomAdmin, nomNouvelUtilisateur, emailNouvelUtilisateur, role, dateCreation } = params
  const roleLabel = role === 'admin' ? 'Administrateur' : 'Opérateur'
  const sujet = `Compte créé : ${nomNouvelUtilisateur} a rejoint votre organisation`
  const html = enveloppe(
    sujet,
    `
    <h1 style="margin:0 0 8px;font-size:20px;color:${COULEUR_TEXTE};">Bonjour ${nomAdmin}</h1>
    <p style="margin:0 0 24px;font-size:14px;line-height:1.6;color:${COULEUR_TEXTE_ATTENUE};">
      Confirmation : vous venez de créer un nouveau compte sur ChurnGuard. Un email de bienvenue avec les identifiants a été envoyé à la personne concernée.
    </p>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:${COULEUR_FOND};border-radius:8px;margin-bottom:24px;">
      <tr>
        <td style="padding:16px 20px;">
          <p style="margin:0 0 10px;font-size:13px;color:${COULEUR_TEXTE_ATTENUE};">Nom</p>
          <p style="margin:0 0 16px;font-size:15px;font-weight:600;color:${COULEUR_TEXTE};">${nomNouvelUtilisateur}</p>
          <p style="margin:0 0 10px;font-size:13px;color:${COULEUR_TEXTE_ATTENUE};">Email</p>
          <p style="margin:0 0 16px;font-size:15px;font-weight:600;color:${COULEUR_TEXTE};font-family:monospace;">${emailNouvelUtilisateur}</p>
          <p style="margin:0 0 10px;font-size:13px;color:${COULEUR_TEXTE_ATTENUE};">Rôle</p>
          <p style="margin:0 0 16px;font-size:15px;font-weight:600;color:${COULEUR_TEXTE};">${roleLabel}</p>
          <p style="margin:0 0 10px;font-size:13px;color:${COULEUR_TEXTE_ATTENUE};">Créé le</p>
          <p style="margin:0;font-size:15px;font-weight:600;color:${COULEUR_TEXTE};">${dateCreation}</p>
        </td>
      </tr>
    </table>
    <p style="margin:0 0 24px;font-size:13px;line-height:1.5;color:${COULEUR_TEXTE_ATTENUE};">
      Si vous n'êtes pas à l'origine de cette création, vérifiez immédiatement les accès de votre organisation.
    </p>
    <table role="presentation" cellpadding="0" cellspacing="0">
      <tr>
        <td style="border-radius:8px;background-color:${COULEUR_PRIMAIRE};">
          <a href="${APP_URL}/team" style="display:inline-block;padding:12px 24px;font-size:14px;font-weight:600;color:#ffffff;text-decoration:none;">
            Voir l'équipe
          </a>
        </td>
      </tr>
    </table>
    `,
  )
  const texte = `Bonjour ${nomAdmin},\n\nVous venez de créer un nouveau compte sur ChurnGuard.\nNom : ${nomNouvelUtilisateur}\nEmail : ${emailNouvelUtilisateur}\nRôle : ${roleLabel}\nCréé le : ${dateCreation}\n\nSi vous n'êtes pas à l'origine de cette création, vérifiez immédiatement les accès de votre organisation.\nÉquipe : ${APP_URL}/team`
  return { sujet, html, texte }
}

export function gabaritOtp(params: {
  nomComplet: string
  code: string
  expireMinutes: number
}): { sujet: string; html: string; texte: string } {
  const { nomComplet, code, expireMinutes } = params
  const sujet = `${code} — votre code de vérification ChurnGuard`
  const html = enveloppe(
    sujet,
    `
    <h1 style="margin:0 0 8px;font-size:20px;color:${COULEUR_TEXTE};">Code de vérification</h1>
    <p style="margin:0 0 24px;font-size:14px;line-height:1.6;color:${COULEUR_TEXTE_ATTENUE};">
      Bonjour ${nomComplet}, voici le code à saisir pour terminer votre connexion à ChurnGuard :
    </p>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:${COULEUR_FOND};border-radius:8px;margin-bottom:24px;">
      <tr>
        <td align="center" style="padding:24px;">
          <span style="font-size:32px;font-weight:700;letter-spacing:0.3em;color:${COULEUR_PRIMAIRE};font-family:monospace;">${code}</span>
        </td>
      </tr>
    </table>
    <p style="margin:0;font-size:13px;line-height:1.5;color:${COULEUR_TEXTE_ATTENUE};">
      Ce code expire dans ${expireMinutes} minutes et ne peut être utilisé qu'une seule fois. Si vous n'êtes pas à l'origine de cette connexion, ignorez cet email.
    </p>
    `,
  )
  const texte = `Bonjour ${nomComplet},\n\nVotre code de vérification ChurnGuard : ${code}\nIl expire dans ${expireMinutes} minutes et ne peut être utilisé qu'une seule fois.\n\nSi vous n'êtes pas à l'origine de cette connexion, ignorez cet email.`
  return { sujet, html, texte }
}
