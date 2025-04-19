# SQL Server Data Explorer

A Streamlit web application for connecting to SQL Server and executing queries.

## Features

- Secure credential management through Streamlit secrets
- Connection pooling for efficient database access
- Error handling and retry logic
- Query caching to improve performance
- Results downloadable as CSV

## Setup Instructions

1. Install required packages:
   ```
   pip install streamlit pyodbc pandas
   ```

2. Configure your database connection:
   - Edit the `.streamlit/secrets.toml` file with your SQL Server credentials.
   - Make sure to keep this file secure and never commit it to version control.

3. Install the ODBC Driver for SQL Server:
   - On Windows: Install "ODBC Driver 17 for SQL Server" from Microsoft
   - On Linux/Mac: Follow Microsoft's installation instructions for your OS

4. Run the application:
   ```
   streamlit run app.py
   ```

## Security Best Practices

- Never commit the secrets.toml file to version control
- Use environment variables in production settings
- Consider using Azure Key Vault or similar for production credentials
- Ensure your database user has minimal required permissions

## Requirements

- Python 3.7+
- Streamlit
- pyodbc
- pandas
- ODBC Driver 17 for SQL Server

