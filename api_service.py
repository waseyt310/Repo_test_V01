import os
import json
import logging
import pyodbc
import pandas as pd
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from pydantic import BaseModel, Field, SecretStr
from jose import JWTError, jwt
from passlib.context import CryptContext

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("sql-api-proxy")

# Configuration
API_CONFIG = {
    "SECRET_KEY": os.getenv("API_SECRET_KEY", "your-secret-key-change-in-production"),
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": 30,
    "DATABASE_CONFIG": {
        "server": os.getenv("DB_SERVER", "zoidberg-ro"),
        "database": os.getenv("DB_DATABASE", "BusinessAnalytics"),
        "username": os.getenv("DB_USERNAME", "svc_powerautomate04"),
        "password": os.getenv("DB_PASSWORD", "Q7Tqon6nqoIiZ7c4Md"),
    }
}

# Hardcoded user for demo (in production, use a database)
DEMO_USER = {
    "username": os.getenv("API_USERNAME", "admin"),
    "hashed_password": os.getenv("API_HASHED_PASSWORD", 
                                "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW"),  # "password"
    "disabled": False,
}

# Security utilities
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str
    disabled: Optional[bool] = None

class UserInDB(User):
    hashed_password: str

class QueryRequest(BaseModel):
    query: str = Field(..., description="SQL query to execute")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Parameters for SQL query")
    
class QueryResult(BaseModel):
    columns: List[str]
    data: List[List[Any]]
    rows_affected: int
    execution_time: float
    timestamp: datetime

class ErrorResponse(BaseModel):
    detail: str
    error_type: str
    timestamp: datetime

# Database connection functions
def get_connection_string():
    """Get database connection string from config"""
    config = API_CONFIG["DATABASE_CONFIG"]
    return (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={config['server']};"
        f"DATABASE={config['database']};"
        f"UID={config['username']};"
        f"PWD={config['password']};"
        f"Connection Timeout=30;"
        f"TrustServerCertificate=yes;"
    )

def execute_query(query: str, params: Optional[Dict[str, Any]] = None) -> dict:
    """
    Execute a SQL query and return results with metadata
    """
    start_time = time.time()
    result = {
        "columns": [],
        "data": [],
        "rows_affected": 0,
        "execution_time": 0,
        "timestamp": datetime.now()
    }
    
    try:
        conn_str = get_connection_string()
        
        # Log query (removing sensitive data)
        sanitized_query = query.replace("\n", " ").strip()
        if len(sanitized_query) > 100:
            sanitized_query = sanitized_query[:100] + "..."
        logger.info(f"Executing query: {sanitized_query}")
        
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            
            # Execute query with or without parameters
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Get column names if we have a result set
            if cursor.description:
                result["columns"] = [column[0] for column in cursor.description]
                
                # Fetch data and convert to list of lists (rows)
                rows = cursor.fetchall()
                result["data"] = [
                    [
                        # Convert non-serializable types to strings
                        str(cell) if isinstance(cell, (datetime, bytes)) else cell
                        for cell in row
                    ]
                    for row in rows
                ]
                result["rows_affected"] = len(rows)
            else:
                # For non-SELECT queries (INSERT, UPDATE, DELETE)
                result["rows_affected"] = cursor.rowcount
                
    except Exception as e:
        # Log the error and re-raise as HTTPException
        logger.error(f"Database error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )
    finally:
        # Calculate execution time
        result["execution_time"] = time.time() - start_time
    
    return result

# Authentication functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(username: str):
    # In a real app, fetch from database
    if username == DEMO_USER["username"]:
        return UserInDB(**DEMO_USER)
    return None

def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, API_CONFIG["SECRET_KEY"], algorithm=API_CONFIG["ALGORITHM"])
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, API_CONFIG["SECRET_KEY"], algorithms=[API_CONFIG["ALGORITHM"]])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Initialize FastAPI
app = FastAPI(
    title="SQL Server API Proxy",
    description="Secure API proxy for SQL Server database access",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production to only allow your Streamlit app's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom exception handler for better error formatting"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "error_type": "HTTPException",
            "timestamp": datetime.now().isoformat(),
        },
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": f"Internal server error: {str(exc)}",
            "error_type": type(exc).__name__,
            "timestamp": datetime.now().isoformat(),
        },
    )

# API endpoints
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """Endpoint to obtain an access token"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=API_CONFIG["ACCESS_TOKEN_EXPIRE_MINUTES"])
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/health")
async def health_check():
    """Simple health check endpoint (no auth required)"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/api/query", response_model=QueryResult)
async def run_sql_query(
    query_req: QueryRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Execute a SQL query and return results"""
    try:
        result = execute_query(query_req.query, query_req.params)
        return result
    except HTTPException as e:
        # Re-raise HTTPExceptions
        raise e
    except Exception as e:
        # Log and convert other exceptions
        logger.error(f"Error executing query: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing query: {str(e)}",
        )

@app.get("/api/tables", response_model=QueryResult)
async def get_tables(current_user: User = Depends(get_current_active_user)):
    """Get list of tables in the database"""
    query = "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES ORDER BY TABLE_SCHEMA, TABLE_NAME"
    return execute_query(query)

@app.get("/api/database-info", response_model=QueryResult)
async def get_database_info(current_user: User = Depends(get_current_active_user)):
    """Get database metadata information"""
    query = """
    SELECT 
        @@SERVERNAME AS ServerName,
        DB_NAME() AS DatabaseName,
        @@VERSION AS SqlServerVersion,
        SERVERPROPERTY('ProductVersion') AS ProductVersion
    """
    return execute_query(query)

# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    # Run the API server
    uvicorn.run("api_service:app", host="0.0.0.0", port=8000, reload=True)

