# SQL Server Data Explorer
A Streamlit web application for connecting to SQL Server and executing queries.

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io/)

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
   - Copy the template file: `cp .streamlit/secrets.toml.example .streamlit/secrets.toml`
   - Edit the `.streamlit/secrets.toml` file with your SQL Server credentials.
   - Make sure to keep this file secure and never commit it to version control (it's already in .gitignore).

3. Install the ODBC Driver for SQL Server:
   - On Windows: Install "ODBC Driver 17 for SQL Server" from Microsoft
   - On Linux/Mac: Follow Microsoft's installation instructions for your OS

4. Run the application:
   ```
   streamlit run app.py
   ```

## Deployment to Streamlit Cloud

### Setting Up Secrets in Streamlit Cloud

When deploying to Streamlit Community Cloud, you need to set up your secrets differently:

1. Go to [Streamlit Community Cloud](https://share.streamlit.io/) and sign in with GitHub
2. Deploy your app by connecting to your GitHub repository
3. In the app's dropdown menu, select "Settings"
4. In the Secrets section, add your secrets in TOML format:

```toml
[sql]
server = "your-server-name.database.windows.net"
database = "YourDatabaseName"
username = "your_username"
password = "your_secure_password"
```

5. Save your changes and reboot the app

For more information on secrets management, refer to the [official Streamlit documentation](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## Security Best Practices

- Never commit the secrets.toml file to version control (use the provided .gitignore)
- Use environment variables in production settings
- Consider using Azure Key Vault or similar for production credentials
- Ensure your database user has minimal required permissions
- Consider using a read-only database user for queries if possible
- Implement proper input validation to prevent SQL injection

## Requirements

- Python 3.7+
- Streamlit
- pyodbc
- pandas
- ODBC Driver 17 for SQL Server

