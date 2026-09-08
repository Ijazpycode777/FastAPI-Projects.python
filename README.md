FastAPI Learning Projects

A collection of backend projects built with Python and FastAPI to learn and practice REST API development, request validation, CRUD operations, database integration, and backend architecture.

These projects are intentionally built step-by-step to understand how FastAPI and backend systems work internally, rather than relying entirely on generated code.

---

📚 Projects

1. Book Manager API

A simple REST API for managing a collection of books.

The project uses an in-memory Python list of dictionaries as its data store, making it focused on learning the fundamentals of FastAPI before introducing a database.

Features

- Create a book
- Retrieve all books
- Retrieve a book by ID
- Update a book
- Delete a book
- UUID-based book IDs
- Pydantic request models
- Pydantic response models
- Request validation
- HTTP 404 error handling
- RESTful HTTP methods

Technologies

- Python
- FastAPI
- Pydantic
- Uvicorn

API Operations

Method| Endpoint| Purpose
"GET"| "/"| Check whether the API is running
"GET"| "/books"| Get all books
"GET"| "/books/{book_id}"| Get a specific book
"POST"| "/books"| Add a new book
"PUT"| "/books/{book_id}"| Update a book
"DELETE"| "/books/{book_id}"| Delete a book

«Note: The Book Manager currently stores data in memory. Any books added during runtime are lost when the application restarts.»

---

💰 2. ExpenseCal API

ExpenseCal is the more advanced project in this collection and is being developed as a practical backend application.

It started with a simple in-memory implementation to understand REST APIs and CRUD operations from scratch, and is being expanded into a database-backed FastAPI application using PostgreSQL.

The project is designed to bring together the backend concepts being learned throughout the FastAPI learning process.

Features

- Create expenses
- Retrieve expenses
- Search expenses
- Update expenses
- Delete expenses
- Expense validation using Pydantic
- UUID-based identifiers
- Response models
- HTTP exception handling
- PostgreSQL persistent storage
- Environment-based configuration
- Database connectivity
- Database integration
- REST API architecture

Technologies

- Python
- FastAPI
- Pydantic
- PostgreSQL
- Uvicorn
- "python-dotenv" / environment configuration

Development Progress

ExpenseCal is being developed progressively:

Python fundamentals
        ↓
REST API fundamentals
        ↓
FastAPI
        ↓
CRUD operations
        ↓
Pydantic validation
        ↓
Response models
        ↓
Error handling
        ↓
PostgreSQL
        ↓
Database integration
        ↓
Authentication & security
        ↓
Production backend concepts

The goal is not simply to produce a working application, but to understand the concepts behind each layer of the backend.

---

🎯 Learning Objectives

These projects are being used to develop a strong understanding of backend development, including:

- Python functions, classes, objects, parameters and arguments
- HTTP fundamentals
- REST architecture
- HTTP methods and status codes
- FastAPI routing
- Path parameters
- Query parameters
- Request bodies
- Pydantic models
- Request and response validation
- Exception handling
- API documentation with Swagger/OpenAPI
- Application configuration
- Environment variables
- Database fundamentals
- SQL and PostgreSQL
- CRUD database operations
- Authentication and authorization
- API security
- Backend project architecture
- Deployment and production concepts

---

🚀 Running the Projects

Install the required dependencies and start the FastAPI application with Uvicorn.

Example:

python -m uvicorn main:app --reload

The API can then be accessed locally.

Interactive API documentation is available through:

/docs

FastAPI also provides an alternative OpenAPI interface through:

/redoc

---

Bank Management System

A practice banking backend built with FastAPI, PostgreSQL, Pydantic, and bcrypt. This project focuses on learning how backend APIs interact with a relational database and how multiple database operations can work together as a single transaction.

Features

- User registration
- User login with bcrypt password hashing
- Customer IDs using PostgreSQL "SERIAL"
- Account balance management
- Deposit funds
- Withdraw funds
- Insufficient-balance validation
- Transaction history
- PostgreSQL foreign-key relationship between customers and transactions
- Pydantic request validation
- Database transactions with commit and rollback
- Swagger/OpenAPI documentation through FastAPI

Database Structure

The system uses two main tables:

customers

- "id"
- "username"
- "password"
- "balance"
- "created_at"

transactions

- "id"
- "customer_id"
- "amount"
- "transaction_type"
- "created_at"

Each transaction is associated with a customer through a foreign key.

API Endpoints

Method| Endpoint| Purpose
POST| "/register"| Register a new customer
POST| "/login"| Authenticate a customer
GET| "/balance/{user_id}"| Check account balance
POST| "/deposit/{user_id}"| Deposit money
POST| "/withdraw/{user_id}"| Withdraw money
GET| "/transactions/{user_id}"| View transaction history

What I Learned

This project helped me practice:

- Designing relational database tables
- Using primary and foreign keys
- Writing SQL queries from Python
- Working with PostgreSQL transactions
- Using Pydantic for request validation
- Password hashing and verification with bcrypt
- Handling database errors
- Designing REST API endpoints
- Keeping current account state separate from transaction history
- Understanding how multiple database operations can be committed or rolled back together

This is a learning project and is not intended to represent a production banking system.
📌 Project Philosophy

These projects are primarily learning projects, but they are being developed with real backend development practices in mind.

The approach is:

«Understand first, implement second, abstract later.»

Simple implementations are intentionally used when learning a concept. More advanced architecture is introduced only after understanding the underlying Python, FastAPI, HTTP, and database concepts.

---

🛠️ Future Improvements

Planned improvements include:

- Better project structure
- Dedicated routers
- Separate Pydantic schemas
- SQLAlchemy database models
- PostgreSQL database operations
- Database migrations
- Authentication
- Password hashing
- JWT-based authorization
- Role-based permissions
- Automated testing
- Improved error handling
- Logging
- Docker
- Production deployment

---

👨‍💻 Author

Personal backend development learning projects built while learning Python, FastAPI, REST APIs, and PostgreSQL.
