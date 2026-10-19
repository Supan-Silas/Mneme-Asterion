"""Read the process's cgroup quota, not the host's advertised capacity."""
from pathlib import Path
import os
import sys


def cpu_affinity():
    """Return known eligible CPU IDs, or None when the OS cannot report them."""
    if hasattr(os, 'sched_getaffinity'):
        return sorted(os.sched_getaffinity(0))
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        kernel.GetProcessAffinityMask.restype = wintypes.BOOL
        process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
        if kernel.GetProcessAffinityMask(kernel.GetCurrentProcess(), ctypes.byref(process_mask), ctypes.byref(system_mask)) and process_mask.value:
            return [i for i in range(process_mask.value.bit_length()) if process_mask.value & (1 << i)]
    return None


def process_usage():
    """CPU seconds and peak resident memory for this worker, without extra packages."""
    if sys.platform != 'win32':
        import resource
        consumed = resource.getrusage(resource.RUSAGE_SELF)
        return {'user_cpu_seconds': consumed.ru_utime, 'system_cpu_seconds': consumed.ru_stime,
                'peak_rss_bytes': int(consumed.ru_maxrss * (1024 if sys.platform.startswith('linux') else 1))}
    import ctypes
    from ctypes import wintypes

    class MemoryCounters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('PeakWorkingSetSize', 'WorkingSetSize',
                'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(MemoryCounters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    counters = MemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    times = os.times()
    return {'user_cpu_seconds': times.user, 'system_cpu_seconds': times.system,
            'peak_rss_bytes': counters.PeakWorkingSetSize}


def limits(base=Path('/sys/fs/cgroup'), *, affinity_count=None):
    base = Path(base)
    cpu, memory = None, None
    if (base / 'cpu.max').exists():
        quota, period = (base / 'cpu.max').read_text().split()
        if quota != 'max':
            cpu = int(quota) / int(period)
    elif (base / 'cpu/cpu.cfs_quota_us').exists():
        quota = int((base / 'cpu/cpu.cfs_quota_us').read_text())
        period = int((base / 'cpu/cpu.cfs_period_us').read_text())
        if quota > 0:
            cpu = quota / period
    memory_path = base / 'memory.max'
    if not memory_path.exists():
        memory_path = base / 'memory/memory.limit_in_bytes'
    if memory_path.exists():
        raw = memory_path.read_text().strip()
        if raw != 'max' and int(raw) < 2 ** 60:
            memory = int(raw)
    affinity = cpu_affinity() if affinity_count is None else None
    eligible = affinity_count if affinity_count is not None else (len(affinity) if affinity else os.cpu_count() or 1)
    return {'cpu_quota_cores': cpu, 'eligible_logical_cpus': eligible,
            'effective_cpu_cores': min(eligible, cpu) if cpu is not None else eligible,
            'memory_limit_bytes': memory}


def safe_parallelism(resource_limits, tasks):
    cpu_slots = max(1, int(resource_limits['effective_cpu_cores'] // 2))
    memory = resource_limits['memory_limit_bytes']
    memory_slots = max(1, int((memory - 128 * 1024 ** 2) // (1536 * 1024 ** 2))) if memory else tasks
    return min(tasks, cpu_slots, memory_slots)
