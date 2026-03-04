from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, Sequence, UniqueConstraint
from sqlmodel import Field, SQLModel


def id_field(table_name: str):
    """
    CREATE SEQUENCE IF NOT EXISTS table_name_id_seq START 1;
    """
    sequence = Sequence(f"{table_name}_id_seq")
    return Field(
        default=None,
        primary_key=True,
        unique=True,
        sa_column_args=[sequence],
        sa_column_kwargs={"server_default": sequence.next_value()},
    )


class Products(SQLModel, table=True):
    """
    This table stores information about the products for the WhatsApp chatbot. It includes the product
    name, description, 

    Args:
        p_id (Optional[int]): Product ID, auto-incremented.
        p_name (str): Name of the product.
        p_description (Optional[str]): Description of the product.
    """

    p_id: Optional[int] = id_field("products")
    p_name: str = Field(unique=True)
    p_description: Optional[str] = Field(default=None)


class Stores(SQLModel, table=True):
    """
    CREATE TABLE IF NOT EXISTS stores (
        s_id INTEGER PRIMARY KEY DEFAULT nextval('stores_id_seq'),
        s_name VARCHAR
    );

    Args:
        s_id (Optional[int]): Store ID, auto-incremented.
        s_name (str): Name of the store.
        s_city (Optional[str]): City where the store is located.
        s_state (Optional[str]): State where the store is located.
        s_country (Optional[str]): Country where the store is located.
        s_type (Optional[str]): Type of the store (e.g., retail, wholesale, online).
        s_cluster (Optional[str]): Cluster of the store (e.g., urban, suburban, rural).
    """

    s_id: Optional[int] = id_field("stores")
    s_name: str = Field(unique=True)
    s_longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    s_latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)


class Sales(SQLModel, table=True):
    """
    CREATE TABLE IF NOT EXISTS sales (
        s_id INTEGER PRIMARY KEY DEFAULT nextval('sales_id_seq'),
        s_p_id INTEGER,
        s_s_id INTEGER,
        s_date DATE,
        s_quantity INTEGER CHECK (s_quantity >= 0),
        UNIQUE (s_p_id, s_s_id, s_date),
        FOREIGN KEY (s_p_id) REFERENCES products(p_id),
        FOREIGN KEY (s_s_id) REFERENCES stores(s_id)
    );

    Args:
        s_id (Optional[int]): Sale ID, auto-incremented.
        s_p_id (int): Foreign key referencing the product.
        s_s_id (int): Foreign key referencing the store.
        s_date (date): Date of the sale.
        s_quantity (int): Quantity sold.
    """

    __table_args__ = (UniqueConstraint("sa_p_id", "sa_s_id", "sa_date", name="unique_sale"),)

    sa_id: Optional[int] = id_field("sales")
    sa_p_id: int = Field(foreign_key="products.p_id")
    sa_s_id: int = Field(foreign_key="stores.s_id")
    sa_date: date = Field(default_factory=lambda: date.today(timezone.utc))
    sa_units_sold: int = Field(ge=0)

from enum import Enum

class PromotionType(str, Enum):
    DISCOUNT = "discount"
    BUY_ONE_GET_ONE = "buy_one_get_one"
    FREE_SHIPPING = "free_shipping"
    OTHER = "other"

class Promotions(SQLModel, table=True):
    """

    Args:
        pr_id (Optional[int]): Promotion ID, auto-incremented.
        pr_p_id (int): Foreign key referencing the product.
        pr_s_id (int): Foreign key referencing the store.
        pr_start_date (date): Start date of the promotion.
        pr_end_date (date): End date of the promotion.
    """

    __table_args__ = (
        UniqueConstraint(
            "pr_p_id",
            "pr_s_id",
            "pr_date",
            "pr_type",
            name="unique_promotion",
        ),
    )

    pr_id: Optional[int] = id_field("promotions")
    pr_p_id: int = Field(foreign_key="products.p_id")
    pr_s_id: int = Field(foreign_key="stores.s_id")
    pr_active_from: date = Field(default_factory=date.today)
    pr_active_upto: date = Field(default_factory=date.today)
    pr_type: PromotionType = Field(default=PromotionType.DISCOUNT)
    pr_description: str = Field(default=None)


