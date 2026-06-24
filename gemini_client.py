"""
Client Gemini : gestion du contexte documentaire et du chat.
"""
import os

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "gemini-1.5-pro"  # Fenêtre de 2M tokens — parfait pour 1 Go de cours

SYSTEM_PROMPT = """Tu es un tuteur expert en Résistance des Matériaux (RDM).
Tu as accès à la totalité des cours, exercices et documents fournis par l'étudiant.
Réponds toujours en français, de manière pédagogique et structurée.
- Pour les calculs, détaille chaque étape avec les formules utilisées.
- Cite le document source quand tu t'appuies sur un passage précis.
- Si la question dépasse le contenu des documents, dis-le clairement.
- Utilise des exemples concrets tirés du cours quand c'est possible.
"""


def init_gemini(api_key: str | None = None):
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        raise ValueError(
            "Clé API Gemini manquante. "
            "Ajoutez GEMINI_API_KEY dans votre fichier .env ou dans les paramètres."
        )
    genai.configure(api_key=key)


def build_model(documents_text: str = "") -> genai.GenerativeModel:
    """Crée le modèle avec le contexte documentaire injecté dans le system prompt."""
    system = SYSTEM_PROMPT
    if documents_text:
        # On limite à ~1,8M caractères pour rester dans les limites du contexte
        truncated = documents_text[:1_800_000]
        system += f"\n\n--- DOCUMENTS DE COURS ---\n{truncated}\n--- FIN DES DOCUMENTS ---"

    return genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=system,
        generation_config=genai.GenerationConfig(
            temperature=0.2,
            max_output_tokens=4096,
        ),
    )


def start_chat(model: genai.GenerativeModel, history: list[dict] | None = None):
    """Démarre (ou reprend) une session de chat Gemini."""
    gemini_history = []
    if history:
        for msg in history:
            gemini_history.append(
                {"role": msg["role"], "parts": [msg["content"]]}
            )
    return model.start_chat(history=gemini_history)


def ask(chat_session, question: str) -> str:
    """Envoie une question et retourne la réponse en texte."""
    response = chat_session.send_message(question)
    return response.text
