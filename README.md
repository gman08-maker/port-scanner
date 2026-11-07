# Concurrent TCP Port Scanner

A command-line TCP connect scanner written in pure Python (standard library only). It scans a range of ports on a host using a bounded thread pool, reports which ports are open along with their service names, and was benchmarked to measure how timeout and concurrency affect scan time and accuracy.

**Headline result:** scanning 100 ports on a firewalled host dropped from **97.7 s to 2.04 s (~48x faster)** by going from 1 to 50 workers, with no change to the connection logic and no loss of accuracy.

## Features

- Scans a single port (`--ports 80`) or an inclusive range (`--ports 1-1024`)
- Concurrent scanning with a configurable thread pool (`--workers`)
- Configurable per-connection timeout (`--timeout`)
- Resolves the hostname once up front, so a DNS failure is reported clearly instead of looking like "every port is closed"
- Maps open ports to service names via the system services database (`socket.getservbyport`)
- Reports total scan time
- No third-party dependencies (Python 3.9+)

## Usage

```bash
python scanner.py <host> [--ports PORTS] [--timeout SECONDS] [--workers N]
```

| Argument    | Default  | Description                                      |
|-------------|----------|--------------------------------------------------|
| `host`      | required | Hostname or IP address to scan                   |
| `--ports`   | `1-1024` | A single port (`80`) or inclusive range (`1-100`) |
| `--timeout` | `1.0`    | Seconds to wait for each connection attempt      |
| `--workers` | `50`     | Number of concurrent worker threads              |

### Example

```bash
python scanner.py <host> --ports 1-100 --timeout 1 --workers 50
```

```
PORT     SERVICE
22       ssh
80       http

Scanned (100) ports in 2.04s
```

## How it works

1. **`check_port`** attempts a full TCP handshake with `socket.create_connection`. If it succeeds the port is open. Any `OSError` (refused, timed out, unreachable) counts as not open.
2. **`scan_range`** submits one `check_port` task per port to a `ThreadPoolExecutor` and collects results in port order, so output is always sorted.
3. **`get_service_name`** looks up the well-known service name for each open port.

Threads are the right tool here because the work is I/O-bound: each thread spends nearly all its time blocked waiting on the network, and the GIL is released while a thread waits on a socket. More workers means more connection attempts waiting in parallel.

## Benchmarks

Both experiments scanned 100 ports on a remote host where most ports are filtered (the firewall silently drops packets). Ports 22 and 80 are open.

### Experiment 1: effect of timeout (1 worker)

| Timeout | Total time | Time per port | Open ports found |
|---------|-----------|---------------|------------------|
| 0.1 s   | 10.36 s   | 0.10 s        | 80 (**missed 22**) |
| 0.5 s   | 49.19 s   | 0.49 s        | 22, 80           |
| 1.0 s   | 97.77 s   | 0.98 s        | 22, 80           |
| 3.0 s   | 291.93 s  | 2.92 s        | 22, 80           |

**Findings**

- Scan time scales almost perfectly linearly with timeout, and the per-port time is nearly equal to the full timeout. That means almost every port is *filtered*: no reply of any kind comes back, so the scanner waits out the entire timeout on each one. (A *closed* port would answer immediately with a reset.)
- At 0.1 s the scan **missed port 22**, a false negative. A TCP connection needs at least one network round trip for the handshake, so a timeout shorter than the round-trip time to the target can't reliably detect open ports. Speed and accuracy trade off directly, and the right timeout depends on network latency.

### Experiment 2: effect of concurrency (1 s timeout)

| Workers | Total time | Predicted by model | Speedup vs. 1 worker | Open ports found |
|---------|-----------|--------------------|----------------------|------------------|
| 1       | 97.70 s   | 100 s              | 1x                   | 22, 80           |
| 10      | 10.06 s   | 10 s               | ~9.7x                | 22, 80           |
| 50      | 2.04 s    | 2 s                | ~48x                 | 22, 80           |

**Model:** `scan time ≈ ceil(ports / workers) × timeout`

The measured times match the model to within a few percent. Because the ceiling is applied to the batch count, adding workers beyond the number of ports gains nothing.

**Finding:** the program went from ~98 s to ~2 s without touching `check_port`. The scan was bound by time spent *waiting*, not computing, so overlapping the waits is what produces the speedup.

### What I got wrong

Before running Experiment 2 I predicted the 10-worker scan would take over two minutes and the 50-worker scan under a minute. The real numbers were 10 s and 2 s. My mental model was off by an order of magnitude because I hadn't yet recognised that the single-worker run was already dominated by timeouts. Writing down the `ceil(ports / workers) × timeout` model afterwards made the results predictable.

## Limitations

- **Open vs. closed vs. filtered:** the scanner currently treats every failure as "not open". It can't tell a closed port (fast reset) from a filtered one (silent drop).
- **IPv4/hostname only:** no CIDR ranges or multiple hosts per run.
- **Full-connect scan only:** it completes the TCP handshake, which is simple and needs no privileges, but it is noisier and easier to detect than a SYN scan.
- **No banner grabbing:** service names come from the port number, not from what is actually listening, so a service on a non-standard port is mislabelled.

## Roadmap

- [ ] Distinguish `open` / `closed` / `filtered` by catching `ConnectionRefusedError` separately from timeouts
- [ ] Validate arguments and port ranges (1-65535, start <= end)
- [ ] Banner grabbing to identify the real service
- [ ] JSON / CSV output
- [ ] Unit tests against a local listening socket
- [ ] Progress indicator for large scans

## Responsible use

Only scan hosts you own or have explicit permission to test. Unauthorised port scanning may violate acceptable-use policies or local law.

## Requirements

- Python 3.9 or newer
- No external packages# port-scanner
