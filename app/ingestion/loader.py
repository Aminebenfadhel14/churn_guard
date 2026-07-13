"""Chargeur de datasets multi-format (Couche 1 — Ingestion).

Accepte les formats CSV, Excel (.xlsx/.xls) et Parquet, avec détection
automatique de l'encodage pour les fichiers CSV (via charset-normalizer).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Extensions reconnues, regroupées par famille de format.
EXTENSIONS_CSV: frozenset[str] = frozenset({".csv", ".txt"})
EXTENSIONS_EXCEL: frozenset[str] = frozenset({".xlsx", ".xls", ".xlsm"})
EXTENSIONS_PARQUET: frozenset[str] = frozenset({".parquet", ".pq"})


def detecter_encodage(chemin: Path, taille_echantillon: int = 100_000) -> str:
    """Détecte l'encodage d'un fichier texte.

    Lit un échantillon des premiers octets et s'appuie sur charset-normalizer.
    Retourne ``"utf-8"`` par défaut si la détection échoue.

    Args:
        chemin: Chemin du fichier à analyser.
        taille_echantillon: Nombre d'octets lus pour la détection.

    Returns:
        Le nom de l'encodage détecté (ex. ``"utf-8"``, ``"latin-1"``).
    """
    try:
        from charset_normalizer import from_bytes

        with open(chemin, "rb") as fichier:
            echantillon = fichier.read(taille_echantillon)
        meilleur = from_bytes(echantillon).best()
        if meilleur is not None and meilleur.encoding:
            return meilleur.encoding
    except Exception:
        # En cas d'échec de la détection, on retombe sur un défaut sûr.
        pass
    return "utf-8"


def _nettoyer_colonnes(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise les noms de colonnes : retire le BOM (﻿) et les espaces parasites.

    Certains fichiers (surtout des CSV exportés sous Windows/Excel) commencent par
    un BOM UTF-8 (``EF BB BF``) qui se colle au nom de la première colonne :
    ``Age`` devient ``﻿Age``. Ce caractère invisible casse toute correspondance de
    colonnes (schéma, prédiction, jointures). On le supprime ici, une fois pour
    toutes, quel que soit le format d'entrée.
    """
    df.columns = [str(c).replace("﻿", "").strip() for c in df.columns]
    return df


def charger_dataset(
    chemin: str | Path,
    *,
    encodage: str | None = None,
    separateur: str | None = None,
) -> pd.DataFrame:
    """Charge un dataset depuis un fichier CSV, Excel ou Parquet.

    Le format est déduit de l'extension du fichier. Pour un CSV, l'encodage
    est détecté automatiquement s'il n'est pas fourni.

    Args:
        chemin: Chemin du fichier à charger.
        encodage: Encodage forcé pour les CSV (sinon détection automatique).
        separateur: Séparateur de colonnes CSV (sinon détection auto de pandas).

    Returns:
        Le dataset chargé sous forme de ``pandas.DataFrame``.

    Raises:
        FileNotFoundError: Si le fichier n'existe pas.
        ValueError: Si l'extension du fichier n'est pas prise en charge.
    """
    chemin = Path(chemin)
    if not chemin.exists():
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")

    suffixe = chemin.suffix.lower()

    if suffixe in EXTENSIONS_CSV:
        enc = encodage or detecter_encodage(chemin)
        # sep=None + engine="python" laisse pandas deviner le séparateur.
        sep = separateur if separateur is not None else None
        moteur = "python" if sep is None else "c"
        df = pd.read_csv(chemin, encoding=enc, sep=sep, engine=moteur)
        return _nettoyer_colonnes(df)

    if suffixe in EXTENSIONS_EXCEL:
        return _nettoyer_colonnes(pd.read_excel(chemin))

    if suffixe in EXTENSIONS_PARQUET:
        return _nettoyer_colonnes(pd.read_parquet(chemin))

    formats = sorted(EXTENSIONS_CSV | EXTENSIONS_EXCEL | EXTENSIONS_PARQUET)
    raise ValueError(
        f"Extension non prise en charge : '{suffixe}'. "
        f"Formats acceptés : {', '.join(formats)}."
    )
