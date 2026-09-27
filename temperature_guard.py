import argparse
import signal
import sys
import time
from datetime import datetime

from pynvml import *


RUNNING = True


def log(message):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {message}", flush=True)


def clamp(value, min_v, max_v):
    return max(min_v, min(max_v, value))


def handle_stop(signum, frame):
    del signum
    del frame
    global RUNNING
    RUNNING = False


def parse_args():
    parser = argparse.ArgumentParser(
        description="Daemon that adjusts GPU fan speed to keep temperatures below a target."
    )
    parser.add_argument(
        "-t", "--target-temp", type=int, required=True,
        help="Target GPU temperature in Celsius (example: 70)"
    )
    parser.add_argument(
        "-i", "--interval", type=float, default=2.0,
        help="Polling interval in seconds (default: 2.0)"
    )
    parser.add_argument(
        "--hysteresis", type=int, default=2,
        help="Hysteresis below target before reducing fan speed (default: 2C)"
    )
    parser.add_argument(
        "--min-speed", type=int, default=30,
        help="Minimum fan speed percentage in manual mode (default: 30)"
    )
    parser.add_argument(
        "--max-speed", type=int, default=100,
        help="Maximum fan speed percentage in manual mode (default: 100)"
    )
    parser.add_argument(
        "--step", type=int, default=5,
        help="Fan speed step change per interval (default: 5)"
    )
    parser.add_argument(
        "--kp", type=float, default=3.0,
        help="Proportional gain for temperature error to fan speed delta (default: 3.0)"
    )
    parser.add_argument(
        "--restore-auto-on-exit", action="store_true",
        help="Restore all fans to automatic mode when the daemon exits"
    )
    return parser.parse_args()


def get_gpu_handles():
    count = nvmlDeviceGetCount()
    return [nvmlDeviceGetHandleByIndex(idx) for idx in range(count)]


def get_name(handle):
    name = nvmlDeviceGetName(handle)
    if isinstance(name, bytes):
        return name.decode("utf-8", errors="replace")
    return str(name)


def get_fan_count(handle):
    try:
        return nvmlDeviceGetNumFans(handle)
    except NVMLError:
        return 1


def get_temp(handle):
    return nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)


def set_gpu_fans(handle, speed):
    fan_count = get_fan_count(handle)
    for fan_idx in range(fan_count):
        nvmlDeviceSetFanSpeed_v2(handle, fan_idx, speed)


def restore_gpu_auto(handle):
    fan_count = get_fan_count(handle)
    for fan_idx in range(fan_count):
        nvmlDeviceSetDefaultFanSpeed_v2(handle, fan_idx)


def compute_next_speed(temp, target, hysteresis, current_speed, min_speed, max_speed, step, kp):
    if temp > target:
        overshoot = temp - target
        dynamic_step = max(step, int(round(overshoot * kp)))
        return clamp(current_speed + dynamic_step, min_speed, max_speed)

    if temp < target - hysteresis:
        return clamp(current_speed - step, min_speed, max_speed)

    return current_speed


def validate_args(args):
    if args.target_temp < 20 or args.target_temp > 95:
        print("Error: --target-temp must be in [20, 95] C", file=sys.stderr)
        sys.exit(1)
    if args.interval <= 0:
        print("Error: --interval must be > 0", file=sys.stderr)
        sys.exit(1)
    if args.hysteresis < 0:
        print("Error: --hysteresis must be >= 0", file=sys.stderr)
        sys.exit(1)
    if args.step <= 0:
        print("Error: --step must be > 0", file=sys.stderr)
        sys.exit(1)
    if args.min_speed < 0 or args.min_speed > 100:
        print("Error: --min-speed must be in [0, 100]", file=sys.stderr)
        sys.exit(1)
    if args.max_speed < 0 or args.max_speed > 100:
        print("Error: --max-speed must be in [0, 100]", file=sys.stderr)
        sys.exit(1)
    if args.min_speed > args.max_speed:
        print("Error: --min-speed cannot be greater than --max-speed", file=sys.stderr)
        sys.exit(1)
    if args.kp <= 0:
        print("Error: --kp must be > 0", file=sys.stderr)
        sys.exit(1)


def main():
    args = parse_args()
    validate_args(args)

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    handles = []
    names = []
    current_speeds = {}

    try:
        nvmlInit()
        handles = get_gpu_handles()
        if not handles:
            print("No NVIDIA GPUs found.", file=sys.stderr)
            sys.exit(1)

        for idx, handle in enumerate(handles):
            names.append(get_name(handle))
            try:
                current = nvmlDeviceGetFanSpeed_v2(handle, 0)
            except NVMLError:
                try:
                    current = nvmlDeviceGetFanSpeed(handle)
                except NVMLError:
                    current = args.min_speed
            current_speeds[idx] = clamp(current, args.min_speed, args.max_speed)

        log(
            f"Started GPU temp daemon for {len(handles)} GPU(s), target={args.target_temp}C, "
            f"range={args.min_speed}-{args.max_speed}%"
        )

        while RUNNING:
            for idx, handle in enumerate(handles):
                try:
                    temp = get_temp(handle)
                    current_speed = current_speeds[idx]
                    next_speed = compute_next_speed(
                        temp=temp,
                        target=args.target_temp,
                        hysteresis=args.hysteresis,
                        current_speed=current_speed,
                        min_speed=args.min_speed,
                        max_speed=args.max_speed,
                        step=args.step,
                        kp=args.kp,
                    )

                    if next_speed != current_speed:
                        set_gpu_fans(handle, next_speed)
                        current_speeds[idx] = next_speed

                    log(
                        f"GPU {idx} ({names[idx]}): {temp}C, fan={current_speeds[idx]}% "
                        f"(target={args.target_temp}C)"
                    )

                except NVMLError as e:
                    log(f"GPU {idx} ({names[idx]}): NVML error: {e}")

            time.sleep(args.interval)

    except NVMLError as e:
        print(f"NVML init/runtime error: {e}", file=sys.stderr)
        print("Hint: Manual fan control may require root privileges and coolbits enabled.", file=sys.stderr)
        sys.exit(1)
    finally:
        if handles and args.restore_auto_on_exit:
            for idx, handle in enumerate(handles):
                try:
                    restore_gpu_auto(handle)
                    log(f"GPU {idx} ({names[idx]}): fan policy restored to Auto")
                except NVMLError as e:
                    log(f"GPU {idx} ({names[idx]}): failed to restore Auto fan policy: {e}")

        try:
            nvmlShutdown()
        except NVMLError:
            pass


if __name__ == "__main__":
    main()
