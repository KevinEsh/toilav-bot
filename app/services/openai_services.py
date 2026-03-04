from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

INSTRUCTIONS = """
Eres un asistente de servicio a cliente, amigable y con el objetivo de concretar una venta para el negocio tremenda nuez, si no sabes algo, no inventes y di que lo preguntaras
"""

def generate_response(message_body, wa_id=None, name=None):
    messages = [
        {"role": "system", "content": INSTRUCTIONS},
        {"role": "user", "content": message_body}
    ]

    response = client.responses.create(
        model="gpt-4o-mini",
        input=messages
    )

    return response.output_text