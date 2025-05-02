# Cluster Setup

This document outlines the hardware and setup process used to configure a small-scale cluster using Raspberry Pi 4 and Nvidia Jetson Nano devices.

---

## 2.1 Used Devices

- **Raspberry Pi 4 Model B** x2  
- **Nvidia Jetson Nano** x2  
- **Storage**: 128 GB microSD cards for each device

---

## 2.2 Device Setup

### Raspberry Pi Setup

1. **Image Preparation**
   - Imaged two 128 GB microSD cards using [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
   - Selected **Raspberry Pi OS Lite (64-bit)** – headless version
   - Set:
     - Timezone: US Central
     - Enabled SSH
     - Keyboard layout: US
     - Hostnames: `pi1`, `pi2`

2. **Static IP and Cgroup Setup**
   - Inserted the SD card, booted up the Raspberry Pi
   - Ran `sudo raspi-config` to apply initial configuration
   - Edited `/boot/cmdline.txt` to include:
     ```
     cgroup_memory=1 cgroup_enable=memory ip=192.168.1.43::192.168.1.1:255.255.255.0:rpiname:eth0:off
     ```
     Replace values accordingly:
     ```
     ip=<client-ip>:<server-ip>:<gateway-ip>:<netmask>:<hostname>:<device>:<autoconf>
     ```
   - Edited `/boot/config.txt` and added:
     ```
     arm_64bit=1
     ```

3. **Passwordless SSH**
   - From the host machine:
     ```bash
     ssh-copy-id -i ~/.ssh/rpi_rsa.pub pi@<pi-ip-address>
     ```

---

### Jetson Nano Setup

1. **Image Preparation**
   - Downloaded Jetson Nano image from the [NVIDIA Developer Site](https://developer.nvidia.com/embedded/learn/get-started-jetson-nano-devkit#write)
   - Used **SD Card Formatter** and **Etcher** to write image to 128 GB microSD cards

2. **Static IP Configuration**
   - Inserted SD card, booted Jetson Nano
   - Edited `/etc/default/networking`:
     ```
     CONFIGURE_INTERFACES=no
     ```
   - Edited `/etc/network/interfaces`:
     ```bash
     # Comment out:
     # interfaces(5) file used by ifup(8) and ifdown(8)
     # Include files from /etc/network/interfaces.d:
     # source-directory /etc/network/interfaces.d

     # Add static IP configuration:
     auto eth0
     iface eth0 inet static
       address <your-ip>
       netmask <your-netmask>
       gateway <your-gateway>
     ```

3. **Passwordless SSH**
   - From the host machine:
     ```bash
     ssh-copy-id -i ~/.ssh/rpi_rsa.pub <nano-username>@<nano-ip-address>
     ```

---

## 2.3 K3S Cluster Setup

### Pre-Installation Steps (Run on All Devices)

Before installing K3S, run the following commands on **each** device:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install iptables -y
sudo iptables -F
sudo update-alternatives --set iptables /usr/sbin/iptables-legacy
sudo update-alternatives --set ip6tables /usr/sbin/ip6tables-legacy
sudo reboot
sudo apt install curl -y
```

---

### K3S Installation

#### Master Node Setup (Jetson Nano - `jetson1`)

Install K3S on the master node:

```bash
curl -sfL https://get.k3s.io | K3S_KUBECONFIG_MODE="644" sh -
```

Retrieve the node token needed for joining worker nodes:

```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

Copy the output token for use on the worker nodes.

---

#### Worker Node Setup (Remaining Devices)

Run the following command on each **worker node** (replace with your actual values):

```bash
curl -sfL https://get.k3s.io | \
K3S_TOKEN="PASTE_YOUR_TOKEN_HERE" \
K3S_URL="https://<master-ip>:6443" \
K3S_NODE_NAME="<node-name>" \
sh -
```

After setup, verify the cluster is operational from the master node:

```bash
kubectl get nodes
```

---

## Prometheus Setup

Prometheus is used to scrape and monitor metrics from the K3S cluster.

We followed the guide and configuration files from this GitHub repo:  
📎 [Team81-Optimizing-Robot-Collaboration](https://github.com/swarnabha13/Team81-Optimizing-Robot-Collaboration)

### Steps:

1. **Clone the Repo and Navigate to Configs**

   On the **master node**, download or clone the necessary files:

2. **Create the Monitoring Namespace**

   ```bash
   kubectl create ns monitoring
   ```

3. **Apply Configurations**

   ```bash
   kubectl apply -f clusterRole.yaml
   kubectl apply -f config-map.yaml
   kubectl apply -f prometheus-deployment.yaml
   kubectl apply -f prometheus-service.yaml
   ```

4. **Access Prometheus UI**

   Prometheus becomes accessible via:

   ```
   http://<master-ip>:30000
   ```

5. **Deploy Additional Metrics Exporters**

   For enhanced metrics:

   ```bash
   kubectl apply -f kube-state-metrics-configs
   kubectl apply -f kubernetes-node-exporter
   ```

---

Prometheus is now successfully collecting metrics from the Kubernetes cluster for monitoring node and pod performance.

## 3. Application Deployment and Performance Testing

### 3.1 Overview

With Prometheus ready to gather data, we began testing the CPU and memory capabilities of our nodes.

The following deployments were used to demonstrate different application profiles:

- **Apache HTTP Server** – simulates a light CPU/memory application capable of handling high traffic.
- **Node.js Tetris Game** – simulates an application with multiple phases and varying CPU usage.
- **YOLOv3 Application** – simulates consistent high memory use and spikes in CPU during requests.

The first two applications were pulled from [Docker Hub](https://hub.docker.com/u/mreecedobson), and the YOLOv3 application was rebuilt using the code from  
[Team81-Optimizing-Robot-Collaboration YOLO](https://github.com/swarnabha13/Team81-Optimizing-Robot-Collaboration/tree/main/Reece_Dobson/Project/docker/yolo/yolo_swarn).

---

### 3.2 Example YAML Deployment (Tetris)

We used YAML files to deploy each application using:

```bash
kubectl apply -f <deployment>.yaml
```

Example `tetris.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: tetris-svc
  namespace: scaling
  annotations:
    metallb.universe.tf/loadBalancerIPs: 192.168.1.245
  labels:
    app: tetris
spec:
  type: LoadBalancer
  ports:
    - port: 1010
      targetPort: 8000
  selector:
    app: tetris
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tetris
  namespace: scaling
  labels:
    app: tetris
spec:
  replicas: 1
  selector:
    matchLabels:
      app: tetris
  template:
    metadata:
      labels:
        app: tetris
      annotations:
        prometheus.io/scrape: 'true'
        prometheus.io/path: '/metrics'
        prometheus.io/port: '8000'
    spec:
      nodeSelector:
        kubernetes.io/hostname: <nodename>
      containers:
        - name: tetris
          image: mreecedobson/tetris-battle:v1-release
          resources:
            requests:
              memory: 32Mi
              cpu: 32m
            limits:
              memory: 64Mi
              cpu: 64m
          ports:
            - containerPort: 8000
```

By specifying `nodeSelector`, we deployed the same application on different nodes for comparison.

---

### 3.3 Data Collection Using Prometheus API

After deployment, metrics were collected using a Python script querying the Prometheus server:

```python
import requests
import csv
import time

PROMETHEUS_URL = 'http://192.168.1.245:30000'

end_time = int(time.time())
start_time = end_time - 1800  # last 30 minutes

queries = {
    "memory_usage": 'sum(container_memory_usage_bytes{pod="tetris-76f5fd9d9f-tmc58", namespace="scaling"}) by (pod)',
    "cpu_usage_specific": 'sum(rate(container_cpu_usage_seconds_total{pod="tetris-76f5fd9d9f-tmc58"}[5m])) by (pod)',
}

csv_filename = "jetson1_tetris.csv"

with open(csv_filename, 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow(['Metric Type', 'Pod', 'Node', 'Timestamp', 'Value'])

    for metric_type, query in queries.items():
        response = requests.get(f'{PROMETHEUS_URL}/api/v1/query_range', params={
            'query': query,
            'start': start_time,
            'end': end_time,
            'step': 15
        })
        data = response.json()

        if data['status'] == 'success':
            for result in data['data']['result']:
                pod = result['metric'].get('pod', 'N/A')
                node = result['metric'].get('node', 'N/A')
                for value in result['values']:
                    timestamp, val = value
                    csv_writer.writerow([metric_type, pod, node, timestamp, val])
        else:
            print(f"Error fetching {metric_type}: {data.get('error', 'unknown error')}")
```

This script queries Prometheus and saves CPU and memory usage data into a CSV file.

---

### 3.4 Special Considerations for YOLOv3 (GPU-Based)

To ensure YOLOv3 utilized the GPU on the Jetson Nanos:

1. **Install OpenCV with CUDA support**  
   Follow the [QEngineering OpenCV Guide](https://qengineering.eu/install-opencv-on-jetson-nano.html).

2. **Increase swap memory** before installation:

```bash
sudo apt-get install dphys-swapfile
sudo nano /sbin/dphys-swapfile  # set CONF_MAXSWAP=4096
sudo nano /etc/dphys-swapfile  # set CONF_MAXSWAP=4096
sudo reboot
```

3. **Install OpenCV**

```bash
wget https://github.com/Qengineering/Install-OpenCV-Jetson-Nano/raw/main/OpenCV-4-10-0.sh
sudo chmod 755 ./OpenCV-4-10-0.sh
./OpenCV-4-10-0.sh
rm OpenCV-4-10-0.sh
sudo /etc/init.d/dphys-swapfile stop
sudo apt-get remove --purge dphys-swapfile
```

4. **Modify `app.py` to use CUDA**  
   Add the following lines:

```python
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)
```

5. **Build Docker image with YOLOv3**

Download required files:

- `coco.names`
- `yolov3.cfg`
- `yolov3.weights`

Then follow the [YOLO Docker Deployment Guide](https://medium.com/analytics-vidhya/object-detection-using-yolo-v3-and-deploying-it-on-docker-and-minikube-c1192e81ae7a), build locally, and push to Docker Hub.  
We hosted ours at `ryanholmes1/yolo3_cuda`.

Now the YOLOv3 deployment can be run on Jetson Nano with GPU acceleration enabled.

## K3S Cluster Lab Setup and HPA

### Introduction

Building on last semester’s work, where a K3S cluster was set up on a home network, this semester began by transitioning the cluster into the lab environment. The main focus afterward was the development of a custom **Horizontal Pod Autoscaler (HPA)** that leverages an **LSTM-based machine learning model** to respond to real-time traffic and improve system efficiency.

The end goal is a scalable architecture capable of managing multiple networked robots while minimizing latency and avoiding computational bottlenecks. This work lays the foundation for future teams to better utilize available CPU, memory, and GPU resources through intelligent load balancing.

---

### Lab Network Setup

The transition to the lab network was relatively smooth due to the use of static IPs for all nodes. However, two key issues were encountered:

1. **Network Routing Conflict**  
   The lab computers were not on the same network as the router used for the cluster. As a result, SSH access from lab desktops failed.  
   **Solution**: Connect lab computers to the router’s Wi-Fi network to access the nodes.

2. **Prometheus Not Working Properly**  
   Prometheus failed to scrape metrics from some nodes and components such as `apiserver` and `cadvisor`.  
   **Solution**: On the master node, run the following command to fix iptables forwarding:
   ```bash
   sudo iptables -P FORWARD ACCEPT
   ```

This restored proper functionality to the Prometheus monitoring stack within the lab network.

## HPA Creation

After clarifying the concept of a Horizontal Pod Autoscaler (HPA), we determined the most effective implementation for our K3s cluster would be through a Python-based custom HPA. This HPA runs on the **master node**, gathers real-time metrics via **Prometheus**, feeds these into a trained **LSTM model**, and adjusts the number of pods based on the model's output.

---

### Metric Selection for Model Training

To train the LSTM model, we first needed to collect useful metrics. The following were chosen:

- **Short_HTTP**  
  `rate(nodejs_active_handles{type="Socket"}[1m])`  
  Recent network activity over a short window.

- **Long_HTTP**  
  `rate(nodejs_active_handles{type="Socket"}[15m])`  
  Longer-term view of network activity.

- **CPU Usage**  
  `rate(container_cpu_usage_seconds_total{pod=~"tetris.*"}[1m])`  
  Average CPU usage per second over the past minute.

- **Memory Usage**  
  `container_memory_usage_bytes{pod=~"tetris.*"}`  
  Current memory usage in bytes.

- **Number of Pods**  
  `kube_deployment_spec_replicas`  
  Number of replicas running for the Tetris deployment.

These metrics were queried from Prometheus using a script called `curl.py`, which formed the foundation for data collection.

---

### Data Collection Scripts

To collect quality data for training, we created three interdependent Python scripts:

- **`collect_metrics.py`**  
  Uses `curl.py` to continuously gather metrics and store them in a CSV file. Also calculates a custom **traffic load** metric based on `Short_HTTP` and `Long_HTTP`, and saves it to a JSON file.

- **`pod.py`**  
  Monitors the traffic load from the JSON file and scales the number of pods accordingly. During the first half of data collection, it scales up. During the second half, it scales down to help create training data that reflects traffic patterns.

- **`traffic.py`**  
  Simulates traffic by issuing POST and GET requests to the Tetris application, ramping up traffic during the first half and ramping it down during the second half.

This setup allowed us to collect approximately **8 hours of clean, useful data** that correlated traffic load with pod scaling behavior — ideal for training an LSTM model.

---

### LSTM Model Training

Using **TensorFlow Keras**, we trained an LSTM model with the collected metrics. This was done using a script called:

- **`train.py`**  
  Trains the LSTM using sequences of 10 historical metric samples as input, and the corresponding number of pods as the prediction target.

---

### Final HPA Implementation

Once trained, the LSTM model was integrated into the final HPA script:

- **`hpa.py`**  
  - Every **30 seconds**, real-time metrics are pulled from Prometheus.
  - The last 10 samples are passed to the LSTM model.
  - The predicted number of pods is compared to the current number.
  - The script then scales **up**, **down**, or maintains the current number of pods using `kubectl scale`.

This custom HPA can be modified easily for other applications by adjusting the metric queries and deployment names.

---

> ✅ The combination of Prometheus for monitoring, Python for control logic, and LSTM for predictive scaling creates a unique and flexible HPA solution beyond what Kubernetes provides natively.
