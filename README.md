# Traffic Congestion Analysis Project

This project provides tools for analyzing traffic congestion patterns and planning routes.

## Setup Instructions

### Prerequisites
- Python 3.10 or higher
- Git

### Local Development Setup

1. Clone the repository
```bash
git clone https://github.com/rawwlf/CSE6242-Project.git
cd CSE6242-Project
```

2. Create and activate a virtual environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Run the application
```bash
python app.py
```

The application should now be running at `http://localhost:5000`

### Project Structure
```
CSE6242-Project/
├── static/
│   ├── data/          # Contains data files
│   └── models/        # Contains model files
├── templates/         # HTML templates
├── app.py            # Main Flask application
├── s3download.py     # Data download script
└── requirements.txt  # Project dependencies
```

### Troubleshooting

- Check that all files in `static/data` and `static/models` were downloaded correctly
- Ensure your Python environment matches the version requirements