"""Core orchestration logic"""

import docker
import time
import requests
import threading
import logging
from typing import Dict, List, Any
import click

logging.basicConfig(
    filename='/var/log/contain.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('contain')

class Orchestrator:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = docker.from_env()
        self.containers: Dict[str, Any] = {}
        self.monitored_containers: Dict[str, Any] = {}
        self.service_name = config.get("name", "app")
        self.network_name = f"{self.service_name}_network"
        self.monitoring_thread = None
        self.running = False

    def _ensure_network(self):
        try:
            network = self.client.networks.get(self.network_name)
        except docker.errors.NotFound:
            network = self.client.networks.create(
                self.network_name,
                driver="bridge",
                check_duplicate=True
            )
            click.echo(f"  Created network: {self.network_name}")
        return network

    def _start_monitoring(self):
        def monitor():
            logger.info("Monitor thread started")
            while self.running:
                for name, container in list(self.monitored_containers.items()):
                    try:
                        container.reload()
                        if container.status != 'running':
                            logger.warning(f"Container {name} is {container.status}, restarting...")
                            click.echo(f" Restarting {name} (status: {container.status})")
                            container.start()
                            logger.info(f"Container {name} restarted successfully")
                            click.echo(f" {name} restarted")
                    except Exception as e:
                        logger.error(f"Monitor error for {name}: {e}")
                time.sleep(5)

        self.running = True
        self.monitoring_thread = threading.Thread(target=monitor, daemon=True)
        self.monitoring_thread.start()
        logger.info("Auto-restart monitoring ON")
        click.echo("  Auto-restart monitoring ON")

    def start_all(self):
        services = self.config.get("services", {})
        self._ensure_network()
        order = self._resolve_order(services)

        for service_name in order:
            self._start_service(service_name, services[service_name])

        logger.info(f"Monitored containers: {list(self.monitored_containers.keys())}")
        click.echo(f"  Monitored: {list(self.monitored_containers.keys())}")
        
        self._start_monitoring()

        click.echo("\nRunning health checks...")
        for service_name in services:
            self._health_check(service_name)

        click.echo("\nAll services started!")

    def _resolve_order(self, services: Dict) -> List[str]:
        visited = set()
        order = []

        def dfs(name):
            if name in visited:
                return
            visited.add(name)
            deps = services.get(name, {}).get("depends_on", [])
            for dep in deps:
                if dep in services:
                    dfs(dep)
            order.append(name)

        for name in services:
            dfs(name)

        return order

    def _start_service(self, name: str, spec: Dict):
        click.echo(f"  Starting {name}...")

        image = spec.get("image")
        build = spec.get("build")

        if build:
            click.echo(f"     Building {name} from {build}...")
            try:
                self.client.images.build(path=build, tag=f"{self.service_name}-{name}")
                image = f"{self.service_name}-{name}"
            except Exception as e:
                click.echo(f"     Build failed: {e}")
                return

        ports = {}
        for p in spec.get("ports", []):
            if ":" in p:
                host, container_port = p.split(":")
                ports[container_port] = host

        env = spec.get("environment", {})

        container_name = f"{self.service_name}-{name}"
        try:
            old_container = self.client.containers.get(container_name)
            old_container.remove(force=True)
        except docker.errors.NotFound:
            pass

        try:
            container = self.client.containers.run(
                image,
                detach=True,
                name=container_name,
                ports=ports,
                environment=env,
                network=self.network_name,
                remove=False
            )
            self.containers[name] = container
            logger.info(f"Started {name} with image {image}")

            restart_policy = spec.get("restart", "no")
            logger.info(f"Service {name} restart policy: {restart_policy}")
            if restart_policy == "always":
                self.monitored_containers[name] = container
                logger.info(f"Added {name} to monitored containers")
                click.echo(f"     {name} started (auto-restart ENABLED)")
            else:
                click.echo(f"     {name} started")

        except Exception as e:
            click.echo(f"     Failed: {e}")

    def _health_check(self, name: str):
        if name not in self.containers:
            click.echo(f"  {name}: container not found, skipping health check")
            return

        container = self.containers[name]
        spec = self.config.get("services", {}).get(name, {})
        hc = spec.get("healthcheck", {})

        if not hc:
            click.echo(f"  {name}: running (no healthcheck defined)")
            return

        timeout = hc.get("timeout", 30)
        interval = hc.get("interval", 5)
        max_attempts = timeout // interval

        click.echo(f"  {name}: checking health (timeout: {timeout}s)...")

        if "http" in hc:
            host_port = None
            for p in spec.get("ports", []):
                if ":" in p:
                    host, _ = p.split(":")
                    host_port = host
                    break
            
            if not host_port:
                click.echo(f" {name}: no port mapping found for HTTP check")
                return

            url = f"http://127.0.0.1:{host_port}{hc['http']}"
            
            for attempt in range(max_attempts):
                time.sleep(interval)
                try:
                    resp = requests.get(url, timeout=3)
                    if resp.status_code == 200:
                        click.echo(f" {name}: healthy (HTTP {resp.status_code})")
                        logger.info(f"Health check passed for {name}")
                        return
                    else:
                        click.echo(f"     Attempt {attempt+1}/{max_attempts}: HTTP {resp.status_code}")
                except Exception as e:
                    click.echo(f"     Attempt {attempt+1}/{max_attempts}: {type(e).__name__}")

        elif "command" in hc:
            for attempt in range(max_attempts):
                time.sleep(interval)
                try:
                    result = container.exec_run(hc["command"])
                    if result.exit_code == 0:
                        click.echo(f" {name}: healthy (command exit 0)")
                        logger.info(f"Health check passed for {name}")
                        return
                    else:
                        click.echo(f"     Attempt {attempt+1}/{max_attempts}: command exit {result.exit_code}")
                except Exception as e:
                    click.echo(f"     Attempt {attempt+1}/{max_attempts}: {e}")

        click.echo(f" {name}: healthcheck FAILED after {timeout}s")

    def stop_all(self):
        self.running = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2)

        for name, container in self.containers.items():
            try:
                container.stop()
                container.remove()
                click.echo(f"  Stopped and removed {name}")
            except Exception as e:
                click.echo(f"  Failed to stop {name}: {e}")

        self.containers.clear()
        self.monitored_containers.clear()

        try:
            network = self.client.networks.get(self.network_name)
            network.remove()
            click.echo(f"  Removed network: {self.network_name}")
        except:
            pass

    def status(self):
        click.echo(f"\nStatus for {self.service_name}:")
        click.echo("-" * 60)

        try:
            all_containers = self.client.containers.list(all=True, filters={"name": self.service_name})
            for container in all_containers:
                name = container.name.replace(f"{self.service_name}-", "")
                status = container.status
                icon = "✅" if status == "running" else "❌"

                restart_info = ""
                if name in self.monitored_containers:
                    restart_info = " [auto-restart: ON]"

                click.echo(f"{icon} {name}: {status}{restart_info}")
        except Exception as e:
            click.echo(f"Error: {e}")
