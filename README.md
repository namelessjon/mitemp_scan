# mitemp_scan

This creates a daemon which periodically polls a xaomi mitemp sensor for temp/humidity/battery

An example sensor config looks like:

``` yaml
---
default_interval: 300 # seconds
sensors:
  - name: xaomi-4C:65:A8:D9:B3:86
    location: Kitchen
    type: xaomi_mitemp
    measure:
      - temperature
      - humidity
      - battery
    mac: "4C:65:A8:D9:B3:86"
```

Use with a systemd service like:

```
[Unit]
Description=Poll Xaomi sensors for temp etc
Wants=bluetooth.service
After=bluetooth.service


[Service]
Type=simple
; keeps options off the commandline
EnvironmentFile=/etc/default/mitemp_scan
ExecStart=/usr/local/bin/mitemp_scan $ARGS
Restart=on-failure
RestartSec=20

; run as a nobody
User=mitemp_scan

; run with a private version of /tmp
PrivateTmp=true

; run with a minimal /dev
PrivateDevices=true

; Make /etc, /boot read only
ProtectSystem=strict

; make /home, /root, /run/user inaccessible to the script
ProtectHome=true

; lock service out of mount points too
InaccessiblePaths=-/mnt -/data -/var

; Also, don't allow it to ever become root again
NoNewPrivileges=true
ProtectControlGroups=true
ProtectKernelTunables=true
ProtectKernelModules=true

;AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN

[Install]
WantedBy=multi-user.target

```

## Backfill (if the database went away)

### 1. Get json sensor readings (stored in systemd journal)

``` bash
# read the service log             | restrict to today | get only the json (not the systemd timestamps)
sudo journalctl --unit mitemp_scan | grep '2019-07-26' | cut -d' ' -f6- >aster.json
```

### 2. Combine, filter and sort the json

The following snippet takes a bunch of sensor reading logs

1. Combine them into an array `--slurp`
2. Sort by the timestamp
3. Select entries between 08:31 and 21:15
4. Create a new object with the readings under "readings", and a short list of sensors under "sensors"

``` bash
cat *.json | jq --slurp 'sort_by(.timestamp) | map(select(.timestamp >= "2019-07-26T08:31:00")) | map(select(.timestamp <= "2019-07-26T21:15:00")) | {readings: ., sensors: (. | map(.name) | unique) }'
```


