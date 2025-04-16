#!/usr/bin/env python3
import os
import time
import hashlib
from datetime import datetime
import pickle
import pandas as pd
import json
import requests
import lightgbm as lgb
from flask import Flask, render_template, jsonify, request
import osmnx as ox
import networkx as nx
from sklearn.model_selection import train_test_split
from s3download import download_from_s3

# Flask app setup
app = Flask(__name__)

# Global variables
MODEL = None
GRAPH = None
X_COLUMNS = None
INITIALIZATION_COMPLETE = False
INITIALIZATION_ERROR = None

# Cache structures
NODE_CACHE = {}
ROUTE_CACHE = {}

# Stats tracking
PERF_STATS = {
    'edge_weight_calculation_time': [],
    'route_calculation_time': [],
    'cache_hits': 0,
    'cache_misses': 0
}

def normalize_address(address):
    """Normalize address format for consistent lookup"""
    if not address:
        return ""
    address = address.lower().strip()
    address = ' '.join(address.split())
    replacements = {
        'street': 'st',
        'avenue': 'ave',
        'boulevard': 'blvd',
        'drive': 'dr',
        'road': 'rd',
        'place': 'pl',
        'lane': 'ln',
        'court': 'ct',
        'new york': 'ny',
        'new york city': 'nyc'
    }
    for full, abbr in replacements.items():
        address = address.replace(f" {full} ", f" {abbr} ")
        address = address.replace(f" {full},", f" {abbr},")
    return address

