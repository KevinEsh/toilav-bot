"""
Seed script: ensures Tremenda Nuez products exist in the catalog and uploads their images.

For each product in the list:
  - If a product with the same p_name already exists, reuse it (no duplicate).
  - Otherwise, create it.
  - Then upload the image.

Reads images from data/imagenes/ and hits the local API at http://localhost:8000.
Run with: python scripts/seed_tremenda_nuez.py
"""
import sys
from pathlib import Path

import requests

API = "http://localhost:8000"
IMG_DIR = Path(__file__).resolve().parent.parent / "data" / "imagenes"

PRODUCTS = [
    {
        "filename": "arandano enchilado.jpg",
        "p_name": "Arándano Enchilado",
        "p_description": (
            "Arándanos deshidratados cubiertos con chile. Snack dulce-picante 100% natural. "
            "Bolsa individual de 100g."
        ),
        "p_sale_price": 65.0,
        "p_net_content": 100.0,
        "p_unit": "gr",
    },
    {
        "filename": "ch gomitas.jpg",
        "p_name": "Charola de Gomitas Enchiladas",
        "p_description": (
            "Charola de regalo con variedad de gomitas enchiladas: aros de mango, botones, "
            "besos y más. Ideal para compartir o regalar."
        ),
        "p_sale_price": 450.0,
        "p_net_content": 1.0,
        "p_unit": "unit",
    },
    {
        "filename": "ch nueces.jpg",
        "p_name": "Charola de Nueces Surtidas",
        "p_description": (
            "Charola de regalo premium con surtido de nueces: nuez de Castilla, nuez de la "
            "India, almendras, pistaches y pecanas. Presentación elegante con listón."
        ),
        "p_sale_price": 650.0,
        "p_net_content": 1.0,
        "p_unit": "unit",
    },
    {
        "filename": "mix chocolate.jpg",
        "p_name": "Tremendo Mix Chocolate 1kg",
        "p_description": (
            "Mezcla premium de nueces cubiertas con chocolate: almendras, pecanas, cacahuate y "
            "pasas chocolatadas. Bolsa de 1kg."
        ),
        "p_sale_price": 520.0,
        "p_net_content": 1000.0,
        "p_unit": "gr",
    },
    {
        "filename": "mix ench.jpg",
        "p_name": "Tremendo Mix Enchilado 100g",
        "p_description": (
            "Mezcla enchilada: nuez tostada, almendra, cacahuate español, arándano y mango "
            "deshidratado con chile. Presentación individual de 100g."
        ),
        "p_sale_price": 65.0,
        "p_net_content": 100.0,
        "p_unit": "gr",
    },
    {
        "filename": "mix enchilado.jpg",
        "p_name": "Tremendo Mix Enchilado 1kg",
        "p_description": (
            "Mezcla enchilada tamaño familiar: nuez, almendra, cacahuate español, arándano y "
            "mango deshidratado con chile. Bolsa de 1kg."
        ),
        "p_sale_price": 450.0,
        "p_net_content": 1000.0,
        "p_unit": "gr",
    },
    {
        "filename": "nuez de corazon.jpg",
        "p_name": "Nuez de Corazón 900g",
        "p_description": (
            "Mitades enteras de nuez pecana de la Comarca Lagunera. 100% natural, sin sal ni "
            "aditivos. Bolsa de 900g."
        ),
        "p_sale_price": 580.0,
        "p_net_content": 900.0,
        "p_unit": "gr",
    },
    {
        "filename": "nuez de la india.jpg",
        "p_name": "Nuez de la India 1kg",
        "p_description": (
            "Nuez de la India (cashew) tostada. Ideal como snack o para cocinar. Bolsa de 1kg."
        ),
        "p_sale_price": 620.0,
        "p_net_content": 1000.0,
        "p_unit": "gr",
    },
    {
        "filename": "nuez pedaceria.jpg",
        "p_name": "Nuez Pedacería Extra Grande 900g",
        "p_description": (
            "Pedacería de nuez pecana tamaño extra grande. Perfecta para repostería, postres "
            "y botana. Bolsa de 900g."
        ),
        "p_sale_price": 480.0,
        "p_net_content": 900.0,
        "p_unit": "gr",
    },
    {
        "filename": "pistache.jpg",
        "p_name": "Pistaches 1kg",
        "p_description": (
            "Pistaches con cáscara tostados y salados. 100% naturales. Bolsa de 1kg."
        ),
        "p_sale_price": 750.0,
        "p_net_content": 1000.0,
        "p_unit": "gr",
    },
]


def fetch_existing_by_name() -> dict[str, int]:
    r = requests.get(f"{API}/products", timeout=15)
    r.raise_for_status()
    return {p["p_name"]: p["p_id"] for p in r.json()}


def create_product(prod: dict) -> dict:
    payload = {
        "p_name": prod["p_name"],
        "p_description": prod["p_description"],
        "p_sale_price": prod["p_sale_price"],
        "p_currency": "MXN",
        "p_net_content": prod["p_net_content"],
        "p_unit": prod["p_unit"],
        "p_is_available": True,
    }
    r = requests.post(f"{API}/products", json=payload, timeout=15)
    r.raise_for_status()
    return r.json()


def upload_image(product_id: int, image_path: Path) -> dict:
    with open(image_path, "rb") as f:
        files = {"file": (image_path.name, f, "image/jpeg")}
        r = requests.post(f"{API}/products/{product_id}/image", files=files, timeout=120)
    r.raise_for_status()
    return r.json()


def main() -> int:
    if not IMG_DIR.is_dir():
        print(f"[ERROR] No existe {IMG_DIR}", file=sys.stderr)
        return 1

    existing = fetch_existing_by_name()
    print(f"Procesando {len(PRODUCTS)} productos en {API} ({len(existing)} ya existen)...\n")

    for prod in PRODUCTS:
        img = IMG_DIR / prod["filename"]
        if not img.is_file():
            print(f"  [SKIP] Falta imagen: {img.name}")
            continue
        try:
            if prod["p_name"] in existing:
                pid = existing[prod["p_name"]]
                action = "REUSE"
            else:
                pid = create_product(prod)["p_id"]
                existing[prod["p_name"]] = pid
                action = "NEW"
            upload_image(pid, img)
            print(f"  [{action:>5}] #{pid:>3} {prod['p_name']:<40} <- {img.name}")
        except requests.HTTPError as e:
            print(f"  [FAIL] {prod['p_name']}: {e.response.status_code} {e.response.text[:200]}")
        except Exception as e:
            print(f"  [FAIL] {prod['p_name']}: {e}")

    print("\nListo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
