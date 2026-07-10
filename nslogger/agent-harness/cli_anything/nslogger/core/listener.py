"""TCP listener that receives live NSLogger connections."""
from __future__ import annotations
import os
import base64
import json
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
from importlib import resources
from typing import Callable, Optional
from .message import LogMessage
from .parser import _parse_message, ParseError

# NSLogger Bonjour service types
NSLOGGER_SERVICE_TYPE = "_nslogger._tcp.local."
NSLOGGER_SSL_SERVICE_TYPE = "_nslogger-ssl._tcp.local."


def _get_local_ip() -> str:
    """Return the primary local IPv4 address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _make_ssl_context() -> tuple[ssl.SSLContext, str]:
    """Generate a temporary self-signed cert and return (SSLContext, tmp_dir)."""
    tmp_dir = tempfile.mkdtemp(prefix="nslogger_cli_")
    cert = os.path.join(tmp_dir, "server.crt")
    key = os.path.join(tmp_dir, "server.key")
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key, "-out", cert,
            "-days", "1", "-nodes",
            "-subj", "/CN=nslogger-cli",
        ],
        check=True,
        capture_output=True,
    )
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    if hasattr(ssl, "TLSVersion"):
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
    try:
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
    except ssl.SSLError:
        pass
    ctx.load_cert_chain(cert, key)
    return ctx, tmp_dir


def _make_pkcs12_identity() -> tuple[str, str, str]:
    """Generate a temporary self-signed PKCS#12 identity for CFStream server SSL."""
    tmp_dir = tempfile.mkdtemp(prefix="nslogger_cli_")
    cert = os.path.join(tmp_dir, "server.crt")
    key = os.path.join(tmp_dir, "server.key")
    p12 = os.path.join(tmp_dir, "server.p12")
    password = "nslogger-cli"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key, "-out", cert,
            "-days", "1", "-nodes",
            "-subj", "/CN=nslogger-cli",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        [
            "openssl", "pkcs12", "-export",
            "-inkey", key,
            "-in", cert,
            "-out", p12,
            "-passout", f"pass:{password}",
        ],
        check=True,
        capture_output=True,
    )
    return p12, password, tmp_dir


def _swift_helper_env() -> dict[str, str]:
    env = os.environ.copy()
    cache_root = tempfile.gettempdir()
    env.setdefault("SWIFT_MODULE_CACHE_PATH", os.path.join(cache_root, "nslogger_cli_swift_module_cache"))
    env.setdefault("CLANG_MODULE_CACHE_PATH", os.path.join(cache_root, "nslogger_cli_clang_module_cache"))
    return env


def _compiled_swift_helper(helper_name: str, on_debug: Callable[[str], None]) -> str:
    helper = resources.files("cli_anything.nslogger").joinpath(f"helpers/{helper_name}.swift")
    helper_path = str(helper)
    cache_dir = os.path.join(tempfile.gettempdir(), "nslogger_cli_swift_helpers")
    os.makedirs(cache_dir, exist_ok=True)
    try:
        stamp = f"{int(os.path.getmtime(helper_path))}_{os.path.getsize(helper_path)}"
    except OSError:
        stamp = "unknown"
    executable = os.path.join(cache_dir, f"{helper_name}_{stamp}")
    if not os.path.exists(executable):
        on_debug(f"Compiling native helper {helper_name}")
        subprocess.run(
            ["swiftc", helper_path, "-o", executable],
            check=True,
            capture_output=True,
            env=_swift_helper_env(),
        )
    return executable


def _peek(conn: socket.socket, size: int = 16) -> bytes:
    try:
        return conn.recv(size, socket.MSG_PEEK)
    except socket.timeout:
        raise
    except (AttributeError, OSError):
        return b""


def _peek_hex(conn: socket.socket, size: int = 16) -> str:
    return _peek(conn, size).hex(" ")


def _looks_like_tls_client_hello(conn: socket.socket) -> bool:
    """Best-effort TLS ClientHello detection without consuming bytes."""
    header = _peek(conn, 5)
    if len(header) < 3:
        return False
    # TLS record header: 0x16, 0x03, version
    return header[0] == 0x16 and header[1] == 0x03


def _classify_connection(conn: socket.socket) -> tuple[str, bytes]:
    """Classify the first bytes without consuming them: tls, raw, or empty."""
    try:
        header = _peek(conn, 5)
    except socket.timeout:
        return "timeout", b""
    if not header:
        return "empty", header
    if len(header) >= 3 and header[0] == 0x16 and header[1] == 0x03:
        return "tls", header
    return "raw", header


