## Query or set NVIDIA GPU fan speeds, power limits using NVML.

#### Prerequisite:

```
pip install pynvml
```

#### Usage:

```
nvconfig --help

Usage: nvconfig.py [-h] [-l] [-g GPU] [-s SPEED] [-f FAN] [-p POWER_LIMIT]
options:
  -h, --help            show this help message and exit
  -l, --list            List all GPUs, fan speeds, power limits, and temperatures (no changes)
  -g, --gpu GPU         GPU index (required when setting fan speed or power limit)
  -s, --speed SPEED     Fan speed percentage (0-100) – set fan speed
  -f, --fan FAN         Fan index (default: 0). Use -1 to set all fans on the GPU.
  -p, --power-limit POWER_LIMIT  
                        Set power limit in watts (e.g., 250) – requires root/admin privileges
```

#### Examples:
List all Nvidia GPU and show all info.
```
nvconfig.py --list
```

For the first Nvidia GPU, set its first fan speed to 75% and power limit to 260W. 
```
nvconfig.py --gpu 0 --speed 75 --power-limit 260
```

For the second Nvidia GPU, set the second fan speed to 30%.
```
nvconfig.py -g 1 -f 1 -s 30
```


## Temperature Guard, keep your NVIDIA GPU stay cool.
#### Prerequisite:
```
pip install pynvml
```

#### Usage:
```
temperature_guard --help

usage: temperature_guard [-h] -t TARGET_TEMP [-i INTERVAL] [--hysteresis HYSTERESIS] [--min-speed MIN_SPEED] [--max-speed MAX_SPEED] [--step STEP] [--kp KP]
                         [--restore-auto-on-exit]

Daemon that adjusts GPU fan speed to keep temperatures below a target.

options:
  -h, --help            show this help message and exit
  -t, --target-temp TARGET_TEMP
                        Target GPU temperature in Celsius (example: 70)
  -i, --interval INTERVAL
                        Polling interval in seconds (default: 2.0)
  --hysteresis HYSTERESIS
                        Hysteresis below target before reducing fan speed (default: 2C)
  --min-speed MIN_SPEED
                        Minimum fan speed percentage in manual mode (default: 30)
  --max-speed MAX_SPEED
                        Maximum fan speed percentage in manual mode (default: 100)
  --step STEP           Fan speed step change per interval (default: 5)
  --kp KP               Proportional gain for temperature error to fan speed delta (default: 3.0)
  --restore-auto-on-exit
                        Restore all fans to automatic mode when the daemon exits
```

#### Examples:
Keep all GPUs stay lower than 70c.
```
temperature_guard -t 70
```

Same goal as above, but without log emitting:
```
temperature_guard -t 70 2>&1 >/dev/null
```

