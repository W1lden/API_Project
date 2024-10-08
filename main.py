from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy.ext.declarative import declarative_base
from models import Product, Order, OrderItem, Base, OrderStatus
from pydantic import BaseModel
import asyncio
import os
from dotenv import load_dotenv


# Загружаем переменные окружения из .env файла
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

app = FastAPI()

# Функция для создания всех таблиц
async def create_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.on_event("startup")
async def startup_event():
    # Создаем таблицы при старте приложения
    await create_database()

# Схемы для валидации данных через Pydantic
class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    stock: int

class OrderCreate(BaseModel):
    items: list[dict]  # Список товаров в заказе

# CRUD функции
async def get_db():
    async with SessionLocal() as session:
        yield session

@app.post("/products")
async def create_product(product: ProductCreate, db: AsyncSession = Depends(get_db)):
    new_product = Product(**product.dict())
    db.add(new_product)
    await db.commit()
    await db.refresh(new_product)
    return new_product

@app.get("/products")
async def list_products(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product))
    products = result.scalars().all()
    return products

@app.get("/products/{product_id}")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.put("/products/{product_id}")
async def update_product(product_id: int, product_data: ProductCreate, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    for key, value in product_data.dict().items():
        setattr(product, key, value)
    
    await db.commit()
    await db.refresh(product)
    return product

@app.delete("/products/{product_id}")
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    await db.delete(product)
    await db.commit()
    return {"message": "Product deleted successfully"}

@app.post("/orders")
async def create_order(order_data: OrderCreate, db: AsyncSession = Depends(get_db)):
    order = Order()
    db.add(order)
    
    for item in order_data.items:
        product = await db.get(Product, item["product_id"])
        if not product or product.stock < item["quantity"]:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        
        product.stock -= item["quantity"]
        order_item = OrderItem(order=order, product=product, quantity=item["quantity"])
        db.add(order_item)
    
    await db.commit()
    await db.refresh(order)
    return order

@app.get("/orders")
async def list_orders(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Order))
    orders = result.scalars().all()
    return orders

@app.get("/orders/{order_id}")
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

class OrderStatusUpdate(BaseModel):
    status: OrderStatus

@app.patch("/orders/{order_id}/status")
async def update_order_status(order_id: int, status_data: OrderStatusUpdate, db: AsyncSession = Depends(get_db)):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order.status = status_data.status
    await db.commit()
    await db.refresh(order)
    return order
