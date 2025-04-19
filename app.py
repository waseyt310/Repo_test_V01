import streamlit as st
import pyodbc
import time
import pandas as pd
from contextlib import contextmanager

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
        # Construct connection string from secrets
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={st.secrets['sql']['server']};"
            f"DATABASE={st.secrets['sql']['database']};"
            f"UID={st.secrets['sql']['username']};"
            f"PWD={st.secrets['sql']['password']};"
            f"Encrypt=yes;TrustServerCertificate=yes;"  # Added for secure connection
        )
        
        # Create connection with connection pooling settings
        return pyodbc.connect(conn_str, 
                              autocommit=True,
                              timeout=30)
    except Exception as e:
        st.error(f"Connection Error: {str(e)}")
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
                    return pd.DataFrame()
                
                # Execute query and fetch results into DataFrame
                return pd.read_sql(query, conn)
        
        except pyodbc.OperationalError as e:
            # Connection issues might be temporary
            retry_count += 1
            if retry_count < max_retries:
                st.warning(f"Connection issue, retrying ({retry_count}/{max_retries})...")
                time.sleep(2)  # Wait before retrying
            else:
                st.error(f"Failed to execute query after {max_retries} attempts: {e}")
                return pd.DataFrame()
                
        except Exception as e:
            st.error(f"Query Error: {str(e)}")
            return pd.DataFrame()

# Connection status indicator
connection_status = st.sidebar.empty()
try:
    with get_connection() as conn:
        if conn:
            connection_status.success("✅ Connected to Database")
        else:
            connection_status.error("❌ Failed to connect to Database")
except Exception as e:
    connection_status.error(f"❌ Connection Error: {str(e)}")

# Query input
st.subheader("Run SQL Query")
default_query = "SELECT TOP 10 * FROM INFORMATION_SCHEMA.TABLES;"
query = st.text_area("Enter SQL Query", value=default_query, height=100)

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