def get_time_key(dt=None):
    """Create time key for caching"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime('%Y%m%d_%H%M')

def fetch_current_weather_nyc():
    """Get NYC weather data"""
    try:
        lat, lon = 40.7128, -74.0060
        url = f'https://api.weather.gov/points/{lat},{lon}'
        response = requests.get(url)
        response.raise_for_status()
        forecast_url = response.json()['properties']['forecastHourly']
        
        forecast_response = requests.get(forecast_url)
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
        next_hour = forecast_data['properties']['periods'][0]

        weather_features = {
            'Temperature(F)': next_hour['temperature'],
            'WindSpeed(mph)': int(next_hour['windSpeed'].split()[0]),
            'Weather_Conditions': next_hour['shortForecast'],
            'Humidity(%)': 50,
            'Visibility(mi)': 10,
            'Precipitation(in)': 0
        }
        return weather_features
    except Exception as e:
        print(f"Error fetching weather data: {e}")
        return None

def get_nyc_graph():
    """Get NYC road network graph"""
    try:
        graph_path = 'static/models/nyc_graph.pkl'
        if os.path.exists(graph_path):
            print("Loading NYC graph from cache...")
            t_start = time.time()
            with open(graph_path, 'rb') as f:
                G = pickle.load(f)
            print(f"Graph loaded from cache successfully in {time.time() - t_start:.2f}s.")
            return G
        
        print("Generating new NYC graph (this may take a while)...")
        G = ox.graph_from_place("New York City, NY, USA", network_type='drive')
        
        print("Saving NYC graph to cache...")
        os.makedirs('static/models', exist_ok=True)
        with open(graph_path, 'wb') as f:
            pickle.dump(G, f)
        print("Graph saved to cache.")
        
        return G
    except Exception as e:
        print(f"Error getting NYC graph: {e}")
        raise

def find_nearest_node(G, address):
    """Find nearest node to address"""
    normalized_address = normalize_address(address)
    cache_key = hashlib.md5(normalized_address.encode()).hexdigest()
    
    if cache_key in NODE_CACHE:
        print(f"Node cache hit for '{address}'")
        return NODE_CACHE[cache_key]
    
    print(f"Node cache miss for '{address}', geocoding...")
    
    try:
        address_with_nyc = address + ', New York City'
        coords = ox.geocoder.geocode(address_with_nyc)
        
        node_id = ox.distance.nearest_nodes(G, coords[1], coords[0])
        
        NODE_CACHE[cache_key] = node_id
        
        cache_path = 'static/models/node_cache.pkl'
        if len(NODE_CACHE) % 10 == 0:
            with open(cache_path, 'wb') as f:
                pickle.dump(NODE_CACHE, f)
        
        return node_id
    except Exception as e:
        print(f"Error finding nearest node for '{address}': {e}")
        raise

def calculate_edge_weights(G, model, current_weather, X_columns, force_recalculate=False, route_datetime=None):
    """Calculate edge weights for routing"""
    t_start = time.time()
    
    now = route_datetime if route_datetime else datetime.now()
    
    edge_weights_path = f'static/models/edge_weights.pkl'
    
    if os.path.exists(edge_weights_path) and not force_recalculate:
        try:
            print(f"Loading cached edge weights...")
            with open(edge_weights_path, 'rb') as f:
                edge_weights = pickle.load(f)
                
            weight_count = 0
            for u, v, key, weight in edge_weights:
                if u in G and v in G and key in G[u][v]:
                    G.edges[u, v, key]['weight'] = weight
                    weight_count += 1
            
            print(f"Applied {weight_count} cached edge weights to the graph in {time.time() - t_start:.2f}s.")
            PERF_STATS['cache_hits'] += 1
            return True
        except Exception as e:
            print(f"Error loading cached edge weights: {e}")
            print("Will recalculate edge weights...")
            PERF_STATS['cache_misses'] += 1
    else:
        PERF_STATS['cache_misses'] += 1
    
    print(f"Calculating edge weights (this may take some time)...")
    
    edge_weights = []
    for u, v, key, data in G.edges(keys=True, data=True):
        edge_features = {
            'Severity': 2,
            'Start_Lat': data.get('y', 40.7128),
            'Start_Lng': data.get('x', -74.0060),
            'Distance(mi)': data.get('length', 100)/1609.34,
            'Temperature(F)': current_weather['Temperature(F)'],
            'Humidity(%)': current_weather['Humidity(%)'],
            'Visibility(mi)': current_weather['Visibility(mi)'],
            'WindSpeed(mph)': current_weather['WindSpeed(mph)'],
            'Precipitation(in)': current_weather['Precipitation(in)'],
            'Start_Hour': now.hour,
            'Start_Minute': now.minute,
            'Start_Day': now.day,
            'Start_Month': now.month,
            'Start_DayOfWeek': now.weekday(),
            'Duration_min': 10,
            'DelayFromFreeFlowSpeed(mins)': 0
        }

        current_condition = current_weather['Weather_Conditions']
        for col in X_columns[X_columns.str.startswith('Weather_Conditions_')]:
            condition_name = col.split('_')[-1]
            edge_features[col] = int(condition_name in current_condition)

        features_df = pd.DataFrame([edge_features])[X_columns]

        predicted_delay = max(model.predict(features_df)[0], 0.1)
        G.edges[u, v, key]['weight'] = predicted_delay
        
        edge_weights.append((u, v, key, predicted_delay))
    
    total_time = time.time() - t_start
    PERF_STATS['edge_weight_calculation_time'].append(total_time)
    print(f"Edge weights calculated in {total_time:.2f}s.")
    
    try:
        os.makedirs('static/models', exist_ok=True)
        with open(edge_weights_path, 'wb') as f:
            pickle.dump(edge_weights, f)
        print(f"Cached {len(edge_weights)} edge weights for future use.")
        return True
    except Exception as e:
        print(f"Error caching edge weights: {e}")
        return False

def find_optimal_route(start_location, end_location, G, route_datetime=None):
    """Find optimal route between locations"""
    t_start = time.time()
    
    try:
        time_key = get_time_key(route_datetime) if route_datetime else 'default'
        
        start_norm = normalize_address(start_location)
        end_norm = normalize_address(end_location)
        
        cache_key = f"{start_norm}:{end_norm}:{time_key}"
        route_cache_path = 'static/models/route_cache.pkl'
        
        if os.path.exists(route_cache_path):
            try:
                with open(route_cache_path, 'rb') as f:
                    route_cache = pickle.load(f)
                    
                    if cache_key in route_cache:
                        print(f"Route cache hit for {start_location} to {end_location} at {time_key}")
                        PERF_STATS['cache_hits'] += 1
                        return route_cache[cache_key]
            except Exception as e:
                print(f"Error reading route cache: {e}")
        
        PERF_STATS['cache_misses'] += 1
        print(f"Route cache miss for {start_location} to {end_location}")
        
        print(f"Finding route from '{start_location}' to '{end_location}'")
        
        start_node = find_nearest_node(G, start_location)
        end_node = find_nearest_node(G, end_location)
        
        print(f"Start node: {start_node}, End node: {end_node}")
        
        try:
            route = nx.dijkstra_path(G, start_node, end_node, weight='weight')
        except nx.NetworkXNoPath:
            route = nx.astar_path(G, start_node, end_node, heuristic=None, weight='weight')
        
        edges = []
        total_distance = 0
        total_base_time = 0
        total_congestion_effect = 0
        
        for i in range(len(route) - 1):
            u, v = route[i], route[i + 1]
            
            edge_data = None
            
            for key in G[u][v]:
                if edge_data is None or G[u][v][key]['weight'] < edge_data['weight']:
                    edge_data = G[u][v][key]
            
            if edge_data:
                distance_mi = edge_data.get('length', 0) / 1609.34
                
                base_time = distance_mi * (60 / 25)
                
                congestion_factor = edge_data['weight']
                
                congestion_multiplier = 1.0 + (congestion_factor * 0.5)
                actual_time = base_time * congestion_multiplier
                
                congestion_impact = actual_time - base_time
                
                total_distance += distance_mi
                total_base_time += base_time
                total_congestion_effect += congestion_impact
                
                congestion_level = min(1.0, congestion_factor / 3.0)
                
                edges.append({
                    'start': (G.nodes[u]['y'], G.nodes[u]['x']),
                    'end': (G.nodes[v]['y'], G.nodes[v]['x']),
                    'distance': distance_mi,
                    'base_time': base_time,
                    'actual_time': actual_time,
                    'congestion_impact': congestion_impact,
                    'congestion_level': congestion_level
                })
        
        route_coords = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in route]
        
        total_estimated_time = total_base_time + total_congestion_effect
        
        result = {
            'route_nodes': route,
            'route_coords': route_coords,
            'edges': edges,
            'estimated_travel_time': round(total_estimated_time, 1),
            'base_travel_time': round(total_base_time, 1),
            'congestion_delay': round(total_congestion_effect, 1),
            'distance_miles': round(total_distance, 1),
            'route_length': len(route)
        }
        
        try:
            route_cache = {}
            if os.path.exists(route_cache_path):
                with open(route_cache_path, 'rb') as f:
                    route_cache = pickle.load(f)
            
            route_cache[cache_key] = result
            
            with open(route_cache_path, 'wb') as f:
                pickle.dump(route_cache, f)
            print(f"Route cached for future use with key: {cache_key}")
        except Exception as e:
            print(f"Error caching route result: {e}")
        
        total_time = time.time() - t_start
        PERF_STATS['route_calculation_time'].append(total_time)
        print(f"Route calculated in {total_time:.2f}s.")
        
        return result
    except Exception as e:
        print(f"Error finding route: {e}")
        import traceback
        traceback.print_exc()
        raise

def load_or_train_model():
    """Load or train traffic prediction model"""
    try:
        model_path = 'static/models/traffic_model.txt'
        X_columns_path = 'static/models/x_columns.json'
        
        if os.path.exists(model_path) and os.path.exists(X_columns_path):
            print("Loading existing traffic model from cache...")
            try:
                model = lgb.Booster(model_file=model_path)
                with open(X_columns_path, 'r') as f:
                    X_columns = pd.Index(json.load(f))
                print("Model loaded from cache successfully.")
                return model, X_columns
            except Exception as e:
                print(f"Error loading cached model (will retrain): {e}")
        else:
            print("No cached model found. Will train new model.")
        
        print("Training new traffic model (this may take several minutes)...")
        file_path = 'nyc_data.csv'
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Dataset file '{file_path}' not found. Please ensure it's in the project root directory.")
            
        df = pd.read_csv(file_path)
        print(f"Dataset loaded: {len(df)} records")
        
        df.fillna({
            'WindSpeed(mph)': 0,
            'Precipitation(in)': 0,
            'Visibility(mi)': df['Visibility(mi)'].median(),
            'Temperature(F)': df['Temperature(F)'].median(),
            'Humidity(%)': df['Humidity(%)'].median()
        }, inplace=True)
        
        common_conditions = df['Weather_Conditions'].value_counts().index[:10]
        df['Weather_Conditions'] = df['Weather_Conditions'].apply(
            lambda x: x if x in common_conditions else 'Other')
        df = pd.get_dummies(df, columns=['Weather_Conditions'], drop_first=True)
        df = df.loc[:, ~df.columns.duplicated()]
        
        X = df.drop(columns=['DelayFromTypicalTraffic(mins)'])
        y = df['DelayFromTypicalTraffic(mins)']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        train_set = lgb.Dataset(X_train, label=y_train)
        valid_set = lgb.Dataset(X_test, label=y_test)
        
        params = {
            'objective': 'regression',
            'metric': ['rmse', 'mae'],
            'learning_rate': 0.05,
            'num_leaves': 63,
            'min_data_in_leaf': 20,
            'feature_fraction': 0.8,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbosity': -1,
            'seed': 42,
            'max_depth': -1
        }
        
        model = lgb.train(
            params,
            train_set=train_set,
            valid_sets=[train_set, valid_set],
            valid_names=['train', 'valid'],
            num_boost_round=1000
        )
        
        print("Model training complete. Saving to cache...")
        
        os.makedirs('static/models', exist_ok=True)
        model.save_model(model_path)
        
        with open(X_columns_path, 'w') as f:
            json.dump(list(X.columns), f)
            
        print("Model and columns saved to cache.")
        
        return model, X.columns
    
    except Exception as e:
        print(f"Error loading/training model: {e}")
        raise

def initialize():
    """Initialize application components"""
    global MODEL, GRAPH, X_COLUMNS, INITIALIZATION_COMPLETE, INITIALIZATION_ERROR, NODE_CACHE
    
    if INITIALIZATION_COMPLETE or INITIALIZATION_ERROR:
        return
    
    print("Initializing application...")
    try:
        t_start = time.time()

        download_from_s3();
        
        MODEL, X_COLUMNS = load_or_train_model()
        print("Model loaded/trained.")
        
        GRAPH = get_nyc_graph()
        print("Graph loaded.")
        
        node_cache_path = 'static/models/node_cache.pkl'
        if os.path.exists(node_cache_path):
            with open(node_cache_path, 'rb') as f:
                NODE_CACHE = pickle.load(f)
            print(f"Loaded {len(NODE_CACHE)} cached node mappings.")
        
        edge_weights_path = 'static/models/edge_weights.pkl'
        edge_weights_cached = os.path.exists(edge_weights_path)
        
        if edge_weights_cached:
            try:
                with open(edge_weights_path, 'rb') as f:
                    edge_weights = pickle.load(f)
                
                weight_count = 0
                for u, v, key, weight in edge_weights:
                    if u in GRAPH and v in GRAPH and key in GRAPH[u][v]:
                        GRAPH.edges[u, v, key]['weight'] = weight
                        weight_count += 1
                
                print(f"Applied {weight_count} cached edge weights to the graph.")
            except Exception as e:
                edge_weights_cached = False
                print(f"Error loading cached edge weights: {e}")
        
        if not edge_weights_cached:
            weather = fetch_current_weather_nyc()
            if weather:
                calculate_edge_weights(GRAPH, MODEL, weather, X_COLUMNS)
                print("Edge weights calculated and cached.")
            else:
                print("Could not fetch initial weather. Edge weights not calculated.")
        
        route_cache_path = 'static/models/route_cache.pkl'
        if not os.path.exists(route_cache_path):
            with open(route_cache_path, 'wb') as f:
                pickle.dump({}, f)
            print("Created empty route cache.")
        
        INITIALIZATION_COMPLETE = True
        init_time = time.time() - t_start
        print(f"Initialization successful in {init_time:.2f}s.")
    except Exception as e:
        INITIALIZATION_ERROR = str(e)
        print(f"FATAL ERROR during initialization: {e}")
        import traceback
        traceback.print_exc()

@app.before_request
def check_initialization():
    """Check initialization status"""
    if request.path.startswith('/static/'):
        return None
        
    if not INITIALIZATION_COMPLETE and not INITIALIZATION_ERROR:
        return "Application is initializing, please wait...", 503
    return None

@app.route('/')
def index():
    """Main page"""
    if INITIALIZATION_ERROR:
        return f"Application initialization failed: {INITIALIZATION_ERROR}", 500
    if not INITIALIZATION_COMPLETE:
        return "Application is initializing, please wait...", 503
    return render_template('map.html')

@app.route('/data')
def get_data():
    """data viz page"""
    year = int(request.args.get('year', 2022))
    years = [2016,2017,2018,2019,2020,2021,2022]
    return render_template('data_viz.html',
                           years=years,
                           selected_year=year)

@app.route('/api/weather', methods=['GET'])
def get_weather():
    """Weather API endpoint"""
    if INITIALIZATION_ERROR:
        return jsonify({"success": False, "error": f"Initialization failed: {INITIALIZATION_ERROR}"})
    if not INITIALIZATION_COMPLETE:
        return jsonify({"success": False, "error": "Application initializing."})
         
    try:
        weather = fetch_current_weather_nyc()
        if weather:
            return jsonify({"success": True, "weather": weather})
        else:
            return jsonify({"success": False, "error": "Could not fetch weather data."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/route', methods=['POST'])
def calculate_route():
    """Route calculation API endpoint"""
    if INITIALIZATION_ERROR:
        return jsonify({"success": False, "error": f"Initialization failed: {INITIALIZATION_ERROR}"})
    if not INITIALIZATION_COMPLETE:
        return jsonify({"success": False, "error": "Application initializing."})
        
    t_start = time.time()
    try:
        data = request.json
        start = data.get('start')
        end = data.get('end')
        date = data.get('date')
        time_str = data.get('time')
        
        if not start or not end:
            return jsonify({"success": False, "error": "Start and End locations are required."})

        print(f"Calculating route from '{start}' to '{end}'")
        
        route_datetime = None
        if date and time_str:
            print(f"For date/time: {date} {time_str}")
            try:
                dt_parts = date.split('-')
                time_parts = time_str.split(':')
                
                year = int(dt_parts[0])
                month = int(dt_parts[1])
                day = int(dt_parts[2])
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                
                route_datetime = datetime(year, month, day, hour, minute)
                print(f"Using datetime: {route_datetime}")
                
                date_specific_cache = f'static/models/edge_weights.pkl'
                
                weather = fetch_current_weather_nyc()
                if weather:
                    import copy
                    request_graph = copy.deepcopy(GRAPH)
                    
                    force_recalc = not os.path.exists(date_specific_cache)
                    
                    if force_recalc:
                        print(f"No cached weights found, calculating...")
                    else:
                        print(f"Using cached weights")
                        
                    calculate_edge_weights(request_graph, MODEL, weather, X_COLUMNS, 
                                          force_recalculate=force_recalc, 
                                          route_datetime=route_datetime)
                    
                    print("Finding optimal route with time-specific weights...")
                    result = find_optimal_route(start, end, request_graph, route_datetime)
                    print("Route found.")
                    return jsonify({"success": True, "route": result})
                else:
                    print("Could not fetch weather. Using previously calculated weights.")
            except Exception as e:
                print(f"Error parsing date/time: {e}. Using current time.")
                route_datetime = datetime.now()
        
        print("Finding optimal route...")
        result = find_optimal_route(start, end, GRAPH)
        print("Route found.")
        print(f"Total route API request time: {time.time() - t_start:.2f}s")
        return jsonify({"success": True, "route": result})
        
    except ValueError as geo_err:
        print(f"Geocoding error: {geo_err}")
        return jsonify({"success": False, "error": f"Could not understand location. Ensure '{start}' and '{end}' are specific, valid locations in NYC."})
    except nx.NetworkXNoPath:
        print(f"No path found between specified nodes.")
        return jsonify({"success": False, "error": f"No path found between the specified locations in the road network. They might be unreachable or too far apart."})
    except Exception as e:
        print(f"Error calculating route: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"An unexpected server error occurred."})

@app.route('/api/cache-status', methods=['GET'])
def cache_status():
    """Cache status API endpoint"""
    model_path = 'static/models/traffic_model.txt'
    X_columns_path = 'static/models/x_columns.json'
    graph_path = 'static/models/nyc_graph.pkl'
    edge_weights_path = 'static/models/edge_weights.pkl'
    node_cache_path = 'static/models/node_cache.pkl'
    route_cache_path = 'static/models/route_cache.pkl'
    
    date_specific_caches = len([f for f in os.listdir('static/models') 
                               if f.startswith('edge_weights_') and f.endswith('.pkl')])
    
    route_cache_size = 0
    if os.path.exists(route_cache_path):
        try:
            with open(route_cache_path, 'rb') as f:
                route_cache = pickle.load(f)
                route_cache_size = len(route_cache)
        except:
            pass
    
    avg_edge_calc_time = 0
    if PERF_STATS['edge_weight_calculation_time']:
        avg_edge_calc_time = sum(PERF_STATS['edge_weight_calculation_time']) / len(PERF_STATS['edge_weight_calculation_time'])
    
    avg_route_calc_time = 0
    if PERF_STATS['route_calculation_time']:
        avg_route_calc_time = sum(PERF_STATS['route_calculation_time']) / len(PERF_STATS['route_calculation_time'])
    
    status = {
        "model_cached": os.path.exists(model_path),
        "model_size_mb": round(os.path.getsize(model_path) / (1024 * 1024), 2) if os.path.exists(model_path) else 0,
        "X_columns_cached": os.path.exists(X_columns_path),
        "graph_cached": os.path.exists(graph_path),
        "graph_size_mb": round(os.path.getsize(graph_path) / (1024 * 1024), 2) if os.path.exists(graph_path) else 0,
        "edge_weights_cached": os.path.exists(edge_weights_path),
        "edge_weights_size_mb": round(os.path.getsize(edge_weights_path) / (1024 * 1024), 2) if os.path.exists(edge_weights_path) else 0,
        "node_cache_size": len(NODE_CACHE) if os.path.exists(node_cache_path) else 0,
        "date_specific_caches": date_specific_caches,
        "route_cache_size": route_cache_size,
        "performance": {
            "cache_hits": PERF_STATS['cache_hits'],
            "cache_misses": PERF_STATS['cache_misses'],
            "hit_rate": round(PERF_STATS['cache_hits'] / (PERF_STATS['cache_hits'] + PERF_STATS['cache_misses'] + 0.0001) * 100, 1),
            "avg_edge_calculation_time": round(avg_edge_calc_time, 2),
            "avg_route_calculation_time": round(avg_route_calc_time, 2)
        }
    }
    
    return jsonify(status)

if __name__ == '__main__':
    os.makedirs('static/models', exist_ok=True)
    
    print("\n" + "="*50)
    print("NYC TRAFFIC PREDICTION APP - STARTUP")
    print("="*50)
    
    print("Initializing application components...")
    initialize()
    
    model_path = 'static/models/traffic_model.txt'
    graph_path = 'static/models/nyc_graph.pkl'
    edge_weights_path = 'static/models/edge_weights.pkl'
    node_cache_path = 'static/models/node_cache.pkl'
    route_cache_path = 'static/models/route_cache.pkl'
    
    print("\nCache Status:")
    print(f"- Model cached: {'Yes' if os.path.exists(model_path) else 'No'}")
    print(f"- Graph cached: {'Yes' if os.path.exists(graph_path) else 'No'}")
    print(f"- Edge weights cached: {'Yes' if os.path.exists(edge_weights_path) else 'No'}")
    print(f"- Node mappings cached: {len(NODE_CACHE) if os.path.exists(node_cache_path) else 0} addresses")
    print(f"- Route cache: {'Yes' if os.path.exists(route_cache_path) else 'No'}")
    print("="*50)
    
    import socket
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    print(f"\nServer accessible at:")
    print(f"- Local URL: http://127.0.0.1:5000")
    print(f"- Network URL: http://{ip_address}:5000")
    print(f"Open one of these URLs in your browser to access the application.")
    print("="*50)
    
    print("Starting Flask application via app.py...")
    app.run(debug=True, host='0.0.0.0', port=5000)
