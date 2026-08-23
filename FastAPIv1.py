import uuid
from fastapi import FastAPI
from pydantic import BaseModel

app=FastAPI()

class Book(BaseModel):
    title:str
    author:str

books=[{"id":uuid.uuid4(),"title":"Harry Potter","author":"J.K. Rowling"},{"id":uuid.uuid4(),"title":"Lord of the Rings","author":"J.R.R. Tolkein"},{"id":uuid.uuid4(),"title":"Superman","author":"Jerry Siegel and Joe Shuster"}]
@app.get("/")
def home():
    return {"message":"Book API is running."}

@app.get("/books")
def get_books():
    return books
@app.get("/books/{book_id}")

def get_book(book_id:uuid.UUID):
   for book in books:
    if book["id"]==book_id:
         return book
    return {"message":"Book not found"}
   
@app.post("/books")
def add_book(book:Book):
    new_book={"id":uuid.uuid4(),"title":book.title,"author":book.author}
    books.append(new_book)
    return new_book

@app.put("/books/{book_id}")
def update_book(book_id:uuid.UUID,book:Book):
    for existing_book in books:
        if existing_book["id"]==book_id:
            existing_book["title"]=book.title
            existing_book["author"]=book.author
            return existing_book

    return {"message":"Book not found"}
@app.delete("/books/{book_id}")
def delete_book(book_id:uuid.UUID):
    for existing_book in books:
          if existing_book["id"]==book_id:
                books.remove(existing_book)
                return {"message":"Book deleted successfully"}
    return {"message":"Book not found"}