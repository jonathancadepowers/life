# Life Tracker

A personal data aggregation and visualization platform to track various aspects of daily life including exercise, weight, food consumption, and fasting.

## Features

- **Data Integration**: Connect with third-party APIs (Whoop, MyFitnessPal, etc.)
- **Personal Database**: Store all your health and fitness data in one place
- **Custom Reporting**: View and analyze your data with custom visualizations
- **Django Admin**: Built-in admin interface for data management

## Planned Integrations

- Exercise tracking (Whoop API)
- Weight tracking
- Food consumption tracking
- Fasting tracking

## Tech Stack

- **Backend**: Django 5.0
- **Database**: SQLite (development), PostgreSQL (production)
- **Frontend**: Django Templates + Bootstrap 5
- **API**: Django REST Framework
- **Task Queue**: Celery + Redis
- **Visualization**: Chart.js / Plotly

## Setup Instructions

### Prerequisites

- Python 3.11+
- pip

### Installation

1. Clone the repository:
```bash
cd /Users/jonathanpowers/repos
git clone https://github.com/jonathancadepowers/life.git
cd life
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Mac/Linux
# or
venv\Scripts\activate  # On Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Create a superuser:
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

7. Visit http://127.0.0.1:8000/ in your browser

## Development

### Project Structure

```
life/
├── lifetracker/        # Main Django project settings
├── manage.py           # Django management script
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

### Running Tests

```bash
python manage.py test
```

### Creating a New App

```bash
python manage.py startapp <app_name>
```

## Environment Variables

Create a `.env` file in the root directory with:

```
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3

# API Keys (to be added as integrations are built)
WHOOP_CLIENT_ID=
WHOOP_CLIENT_SECRET=
```

## Contributing

This is a personal project, but feel free to fork and adapt for your own use!

## License

MIT License
