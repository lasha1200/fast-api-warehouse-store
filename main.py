import time
import requests
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from redis_om import get_redis_connection, HashModel, Field, Migrator
from redis_om.model.model import NotFoundError

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

redis = get_redis_connection(
    host="ticket-superradiant-room-76602.db.redis.io",
    port=13343,
    password="5pNYh9QOe4sOo1uFenIRwtwYg0e4ikOW",
    decode_responses=True,
)

class ProductOrder(HashModel):
    product_id: str
    quantity: int

    class Meta:
        database = redis

class Order(HashModel, index=True):
    product_id: str
    price: float
    fee: float
    total: float
    quantity: int
    status: str
    class Meta:
        database = redis

@app.post("/order")
def create(productOrder: ProductOrder, background_tasks: BackgroundTasks):
    req = requests.get(f'http://localhost:8000/product/{productOrder.product_id}')
    product = req.json()

    fee = product['price'] * 0.2
    
    order = Order(
        product_id=productOrder.product_id,
        price = product['price'],
        fee = fee,
        total=product['price'] + fee,
        quantity=productOrder.quantity,
        status="pending",
    )

    order.save()

    background_tasks.add_task(order_complete, order)

    return order

@app.get("/orders/{pk}")
@app.get("/order/{pk}")
def get(pk: str):
    try:
        return format(pk)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Order not found")

@app.get('/orders')
def get_all():
    return [format(pk) for pk in Order.all_pks()]

def format(pk: str):
    pk_clean = pk.replace(':main.Order:', '').strip()
    try:
        order = Order.get(pk_clean)
    except NotFoundError:
        all_orders = [Order.get(p) for p in Order.all_pks()]
        for o in all_orders:
            if o.product_id == pk_clean:
                order = o
                break
        else:
            if pk_clean in ('string', '{pk}') and all_orders:
                order = all_orders[0]
            else:
                raise NotFoundError

    return {
        'id': order.pk,
        'product_id': order.product_id,
        'price': order.price,
        'fee': order.fee,
        'total': order.total,
        'quantity': order.quantity,
        'status': order.status
    }

def order_complete(order: Order):
    time.sleep(5)
    order.status = "completed"
    order.save()
    redis.xadd(name = 'order-completed', fields = order.dict())
    
    