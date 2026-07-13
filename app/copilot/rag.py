"""RAG (Retrieval-Augmented Generation) pour l'Assistant ChurnGuard.

Indexe les playbooks de retention du dossier ``knowledge/`` et retrouve, pour une
question donnee, les extraits les plus pertinents. Ces extraits sont injectes
dans le prompt de l'Assistant : ses reponses s'appuient alors sur des bonnes
pratiques ecrites, pas seulement sur les facteurs bruts du modele.

Choix technique : recuperation par TF-IDF (scikit-learn, deja installe). Aucun
telechargement de modele lourd. L'index est reconstruit automatiquement quand les
fichiers de ``knowledge/`` changent. La conception est generique : deposer un
nouveau document (n'importe quel secteur / dataset) suffit, sans toucher au code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import settings

# Extensions de documents pris en charge.
_EXT_TEXTE = {".md", ".txt", ".markdown"}
_EXT_PDF = {".pdf"}

# Cache module : (signature_fichiers, chunks, vectorizer, matrice).
_CACHE: dict[str, Any] = {"signature": None, "chunks": [], "vectorizer": None, "matrice": None}


def _lire_pdf(chemin: Path) -> str:
    """Extrait le texte d'un PDF si une bibliotheque est disponible, sinon ''."""
    try:
        from pypdf import PdfReader

        lecteur = PdfReader(str(chemin))
        return "\n".join((page.extract_text() or "") for page in lecteur.pages)
    except Exception:  # noqa: BLE001 — pas de lib PDF ou PDF illisible : on ignore
        return ""


def _charger_documents() -> list[tuple[str, str]]:
    """Charge (source_relative, texte) pour tous les documents de knowledge/."""
    racine = settings.knowledge_dir
    if not racine.exists():
        return []
    docs: list[tuple[str, str]] = []
    for chemin in sorted(racine.rglob("*")):
        if not chemin.is_file():
            continue
        suffixe = chemin.suffix.lower()
        try:
            if suffixe in _EXT_TEXTE:
                texte = chemin.read_text(encoding="utf-8", errors="ignore")
            elif suffixe in _EXT_PDF:
                texte = _lire_pdf(chemin)
            else:
                continue
        except Exception:  # noqa: BLE001
            continue
        if texte.strip():
            docs.append((str(chemin.relative_to(racine)), texte))
    return docs


# Taille max d'un chunk (caracteres) avant decoupage supplementaire.
_TAILLE_MAX = 1600


def _sous_decouper(source: str, titre: str, contenu: str) -> list[dict[str, str]]:
    """Redecoupe un contenu trop long en morceaux <= _TAILLE_MAX (par paragraphes)."""
    if len(contenu) <= _TAILLE_MAX:
        return [{"source": source, "titre": titre, "texte": contenu}]
    morceaux: list[dict[str, str]] = []
    buffer = ""
    for para in contenu.split("\n\n"):
        if buffer and len(buffer) + len(para) + 2 > _TAILLE_MAX:
            morceaux.append({"source": source, "titre": titre, "texte": buffer.strip()})
            buffer = para
        else:
            buffer = f"{buffer}\n\n{para}" if buffer else para
    if buffer.strip():
        morceaux.append({"source": source, "titre": titre, "texte": buffer.strip()})
    return morceaux


def _decouper(source: str, texte: str) -> list[dict[str, str]]:
    """Decoupe un document par section de premier niveau (titre ``# ``).

    Les playbooks courts restent d'un seul bloc (signaux + actions + message),
    ce qui donne un contexte complet a l'Assistant. Les sections trop longues
    (gros PDF) sont redecoupees par taille. Chaque chunk garde sa source et son
    titre pour permettre la citation.
    """
    lignes = texte.splitlines()
    chunks: list[dict[str, str]] = []
    titre = source
    buffer: list[str] = []

    def _vider() -> None:
        contenu = "\n".join(buffer).strip()
        if contenu:
            chunks.extend(_sous_decouper(source, titre, contenu))

    for ligne in lignes:
        nu = ligne.lstrip()
        # Coupe uniquement sur un titre de premier niveau ("# ", pas "## ").
        if nu.startswith("# ") and not nu.startswith("## "):
            _vider()
            buffer = [ligne]
            titre = nu.lstrip("# ").strip() or source
        else:
            buffer.append(ligne)
    _vider()
    return chunks


