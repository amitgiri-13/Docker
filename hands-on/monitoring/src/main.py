from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import docker
import psutil
import time
import os
from datetime import datetime

app = FastAPI(title="Docker Monitor")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_docker_client():
    try:
        client = docker.from_env()
        client.ping()
        return client
    except Exception:
        return None


def bytes_to_human(n):
    symbols = ('K', 'M', 'G', 'T', 'P', 'E', 'Z', 'Y')
    prefix = {}
    for i, s in enumerate(symbols):
        prefix[s] = 1 << (i + 1) * 10
    for s in reversed(symbols):
        if abs(n) >= prefix[s]:
            value = float(n) / prefix[s]
            return f"{value:.1f} {s}B"
    return f"{n} B"


@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/api/stats")
async def get_stats():
    client = get_docker_client()
    docker_connected = client is not None

    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.1)
    cpu_count = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)

    # Memory
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # Disk
    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
            io = psutil.disk_io_counters(perdisk=True)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total": bytes_to_human(usage.total),
                "used": bytes_to_human(usage.used),
                "free": bytes_to_human(usage.free),
                "percent": usage.percent
            })
        except Exception:
            continue

    # Network
    net_io = psutil.net_io_counters(pernic=True)
    networks = []
    for nic, stats in net_io.items():
        net_addrs = psutil.net_if_addrs().get(nic, [])
        addrs = [a.address for a in net_addrs if a.family.name in ('AF_INET', 'AF_INET6')]
        networks.append({
            "name": nic,
            "bytes_sent": bytes_to_human(stats.bytes_sent),
            "bytes_recv": bytes_to_human(stats.bytes_recv),
            "packets_sent": stats.packets_sent,
            "packets_recv": stats.packets_recv,
            "errin": stats.errin,
            "errout": stats.errout,
            "dropin": stats.dropin,
            "dropout": stats.dropout,
            "addresses": addrs[:2]
        })

    # Docker containers
    containers = []
    docker_info = {}
    docker_images = []
    docker_volumes = []

    if client:
        try:
            info = client.info()
            docker_info = {
                "version": client.version().get("Version", "unknown"),
                "containers_total": info.get("Containers", 0),
                "containers_running": info.get("ContainersRunning", 0),
                "containers_paused": info.get("ContainersPaused", 0),
                "containers_stopped": info.get("ContainersStopped", 0),
                "images": info.get("Images", 0),
                "os": info.get("OperatingSystem", "unknown"),
                "kernel": info.get("KernelVersion", "unknown"),
                "arch": info.get("Architecture", "unknown"),
                "cpus": info.get("NCPU", 0),
                "memory": bytes_to_human(info.get("MemTotal", 0)),
                "driver": info.get("Driver", "unknown"),
                "server_version": info.get("ServerVersion", "unknown"),
            }

            for c in client.containers.list(all=True):
                attrs = c.attrs
                state = attrs.get("State", {})
                created = attrs.get("Created", "")[:19].replace("T", " ")
                
                # Get container stats if running
                cpu_pct = 0.0
                mem_usage = "—"
                mem_pct = 0.0
                net_rx = "—"
                net_tx = "—"
                
                if c.status == "running":
                    try:
                        s = c.stats(stream=False)
                        # CPU
                        cpu_delta = s["cpu_stats"]["cpu_usage"]["total_usage"] - s["precpu_stats"]["cpu_usage"]["total_usage"]
                        sys_delta = s["cpu_stats"].get("system_cpu_usage", 0) - s["precpu_stats"].get("system_cpu_usage", 0)
                        ncpus = s["cpu_stats"].get("online_cpus", 1)
                        if sys_delta > 0:
                            cpu_pct = round((cpu_delta / sys_delta) * ncpus * 100.0, 2)
                        # Memory
                        mem_used = s["memory_stats"].get("usage", 0) - s["memory_stats"].get("stats", {}).get("cache", 0)
                        mem_limit = s["memory_stats"].get("limit", 1)
                        mem_usage = bytes_to_human(mem_used)
                        mem_pct = round((mem_used / mem_limit) * 100, 2) if mem_limit else 0
                        # Network
                        nets = s.get("networks", {})
                        if nets:
                            rx = sum(v.get("rx_bytes", 0) for v in nets.values())
                            tx = sum(v.get("tx_bytes", 0) for v in nets.values())
                            net_rx = bytes_to_human(rx)
                            net_tx = bytes_to_human(tx)
                    except Exception:
                        pass

                containers.append({
                    "id": c.short_id,
                    "name": c.name,
                    "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                    "status": c.status,
                    "created": created,
                    "ports": str(c.ports) if c.ports else "—",
                    "cpu_percent": cpu_pct,
                    "mem_usage": mem_usage,
                    "mem_percent": mem_pct,
                    "net_rx": net_rx,
                    "net_tx": net_tx,
                    "restart_count": attrs.get("RestartCount", 0),
                })

            for img in client.images.list():
                tags = img.tags if img.tags else ["<none>:<none>"]
                docker_images.append({
                    "id": img.short_id.replace("sha256:", ""),
                    "tags": tags,
                    "size": bytes_to_human(img.attrs.get("Size", 0)),
                    "created": img.attrs.get("Created", "")[:10],
                })

            # Docker Volumes
            for vol in client.volumes.list():
                attrs = vol.attrs
                vol_name = attrs.get("Name", "unknown")
                mountpoint = attrs.get("Mountpoint", "")
                driver = attrs.get("Driver", "unknown")
                labels = attrs.get("Labels") or {}
                options = attrs.get("Options") or {}
                created = attrs.get("CreatedAt", "")[:19].replace("T", " ")


                vol_total = "—"
                vol_used = "—"
                vol_free = "—"
                vol_percent = None

                # Check if mountpoint exists
                if mountpoint and os.path.exists(mountpoint):
                    try:
                        usage = psutil.disk_usage(mountpoint)
                        vol_total = bytes_to_human(usage.total)
                        vol_used = bytes_to_human(usage.used)
                        vol_free = bytes_to_human(usage.free)
                        vol_percent = round(usage.percent, 1)
                    except Exception:
                        pass

                # Find containers using this volume
                used_by = []
                for c in client.containers.list(all=True):
                    try:
                        mounts = c.attrs.get("Mounts", [])
                        for m in mounts:
                            if (vol_name and m.get("Name") == vol_name) or \
                            (mountpoint and os.path.abspath(m.get("Source", "")) == os.path.abspath(mountpoint)):
                                used_by.append(c.name)
                                break
                    except Exception:
                        continue

                docker_volumes.append({
                    "name": vol_name,
                    "driver": driver,
                    "mountpoint": mountpoint,
                    "created": created,
                    "labels": labels,
                    "options": options,
                    "total": vol_total,
                    "used": vol_used,
                    "free": vol_free,
                    "percent": vol_percent,
                    "used_by": used_by,
                })

        except Exception as e:
            docker_info["error"] = str(e)

    return JSONResponse({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "docker_connected": docker_connected,
        "docker_info": docker_info,
        "host": {
            "cpu_percent": cpu_percent,
            "cpu_count": cpu_count,
            "cpu_freq_mhz": round(cpu_freq.current, 0) if cpu_freq else 0,
            "cpu_per_core": cpu_per_core,
            "mem_total": bytes_to_human(mem.total),
            "mem_used": bytes_to_human(mem.used),
            "mem_available": bytes_to_human(mem.available),
            "mem_percent": mem.percent,
            "swap_total": bytes_to_human(swap.total),
            "swap_used": bytes_to_human(swap.used),
            "swap_percent": swap.percent,
            "uptime": str(datetime.now() - datetime.fromtimestamp(psutil.boot_time())).split(".")[0],
            "load_avg": [round(x, 2) for x in psutil.getloadavg()],
        },
        "disks": disks,
        "networks": networks,
        "containers": containers,
        "images": docker_images,
        "volumes": docker_volumes,
    })