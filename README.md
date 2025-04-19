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

### Database Accessibility Requirements

**IMPORTANT:** When deploying to Streamlit Cloud, your SQL Server database must be publicly accessible:

- **Public Access Required**: Streamlit Cloud can only connect to databases that are accessible over the public internet
- **Private Networks Not Accessible**: Internal, localhost, or VPN-only databases cannot be accessed from Streamlit Cloud
- **Firewall Configuration**: You must allowlist Streamlit Cloud's IP addresses in your database firewall

#### Streamlit Cloud IP Addresses

Configure your database firewall to allow these Streamlit Cloud IP addresses:
```
35.192.32.0/20
34.67.232.0/22
34.67.64.0/22
34.82.0.0/20
34.98.64.0/20
34.106.136.0/21
```

#### Solutions for Private Databases

If your database is not publicly accessible, consider these alternatives:

1. **Cloud-Hosted Database**: Migrate to a cloud database service like Azure SQL Database or AWS RDS
2. **API Proxy**: Create an API that serves as a proxy between Streamlit Cloud and your database
3. **SSH Tunnel**: Set up a secure tunnel with a public endpoint (advanced)
4. **Streamlit Hosting**: Host the Streamlit app yourself on infrastructure with access to your database

For more details, see the [Streamlit Community discussion](https://discuss.streamlit.io/t/error-to-connect-sql-server/24892).

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
- When exposing a database to the internet, use firewall rules to limit access to specific IP addresses
- Enable encryption for database connections
- Consider using a VPN or SSH tunnel for secure remote access to private databases
- Regularly audit database access logs and review permissions

## Requirements

- Python 3.7+
- Streamlit
- pyodbc
- pandas
- ODBC Driver 17 for SQL Server

