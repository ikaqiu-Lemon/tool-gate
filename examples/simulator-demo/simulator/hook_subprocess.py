"""
Hook Subprocess Wrapper - Manages tg-hook process lifecycle and communication.

This module provides the HookSubprocess class that spawns tg-hook subprocesses,
sends JSON events via stdin, and reads JSON responses from stdout.

Stage B: Skeleton only - subprocess spawning and basic communication.
"""

import json
import subprocess
import sys
from typing import Any, Dict, Optional


class HookSubprocess:
    """
    Wrapper for tg-hook subprocess invocations.

    Responsibilities:
    - Spawn tg-hook subprocess for each hook event
    - Write JSON event to stdin
    - Read JSON response from stdout
    - Wait for subprocess exit
    - Handle timeouts and cleanup

    Does NOT:
    - Implement hook logic (delegated to tg-hook binary)
    - Parse or validate hook responses (just captures raw JSON)
    - Manage session state (delegated to SQLite via tg-hook)
    """

    def __init__(self, timeout: float = 10.0):
        """
        Initialize the hook subprocess wrapper.

        Args:
            timeout: Maximum time to wait for subprocess (seconds)
        """
        self.timeout = timeout

    def invoke(
        self,
        event: Dict[str, Any],
        hook_binary: str = "tg-hook",
    ) -> Dict[str, Any]:
        """
        Invoke tg-hook subprocess with a JSON event.

        Args:
            event: JSON event to send to tg-hook (must contain 'event' and 'session_id')
            hook_binary: Path to tg-hook binary (default: "tg-hook" from PATH)

        Returns:
            JSON response from tg-hook

        Raises:
            subprocess.TimeoutExpired: If subprocess exceeds timeout
            subprocess.CalledProcessError: If subprocess exits with non-zero code
            json.JSONDecodeError: If response is not valid JSON
        """
        # Validate event has required fields
        if "event" not in event:
            raise ValueError("Event must contain 'event' field")
        if "session_id" not in event:
            raise ValueError("Event must contain 'session_id' field")

        # Serialize event to JSON
        event_json = json.dumps(event)

        # Spawn tg-hook subprocess
        process = subprocess.Popen(
            [hook_binary],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            # Write event to stdin and read response from stdout
            stdout, stderr = process.communicate(
                input=event_json,
                timeout=self.timeout,
            )

            # Check exit code
            if process.returncode != 0:
                error_msg = f"tg-hook exited with code {process.returncode}"
                if stderr:
                    error_msg += f"\nstderr: {stderr}"
                raise subprocess.CalledProcessError(
                    process.returncode,
                    hook_binary,
                    output=stdout,
                    stderr=stderr,
                )

            # Parse JSON response
            if not stdout.strip():
                return {}

            try:
                return json.loads(stdout)
            except json.JSONDecodeError as e:
                error_msg = f"tg-hook returned invalid JSON: {e}"
                if stderr:
                    error_msg += f"\nstderr: {stderr}"
                if stdout:
                    error_msg += f"\nstdout: {stdout[:200]}"
                raise ValueError(error_msg) from e

        except subprocess.TimeoutExpired as e:
            # Kill subprocess if it exceeds timeout
            process.kill()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                # Force kill if graceful kill fails
                process.terminate()
                process.wait()
            raise subprocess.TimeoutExpired(
                cmd=hook_binary,
                timeout=self.timeout,
                output=e.output,
                stderr=e.stderr,
            ) from e

    def __repr__(self) -> str:
        return f"HookSubprocess(timeout={self.timeout})"
