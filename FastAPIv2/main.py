from datetime import datetime
from database import conn, cur
import psycopg2
import uuid
from uuid import UUID
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
#Initialze app
app = FastAPI()

#Response and request models
class ExpenseResponse(BaseModel):
    id: UUID
    expense: str
    amount: float
    created_at: datetime

class ExpenseCreate(BaseModel):
    expense: str = Field(min_length=2, max_length=100)
    amount: float = Field(gt=0, le=1_000_000)
    @field_validator("expense")
    @classmethod
    def validate_expense_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Expense name cannot be empty or whitespace.")
        return value
    
#Postgres table creation
def create_table():
    cur.execute('''CREATE TABLE IF NOT
    EXISTS expenses (id UUID PRIMARY KEY, 
    expense VARCHAR(100) NOT NULL, amount 
    NUMERIC(10,2) NOT NULL, 
    created_at TIMESTAMPTZ NOT NULL 
    DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
create_table()

#API endpoints
@app.post("/expenses", status_code=201, response_model=ExpenseResponse)
def add_expense(expense: ExpenseCreate):
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
        if new_expense is None:
            conn.rollback()
            raise HTTPException(status_code=500, detail="Failed to insert expense.")
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

@app.get("/expenses", response_model=list[ExpenseResponse])
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

@app.get("/expenses/{expense_id}", response_model=ExpenseResponse)
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
    
@app.put("/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(expense_id:UUID, expense: ExpenseCreate):
    try:
        cur.execute("""UPDATE expenses SET expense=%s, amount=%s
        WHERE id=%s RETURNING id, expense, amount, created_at""", (expense.expense, expense.amount,str(expense_id)))
        updated_expense=cur.fetchone()
        if not updated_expense:
            conn.rollback()
            raise HTTPException(status_code=404, detail="No expense found!")
        conn.commit()
        return {
            "id": updated_expense[0],
            "expense": updated_expense[1],
            "amount": updated_expense[2],
            "created_at": updated_expense[3]
        }
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
#End of file
