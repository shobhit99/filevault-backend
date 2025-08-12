# PostgreSQL Setup for File Vault Backend

This guide will help you migrate from SQLite to PostgreSQL for the File Vault backend.

## Prerequisites

1. **Install PostgreSQL**
   - **macOS**: `brew install postgresql`
   - **Ubuntu/Debian**: `sudo apt-get install postgresql postgresql-contrib`
   - **Windows**: Download from https://www.postgresql.org/download/windows/

2. **Start PostgreSQL Service**
   - **macOS**: `brew services start postgresql`
   - **Ubuntu/Debian**: `sudo systemctl start postgresql`
   - **Windows**: PostgreSQL service should start automatically

## Database Setup

1. **Create Database and User**
   ```bash
   # Connect to PostgreSQL as superuser
   sudo -u postgres psql
   
   # Or on macOS:
   psql postgres
   
   # Create database
   CREATE DATABASE filevault;
   
   # Create user (optional - you can use the default postgres user)
   CREATE USER filevault_user WITH PASSWORD 'your_secure_password';
   
   # Grant privileges
   GRANT ALL PRIVILEGES ON DATABASE filevault TO filevault_user;
   
   # Exit PostgreSQL
   \q
   ```

2. **Configure Environment Variables**
   
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   
   Update the `.env` file with your PostgreSQL credentials:
   ```env
   DB_NAME=filevault
   DB_USER=postgres  # or filevault_user if you created a custom user
   DB_PASSWORD=your_password_here
   DB_HOST=localhost
   DB_PORT=5432
   ```

## Migration Process

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run Migrations**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

3. **Create Superuser**
   ```bash
   python manage.py createsuperuser
   ```

4. **Test the Connection**
   ```bash
   python manage.py dbshell
   ```

## Data Migration (if you have existing SQLite data)

If you need to migrate existing data from SQLite to PostgreSQL:

1. **Export data from SQLite**
   ```bash
   python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission > data.json
   ```

2. **Switch to PostgreSQL configuration** (already done)

3. **Run migrations on PostgreSQL**
   ```bash
   python manage.py migrate
   ```

4. **Import data to PostgreSQL**
   ```bash
   python manage.py loaddata data.json
   ```

## Troubleshooting

### Connection Issues
- Ensure PostgreSQL is running: `sudo systemctl status postgresql`
- Check if the database exists: `psql -l`
- Verify user permissions: `psql -U your_user -d filevault`

### Authentication Issues
- Check `pg_hba.conf` file for authentication methods
- Ensure the user has the correct password and permissions

### Performance Optimization
For production, consider adding these settings to your PostgreSQL configuration:
```sql
-- Increase shared_buffers (typically 25% of RAM)
shared_buffers = 256MB

-- Increase effective_cache_size (typically 75% of RAM)
effective_cache_size = 1GB

-- Optimize for your workload
random_page_cost = 1.1
```

## Benefits of PostgreSQL over SQLite

1. **Better Concurrency**: Multiple users can read/write simultaneously
2. **Advanced Features**: Full-text search, JSON support, custom functions
3. **Scalability**: Better performance with large datasets
4. **Data Integrity**: More robust constraint checking
5. **Production Ready**: Better suited for production deployments

## Next Steps

After successful migration:
1. Test all application functionality
2. Set up database backups
3. Configure connection pooling for production
4. Monitor database performance