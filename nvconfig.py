#!/home/tianye/miniconda3/bin/python
import argparse
import sys
from pynvml import *

def safe_decode(name):
    """Return a string from nvmlDeviceGetName result (bytes or str)."""
    if name is None:
        return "Unknown"
    if isinstance(name, bytes):
        return name.decode('utf-8')
    return str(name)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Query or set NVIDIA GPU fan speeds, power limits using NVML."
    )
    parser.add_argument(
        "-l", "--list", action="store_true",
        help="List all GPUs, fan speeds, power limits, and temperatures (no changes)"
    )
    parser.add_argument(
        "-g", "--gpu", type=int,
        help="GPU index (required when setting fan speed or power limit)"
    )
    parser.add_argument(
        "-s", "--speed", type=int,
        help="Fan speed percentage (0-100) – set fan speed"
    )
    parser.add_argument(
        "-f", "--fan", type=int, default=0,
        help="Fan index (default: 0). Use -1 to set all fans on the GPU."
    )
    parser.add_argument(
        "-p", "--power-limit", type=int,
        help="Set power limit in watts (e.g., 250) – requires root/admin privileges"
    )
    return parser.parse_args()

def get_current_fan_speed(handle, fan_idx):
    """Return current fan speed percentage for a given fan, or None if error."""
    try:
        speed = nvmlDeviceGetFanSpeed_v2(handle, fan_idx)
        return speed
    except NVMLError:
        try:
            if fan_idx == 0:
                return nvmlDeviceGetFanSpeed(handle)
            else:
                return None
        except NVMLError:
            return None

def get_power_limit(handle):
    """Return current power management limit in watts, or None if not supported."""
    try:
        limit_mw = nvmlDeviceGetPowerManagementLimit(handle)
        return limit_mw / 1000.0
    except NVMLError:
        return None

def get_power_limit_range(handle):
    """Return (min_watts, max_watts) for power limit, or (None, None) if not supported."""
    try:
        min_mw, max_mw = nvmlDeviceGetPowerManagementLimitConstraints(handle)
        return min_mw / 1000.0, max_mw / 1000.0
    except NVMLError:
        return None, None

def get_gpu_temperature(handle):
    """Return GPU temperature in Celsius, or None if not supported."""
    try:
        # NVML_TEMPERATURE_GPU is the standard GPU die temperature
        temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
        return temp
    except NVMLError:
        return None

