"""Prometheus metrics exporter"""

import psutil
import time
import threading
from prometheus_client import start_http_server, Gauge, Counter, Info

CPU_USAGE = Gauge("container_cpu_usage_percent", "CPU usage percentage")
MEMORY_USAGE = Gauge("container_memory_usage_bytes", "Memory usage in bytes")
NETWORK_RX = Counter("container_network_receive_bytes", "Network received bytes")
NETWORK_TX = Counter("container_network_transmit_bytes", "Network transmitted bytes")
CONTAINER_COUNT = Gauge("container_count", "Number of running containers")
APP_INFO = Info("app_info", "Application information")

class MetricsExporter:
    def __init__(self, port=9092):
        self.port = port
        self.running = True
        self._last_rx = 0
        self._last_tx = 0

    def _collect_metrics(self):
        while self.running:
            CPU_USAGE.set(psutil.cpu_percent(interval=1))
            mem = psutil.virtual_memory()
            MEMORY_USAGE.set(mem.used)

            net = psutil.net_io_counters()
            NETWORK_RX.inc(net.bytes_recv - self._last_rx)
            NETWORK_TX.inc(net.bytes_sent - self._last_tx)
            self._last_rx = net.bytes_recv
            self._last_tx = net.bytes_sent

            try:
                import docker
                client = docker.from_env()
                containers = client.containers.list()
                CONTAINER_COUNT.set(len(containers))
            except:
                pass

            APP_INFO.info({"name": "contain-cli", "version": "0.1.0"})
            time.sleep(15)

    def run(self):
        start_http_server(self.port)
        collector_thread = threading.Thread(target=self._collect_metrics, daemon=True)
        collector_thread.start()
        print(f"Metrics server started on port {self.port}")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.running = False
            print("\nMetrics server stopped")
