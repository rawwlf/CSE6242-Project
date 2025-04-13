from flask import Flask, render_template, request
import pandas as pd
import folium
from folium.plugins import HeatMap
import json
import boto3
from botocore import UNSIGNED
from botocore.config import Config

app = Flask(__name__)

bucket_name = 'cse6242-project-team81'
state_year_data = pd.read_csv(f's3://{bucket_name}/state_year_data.csv')
location_counts = pd.read_csv(f's3://{bucket_name}/filtered_location_counts.csv')

s3 = boto3.client('s3', config=Config(signature_version=UNSIGNED))

response = s3.get_object(Bucket=bucket_name, Key='us-states.json')
json_data = response['Body'].read().decode('utf-8')

us_states = json.loads(json_data)

# Function to create the map
def create_map(year):
    filtered_data = state_year_data[state_year_data['Start_Year'] == year]

    # Prepare data for the heatmap
    filtered_heat_data = location_counts[location_counts['Start_Year'] == year]   
    heat_data = filtered_heat_data[['Start_Lat', 'Start_Lng','Count']].values.tolist()

    m = folium.Map(location=[37.8, -96], zoom_start=4.5, tiles="Cartodb Positron")

    folium.Choropleth(
        name='Choropleth',
        geo_data=us_states,
        data=filtered_data,
        columns=['code', 'Count'],
        key_on='feature.properties.STATE',
        fill_color='YlGn',
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name=f'Traffic Congestion Count in {year}',
        highlight=True,
        use_jenks=True
    ).add_to(m)

    HeatMap(
        name='Heat Map',
        data=heat_data, 
        radius=8, 
        blur=4,
        min_opacity=0.6, 
        show=False,
    ).add_to(m)

    # Add Layer Control
    folium.LayerControl().add_to(m)

    return m


# Flask routes
@app.route('/')
def index():
    year = int(request.args.get('year', 2022))  # Default to 2022 if no year is provided
    years = sorted(state_year_data['Start_Year'].unique())
    m = create_map(year)
    map_html = m._repr_html_()
    return render_template('index.html', map_html=map_html, years=years, selected_year=year)

# New route for the Traffic Flow Optimization page
@app.route('/route')
def route_map():
    return render_template('map.html')

if __name__ == '__main__':
    app.run(debug=True)