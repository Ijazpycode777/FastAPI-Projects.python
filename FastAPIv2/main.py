from database import conn, cur
import psycopg2
import uuid
from uuid import UUID
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

app = FastAPI()

class Expense(BaseModel):
    expense: str
    amount: float = Field(gt=0, le=1_000_000)
    @field_validator("expense")
    @classmethod
    def validate_expense(cls,value):
        value=value.strip()
        if not value:
            raise ValueError("Expense name cannot be empty!")
        if len(value)>100:
            raise ValueError("Expense name is too long!")
        return value

def create_table():
    cur.execute('''CREATE TABLE IF NOT
    EXISTS expenses (id UUID PRIMARY KEY, 
    expense VARCHAR(100) NOT NULL, amount 
    NUMERIC(10,2) NOT NULL, 
    created_at TIMESTAMPTZ NOT NULL 
    DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
create_table()

@app.post("/expenses", status_code=201)
def add_expense(expense: Expense):
    try:
        expense_id = uuid.uuid4()

        cur.execute(
            """
            INSERT INTO expenses (id, expense, amount)
            VALUES (%s, %s, %s)
            RETURNING id, expense, amount, created_at
            """,
            (str(expense_id), expense.expense, expense.amount)
        )

        new_expense = cur.fetchone()
        conn.commit()

        return {
            "id": new_expense[0],
            "expense": new_expense[1],
            "amount": new_expense[2],
            "created_at": new_expense[3]
        }

    except psycopg2.Error as e:
        conn.rollback()
        print(f"Database error: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
@app.get("/")
def home():
    return {"message": "Expensecal API is running"}

@app.get("/expenses")
def show_expenses():
    cur.execute("""SELECT id, expense, amount, created_at FROM expenses ORDER BY created_at DESC""")
    expenses=cur.fetchall()
    return [
        {
            "id": expense[0],
            "expense": expense[1],
            "amount": expense[2],
            "created_at": expense[3]
        }
        for expense in expenses
    ]

@app.get("/expenses/{expense_id}")
def get_expense(expense_id:UUID):
    cur.execute("""SELECT id, expense, amount, created_at FROM expenses WHERE id=%s""",
    (str(expense_id),))
    expense = cur.fetchone()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found!")
    return{
        "id": expense[0],
        "expense": expense[1],
        "amount": expense[2],
        "created_at": expense[3]
    }  

@app.delete("/expenses/{expense_id}",status_code=204)
def delete_expense(expense_id:UUID):
    try:
        cur.execute("""DELETE FROM expenses WHERE id=%s""",(str(expense_id),))
        if cur.rowcount==0:
            raise HTTPException(status_code=404, detail="No expense found")
        conn.commit()
    
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500,detail=str(e))
    
@app.put("/expenses/{expense_id}")
def update_expense(expense_id:UUID,expense:Expense):
    try:
        cur.execute("""UPDATE expenses SET expense=%s, amount=%s
        WHERE id=%s RETURNING id, expense, amount, created_at""", (expense.expense, expense.amount,str(expense_id)))
        updated_expense=cur.fetchone()
        if not updated_expense:
            conn.rollback()
            raise HTTPException(status_code=404, detail="No expense found!")
        conn.commit()
        return {
            "id":"updated_expense[0]",
            "expense":"updated_expense[1]",
            "amount":"updated_expense[2]",
            "created_at":"updated_expense[3]"
        }
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