def _dns_sd_txt_args(service_name: str, filter_clients: bool = False) -> list[str]:
    """Return TXT records matching NSLogger.app's named-service publishing."""
    return ["filterClients=1"] if service_name and filter_clients else []


def _bonjour_service_types(use_ssl: bool, allow_plaintext: bool = False) -> tuple[str, ...]:
    """Return the Bonjour service type advertised by NSLogger.app for this mode."""
    if use_ssl and allow_plaintext:
        return ("_nslogger._tcp", "_nslogger-ssl._tcp")
    return ("_nslogger-ssl._tcp",) if use_ssl else ("_nslogger._tcp",)


class _ZeroconfBonjourPublisher:
    """In-process Bonjour publisher so Ctrl-C cannot leave dns-sd children behind."""

    def __init__(self, service_name: str, service_types: tuple[str, ...], port: int, local_ip: str, filter_clients: bool):
        from zeroconf import ServiceInfo, Zeroconf

        self._zeroconf = Zeroconf()
        self._infos = []
        properties = {"filterClients": "1"} if service_name and filter_clients else {}
        addresses = [] if local_ip == "127.0.0.1" else [socket.inet_aton(local_ip)]
        hostname = socket.gethostname().split(".")[0]
        server = f"{hostname}.local."

        for service_type in service_types:
            type_domain = f"{service_type}.local."
            info = ServiceInfo(
                type_domain,
                f"{service_name}.{type_domain}",
                addresses=addresses,
                port=port,
                properties=properties,
                server=server,
            )
            self._zeroconf.register_service(info)
            self._infos.append(info)

    def close(self):
        for info in self._infos:
            try:
                self._zeroconf.unregister_service(info)
            except Exception:
                pass
        self._zeroconf.close()


class _DnsSdBonjourPublisher:
    """Fallback Bonjour publisher using macOS dns-sd."""

    def __init__(
        self,
        service_name: str,
        service_types: tuple[str, ...],
        port: int,
        filter_clients: bool,
        on_debug: Callable[[str], None],
    ):
        self._procs = []
        txt_args = _dns_sd_txt_args(service_name, filter_clients)
        for service_type in service_types:
            command = ["dns-sd", "-R", service_name, service_type, "local", str(port), *txt_args]
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            self._procs.append(proc)
            on_debug(f"Started dns-sd publisher pid={proc.pid} command={' '.join(command)}")
            threading.Thread(
                target=self._drain_output,
                args=(proc, service_type, on_debug),
                daemon=True,
            ).start()

    @staticmethod
    def _drain_output(proc: subprocess.Popen, service_type: str, on_debug: Callable[[str], None]):
        if proc.stdout is None:
            return
        try:
            for line in proc.stdout:
                line = line.strip()
                if line:
                    on_debug(f"dns-sd[{service_type}] {line}")
        finally:
            code = proc.poll()
            if code is not None:
                on_debug(f"dns-sd[{service_type}] exited with code {code}")

    def close(self):
        for proc in self._procs:
            try:
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


class _NativeBonjourPublisher:
    """macOS Bonjour publisher backed by Foundation.NetService, matching NSLogger.app more closely."""

    def __init__(
        self,
        service_name: str,
        service_types: tuple[str, ...],
        port: int,
        filter_clients: bool,
        on_debug: Callable[[str], None],
    ):
        helper = _compiled_swift_helper("native_bonjour_publisher", on_debug)
        command = [
            helper,
            "--name",
            service_name,
            "--port",
            str(port),
            "--types",
            ",".join(service_types),
        ]
        if filter_clients:
            command.extend(["--txt", "filterClients=1"])

        self._proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=_swift_helper_env(),
        )
        on_debug(f"Started native Bonjour publisher pid={self._proc.pid} command={' '.join(command)}")
        threading.Thread(
            target=self._drain_output,
            args=(self._proc, on_debug),
            daemon=True,
        ).start()

    @staticmethod
    def _drain_output(proc: subprocess.Popen, on_debug: Callable[[str], None]):
        if proc.stdout is None:
            return
        try:
            for line in proc.stdout:
                line = line.strip()
                if line:
                    on_debug(f"native-bonjour {line}")
        finally:
            code = proc.poll()
            if code is not None:
                on_debug(f"native-bonjour exited with code {code}")

    def close(self):
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2.0)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass


