#!/bin/sh
# Docker Desktop's kernel has Open vSwitch built in (CONFIG_OPENVSWITCH=y), so `ovs-ctl start`
# fails on `modprobe openvswitch`. Start the database with ovs-ctl and the switch daemon directly.
set -e
/usr/share/openvswitch/scripts/ovs-ctl start --no-ovs-vswitchd --system-id=random
ovs-vswitchd unix:/var/run/openvswitch/db.sock --pidfile --detach --log-file
exec python3 -m uvicorn agent:app --host 0.0.0.0 --port 9000 --workers 1
