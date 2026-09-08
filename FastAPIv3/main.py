from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from database import cur, conn
import psycopg2
import bcrypt

app = FastAPI()

def create_table():
    cur.execute('''CREATE TABLE IF NOT
    EXISTS customers (id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(61) NOT NULL,
    balance NUMERIC(10,2) NOT NULL DEFAULT 0.00 CHECK (balance >= 0),
    created_at TIMESTAMPTZ NOT NULL
    DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()

def transaction_table():
    cur.execute('''CREATE TABLE IF NOT
    EXISTS transactions (id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(id),
    amount NUMERIC(10,2) NOT NULL,
    transaction_type VARCHAR(10) NOT NULL CHECK (transaction_type IN ('deposit', 'withdrawal')),
    created_at TIMESTAMPTZ NOT NULL
    DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()

create_table()
transaction_table()

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=50)
    @field_validator('username')
    @classmethod
    def validate_username(cls, value):
        if not value.isalnum():
            raise ValueError('Username must be alphanumeric')
        return value

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=50)

class MoneyRequest(BaseModel):
    amount: float = Field(..., gt=0)


@app.post("/register")
def register_user(request: RegisterRequest):
    username = request.username
    hashed_password = bcrypt.hashpw(request.password.encode('utf-8'), bcrypt.gensalt())
    try:
        cur.execute("INSERT INTO customers (username, password) VALUES (%s, %s) RETURNING id", (username,hashed_password.decode('utf-8')))
        user_id = cur.fetchone()
        if user_id is None:
            raise HTTPException(status_code=500, detail="Failed to register user")
        conn.commit()
        return {"message": "User registered successfully", "user_id": user_id[0]}
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Username already exists")

@app.post("/login")
def login_user(request: LoginRequest):
    username = request.username
    cur.execute("SELECT id, password FROM customers WHERE username = %s", (username,))
    user = cur.fetchone()
    if not user:
        raise HTTPException(status_code=400, detail="Username does not exist")
    user_id, hashed_password = user
    if not bcrypt.checkpw(request.password.encode('utf-8'), hashed_password.encode('utf-8')):
        raise HTTPException(status_code=400, detail="Invalid username or password")
    return {"message": "Login successful", "user_id": user_id}

@app.get("/balance/{user_id}")
def get_balance(user_id: int):
    try:
        cur.execute("SELECT balance FROM customers WHERE id = %s", (user_id,))
        balance = cur.fetchone()
        if not balance:
            raise HTTPException(status_code=400, detail="User does not exist")
        return {"balance": float(balance[0])}
    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Failed to retrieve balance")

@app.post("/deposit/{user_id}")
def deposit(user_id: int, request: MoneyRequest):
    try:
        cur.execute("SELECT id FROM customers WHERE id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=400, detail="User does not exist")
        amount = request.amount
        cur.execute("INSERT INTO transactions (customer_id, amount, transaction_type) VALUES (%s, %s, 'deposit')", (user_id, amount))
        cur.execute("UPDATE customers SET balance = balance + %s WHERE id = %s RETURNING balance", (amount, user_id))
        new_balance = cur.fetchone()
        if not new_balance:
            raise HTTPException(status_code=400, detail="User does not exist")
        conn.commit()
        return {"message": "Deposit successful", "new_balance": float(new_balance[0])}
    except psycopg2.Error:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to deposit funds")

@app.post("/withdraw/{user_id}")
def withdraw(user_id: int, request: MoneyRequest):
    try:
        cur.execute("SELECT balance FROM customers WHERE id = %s", (user_id,))
        balance = cur.fetchone()
        if not balance:
            raise HTTPException(status_code=400, detail="User does not exist")
        if balance[0] < request.amount:
            raise HTTPException(status_code=400, detail="Insufficient funds")
        amount = request.amount
        cur.execute("INSERT INTO transactions (customer_id, amount, transaction_type) VALUES (%s, %s, 'withdrawal')", (user_id, amount))
        cur.execute("UPDATE customers SET balance = balance - %s WHERE id = %s RETURNING balance", (amount, user_id))
        new_balance = cur.fetchone()
        if not new_balance:
            raise HTTPException(status_code=400, detail="User does not exist")
        conn.commit()
        return {"message": "Withdrawal successful", "new_balance": float(new_balance[0])}
    except psycopg2.Error:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Failed to withdraw funds")

@app.get("/transactions/{user_id}")
def get_transactions(user_id: int):
    try:
        cur.execute("SELECT id FROM customers WHERE id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=400, detail="User does not exist")
        cur.execute("SELECT amount, transaction_type, created_at FROM transactions WHERE customer_id = %s ORDER BY created_at DESC", (user_id,))
        transactions = cur.fetchall()
        return {"transactions": [{"amount": float(t[0]), "transaction_type": t[1], "created_at": t[2]} for t in transactions]}
    except psycopg2.Error:
        raise HTTPException(status_code=500, detail="Failed to retrieve transactions")    
