/**
 * Route interne appelée uniquement par le backend FastAPI (jamais depuis le
 * navigateur) : le backend est en Python, nodemailer ne peut donc pas y
 * tourner directement, cette route lui sert de "service d'envoi d'email".
 * Protégée par un secret partagé (X-Internal-Secret), voir
 * CHURNGUARD_EMAIL_SERVICE_SECRET côté backend / INTERNAL_EMAIL_SECRET ici.
 */

import nodemailer from 'nodemailer'
import { NextRequest, NextResponse } from 'next/server'
import {
  gabaritBienvenue,
  gabaritConfirmationCreation,
  gabaritOtp,
  gabaritReinitialisation,
} from '@/lib/email-templates'

function creerTransporteur() {
  return nodemailer.createTransport({
    host: process.env.SMTP_HOST,
    port: Number(process.env.SMTP_PORT ?? 587),
    secure: process.env.SMTP_SECURE === 'true',
    auth: process.env.SMTP_USER
      ? { user: process.env.SMTP_USER, pass: process.env.SMTP_PASSWORD }
      : undefined,
  })
}

export async function POST(request: NextRequest) {
  const secret = request.headers.get('x-internal-secret')
  if (!secret || secret !== process.env.INTERNAL_EMAIL_SECRET) {
    return NextResponse.json({ detail: 'Accès refusé.' }, { status: 403 })
  }

  const body = await request.json().catch(() => null)
  if (!body || typeof body.to !== 'string' || !body.to) {
    return NextResponse.json({ detail: 'Payload invalide.' }, { status: 400 })
  }

  let gabarit: { sujet: string; html: string; texte: string }
  if (body.type === 'bienvenue') {
    gabarit = gabaritBienvenue({
      nomComplet: String(body.nom_complet ?? ''),
      motDePasse: String(body.mot_de_passe ?? ''),
      email: String(body.to),
    })
  } else if (body.type === 'reinitialisation') {
    gabarit = gabaritReinitialisation({
      nomComplet: String(body.nom_complet ?? ''),
      motDePasse: String(body.mot_de_passe ?? ''),
      email: String(body.to),
    })
  } else if (body.type === 'confirmation_creation') {
    gabarit = gabaritConfirmationCreation({
      nomAdmin: String(body.nom_admin ?? ''),
      nomNouvelUtilisateur: String(body.nom_nouvel_utilisateur ?? ''),
      emailNouvelUtilisateur: String(body.email_nouvel_utilisateur ?? ''),
      role: String(body.role ?? 'operateur'),
      dateCreation: new Date().toLocaleString('fr-FR', {
        dateStyle: 'long',
        timeStyle: 'short',
        timeZone: 'Europe/Paris',
      }),
    })
  } else if (body.type === 'otp') {
    gabarit = gabaritOtp({
      nomComplet: String(body.nom_complet ?? ''),
      code: String(body.code ?? ''),
      expireMinutes: Number(body.expire_minutes ?? 10),
    })
  } else {
    return NextResponse.json({ detail: "Type d'email inconnu." }, { status: 400 })
  }

  if (!process.env.SMTP_HOST) {
    // Dev local sans SMTP : journalise le contenu au lieu d'envoyer, pour
    // pouvoir tester le parcours (bienvenue/OTP) sans compte SMTP réel.
    console.log(
      `[send-email] SMTP non configuré — email "${body.type}" pour ${body.to} (non envoyé réellement) :\n${gabarit.texte}`,
    )
    return NextResponse.json({ ok: true })
  }

  const transporteur = creerTransporteur()
  try {
    await transporteur.sendMail({
      from: process.env.SMTP_FROM ?? 'ChurnGuard <no-reply@churnguard.app>',
      to: body.to,
      subject: gabarit.sujet,
      html: gabarit.html,
      text: gabarit.texte,
    })
    return NextResponse.json({ ok: true })
  } catch (erreur) {
    console.error('[send-email] Échec envoi:', erreur)
    return NextResponse.json({ detail: "Échec de l'envoi." }, { status: 500 })
  }
}
