# Currency Exchange Admin App

A simple web application for managing currency exchange rates to and from the UAE Dirham (AED).

## Features

- **Public Exchange Rates**: Open access to current exchange rates without authentication
- **Authentication**: Secure admin login with hard-coded credentials
- **Currency Management**: Full CRUD operations for currencies (admin only)
- **Exchange Rate Views**:
  - Public page: Shows both "From AED" and "To AED" rates
  - Admin "From AED": Shows how much other currencies are worth in AED
  - Admin "To AED": Shows how much AED other currencies are worth
- **Persistent Storage**: SQLite database for data persistence
- **Responsive UI**: Clean, Bootstrap-based interface

## Requirements

- Python 3.7+
- Flask and related dependencies (see requirements.txt)

## Installation

### Render Deployment (Recommended)

Deploy automatically to Render with GitHub integration:

1. **Push to GitHub**: Push your code to a GitHub repository
2. **Connect to Render**: Link your GitHub repo to Render
3. **Auto-Deploy**: Every push to main branch triggers deployment
4. **Custom Domain**: Add your domain in Render dashboard

For complete Render deployment guide, see [`DEPLOYMENT.md`](DEPLOYMENT.md).

### Docker Deployment

#### Development
```bash
# Start development environment with sample data
docker-compose -f docker-compose.dev.yml up --build

# Access at http://localhost:5001
# Default credentials: admin / admin123
```

#### Production
```bash
# Update production environment variables
cp .env.production .env
# Edit .env with your secure credentials

# Start production environment
docker-compose up --build -d

# Access at http://localhost:8000
```

For complete Docker deployment guide, see [`DOCKER_DEPLOYMENT.md`](DOCKER_DEPLOYMENT.md).

### Manual Setup

1. Clone or download the project files
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment:
   ```bash
   cp .env.development .env
   # Edit .env file with your settings
   ```

## Usage

### Docker (Recommended)

```bash
# Development with sample data
docker-compose -f docker-compose.dev.yml up

# Production (empty database)
docker-compose up -d
```

### Manual Execution

#### Development Mode (with sample data)
```bash
# Load environment variables
source .env.development

# Start application
python app.py
```

#### Production Mode (no sample data)
```bash
# Load environment variables
source .env.production

# Start application
python app.py
```

### Features

1. **Public Access**: View current exchange rates without login
   - The main page shows all current exchange rates
   - Both "From AED" and "To AED" conversions are displayed
   - Infinite scroll for currency cards
   - Alphabetic sorting of currencies
   - No authentication required

2. **Admin Access**: Click "Admin" in the navigation or go to `/admin`
   - Login with the default credentials:
     - Username: `admin`
     - Password: `admin123`
   - Use the dashboard to manage currencies:
     - Add new currencies with their exchange rates
     - Edit existing currency rates
     - Delete currencies
     - View detailed exchange rate management
     - Currencies sorted alphabetically

## Sample Data

Sample data is loaded only in development mode or when `LOAD_SAMPLE_DATA=true`:
- US Dollar (USD): 0.27 to 1 AED
- Euro (EUR): 0.25 to 1 AED
- British Pound (GBP): 0.22 to 1 AED
- Japanese Yen (JPY): 30.0 to 1 AED

In production mode, the database starts empty and you must add currencies through the admin interface.

## Database

The application uses SQLite database (`currency_exchange.db`) which will be created automatically on first run.

## Environment Variables

- `FLASK_ENV`: Set to `development` or `production`
- `DEBUG`: Enable debug mode (`true`/`false`)
- `PORT`: Port number (default: 5001 dev, 8000 prod)
- `SECRET_KEY`: Secret key for sessions (change in production)
- `LOAD_SAMPLE_DATA`: Set to `true` to load sample data
- `DATABASE_URL`: Database connection string
- `ADMIN_USERNAME`: Admin username (stored in database)
- `ADMIN_PASSWORD`: Admin password (hashed in database)

## Database Migrations

The application uses database migrations for admin user management:

- **Automatic**: Migrations run on application startup
- **Admin Users**: Created/updated from environment variables
- **Password Hashing**: Secure password storage using Werkzeug
- **Sample Data**: Loaded only when `LOAD_SAMPLE_DATA=true`

## Security Notes

**For Production Deployment:**
- Generate secure `SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
- Change `ADMIN_USERNAME` and `ADMIN_PASSWORD` in `.env.production`
- Set `FLASK_ENV=production` and `LOAD_SAMPLE_DATA=false`
- Use HTTPS with SSL certificate
- Configure firewall and security groups
- Admin passwords are automatically hashed in database
- See [`DOCKER_DEPLOYMENT.md`](DOCKER_DEPLOYMENT.md) for complete security checklist

## New Features

### Alphabetic Sorting
- All currencies are automatically sorted alphabetically by symbol
- Applies to both public and admin interfaces
- Sort indicator shown in admin tables

### Infinite Scroll
- Public page loads currency cards progressively
- Improves performance with large numbers of currencies
- Smooth scrolling experience with automatic loading

## File Structure

```
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/            # HTML templates
│   ├── base.html         # Base template
│   ├── login.html        # Login page
│   ├── dashboard.html    # Main dashboard
│   ├── from_aed.html     # From AED view
│   └── to_aed.html       # To AED view
└── currency_exchange.db  # SQLite database (created on first run)