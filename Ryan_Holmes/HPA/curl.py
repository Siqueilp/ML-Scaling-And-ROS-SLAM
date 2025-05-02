import requests
import json

class curl:

    def __init__(self, deployment):
        self.deployment = deployment
        self.short_http = 1
        self.long_http = 1
        self.waiting = 1
        self.cpu = 0
        self.memory = 0

    def _fetch(self, query):
        # Hit the Prometheus API with a given query
        url = f"http://192.168.1.245:30000/api/v1/query?query={query}"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # If the fetch fails, log the error and return empty results
            print(f"[ERROR] Fetch failed for query: {query} - {e}")
            return {"data": {"result": []}}

    def hpa_curl(self):
        # Reset all metrics back to default
        self.short_http = 1
        self.long_http = 1
        self.waiting = 1

        if self.deployment == "apache":
            # Fetch apache load metrics
            data = self._fetch("apache_load")
            for result in data['data']['result']:
                interval = result['metric'].get('interval', '')
                name = result['metric'].get('app', '')
                value = float(result['value'][1])
                # Split by interval into short and long HTTP metrics
                if interval == '15min' and name == self.deployment:
                    self.long_http += value
                elif interval == '1min' and name == self.deployment:
                    self.short_http += value
            # Default to 100 if no traffic was recorded
            if self.short_http == 1:
                self.short_http = 100
            if self.long_http == 1:
                self.long_http = 100

            # Fetch apache busy worker count
            data = self._fetch("apache_workers")
            for result in data['data']['result']:
                state = result['metric'].get('state', '')
                name = result['metric'].get('app', '')
                if state == "busy" and name == self.deployment:
                    self.waiting += int(float(result['value'][1]))

        elif self.deployment == "tetris":
            # Fetch short term socket activity (1m)
            data = self._fetch('rate(nodejs_active_handles{type="Socket"}[1m])')
            for result in data['data']['result']:
                self.short_http += 2 * float(result['value'][1])

            # Fetch long term socket activity (15m)
            data = self._fetch('rate(nodejs_active_handles{type="Socket"}[15m])')
            for result in data['data']['result']:
                self.long_http += 2 * float(result['value'][1])

            # Add active filesystem requests to waiting
            data = self._fetch('nodejs_active_requests{type="FSReqCallback"}')
            for result in data['data']['result']:
                self.waiting += int(float(result['value'][1]))

            # Subtract open socket handles from waiting (adjust load estimate)
            data = self._fetch('nodejs_active_handles{type="Socket"}')
            for result in data['data']['result']:
                self.waiting -= int(float(result['value'][1]))

        elif self.deployment == "nginx-pic":
            # Fetch short term nginx HTTP requests (1m rate)
            data = self._fetch('rate(nginx_http_requests_total[1m])')
            for result in data['data']['result']:
                self.short_http += float(result['value'][1])

            # Fetch long term nginx HTTP requests (15m rate)
            data = self._fetch('rate(nginx_http_requests_total[15m])')
            for result in data['data']['result']:
                self.long_http += float(result['value'][1])

            # Add nginx connections in waiting state
            data = self._fetch('nginx_connections_waiting')
            for result in data['data']['result']:
                self.waiting += int(float(result['value'][1]))

        elif self.deployment == "yolo-m":
            # Fetch short term flask HTTP request creation (1m rate)
            data = self._fetch('rate(flask_http_request_created[1m])')
            for result in data['data']['result']:
                self.short_http += float(result['value'][1])

            # Fetch long term flask HTTP request creation (15m rate)
            data = self._fetch('rate(flask_http_request_created[15m])')
            for result in data['data']['result']:
                self.long_http += float(result['value'][1])

            # Fetch flask request exceptions over 5m window, add to waiting
            data = self._fetch('delta(flask_http_request_exceptions_total[5m])')
            for result in data['data']['result']:
                self.waiting += int(float(result['value'][1]))

        # Always grab CPU and Memory usage no matter what deployment
        self.cpu, self.memory = self.resources()

        return self.short_http, self.long_http, self.waiting, self.cpu, self.memory

    def resources(self):
        # Build CPU and memory queries based on pod name pattern
        cpu_query = f'rate(container_cpu_usage_seconds_total{{pod=~"{self.deployment}.*"}}[1m])'
        mem_query = f'container_memory_usage_bytes{{pod=~"{self.deployment}.*"}}'

        cpu = 0
        mem = 0

        try:
            # Sum CPU usage across matching pods
            data = self._fetch(cpu_query)
            for result in data['data']['result']:
                cpu += float(result['value'][1])
        except Exception as e:
            print(f"[resources] CPU error: {e}")

        try:
            # Sum memory usage across matching pods
            data = self._fetch(mem_query)
            for result in data['data']['result']:
                mem += float(result['value'][1])
        except Exception as e:
            print(f"[resources] Memory error: {e}")

        return cpu, mem

    def replicas(self):
        # Fetch the expected replica count from the deployment spec
        data = self._fetch("kube_deployment_spec_replicas")
        pods = 0
        for result in data['data']['result']:
            name = result['metric'].get('deployment', '')
            if name == self.deployment:
                pods = int(float(result['value'][1]))
        return pods