class _NativeBonjourListenerProcess:
    """macOS NetService listener using NSNetServiceListenForConnections."""

    def __init__(
        self,
        service_name: str,
        service_type: str,
        port: int,
        filter_clients: bool,
        secure: bool,
        p12_path: Optional[str],
        p12_password: Optional[str],
        on_debug: Callable[[str], None],
    ):
        helper = _compiled_swift_helper("native_bonjour_listener", on_debug)
        command = [
            helper,
            "--name",
            service_name,
            "--port",
            str(port),
            "--type",
            service_type,
        ]
        if filter_clients:
            command.extend(["--txt", "filterClients=1"])
        if secure:
            command.append("--secure")
            if p12_path:
                command.extend(["--p12", p12_path])
            if p12_password:
                command.extend(["--p12-pass", p12_password])

        self._proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=_swift_helper_env(),
            start_new_session=True,  # don't propagate terminal Ctrl-C SIGINT to this helper
        )
        on_debug(f"Started native Bonjour listener pid={self._proc.pid} command={' '.join(command)}")

    @property
    def stdout(self):
        return self._proc.stdout

    def poll(self):
        return self._proc.poll()

    def close(self):
        try:
            self._proc.terminate()
            self._proc.wait(timeout=2.0)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass


class NSLoggerListener:
    """Listen on a TCP port for NSLogger client connections."""

    def __init__(
        self,
        port: int = 50001,
        timeout: Optional[float] = None,
        on_message: Optional[Callable[[LogMessage], None]] = None,
        on_connect: Optional[Callable[[str, int], None]] = None,
        on_disconnect: Optional[Callable[[str, int], None]] = None,
        on_bonjour_ready: Optional[Callable[[str, int], None]] = None,
        on_parse_error: Optional[Callable[[str, int, bytes, Exception], None]] = None,
        on_debug: Optional[Callable[[str], None]] = None,
        use_ssl: Optional[bool] = None,
        allow_plaintext: Optional[bool] = None,
        bonjour: bool = False,
        bonjour_name: Optional[str] = None,
        filter_clients: Optional[bool] = None,
        bonjour_publisher: str = "native",
        advertise_host: Optional[str] = None,
    ):
        self.port = port
        self.timeout = timeout
        self.on_message = on_message or (lambda m: None)
        self.on_connect = on_connect or (lambda h, p: None)
        self.on_disconnect = on_disconnect or (lambda h, p: None)
        self.on_bonjour_ready = on_bonjour_ready or (lambda name, port: None)
        self.on_parse_error = on_parse_error or (lambda h, p, raw, e: None)
        self.on_debug = on_debug or (lambda message: None)
        # Bonjour mode mirrors NSLogger.app: publish the SSL service by default.
        self.use_ssl = bonjour if use_ssl is None else use_ssl
        self.allow_plaintext = False if allow_plaintext is None else allow_plaintext
        self.bonjour = bonjour
        self.bonjour_name = bonjour_name if bonjour_name is not None else ""
        self.filter_clients = bool(self.bonjour_name) if filter_clients is None else filter_clients
        self.bonjour_publisher = bonjour_publisher
        self.advertise_host = advertise_host
        self._stop = threading.Event()
        self._ssl_ctx: Optional[ssl.SSLContext] = None
        self.messages: list[LogMessage] = []

    def stop(self):
        self._stop.set()

    def _handle_client(self, conn: socket.socket, addr: tuple):
        host, port = addr[0], addr[1]
        saw_first_byte = False
        if self._ssl_ctx:
            try:
                conn.settimeout(10.0)
            except OSError:
                pass
            while not self._stop.is_set():
                mode, initial = _classify_connection(conn)
                if mode == "timeout":
                    self.on_debug(f"Waiting for first TLS/raw byte from {host}:{port}")
                    continue
                break
            else:
                conn.close()
                return
            initial_hex = initial.hex(" ")
            if mode == "empty":
                self.on_debug(f"Ignoring connection closed before NSLogger data from {host}:{port}")
                conn.close()
                return
            if mode == "raw" and self.allow_plaintext:
                self.on_debug(f"Raw NSLogger connection from {host}:{port} first_bytes={initial_hex}")
            elif mode == "tls":
                self.on_debug(f"Starting TLS handshake for {host}:{port} client_hello={initial_hex}")
                try:
                    conn = self._ssl_ctx.wrap_socket(conn, server_side=True)
                    self.on_debug(
                        f"TLS handshake completed for {host}:{port}"
                        f" protocol={conn.version()} cipher={conn.cipher()}"
                    )
                except (ssl.SSLError, OSError) as exc:
                    self.on_debug(f"TLS handshake failed for {host}:{port}: {exc!r}")
                    conn.close()
                    return
            else:
                self.on_debug(
                    f"Expected TLS ClientHello from {host}:{port}, got first_bytes={initial_hex}"
                )
                conn.close()
                return
        else:
            self.on_debug(f"Raw NSLogger connection from {host}:{port}")
        self.on_connect(host, port)
        try:
            conn.settimeout(2.0)
            while not self._stop.is_set():
                try:
                    header = b""
                    while len(header) < 4:
                        chunk = conn.recv(4 - len(header))
                        if not chunk:
                            if not saw_first_byte:
                                self.on_debug(f"No data before disconnect from {host}:{port}")
                            return
                        saw_first_byte = True
                        header += chunk
                    msg_len = struct.unpack(">I", header)[0]
                    self.on_debug(f"Frame header from {host}:{port}: len={msg_len} bytes")
                    if msg_len == 0:
                        continue
                    raw = b""
                    while len(raw) < msg_len:
                        chunk = conn.recv(msg_len - len(raw))
                        if not chunk:
                            return
                        raw += chunk
                    try:
                        msg = _parse_message(raw)
                        self.messages.append(msg)
                        self.on_message(msg)
                    except ParseError as exc:
                        self.on_parse_error(host, port, raw, exc)
                except socket.timeout:
                    if not saw_first_byte:
                        self.on_debug(f"Waiting for first frame from {host}:{port}")
                    continue
                except OSError as exc:
                    self.on_debug(f"Socket error from {host}:{port}: {exc}")
                    return
        finally:
            conn.close()
            self.on_disconnect(host, port)

    def _start_bonjour(self, local_ip: str) -> object:
        """Advertise NSLogger services via Bonjour/mDNS."""
        service_types = _bonjour_service_types(self.use_ssl, self.allow_plaintext)
        self.on_debug(
            "Bonjour service types: "
            f"{', '.join(service_types)} filter_clients={int(self.filter_clients)}"
        )
        if self.bonjour_publisher == "native" and sys.platform == "darwin":
            self.on_debug("Advertising Bonjour with macOS NetService")
            publisher = _NativeBonjourPublisher(
                self.bonjour_name,
                service_types,
                self.port,
                self.filter_clients,
                self.on_debug,
            )
            self.on_bonjour_ready(self.bonjour_name, self.port)
            return publisher

        if self.bonjour_publisher == "dns-sd" and sys.platform == "darwin":
            self.on_debug("Advertising Bonjour with macOS dns-sd")
            publisher = _DnsSdBonjourPublisher(
                self.bonjour_name,
                service_types,
                self.port,
                self.filter_clients,
                self.on_debug,
            )
            self.on_bonjour_ready(self.bonjour_name, self.port)
            return publisher

        try:
            self.on_debug(f"Advertising Bonjour with zeroconf address={local_ip}")
            publisher = _ZeroconfBonjourPublisher(
                self.bonjour_name,
                service_types,
                self.port,
                local_ip,
                self.filter_clients,
            )
        except ImportError:
            self.on_debug("zeroconf package unavailable; falling back to macOS dns-sd")
            publisher = _DnsSdBonjourPublisher(
                self.bonjour_name,
                service_types,
                self.port,
                self.filter_clients,
                self.on_debug,
            )
        self.on_bonjour_ready(self.bonjour_name, self.port)
        return publisher

    def _should_use_native_bonjour_listener(self) -> bool:
        if not (self.bonjour and self.bonjour_publisher == "native" and sys.platform == "darwin"):
            return False
        # NSNetServiceListenForConnections owns the listening socket, so it can only
        # publish one service type on the port. The explicit "auto" mode still uses
        # Python's socket listener plus a publisher so it can advertise raw+SSL.
        return len(_bonjour_service_types(self.use_ssl, self.allow_plaintext)) == 1

    def _listen_native_bonjour(self):
        """Use macOS NetService as both Bonjour publisher and listener."""
        import select
        import shutil
        import time

        p12_path = None
        tmp_dir = None
        if self.use_ssl:
            p12_path, p12_password, tmp_dir = _make_pkcs12_identity()
        else:
            p12_password = None

        service_type = _bonjour_service_types(self.use_ssl, self.allow_plaintext)[0]
        listener = _NativeBonjourListenerProcess(
            self.bonjour_name,
            service_type,
            self.port,
            self.filter_clients,
            self.use_ssl,
            p12_path,
            p12_password,
            self.on_debug,
        )

        deadline = None
        if self.timeout is not None:
            deadline = time.monotonic() + self.timeout

        def _drain(stdout, timeout_s: float = 1.0):
            """Read any frames already buffered in the pipe before closing."""
            drain_deadline = time.monotonic() + timeout_s
            while time.monotonic() < drain_deadline:
                try:
                    readable, _, _ = select.select([stdout], [], [], 0.1)
                except (OSError, ValueError):
                    break
                if not readable:
                    break
                line = stdout.readline()
                if not line:
                    break
                self._handle_native_bonjour_event(line)

        try:
            stdout = listener.stdout
            while not self._stop.is_set():
                if deadline and time.monotonic() > deadline:
                    break
                if stdout is None:
                    break
                readable, _, _ = select.select([stdout], [], [], 0.2)
                if not readable:
                    code = listener.poll()
                    if code is not None:
                        self.on_debug(f"native-bonjour listener exited with code {code} (no pending output)")
                        break
                    continue
                line = stdout.readline()
                if not line:
                    code = listener.poll()
                    if code is not None:
                        self.on_debug(f"native-bonjour listener exited with code {code}")
                        break
                    continue
                self._handle_native_bonjour_event(line)
        except KeyboardInterrupt:
            self._stop.set()
            if stdout is not None:
                _drain(stdout, timeout_s=1.0)
            raise
        finally:
            listener.close()
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        return self.messages

    def _handle_native_bonjour_event(self, line: str):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            self.on_debug(f"native-bonjour {line.strip()}")
            return

        event_type = event.get("event")
        if event_type == "ready":
            self.port = int(event.get("port") or self.port)
            self.on_bonjour_ready(event.get("name", self.bonjour_name), self.port)
        elif event_type == "debug":
            self.on_debug(f"native-bonjour {event.get('message', '')}")
        elif event_type == "connect":
            self.on_connect("native-bonjour", 0)
        elif event_type == "disconnect":
            self.on_disconnect("native-bonjour", 0)
        elif event_type == "error":
            details = " ".join(
                str(event.get(key, ""))
                for key in ("message", "error", "status")
                if event.get(key, "") != ""
            )
            self.on_debug(f"native-bonjour error: {details}")
        elif event_type == "frame":
            try:
                raw = base64.b64decode(event.get("payload", ""), validate=True)
                self.on_debug(
                    f"Frame #{len(self.messages) + 1}: {len(raw)} bytes"
                    f" head={raw[:8].hex(' ')}"
                )
                msg = _parse_message(raw)
                self.messages.append(msg)
                self.on_message(msg)
            except (ValueError, ParseError) as exc:
                raw_bytes = base64.b64decode(event.get("payload", "") or "", validate=False)
                self.on_parse_error("native-bonjour", 0, raw_bytes, exc)

    def listen(self):
        """Block until timeout or stop() is called. Returns collected messages."""
        if self._should_use_native_bonjour_listener():
            return self._listen_native_bonjour()

        tmp_dir = None
        if self.use_ssl:
            self._ssl_ctx, tmp_dir = _make_ssl_context()

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("0.0.0.0", self.port))
        server.listen(5)
        server.settimeout(1.0)

        publisher = None
        if self.bonjour:
            local_ip = self.advertise_host or _get_local_ip()
            publisher = self._start_bonjour(local_ip)

        deadline = None
        if self.timeout is not None:
            import time
            deadline = time.monotonic() + self.timeout

        threads = []
        try:
            import time
            while not self._stop.is_set():
                if deadline and time.monotonic() > deadline:
                    break
                try:
                    conn, addr = server.accept()
                    t = threading.Thread(
                        target=self._handle_client,
                        args=(conn, addr),
                        daemon=True,
                    )
                    t.start()
                    threads.append(t)
                except socket.timeout:
                    continue
        finally:
            server.close()
            self._stop.set()
            for t in threads:
                t.join(timeout=2.0)
            if publisher:
                publisher.close()
            if tmp_dir:
                import shutil
                shutil.rmtree(tmp_dir, ignore_errors=True)

        return self.messages
