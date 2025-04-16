import boto3
import os
from botocore import UNSIGNED
from botocore.config import Config

def download_from_s3():
    dir_data = 'static/data'
    dir_model = 'static/models'

    data_files = [
        'filtered_location_counts.csv',
        'state_year_data.csv',
        'us-states.json'
    ]

    model_files = [
        'edge_weights.pkl',
        'nyc_graph.pkl',
        'route_cache.pkl',
        'traffic_model.txt',
        'x_columns.json'
    ]

    if not os.path.exists(dir_data):
        os.makedirs(dir_data)
    if not os.path.exists(dir_model):
        os.makedirs(dir_model)

    bucket_name = 'cse6242-project-team81'
    s3 = boto3.client('s3',config=Config(signature_version=UNSIGNED))

    try:
        for key in data_files:
            local_path = os.path.join(dir_data, key)
            if os.path.exists(local_path):
                print(f"Skipping {key} - file already exists")
                continue
            print(f"Downloading {key}...")
            s3.download_file(bucket_name, key, local_path)
            print(f"{key} Saved to {dir_data}")

        for key in model_files:
            local_path = os.path.join(dir_model, key)
            if os.path.exists(local_path):
                print(f"Skipping {key} - file already exists")
                continue
            print(f"Downloading {key}...")
            s3.download_file(bucket_name, key, local_path)
            print(f"{key} Saved to {dir_model}")
        
    except Exception as e:
        print(f"Failed to download {key}: {e}")