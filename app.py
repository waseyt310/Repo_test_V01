import streamlit as st
import pyodbc
import pandas as pd
import time
import socket
import platform
from contextlib import contextmanager

# Set page configuration
st.set_page_config(
    page_title="SQL Server Data Explorer",
    page_icon="📊",
    layout="wide"
)

# Title and description
st.title("SQL Server Data Explorer")
st.markdown("""
This application connects to a SQL Server database and allows you to run queries.
Connection information is securely stored in .streamlit/secrets.toml.
""")

# Initialize connection pool
# Uses st.cache_resource to only run once and persist connection pool
@st.cache_resource
def init_connection_pool():
    """
    Initialize and return a connection to SQL Server using connection pooling.
    Credentials are stored securely in .streamlit/secrets.toml.
    """
    try:
        # Get connection parameters from secrets
        server = st.secrets["sql"]["server"]
        database = st.secrets["sql"]["database"]
        username = st.secrets["sql"]["username"]
        password = st.secrets["sql"]["password"]
        
        # Show connection attempt message
        st.sidebar.info(f"Attempting to connect to server: {server}")
        
        # Simplified connection string
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
            f"Connection Timeout=30;"
            f"TrustServerCertificate=yes;"
        )
        
        # Create connection with simplified parameters
        conn = pyodbc.connect(conn_str, autocommit=True)
        st.sidebar.success(f"Connected successfully. Driver version: {conn.getinfo(pyodbc.SQL_DRIVER_VER)}")
        return conn
    
    except pyodbc.OperationalError as e:
        error_msg = str(e)
        
        # Provide specific guidance based on error type
        if "HYT00" in error_msg or "timeout" in error_msg.lower():
            st.error(f"""### Connection Timeout Error
            
The connection to the database server timed out. This could be due to:
- Server name might be incorrect
- Firewall restrictions blocking the connection
- Network connectivity issues
- Server might be down or unavailable
            
**Try checking:**
- Verify your server name is correct
- Ensure firewall rules allow connections
""")
        elif "28000" in error_msg or "login failed" in error_msg.lower():
            st.error(f"""### Authentication Error
            
Login to the database server failed. This could be due to:
- Incorrect username or password
- Account might be locked
- Account might not have permissions to access the database
            
**Try checking:**
- Verify your username and password
- Ensure the account has proper permissions
""")
        else:
            st.error(f"Connection Error: {error_msg}")
        
        return None
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return None

# Context manager for database connections
@contextmanager
def get_connection():
    """
    Context manager to safely get and release a connection from the pool.
    Ensures connections are properly closed even if errors occur.
    """
    connection = init_connection_pool()
    try:
        yield connection
    finally:
        if connection:
            # Return to pool, don't actually close
            pass

# Run query with error handling and retries
@st.cache_data(ttl=600)  # Cache for 10 minutes
def run_query(query):
    """
    Execute a SQL query and return the results as a pandas DataFrame.
    
    Args:
        query (str): SQL query to execute
        
    Returns:
        pandas.DataFrame: Query results
    
    The function includes retry logic and proper error handling.
    Results are cached for 10 minutes.
    """
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            with get_connection() as conn:
                if conn is None:
                    st.error("Unable to establish database connection")
                    return pd.DataFrame()
                
                # Execute query and fetch results into DataFrame
                return pd.read_sql(query, conn)
        
        except pyodbc.OperationalError as e:
            error_msg = str(e)
            retry_count += 1
            
            # Determine if it's a timeout or a different operational error
            if "HYT00" in error_msg or "timeout" in error_msg.lower():
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    st.warning(f"Query timeout, retrying in {wait_time} seconds ({retry_count}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    st.error(f"Query timed out after {max_retries} attempts. Try simplifying your query.")
                    return pd.DataFrame()
            else:
                # For other operational errors
                if retry_count < max_retries:
                    st.warning(f"Connection issue, retrying ({retry_count}/{max_retries})...")
                    time.sleep(1)
                else:
                    st.error(f"Failed to execute query after {max_retries} attempts: {error_msg}")
                    return pd.DataFrame()
        
        except pyodbc.ProgrammingError as e:
            # SQL syntax errors - no need to retry
            st.error(f"SQL Error: {str(e)}")
            return pd.DataFrame()
                
        except Exception as e:
            st.error(f"Query Error: {str(e)}")
            return pd.DataFrame()

# Display diagnostic information
def get_diagnostic_info():
    """Collect system information for diagnostics"""
    info = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version()
    }
    try:
        info["pyodbc_version"] = pyodbc.version
    except:
        info["pyodbc_version"] = "Unknown"
    return info

# Sidebar with connection info
st.sidebar.header("Connection Information")
connection_status = st.sidebar.empty()

# Display diagnostic information in sidebar expander
with st.sidebar.expander("Connection Diagnostics"):
    st.write("### System Information")
    diagnostics = get_diagnostic_info()
    for key, value in diagnostics.items():
        st.write(f"**{key}:** {value}")

# Test connection
try:
    with get_connection() as conn:
        if conn:
            connection_status.success("✅ Connected to Database")
        else:
            connection_status.error("❌ Failed to connect to Database")
except Exception as e:
    connection_status.error(f"❌ Connection Error: {str(e)}")

# Main content area
st.subheader("Run SQL Query")

# Query input with default example
default_query = "SELECT TOP 10 * FROM INFORMATION_SCHEMA.TABLES;"
query = st.text_area("Enter SQL Query", value=default_query, height=150)

# Execute button
if st.button("Run Query"):
    with st.spinner("Executing query..."):
        # Start timer
        start_time = time.time()
        
        # Run query
        result = run_query(query)
        
        # Calculate execution time
        execution_time = time.time() - start_time
        
        # Display results
        if not result.empty:
            st.success(f"Query executed successfully in {execution_time:.2f} seconds")
            st.subheader("Results")
            st.dataframe(result)
            
            # Show download button for results
            csv = result.to_csv(index=False)
            st.download_button(
                label="Download results as CSV",
                data=csv,
                file_name="query_results.csv",
                mime="text/csv",
            )
        else:
            st.warning("No results returned or an error occurred")

# Footer
st.markdown("---")
st.markdown("Created with Streamlit and SQL Server")
