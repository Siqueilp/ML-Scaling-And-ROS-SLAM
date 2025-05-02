import requests
import csv
import time

PROMETHEUS_URL = 'http://192.168.1.245:30000'

# Define the start and end time for your query
end_time = int(time.time())  # Current time in seconds
start_time = end_time - 1800  # One hour ago

# Queries for yolo-deployment
queries = {
    "memory_usage": 'sum(container_memory_usage_bytes{pod="yolo-deployment-5d94d5ccff-6vcpk", namespace="default"}) by (pod)',
    "cpu_usage_specific": 'sum(rate(container_cpu_usage_seconds_total{pod="yolo-deployment-5d94d5ccff-6vcpk", namespace="default"}[5m])) by (pod)',
}

# Open a CSV file for writing
with open('jetson1_yolo_city_cuda.csv', 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    # Write header
    csv_writer.writerow(['Metric Type', 'Pod', 'Timestamp', 'Value'])

    for metric_type, query in queries.items():
        # Perform the query to Prometheus API
        response = requests.get(
            f'{PROMETHEUS_URL}/api/v1/query_range',
            params={'query': query, 'start': start_time, 'end': end_time, 'step': 15}
        )

        data = response.json()

        if data['status'] == 'success':
            # Iterate through results and write them to the CSV file
            for result in data['data']['result']:
                pod = result['metric'].get('pod', 'N/A')
                for value in result['values']:
                    timestamp, val = value  # Each value is a [timestamp, value] pair
                    csv_writer.writerow([metric_type, pod, timestamp, val])
        else:
            print(f"Error fetching {metric_type}: {data['error']}")
