"""Resource-limited execution of one bot evaluation cycle.

TradeBot sandbox:
- Wall-clock timeout
- CPU limit where supported
- Memory/address-space limit where supported
- Process isolation
- Windows + Linux compatibility

Users can only configure parameters of the fixed/versioned Hybrid Engine.
They do not upload arbitrary Python code.
"""

import multiprocessing as mp
import sys
import traceback
from dataclasses import dataclass


# resource is Unix-only.
# Windows does not provide the resource module.
if sys.platform != "win32":
    import resource


class SandboxError(RuntimeError):
    pass


class SandboxTimeout(SandboxError):
    pass


@dataclass(frozen=True)
class SandboxLimits:
    wall_timeout_s: float = 10.0
    cpu_seconds: int = 10
    memory_mb: int = 2048


def _apply_resource_limits(limits: SandboxLimits):
    """Apply OS-level resource limits where supported."""

    if sys.platform == "win32":
        # Windows does not expose Unix resource.setrlimit().
        #
        # The sandbox still provides:
        # - separate process
        # - wall-clock timeout
        # - forced process termination
        #
        # OS-level CPU/address-space limits should be implemented
        # separately using Windows Job Objects if required.
        return

    # Unix / Linux
    resource.setrlimit(
        resource.RLIMIT_CPU,
        (
            limits.cpu_seconds,
            limits.cpu_seconds + 1,
        ),
    )

    memory_bytes = limits.memory_mb * 1024 * 1024

    resource.setrlimit(
        resource.RLIMIT_AS,
        (
            memory_bytes,
            memory_bytes,
        ),
    )


def _child(conn, fn, args, kwargs, limits: SandboxLimits):
    """Execute one evaluation inside the isolated child process."""

    try:
        _apply_resource_limits(limits)

        result = fn(*args, **kwargs)

        conn.send(("ok", result))

    except MemoryError:
        conn.send(
            (
                "error",
                "MemoryError: evaluation exceeded memory limit",
            )
        )

    except BaseException:
        conn.send(
            (
                "error",
                traceback.format_exc(limit=5),
            )
        )

    finally:
        conn.close()


def _get_process_context():
    """Return a multiprocessing context supported by the current OS."""

    if sys.platform == "win32":
        # Windows supports spawn, not fork.
        return mp.get_context("spawn")

    # Linux/Unix can use fork.
    return mp.get_context("fork")


def run_sandboxed(
    fn,
    *args,
    limits: SandboxLimits = SandboxLimits(),
    **kwargs,
):
    """Run fn(*args, **kwargs) inside an isolated process.

    Parameters
    ----------
    fn:
        Module-level picklable function.

    args / kwargs:
        Arguments passed to fn.

    limits:
        Sandbox execution limits.

    Returns
    -------
    Any:
        Picklable result returned by fn.

    Raises
    ------
    SandboxTimeout:
        If execution exceeds wall_timeout_s.

    SandboxError:
        If the child process fails or returns an error.
    """

    ctx = _get_process_context()

    parent, child = ctx.Pipe(duplex=False)

    proc = ctx.Process(
        target=_child,
        args=(child, fn, args, kwargs, limits),
        daemon=True,
    )

    proc.start()

    # Parent no longer needs the child-side pipe.
    child.close()

    try:
        # Wall-clock protection works on both Windows and Linux.
        if not parent.poll(limits.wall_timeout_s):
            raise SandboxTimeout(
                f"evaluation exceeded {limits.wall_timeout_s}s"
            )

        try:
            status, payload = parent.recv()

        except EOFError:
            raise SandboxError(
                f"evaluation process died "
                f"(exit code {proc.exitcode})"
            )

        if status != "ok":
            raise SandboxError(payload)

        return payload

    finally:
        # Make sure runaway evaluation cannot remain alive.
        if proc.is_alive():
            proc.kill()

        proc.join(1)

        parent.close()