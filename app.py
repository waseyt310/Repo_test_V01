import streamlit as st
import pyodbc
import time
import pandas as pd
import socket
import platform
from contextlib import contextmanager

# Title and description
st.title("SQL Server Data Explorer")
st.markdown("""
This application connects to a SQL Server database and allows you to run queries.
Connection information is securely stored in .streamlit/secrets.toml.
""")

# Diagnostic information for troubleshooting
def get_diagnostic_info():
    """
    Collect diagnostic information about the environment to help troubleshoot connection issues.
    """
    info = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "pyodbc_version": pyodbc.version,
        "python_version": platform.python_version(),
    }
    return info

# Function to safely handle server name formatting
def format_server_address(server):
    """
    Safely handle server name formatting without making assumptions.
    Only formats the server name if explicitly requested in settings.
    """
    # IMPORTANT: By default, return the server name exactly as provided
    # This avoids incorrect assumptions about server type
    
    # If we detect specific Azure naming patterns that are incomplete, 
    # we might suggest formatting but we won't automatically apply it
    is_likely_azure = (
        # No dots, no special chars, not localhost
        "." not in server and
        not any(x in server.lower() for x in ["localhost", "127.0.0.1", "\\", ","]) and
        # Follows Azure naming pattern (alphanumeric, hyphens)
        all(c.isalnum() or c == '-' for c in server)
    )
    
    if is_likely_azure:
        st.sidebar.info(
            f"Server name '{server}' might be an Azure SQL server name. " +
            f"If connecting fails, try using '{server}.database.windows.net'"
        )
        
    # Always return the original name - let the user explicitly specify the full name
    return server

# Initialize connection pool
# Uses st.cache_resource to only run once and persist connection pool
@st.cache_resource
def init_connection_pool():
    """
    Initialize and return a connection to SQL Server using connection pooling.
    Credentials are stored securely in .streamlit/secrets.toml.
    
    Includes:
    - Server address format validation
    - Robust error handling
    - Connection timeout parameters
    - Diagnostic information
    """
    # Get diagnostic information for troubleshooting
    diagnostics = get_diagnostic_info()
    try:
        # Get server name - use EXACTLY as provided in secrets
        server = st.secrets['sql']['server']
        
        # Show connection attempt message
        st.sidebar.info(f"Attempting to connect to server: {server}")
        
        # Check if server might need formatting (but don't apply automatically)
        format_server_address(server)
        
        # Simplified connection string using exact server name from secrets
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server};"  # Use server name exactly as provided
            f"DATABASE={st.secrets['sql']['database']};"
            f"UID={st.secrets['sql']['username']};"
            f"PWD={st.secrets['sql']['password']};"
            f"Connection Timeout=30;"  # Standard timeout
            f"TrustServerCertificate=yes;"  # Trust certificate
        )
        
        # Log connection attempt details (without credentials)
        st.sidebar.info("Connecting with driver: ODBC Driver 17 for SQL Server")
        
        # Create connection with simplified parameters
        conn = pyodbc.connect(conn_str, autocommit=True)
        st.sidebar.success(f"Driver version: {conn.getinfo(pyodbc.SQL_DRIVER_VER)}")
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
            
**Current server address:** {server}
**Try checking:**
- Verify your server name is correct
- Ensure firewall rules allow connections from your current IP
- Check if you can ping the server
- Verify VPN connection if required
- Try alternative connection methods (see below)

**Alternative connection options to try:**
```python
# Try with encryption disabled
conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={st.secrets['sql']['database']};UID={st.secrets['sql']['username']};PWD=your_password;Encrypt=no;"

# If this is an Azure SQL server, try with the full domain name:
conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server}.database.windows.net;DATABASE={st.secrets['sql']['database']};UID={st.secrets['sql']['username']};PWD=your_password;"

# Try a basic connection string:
conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={st.secrets['sql']['database']};UID={st.secrets['sql']['username']};PWD=your_password;"
```
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
        
        # Display diagnostic information to help troubleshoot
        with st.expander("View diagnostic information"):
            st.json(diagnostics)
            
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
    max_retries = 5  # Increased from 3 to 5
    retry_count = 0
    backoff_factor = 1.5  # Exponential backoff factor
    
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
                    wait_time = backoff_factor ** retry_count  # Exponential backoff
                    st.warning(f"Query timeout, retrying in {wait_time:.1f} seconds ({retry_count}/{max_retries})...")
                    time.sleep(wait_time)  # Wait with exponential backoff
                else:
                    st.error(f"Query timed out after {max_retries} attempts. Try simplifying your query.")
                    return pd.DataFrame()
            else:
                # For other operational errors
                if retry_count < max_retries:
                    st.warning(f"Connection issue, retrying ({retry_count}/{max_retries})...")
                    time.sleep(1)  # Short delay
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

# Connection status indicator
connection_status = st.sidebar.empty()
diagnostics_expander = st.sidebar.expander("Connection Diagnostics")

with diagnostics_expander:
    st.write("### System Information")
    diagnostics = get_diagnostic_info()
    for key, value in diagnostics.items():
        st.write(f"**{key}:** {value}")
    
    # Add server connectivity test button
    if st.button("Test Server Connectivity"):
        server = st.secrets['sql']['server']
        
        try:
            # Remove domain for ping test if it's a fully qualified domain name
            ping_server = server.split('.')[0] if '.' in server else server
            st.info(f"Testing connectivity to {ping_server}...")
            
            # Simple hostname lookup test
            try:
                ip_address = socket.gethostbyname(ping_server)
                st.success(f"✅ DNS Resolution successful: {ping_server} → {ip_address}")
            except socket.gaierror:
                st.error(f"❌ Unable to resolve hostname: {ping_server}")
                
            # Try a basic socket connection on port 1433 (SQL Server default)
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect((ping_server, 1433))
                s.close()
                st.success(f"✅ TCP connection successful to {ping_server}:1433")
            except Exception as e:
                st.error(f"❌ TCP connection failed to {ping_server}:1433: {str(e)}")
                
        except Exception as e:
            st.error(f"❌ Connectivity test failed: {str(e)}")

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

