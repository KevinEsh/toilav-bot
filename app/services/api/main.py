from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from dbconfig import get_session, create_db_and_tables
from chatbot_schema import Products
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

app = FastAPI(title="Toilav Bot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Schema para crear/editar productos (no incluye id ni timestamps)
class ProductCreate(BaseModel):
    p_name: str
    p_description: Optional[str] = None
    p_sale_price: float = 0.0
    p_currency: str = "MXN"
    p_net_content: float = 1.0
    p_unit: str = "unit"
    p_image_uuid: Optional[str] = None
    p_properties: Optional[dict] = None
    p_rag_text: Optional[str] = None
    p_is_available: bool = True


class ProductUpdate(BaseModel):
    p_name: Optional[str] = None
    p_description: Optional[str] = None
    p_sale_price: Optional[float] = None
    p_currency: Optional[str] = None
    p_net_content: Optional[float] = None
    p_unit: Optional[str] = None
    p_image_uuid: Optional[str] = None
    p_properties: Optional[dict] = None
    p_rag_text: Optional[str] = None
    p_is_available: Optional[bool] = None


# ---- ENDPOINTS ----

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "toilav-api"}


@app.get("/products")
def list_products(session: Session = Depends(get_session)):
    products = session.exec(select(Products)).all()
    return products


@app.get("/products/{product_id}")
def get_product(product_id: int, session: Session = Depends(get_session)):
    product = session.get(Products, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product


@app.post("/products", status_code=201)
def create_product(data: ProductCreate, session: Session = Depends(get_session)):
    product = Products(**data.model_dump())
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@app.put("/products/{product_id}")
def update_product(product_id: int, data: ProductUpdate, session: Session = Depends(get_session)):
    product = session.get(Products, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(product, key, value)
    product.p_updated_at = datetime.now(timezone.utc)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@app.delete("/products/{product_id}")
def delete_product(product_id: int, session: Session = Depends(get_session)):
    product = session.get(Products, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    session.delete(product)
    session.commit()
    return {"detail": "Producto eliminado", "id": product_id}