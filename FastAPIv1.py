import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel 

#INITIALIZE APP 
app=FastAPI()

#Create request model 
class Book(BaseModel):
    title:str
    author:str

#Create response model 
class Book_response(BaseModel):
    id:uuid.UUID
    title:str
    author:str

#Simple list to store books
books=[{"id":uuid.uuid4(),"title":"Harry Potter","author":"J.K. Rowling"},{"id":uuid.uuid4(),"title":"Lord of the Rings","author":"J.R.R. Tolkein"},{"id":uuid.uuid4(),"title":"Superman","author":"Jerry Siegel and Joe Shuster"}]

#First endpoint for HTTP
@app.get("/")
def home():
    return {"message":"Book API is running."} 

#Show all info/books
@app.get("/books",response_model=list[Book_response])
def get_books():
    return books  #return = print() for http requests

#Search a book
@app.get("/books/{title}",response_model=Book_response)
def get_book(title: str):
    for book in books:
        if book["title"] == title:
            return book
    raise HTTPException(status_code=404, detail="Book not found")  # Raise an error if book is not found

#Client adds a book   
@app.post("/books",response_model=Book_response)
def add_book(book:Book):
    new_book={"id":uuid.uuid4(),"title":book.title,"author":book.author}
    books.append(new_book)
    return new_book

#Client updates a book
@app.put("/books/{book_id}",response_model=Book_response)
def update_book(book_id:uuid.UUID,book:Book):
    for existing_book in books:   #Apply a variable
        if existing_book["id"]==book_id:
            existing_book["title"]=book.title
            existing_book["author"]=book.author
            return existing_book
    raise HTTPException(status_code=404,detail="Book not found")  #Raise an error if book is not found

#Client deletes a book
@app.delete("/books/{title}")
def delete_book(title: str):
    for existing_book in books:
        if existing_book["title"] == title:
            books.remove(existing_book)
            return {"message":"Book deleted successfully"}
    raise HTTPException(status_code=404,detail="Book not found")  #Raise an error if book is not found
