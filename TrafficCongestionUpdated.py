# THIS WAS THE INITIAL FILE DONE ON Tuesday 25th, use the IPYNB FILE!
import pandas as pd
import osmnx as ox
import networkx as nx
import requests
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from datetime import datetime

file_path = 'nyc_data.csv'
df = pd.read_csv(file_path)

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
# Evaluation
y_pred = model.predict(X_test)
print(f"RMSE: {mean_squared_error(y_test, y_pred):.2f}")
print(f"R²: {r2_score(y_test, y_pred):.4f}")
print(f"MAE: {mean_absolute_error(y_test, y_pred):.2f} mins")

def fetch_current_weather_nyc():
    lat, lon = 40.7128, -74.0060  # New York City
    url = f'https://api.weather.gov/points/{lat},{lon}'
    forecast_url = requests.get(url).json()['properties']['forecastHourly']
    forecast_data = requests.get(forecast_url).json()
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

current_weather = fetch_current_weather_nyc()
print("NYC Current Weather:", current_weather)

G = ox.graph_from_place("New York City, NY, USA", network_type='drive')
def calculate_edge_weights(G, model, current_weather, X_columns):
    for u, v, key, data in G.edges(keys=True, data=True):
        now = datetime.now()
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

calculate_edge_weights(G, model, current_weather, X.columns)
