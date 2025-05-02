import requests
import csv
import time

PROMETHEUS_URL = 'http://192.168.1.245:30000'  # Replace with your actual Prometheus server URL

# Define the start and end time for your query
end_time = int(time.time())  # Current time in seconds
start_time = end_time - 900  # One hour ago

queries = {
    "memory_usage": 'sum(container_memory_usage_bytes{pod="apache-9c945cfdd-zq4q4", namespace="scaling"}) by (pod)',
    "cpu_usage_specific": 'sum(rate(container_cpu_usage_seconds_total{pod="apache-9c945cfdd-zq4q4"}[5m])) by (pod)',
}

# Open a CSV file for writing
with open('prometheus_data_pi2.csv', 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    # Write header
    csv_writer.writerow(['Metric Type', 'Pod', 'Timestamp', 'Value'])

    for metric_type, query in queries.items():
        response = requests.get(f'{PROMETHEUS_URL}/api/v1/query_range', params={'query': query, 'start': start_time, 'end': end_time, 'step': 15})
        data = response.json()

        if data['status'] == 'success':
            for result in data['data']['result']:
                pod = result['metric'].get('pod', 'N/A')
                for value in result['values']:
                    timestamp, val = value  # Each value is a [timestamp, value] pair
                    csv_writer.writerow([metric_type, pod, timestamp, val])
        else:
            print(f"Error fetching {metric_type}: {data['error']}")