def list_gpus():
    """Display GPU indices, names, fan counts, speeds, power limits, and temperatures."""
    try:
        nvmlInit()
        device_count = nvmlDeviceGetCount()
        if device_count == 0:
            print("No NVIDIA GPUs found.")
            return

        # Collect data and find max name length
        gpu_data = []
        max_name_len = len("Name")
        for gpu_idx in range(device_count):
            handle = nvmlDeviceGetHandleByIndex(gpu_idx)
            raw_name = nvmlDeviceGetName(handle)
            name = safe_decode(raw_name)
            max_name_len = max(max_name_len, len(name))

            try:
                fan_count = nvmlDeviceGetNumFans(handle)
            except NVMLError:
                fan_count = 1

            speeds = []
            for f_idx in range(fan_count):
                spd = get_current_fan_speed(handle, f_idx)
                speeds.append(str(spd) if spd is not None else "N/A")

            power_limit = get_power_limit(handle)
            power_str = f"{power_limit:.1f}" if power_limit is not None else "N/A"
            temp = get_gpu_temperature(handle)
            temp_str = f"{temp}°C" if temp is not None else "N/A"

            gpu_data.append((gpu_idx, name, fan_count, speeds, power_str, temp_str))

        name_width = min(max_name_len, 50)  # adjusted to leave room for other columns
        # Build header with temperature column
        header = (f"{'GPU':<4} {'Name':<{name_width}} {'Fans':<5} {'Fan Spd(%)':<12} "
                  f"{'PwrLim(W)':<10} {'Temp':<6}")
        separator = "-" * (4 + 1 + name_width + 1 + 5 + 1 + 12 + 1 + 10 + 1 + 6)
        print(header)
        print(separator)

        for gpu_idx, name, fan_count, speeds, power_str, temp_str in gpu_data:
            display_name = name if len(name) <= name_width else name[:name_width-3] + "..."
            speeds_str = ", ".join(speeds)
            # Truncate speeds string if too long (unlikely but safe)
            if len(speeds_str) > 12:
                speeds_str = speeds_str[:9] + "..."
            print(f"{gpu_idx:<4} {display_name:<{name_width}} {fan_count:<5} {speeds_str:<12} "
                  f"{power_str:<10} {temp_str:<6}")

    except NVMLError as e:
        print(f"NVML error while listing: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            nvmlShutdown()
        except NVMLError:
            pass

def set_fan_speed(gpu_idx, speed, fan_idx):
    """Set fan speed on a specific GPU."""
    if not (0 <= speed <= 100):
        print(f"Error: Speed must be between 0 and 100 (got {speed})", file=sys.stderr)
        sys.exit(1)

    try:
        nvmlInit()
        device_count = nvmlDeviceGetCount()
        if gpu_idx >= device_count:
            print(f"Error: GPU index {gpu_idx} not found. Available GPUs: 0-{device_count-1}", file=sys.stderr)
            sys.exit(1)

        handle = nvmlDeviceGetHandleByIndex(gpu_idx)

        if fan_idx == -1:
            try:
                fan_count = nvmlDeviceGetNumFans(handle)
            except NVMLError:
                fan_count = 1
            for f in range(fan_count):
                nvmlDeviceSetFanSpeed_v2(handle, f, speed)
                print(f"GPU {gpu_idx} fan {f} set to {speed}%")
        else:
            if fan_idx < 0:
                print("Error: Fan index must be >= 0 or -1 for all fans", file=sys.stderr)
                sys.exit(1)
            nvmlDeviceSetFanSpeed_v2(handle, fan_idx, speed)
            print(f"GPU {gpu_idx} fan {fan_idx} set to {speed}%")

    except NVMLError as e:
        print(f"NVML error setting fan speed: {e}", file=sys.stderr)
        print("Hint: Manual fan control may require root privileges and coolbits enabled.", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            nvmlShutdown()
        except NVMLError:
            pass

def set_power_limit(gpu_idx, watt):
    """Set power limit on a specific GPU."""
    try:
        nvmlInit()
        device_count = nvmlDeviceGetCount()
        if gpu_idx >= device_count:
            print(f"Error: GPU index {gpu_idx} not found. Available GPUs: 0-{device_count-1}", file=sys.stderr)
            sys.exit(1)

        handle = nvmlDeviceGetHandleByIndex(gpu_idx)

        min_w, max_w = get_power_limit_range(handle)
        if min_w is None or max_w is None:
            print(f"Error: GPU {gpu_idx} does not support power limit setting.", file=sys.stderr)
            sys.exit(1)

        if watt < min_w or watt > max_w:
            print(f"Error: Power limit {watt}W is out of allowed range [{min_w:.1f}W, {max_w:.1f}W]", file=sys.stderr)
            sys.exit(1)

        nvmlDeviceSetPowerManagementLimit(handle, int(watt * 1000))
        print(f"GPU {gpu_idx} power limit set to {watt} W (allowed range: {min_w:.1f}–{max_w:.1f} W)")

    except NVMLError as e:
        print(f"NVML error setting power limit: {e}", file=sys.stderr)
        print("Hint: Setting power limit may require root/admin privileges.", file=sys.stderr)
        sys.exit(1)
    finally:
        try:
            nvmlShutdown()
        except NVMLError:
            pass

def main():
    args = parse_args()

    if args.list:
        list_gpus()
        return

    if args.gpu is None:
        print("Error: GPU index (--gpu) is required when setting fan speed or power limit.", file=sys.stderr)
        print("Use --list to view available GPUs.", file=sys.stderr)
        sys.exit(1)

    if args.power_limit is not None:
        set_power_limit(args.gpu, args.power_limit)

    if args.speed is not None:
        set_fan_speed(args.gpu, args.speed, args.fan)

    if args.power_limit is None and args.speed is None:
        print("Error: No action specified. Use --speed or --power-limit (or --list).", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
