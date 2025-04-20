# Traffic Congestion Analysis Project

This project provides tools for analyzing traffic patterns and planning optimized routes. It is a web-based application built using Flask for the backend and Leaflet.js for interactive map visualizations on the frontend. The project integrates various features, including route planning, real-time traffic visualization, heatmaps, and choropleth maps, to provide users with insights into traffic congestion and weather conditions.

The frontend is heavily focused on map-based interactivity, with features like dynamic layer switching, incident filtering, and route visualization. The map is initialized using Leaflet.js, with multiple layers such as heatmaps for congestion and choropleth layers for state-level data. The application also includes a control panel for user inputs like start and end locations, departure time, and incident type filtering. The backend fetches data from APIs and S3 buckets, processes it, and serves it to the frontend. 

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