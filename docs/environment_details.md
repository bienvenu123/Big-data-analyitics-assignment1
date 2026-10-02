# Environment record (2 October 2026, CAT)

| Item | Recorded value |
|---|---|
| Host | HP ENVY x360 2-in-1 Laptop 13-bf0xxx, x64 |
| CPU | 12th Gen Intel Core i7-1250U; 10 cores, 12 logical processors |
| Host RAM | 16,077 MB installed; 3,093 MB available when sampled |
| OS | Microsoft Windows 11 Pro, version 10.0.26200, build 26200 |
| Storage | Docker named volume in Docker Desktop VM; Windows reports about 34.2 GB free on C:. Physical drive media type was not exposed by the available Windows storage queries and still needs to be recorded manually. |
| Python | 3.14.4 |
| PostgreSQL | 17.11, running in the `timescaledb` Docker container |
| TimescaleDB | 2.30.1 |
| MQTT broker | Eclipse Mosquitto 2.1.2 in the `mosquitto` Docker container. The assignment specifies EMQX; this pilot used the running Mosquitto service instead. |
| Docker engine | 12 CPUs and 8,167,571,456 bytes reported. The database container has no explicit CPU or memory limit (`NanoCpus=0`, `Memory=0`), so it can use the Docker VM's available resources. |
| PostgreSQL session time zone | `Africa/Kigali` (CAT, UTC+02:00); set as the assignment database default. |
| Windows clock | **Not synchronized at the time of capture.** `W32Time` was running but reported `Local CMOS Clock`, Stratum 0, and no successful sync; `w32tm /resync /force` returned Access denied in this session. Synchronize from an elevated Windows PowerShell and re-record the CAT timestamps before submission. |
| `shared_buffers` | 1,947 MB |
| `work_mem` | 5,192 kB |
| `max_parallel_workers_per_gather` | 6 |
| `jit` | off |

The machine identifier used in benchmark CSVs is returned by Python `platform.node()`. PostgreSQL ran inside a Docker Desktop Linux VM, without an explicit per-container CPU/RAM cap.
