"""
Tuteur IA en Résistance des Matériaux — Interface Streamlit
"""
import os

import streamlit as st
from dotenv import load_dotenv

from drive_connector import sync_drive_content
from gemini_client import ask, build_model, init_gemini, start_chat

load_dotenv()

# ── Configuration de la page ────────────────────────────────────────────────
st.set_page_config(
    page_title="Tuteur RDM — IA",
    page_icon="📐",
    layout="wide",
)

# ── Initialisation de l'état de session ─────────────────────────────────────
for key, default in {
    "messages": [],
    "documents_text": "",
    "synced_files": [],
    "gemini_model": None,
    "chat_session": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Barre latérale — Configuration ──────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Configuration")

    gemini_key = st.text_input(
        "Clé API Gemini",
        value=os.getenv("GEMINI_API_KEY", ""),
        type="password",
        help="Obtenez votre clé sur https://aistudio.google.com/app/apikey",
    )

    folder_id = st.text_input(
        "ID du dossier Google Drive",
        value=os.getenv("DRIVE_FOLDER_ID", ""),
        help="L'ID se trouve dans l'URL de votre dossier Drive (après /folders/)",
    )

    st.divider()

    if st.button("🔄 Synchroniser les fichiers du Drive", use_container_width=True):
        if not folder_id:
            st.error("Veuillez entrer l'ID du dossier Drive.")
        elif not gemini_key:
            st.error("Veuillez entrer votre clé API Gemini.")
        else:
            try:
                progress_bar = st.progress(0, text="Connexion à Google Drive…")
                status_text = st.empty()

                def update_progress(current, total, filename):
                    pct = int((current / total) * 100)
                    progress_bar.progress(pct, text=f"Téléchargement ({current}/{total})")
                    status_text.caption(f"📄 {filename}")

                docs_text, file_names = sync_drive_content(folder_id, update_progress)

                st.session_state.documents_text = docs_text
                st.session_state.synced_files = file_names

                # Réinitialiser le modèle avec le nouveau contexte
                init_gemini(gemini_key)
                st.session_state.gemini_model = build_model(docs_text)
                st.session_state.chat_session = start_chat(st.session_state.gemini_model)
                st.session_state.messages = []

                progress_bar.progress(100, text="Synchronisation terminée !")
                status_text.empty()
                st.success(f"✅ {len(file_names)} fichier(s) chargé(s) avec succès !")

            except FileNotFoundError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Erreur : {e}")

    if st.session_state.synced_files:
        st.divider()
        st.subheader(f"📚 {len(st.session_state.synced_files)} fichier(s) chargé(s)")
        for name in st.session_state.synced_files:
            st.caption(f"• {name}")

    st.divider()
    if st.button("🗑️ Effacer la conversation", use_container_width=True):
        st.session_state.messages = []
        if st.session_state.gemini_model:
            st.session_state.chat_session = start_chat(st.session_state.gemini_model)
        st.rerun()


# ── Zone principale — Chat ───────────────────────────────────────────────────
st.title("📐 Tuteur IA — Résistance des Matériaux")

if not st.session_state.synced_files:
    st.info(
        "👈 Pour commencer, entrez votre clé API Gemini et l'ID de votre dossier Drive, "
        "puis cliquez sur **Synchroniser les fichiers du Drive**."
    )
    with st.expander("ℹ️ Comment trouver l'ID de mon dossier Drive ?"):
        st.markdown(
            """
            1. Ouvrez votre dossier Google Drive dans le navigateur.
            2. Regardez l'URL : `https://drive.google.com/drive/folders/**1AbCdEfGhIjKlMnOpQrStUvWxYz**`
            3. La partie en gras après `/folders/` est votre ID de dossier.
            """
        )
    with st.expander("ℹ️ Comment configurer credentials.json ?"):
        st.markdown(
            """
            1. Allez sur [Google Cloud Console](https://console.cloud.google.com/).
            2. Créez un projet → activez l'**API Google Drive**.
            3. Créez des identifiants OAuth 2.0 (type : Application de bureau).
            4. Téléchargez le fichier JSON et renommez-le **credentials.json**.
            5. Placez-le dans le même dossier que `app.py`.
            """
        )

# Affichage de l'historique de la conversation
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Zone de saisie
if prompt := st.chat_input(
    "Posez votre question sur le cours de RDM…",
    disabled=not st.session_state.synced_files,
):
    # S'assurer que la session Gemini est active
    if not st.session_state.chat_session:
        if not gemini_key:
            st.error("Clé API Gemini manquante.")
            st.stop()
        try:
            init_gemini(gemini_key)
            if not st.session_state.gemini_model:
                st.session_state.gemini_model = build_model(st.session_state.documents_text)
            st.session_state.chat_session = start_chat(
                st.session_state.gemini_model, st.session_state.messages
            )
        except Exception as e:
            st.error(f"Erreur d'initialisation Gemini : {e}")
            st.stop()

    # Afficher le message utilisateur
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Obtenir et afficher la réponse
    with st.chat_message("assistant"):
        with st.spinner("Analyse en cours…"):
            try:
                answer = ask(st.session_state.chat_session, prompt)
                st.markdown(answer)
                st.session_state.messages.append({"role": "model", "content": answer})
            except Exception as e:
                err = f"Erreur lors de la réponse : {e}"
                st.error(err)
                st.session_state.messages.append({"role": "model", "content": err})
