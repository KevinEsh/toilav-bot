import json
import os
import uuid

import boto3
from botocore.config import Config
from fastapi import FastAPI, File, HTTPException, Depends, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlmodel import Session, select
from dbconfig import get_session, create_db_and_tables
from chatbot_schema import Products
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

_s3 = None


def get_s3():
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            endpoint_url=f"http://{os.getenv('MINIO_ENDPOINT', 'minio:9000')}",
            aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            config=Config(signature_version="s3v4"),
        )
    return _s3


MINIO_BUCKET = os.getenv("MINIO_BUCKET", "products")
MINIO_PUBLIC_URL = os.getenv("MINIO_PUBLIC_URL", "http://localhost:9000")

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
    p_image_url: Optional[str] = None
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
    p_image_url: Optional[str] = None
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


@app.post("/products/{product_id}/image")
async def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    product = session.get(Products, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else "jpg"
    object_name = f"{product_id}/{uuid.uuid4()}.{ext}"

    get_s3().upload_fileobj(
        file.file,
        MINIO_BUCKET,
        object_name,
        ExtraArgs={"ContentType": file.content_type or "image/jpeg"},
    )

    image_url = f"{MINIO_PUBLIC_URL}/{MINIO_BUCKET}/{object_name}"
    product.p_image_url = image_url
    product.p_updated_at = datetime.now(timezone.utc)
    session.add(product)
    session.commit()
    session.refresh(product)
    return {"image_url": image_url, "product": product}


# ---- ORDERS ----

@app.get("/orders")
def list_orders(session: Session = Depends(get_session)):
    rows = session.execute(text("""
        SELECT o.*, c.c_name AS customer_name, c.c_phone AS customer_phone
        FROM orders o
        LEFT JOIN customers c ON o.o_c_id = c.c_id
        ORDER BY o.o_created_at DESC
    """)).mappings().all()
    return [dict(r) for r in rows]


@app.get("/orders/{order_id}")
def get_order_detail(order_id: int, session: Session = Depends(get_session)):
    order = session.execute(text("""
        SELECT o.*, c.c_name AS customer_name, c.c_phone AS customer_phone
        FROM orders o
        LEFT JOIN customers c ON o.o_c_id = c.c_id
        WHERE o.o_id = :order_id
    """), {"order_id": order_id}).mappings().first()
    if not order:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    items = session.execute(text("""
        SELECT oi.*, p.p_name AS product_name
        FROM orderitems oi
        LEFT JOIN products p ON oi.oi_p_id = p.p_id
        WHERE oi.oi_o_id = :order_id
    """), {"order_id": order_id}).mappings().all()
    return {**dict(order), "items": [dict(i) for i in items]}


# ---- METRICS ----

@app.get("/metrics")
def get_metrics(session: Session = Depends(get_session)):
    totals = session.execute(text("""
        SELECT
            COUNT(*) AS total_orders,
            SUM(CASE WHEN LOWER(o_payment_status::text) = 'completed' THEN o_total ELSE 0 END) AS total_revenue
        FROM orders
    """)).mappings().first()

    by_status = session.execute(text(
        "SELECT o_status, COUNT(*) AS count FROM orders GROUP BY o_status ORDER BY count DESC"
    )).mappings().all()

    top_products = session.execute(text("""
        SELECT p.p_name, SUM(s.sa_units_sold) AS units_sold
        FROM sales s
        LEFT JOIN products p ON s.sa_p_id = p.p_id
        GROUP BY p.p_id, p.p_name
        ORDER BY units_sold DESC
        LIMIT 5
    """)).mappings().all()

    daily_revenue = session.execute(text("""
        SELECT
            DATE(o_created_at) AS date,
            SUM(CASE WHEN LOWER(o_payment_status::text) = 'completed' THEN o_total ELSE 0 END) AS revenue
        FROM orders
        GROUP BY DATE(o_created_at)
        ORDER BY date
    """)).mappings().all()

    active_customers = session.execute(text(
        "SELECT COUNT(*) AS count FROM customers WHERE LOWER(c_status::text) = 'active'"
    )).scalar()

    return {
        "total_orders": totals["total_orders"],
        "total_revenue": float(totals["total_revenue"] or 0),
        "active_customers": active_customers,
        "orders_by_status": {r["o_status"]: r["count"] for r in by_status},
        "top_products": [{"name": r["p_name"], "units_sold": r["units_sold"]} for r in top_products],
        "daily_revenue": [{"date": str(r["date"]), "revenue": float(r["revenue"] or 0)} for r in daily_revenue],
    }


# ---- FAQ ----

class FAQCreate(BaseModel):
    faq_category: str = "general"
    faq_question: str
    faq_answer: str
    faq_keywords: Optional[list] = None
    faq_display_order: int = 0
    faq_is_active: bool = True


@app.get("/faqitems")
def list_faqs(session: Session = Depends(get_session)):
    rows = session.execute(text(
        "SELECT * FROM faqitems ORDER BY faq_category, faq_display_order, faq_id"
    )).mappings().all()
    return [dict(r) for r in rows]


@app.post("/faqitems", status_code=201)
def create_faq(data: FAQCreate, session: Session = Depends(get_session)):
    row = session.execute(text("""
        INSERT INTO faqitems
            (faq_category, faq_question, faq_answer, faq_keywords,
             faq_display_order, faq_is_active, faq_view_count, faq_created_at, faq_updated_at)
        VALUES
            (:category, :question, :answer, CAST(:keywords AS json),
             :display_order, :is_active, 0, NOW(), NOW())
        RETURNING *
    """), {
        "category": data.faq_category,
        "question": data.faq_question,
        "answer": data.faq_answer,
        "keywords": json.dumps(data.faq_keywords) if data.faq_keywords else "null",
        "display_order": data.faq_display_order,
        "is_active": data.faq_is_active,
    }).mappings().first()
    session.commit()
    return dict(row)


@app.put("/faqitems/{faq_id}")
def update_faq(faq_id: int, data: FAQCreate, session: Session = Depends(get_session)):
    row = session.execute(text("""
        UPDATE faqitems
        SET faq_category = :category, faq_question = :question, faq_answer = :answer,
            faq_keywords = CAST(:keywords AS json), faq_display_order = :display_order,
            faq_is_active = :is_active, faq_updated_at = NOW()
        WHERE faq_id = :faq_id
        RETURNING *
    """), {
        "faq_id": faq_id,
        "category": data.faq_category,
        "question": data.faq_question,
        "answer": data.faq_answer,
        "keywords": json.dumps(data.faq_keywords) if data.faq_keywords else "null",
        "display_order": data.faq_display_order,
        "is_active": data.faq_is_active,
    }).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="FAQ no encontrado")
    session.commit()
    return dict(row)


@app.delete("/faqitems/{faq_id}")
def delete_faq(faq_id: int, session: Session = Depends(get_session)):
    result = session.execute(
        text("DELETE FROM faqitems WHERE faq_id = :id RETURNING faq_id"), {"id": faq_id}
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="FAQ no encontrado")
    session.commit()
    return {"detail": "FAQ eliminado", "id": faq_id}