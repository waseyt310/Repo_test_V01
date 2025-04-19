import streamlit as st
import requests
import time
import pandas as pd
import socket
import platform
from datetime import datetime
import json

# Title and description
st.title("SQL Server Data Explorer (API Mode)")
st.markdown("""
This application connects to a SQL Server database through a secure API proxy.
This allows accessing private databases from Streamlit Cloud.
""")

# Configuration for the API
API_CONFIG = {
    "API_URL": st.secrets.get("api", {}).get("url", "http://localhost:8000"),
    "API_USERNAME": st.secrets.get("api", {}).get("username", "admin"),
    "API_PASSWORD": st.secrets.get("api", {}).get("password", "password"),
}

# Session state for authentication
if "api_token" not in st.session_state:
    st.session_state.api_token = None
    st.session_state.token_expiry = None

# Diagnostic information for troubleshooting
def get_diagnostic_info():
    """
    Collect diagnostic information about the environment.
    """
    info = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "timestamp": datetime.now().isoformat(),
    }
    return info

# API Authentication
def authenticate_api():
    """Authenticate with the API service and get access token"""
    try:
        response = requests.post(
            f"{API_CONFIG['API_URL']}/token",
            data={
                "username": API_CONFIG["API_USERNAME"],
                "password": API_CONFIG["API_PASSWORD"],
            },
            timeout=10,
        )
        
        if response.status_code == 200:
            token_data = response.json()
            st.session_state.api_token = token_data["access_token"]
            # Token is valid for 30 minutes, but we'll refresh slightly earlier
            st.session_state.token_expiry = time.time() + 25 * 60
            return True
        else:
            st.error(f"Authentication failed: {response.text}")
            return False
    except requests.RequestException as e:
        st.error(f"API connection error: {str(e)}")
        return False

# Get or refresh API token
def get_api_token():
    """Get a valid API token, refreshing if necessary"""
    if st.session_state.api_token is None or st.session_state.token_expiry is None or time.time() > st.session_state.token_expiry:
        if not authenticate_api():
            return None
    return st.session_state.api_token

# Function to make authenticated API requests
def api_request(endpoint, method="get", data=None, params=None):
    """Make authenticated request to the API"""
    token = get_api_token()
    if token is None:
        st.error("Authentication failed. Unable to make API request.")
        return None
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        url = f"{API_CONFIG['API_URL']}{endpoint}"
        
        if method.lower() == "get":
            response = requests.get(url, headers=headers, params=params, timeout=30)
        elif method.lower() == "post":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        else:
            st.error(f"Unsupported HTTP method: {method}")
            return None
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            # Token might have expired, try re-authenticating once
            st.session_state.api_token = None
            token = get_api_token()
            if token is None:
                return None
                
            # Retry with new token
            headers = {"Authorization": f"Bearer {token}"}
            if method.lower() == "get":
                response = requests.get(url, headers=headers, params=params, timeout=30)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=30)
                
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"API request failed: {response.text}")
                return None
        else:
            st.error(f"API request failed: {response.text}")
            return None
    except requests.RequestException as e:
        st.error(f"API request error: {str(e)}")
        return None

# Run query using the API
@st.cache_data(ttl=600)  # Cache for 10 minutes
def run_query(query):
    """
    Execute a SQL query through the API and return the results as a pandas DataFrame.
    
    Args:
        query (str): SQL query to execute
        
    Returns:
        pandas.DataFrame: Query results
    """
    try:
        # Prepare the request payload
        data = {"query": query, "params": None}
        
        # Make API call
        result = api_request("/api/query", method="post", data=data)
        
        if result is None:
            return pd.DataFrame()
        
        # Convert API result to DataFrame
        if len(result.get("columns", [])) > 0 and len(result.get("data", [])) > 0:
            df = pd.DataFrame(result["data"], columns=result["columns"])
            return df
        else:
            # Empty result set but successful query
            if result.get("rows_affected", 0) > 0:
                st.info(f"Query successful. Affected {result['rows_affected']} rows, but no results to display.")
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error processing query: {str(e)}")
        return pd.DataFrame()

# Get database information using the API
def get_database_info():
    """Retrieve database information from API"""
    return api_request("/api/database-info")

# Get tables using the API
def get_tables():
    """Retrieve tables from the database"""
    return api_request("/api/tables")

# Connection status indicator
connection_status = st.sidebar.empty()
diagnostics_expander = st.sidebar.expander("Connection Diagnostics")

with diagnostics_expander:
    st.write("### System Information")
    diagnostics = get_diagnostic_info()
    for key, value in diagnostics.items():
        st.write(f"**{key}:** {value}")
    
    # Add API connectivity test button
    if st.button("Test API Connectivity"):
        try:
            health_response = requests.get(f"{API_CONFIG['API_URL']}/api/health", timeout=5)
            if health_response.status_code == 200:
                st.success("✅ API health check successful")
                st.json(health_response.json())
            else:
                st.error(f"❌ API health check failed: {health_response.status_code}")
        except Exception as e:
            st.error(f"❌ API connection failed: {str(e)}")
    
    # Add database info button
    if st.button("Database Information"):
        db_info = get_database_info()
        if db_info and "data" in db_info and len(db_info["data"]) > 0:
            st.success("✅ Database information retrieved successfully")
            info = {
                "Server": db_info["data"][0][0],
                "Database": db_info["data"][0][1],
                "SQL Version": db_info["data"][0][2][:50] + "..." if len(db_info["data"][0][2]) > 50 else db_info["data"][0][2],
                "Product Version": db_info["data"][0][3],
            }
            st.json(info)
        else:
            st.error("❌ Failed to retrieve database information")

# Initial authentication and connectivity check
try:
    # Try to authenticate with API
    token = get_api_token()
    if token:
        # Check database connectivity by getting tables
        tables_result = get_tables()
        if tables_result and "columns" in tables_result:
            connection_status.success("✅ Connected to API and Database")
        else:
            connection_status.warning("✅ Connected to API but database access failed")
    else:
        connection_status.error("❌ Failed to connect to API")
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

# Show tables section
with st.expander("Browse Tables"):
    if st.button("Refresh Tables"):
        tables_result = get_tables()
        if tables_result and "data" in tables_result:
            tables_df = pd.DataFrame(tables_result["data"], columns=tables_result["columns"])
            st.dataframe(tables_df)
            
            # Allow selecting and querying a table
            schemas = tables_df[tables_result["columns"][0]].unique().tolist()
            selected_schema = st.selectbox("Select Schema", schemas)
            
            filtered_tables = tables_df[tables_df[tables_result["columns"][0]] == selected_schema]
            if not filtered_tables.empty:
                selected_table = st.selectbox("Select Table", filtered_tables[tables_result["columns"][1]].tolist())
                
                if st.button(f"Query {selected_schema}.{selected_table}"):
                    sample_query = f"SELECT TOP 100 * FROM {selected_schema}.{selected_table}"
                    st.code(sample_query)
                    with st.spinner("Fetching data..."):
                        sample_data = run_query(sample_query)
                        if not sample_data.empty:
                            st.dataframe(sample_data)
                        else:
                            st.warning("No data returned or error occurred")
        else:
            st.error("Failed to retrieve tables")

# Footer
st.markdown("---")
st.markdown("Created with Streamlit and SQL Server API Proxy")

