## Query or set NVIDIA GPU fan speeds, power limits using NVML.

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