def _signature() -> tuple:
    """Signature des fichiers de knowledge/ (chemin, mtime, taille) pour le cache."""
    racine = settings.knowledge_dir
    if not racine.exists():
        return ()
    infos = []
    for chemin in sorted(racine.rglob("*")):
        if chemin.is_file() and chemin.suffix.lower() in (_EXT_TEXTE | _EXT_PDF):
            st = chemin.stat()
            infos.append((str(chemin), st.st_mtime_ns, st.st_size))
    return tuple(infos)


def _construire_index() -> None:
    """(Re)construit l'index TF-IDF si les fichiers ont change."""
    signature = _signature()
    if signature == _CACHE["signature"] and _CACHE["vectorizer"] is not None:
        return  # index a jour

    chunks: list[dict[str, str]] = []
    for source, texte in _charger_documents():
        chunks.extend(_decouper(source, texte))

    _CACHE["signature"] = signature
    _CACHE["chunks"] = chunks
    _CACHE["vectorizer"] = None
    _CACHE["matrice"] = None

    if not chunks:
        return

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer

        vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=1)
        matrice = vectorizer.fit_transform([c["texte"] for c in chunks])
        _CACHE["vectorizer"] = vectorizer
        _CACHE["matrice"] = matrice
    except Exception:  # noqa: BLE001 — sklearn indisponible : RAG inactif proprement
        _CACHE["vectorizer"] = None
        _CACHE["matrice"] = None


def rechercher(question: str, k: int = 4, score_min: float = 0.04) -> list[dict[str, Any]]:
    """Retourne les k extraits les plus pertinents pour une question.

    Args:
        question: Question ou contexte en langage naturel.
        k: Nombre maximum d'extraits a renvoyer.
        score_min: Similarite minimale (0-1) pour retenir un extrait.

    Returns:
        Liste de dicts ``{source, titre, texte, score}`` tries par pertinence.
        Liste vide si le corpus est absent ou aucun extrait pertinent.
    """
    if not question or not question.strip():
        return []
    _construire_index()
    vectorizer = _CACHE["vectorizer"]
    matrice = _CACHE["matrice"]
    chunks = _CACHE["chunks"]
    if vectorizer is None or matrice is None or not chunks:
        return []

    from sklearn.metrics.pairwise import cosine_similarity

    vecteur = vectorizer.transform([question])
    scores = cosine_similarity(vecteur, matrice)[0]
    ordre = scores.argsort()[::-1][:k]
    resultats: list[dict[str, Any]] = []
    for i in ordre:
        score = float(scores[i])
        if score < score_min:
            continue
        c = chunks[i]
        resultats.append({"source": c["source"], "titre": c["titre"], "texte": c["texte"], "score": round(score, 3)})
    return resultats


def contexte_pour_prompt(question: str, k: int = 4) -> str:
    """Formatte les extraits pertinents en un bloc texte injectable dans un prompt.

    Renvoie une chaine vide si aucun extrait pertinent (l'Assistant fonctionne
    alors normalement, sans connaissance additionnelle).
    """
    extraits = rechercher(question, k=k)
    if not extraits:
        return ""
    blocs = []
    for e in extraits:
        blocs.append(f"[Source : {e['source']} - {e['titre']}]\n{e['texte']}")
    return "\n\n".join(blocs)


def statut() -> dict[str, Any]:
    """Petit resume de l'etat du RAG (utile pour un endpoint de diagnostic)."""
    _construire_index()
    return {
        "dossier": str(settings.knowledge_dir),
        "existe": settings.knowledge_dir.exists(),
        "n_chunks": len(_CACHE["chunks"]),
        "actif": _CACHE["vectorizer"] is not None,
    }


def reindexer() -> dict[str, Any]:
    """Force la reconstruction de l'index (apres ajout de documents)."""
    _CACHE["signature"] = None
    return statut()