class Stocks(SQLModel, table=True):
    """
    CREATE TABLE IF NOT EXISTS stocks (
        sk_id INTEGER PRIMARY KEY DEFAULT nextval('stocks_id_seq'),
        sk_p_id INTEGER,
        sk_s_id INTEGER,
        sk_date DATE,
        sk_starting_inventory INTEGER CHECK (sk_starting_inventory >= 0),
        sk_ending_inventory INTEGER CHECK (sk_ending_inventory >= 0),
        UNIQUE (sk_p_id, sk_s_id, sk_date),
        FOREIGN KEY (sk_p_id) REFERENCES products(p_id),
        FOREIGN KEY (sk_s_id) REFERENCES stores(s_id)
    );

    Args:
        sk_id (Optional[int]): Stock ID, auto-incremented.
        sk_p_id (int): Foreign key referencing the product.
        sk_s_id (int): Foreign key referencing the store.
        sk_datetime (datetime): Date and time of the stock record.
        sk_units (int): Ending inventory for the period in sk_date.
    """

    __table_args__ = (UniqueConstraint("sk_p_id", "sk_s_id", "sk_date", name="unique_stock"),)

    sk_id: Optional[int] = id_field("stocks")
    sk_p_id: int = Field(foreign_key="products.p_id")
    sk_s_id: int = Field(foreign_key="stores.s_id")
    sk_datetime: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sk_units: int = Field(default=0, ge=0)



if __name__ == "__main__":
    from os import path

    from sqlmodel import Session, create_engine

    if not path.exists("data/test.db"):
        engine = create_engine("duckdb:///data/test.db")
        SQLModel.metadata.create_all(engine)
    else:
        engine = create_engine("duckdb:///data/test.db")

    with Session(engine) as session:
        # Upload dummy data

        # 1. Product Groups
        pg1 = ProductGroups(pg_name="BREAD/BAKERY")
        pg2 = ProductGroups(pg_name="DAIRY")
        pgs = [pg1, pg2]
        session.add_all(pgs)
        session.commit()

        # 2. Products
        p1 = Products(p_name="Donut", p_pg_id=pg1.pg_id, perishable=True)
        session.add(p1)

        # 3. Stores
        s1 = Stores(
            s_name="Market A",
            s_city="Quito",
            s_state="Pichincha",
            s_country="Ecuador",
            s_type="D",
            s_cluster="8",
        )
        session.add(s1)
        session.commit()

        # 4. Workshops
        w1 = Workshops(w_name="Bakery A")
        session.add(w1)
        session.commit()

        # 5. Transport Links
        tl1 = TransportLinks(tl_w_id=w1.w_id, tl_s_id=s1.s_id, tl_cost=10.0)
        session.add(tl1)

        # 6. Procurements
        pc1 = Procurements(
            pc_p_id=p1.p_id,
            pc_s_id=s1.s_id,
            pc_active_from=date(2023, 10, 1),
            pc_active_upto=date(2023, 10, 31),
        )
        session.add(pc1)
        session.commit()

        # 7. Demand Predictions
        dp1 = DemandPredictions(
            dp_p_id=p1.p_id,
            dp_s_id=s1.s_id,
            dp_date=date(2023, 10, 15),
            dp_mean=100,
        )
        session.add(dp1)
        session.commit()

        # 8. Stocks
        sk1 = Stocks(
            sk_p_id=p1.p_id,
            sk_s_id=s1.s_id,
            sk_date=date(2023, 10, 15),
            sk_starting_inventory=50,
            sk_ending_inventory=30,
        )
        session.add(sk1)
        session.commit()

        # 9. Events
        e1 = Events(e_name="Bakery Festival")
        session.add(e1)
        session.commit()

        # 10. Event Stores
        es1 = EventStores(es_e_id=e1.e_id, es_s_id=s1.s_id, es_date=date(2023, 10, 20))
        session.add(es1)
        session.commit()

        # print(session.exec(select(ProductGroups)).all())
        # print(session.exec(select(Products)).all())

    engine.dispose()

    import duckdb

    with duckdb.connect(database="./data/test.db", read_only=True) as con:
        pgroups_df = con.execute("""SELECT * FROM productgroups""").pl()
        print(pgroups_df)
        products_df = con.execute("""SELECT * FROM products""").pl()
        print(products_df)
        stores_df = con.execute("""SELECT * FROM stores""").pl()
        print(stores_df)
        workshops_df = con.execute("""SELECT * FROM workshops""").pl()
        print(workshops_df)
        transportlinks_df = con.execute("""SELECT * FROM transportlinks""").pl()
        print(transportlinks_df)
        procurements_df = con.execute("""SELECT * FROM procurements""").pl()
        print(procurements_df)
        demandpredictions_df = con.execute("""SELECT * FROM demandpredictions""").pl()
        print(demandpredictions_df)
        stocks_df = con.execute("""SELECT * FROM stocks""").pl()
        print(stocks_df)
        events_df = con.execute("""SELECT * FROM events""").pl()
        print(events_df)
        eventstores_df = con.execute("""SELECT * FROM eventstores""").pl()
        print(eventstores_df)
