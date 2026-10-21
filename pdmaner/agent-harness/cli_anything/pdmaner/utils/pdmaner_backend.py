"""Java backend wrapper for PDManer operations.

PDManer ships a pdmaner-java.jar that handles:
- Database connection testing
- Database reverse engineering
- Code generation (Java, MyBatis, etc.)

This module provides Python wrappers around those Java operations.
"""

import subprocess
import os
import json


def _find_jar():
    """Find pdmaner-java.jar. Checks:
    1. PDMANER_JAVA_JAR env var
    2. Default paths relative to this project
    """
    env_jar = os.environ.get("PDMANER_JAVA_JAR")
    if env_jar and os.path.exists(env_jar):
        return env_jar

    # Check relative to the source tree
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "public", "jar", "pdmaner-java.jar"),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "public", "jar", "pdmaner-java.jar"),
    ]
    for c in candidates:
        if os.path.exists(os.path.abspath(c)):
            return os.path.abspath(c)

    return None


def _find_java():
    """Find java executable."""
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        java = os.path.join(java_home, "bin", "java")
        if os.path.exists(java):
            return java
    return "java"


def is_available():
    """Check if the Java backend is available."""
    jar = _find_jar()
    if not jar:
        return False, "pdmaner-java.jar not found. Set PDMANER_JAVA_JAR env var or place jar in public/jar/."
    try:
        result = subprocess.run(
            [_find_java(), "-version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            return False, "Java not found. Install Java 8+ and set JAVA_HOME."
    except FileNotFoundError:
        return False, "Java not found. Install Java 8+ and set JAVA_HOME."
    except Exception as e:
        return False, f"Java check failed: {e}"
    return True, jar


def run_java(jar_path, *args, timeout=120):
    """Run the PDManer Java jar with arguments."""
    cmd = [_find_java(), "-jar", jar_path] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def test_db_connection(db_type, url, username, password, driver_class=""):
    """Test a database connection."""
    available, jar = is_available()
    if not available:
        raise RuntimeError(jar)  # jar here is the error message
    args = [
        "connect",
        "--type", db_type,
        "--url", url,
        "--username", username,
        "--password", password,
    ]
    if driver_class:
        args += ["--driver", driver_class]
    result = run_java(jar, *args)
    if result["returncode"] != 0:
        raise RuntimeError(f"DB connection test failed: {result['stderr']}")
    return result


def reverse_db(db_type, url, username, password, schema="", driver_class=""):
    """Reverse engineer a database schema into entities."""
    available, jar = is_available()
    if not available:
        raise RuntimeError(jar)
    args = [
        "reverse",
        "--type", db_type,
        "--url", url,
        "--username", username,
        "--password", password,
    ]
    if schema:
        args += ["--schema", schema]
    if driver_class:
        args += ["--driver", driver_class]
    result = run_java(jar, *args, timeout=300)
    if result["returncode"] != 0:
        raise RuntimeError(f"DB reverse failed: {result['stderr']}")
    return result
