from concurrent.futures import ThreadPoolExecutor
import socket
import time
import argparse


def check_port(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return True if a TCP connection to host:port succeeds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

def argparse_example():
    parser = argparse.ArgumentParser(description="Scan a range of ports on a given host.")
    parser.add_argument("host", help="The hostname or IP address to scan.")
    parser.add_argument("--ports", type=str, default="1-1024", help="Specific ports to scan (e.g., '80' or '1-1024').")
    parser.add_argument("--timeout", type=float, default=1.0, help="Timeout for each port scan in seconds.")
    parser.add_argument("--workers", type=int, default=50, help="Number of concurrent workers for scanning.") 
    args = parser.parse_args()
    return args.host, args.ports, args.timeout, args.workers

# turn parse ports into a lambda function that takes a string and returns a tuple of two integers
def parse_ports(ports: str) -> tuple[int, int]:
    """Parse a string of the form 'start-end' or 'port' and return a tuple of two integers."""
    if "-" in ports:
        start, end = map(int, ports.split("-"))
        return start, end
    else:
        port = int(ports)
        return port, port

# Check --workers and --timeouts 
def validate_args(workers: int, timeout: float):
    """Validate the command-line arguments for workers and timeout."""
    if workers < 1:
        raise ValueError("Workers must be at least 1.")
    if timeout <= 0:
        raise ValueError("Timeout must be a positive number.")

def scan_range(host: str, start: int, end: int, timeout: float = 1.0, workers: int = 50) -> list[int]:
    """Concurrently scan ports start..end (inclusive) with a bounded pool and return the open ones."""
    open_ports = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(check_port, host, port, timeout) for port in range(start, end + 1)]
        for port, future in zip(range(start, end + 1), futures):
            if future.result():
                open_ports.append(port)
    return open_ports

# takes a port number, calls socket.getservbyport with that port and "tcp", and returns the name
def get_service_name(port: int) -> str:
    """Return the service name for a given port number, or 'unknown' if not found."""
    try:
        return socket.getservbyport(port, "tcp")
    except OSError:
        return "unknown"



if __name__ == "__main__":
    host, ports, timeout, workers = argparse_example()
    # call parse_ports once on the string and unpack the result into two variables
    start, end = parse_ports(ports)

    # Resolve the hostname once up front so a DNS failure isn't
    # mistaken for "every port is closed"
    try:
        socket.gethostbyname(host)
    except socket.gaierror:
        print(f"Could not resolve host: {host}")
        raise SystemExit(1)

    t0 = time.time()
    open_ports = scan_range(host, start, end, timeout=timeout, workers=workers)
    elapsed = time.time() - t0
    if not open_ports:
        print(f"No open ports found in range {ports} on host {host}.")
    else:
        print(f"{'PORT':<8} {'SERVICE':<20}")
        for port in open_ports:
            service = get_service_name(port)
            print(f"{port:<8} {service:<20}")

    print(f"\nScanned ({(end - start + 1)}) ports in {elapsed:.2f}s")
    