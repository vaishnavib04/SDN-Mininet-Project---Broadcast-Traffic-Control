# SDN Broadcast Traffic Control
### Mininet + Ryu OpenFlow Controller Project

## Problem Statement

In traditional networks, broadcast packets (destination MAC `ff:ff:ff:ff:ff:ff`) are flooded to every port on a switch. When hosts send excessive broadcasts — such as during ARP storms or misconfigured applications — this causes **broadcast storms** that congest the network and degrade performance for all users.

This project implements an **SDN-based solution** using Mininet and the Ryu OpenFlow controller to:
- Detect broadcast packets at the controller level
- Track broadcast frequency per source MAC address
- Automatically install **DROP rules** on the switch when a host exceeds the broadcast threshold
- Allow normal unicast traffic to continue unaffected

---

## Project Structure

```
sdn_project/
│
├── controller/
│   └── broadcast_control.py        ← your main SDN logic
│
├── topology/
│   └── topology.py                ← Mininet topology
│
├── flood_test.py              ← broadcast attack script
│
├── results/
│   └── screenshots/                  ← controller logs 
│
└──docs/
    └──README.md                  ← GitHub documentation


```

---

## Topology

```
    h1
     \
      s1 --- h2
     /
    h3
```

- 1 Open vSwitch (`s1`) running OpenFlow 1.3
- 3 hosts (`h1`, `h2`, `h3`) connected to the switch
- Remote Ryu controller managing all flow decisions

---

## Setup & Execution

### Prerequisites

- Ubuntu 20.04 / 22.04 (or equivalent Linux)
- Python 3.10
- Mininet
- Ryu SDN Framework

### Install Dependencies

```bash
pip install ryu
pip install dnspython==2.1.0
pip install eventlet==0.30.2
```

### Step 1 — Start the Ryu Controller

Open **Terminal 1**:

```bash
cd ~/sdn_project/controller
ryu-manager broadcast_control.py
```

You should see:
```
loading app broadcast_control.py
instantiating app broadcast_control.py of BroadcastControl
Switch 1 connected
```

### Step 2 — Start the Mininet Topology

Open **Terminal 2**:

```bash
cd ~/sdn_project
sudo mn --custom topology/topology.py --topo simpletopo \
  --controller=remote --switch ovsk,protocols=OpenFlow13
```

---

## Controller Logic

The Ryu controller (`broadcast_control.py`) implements:

1. **Default flow rule** — unknown packets sent to controller (`packet_in`)
2. **MAC learning** — learns source MAC → port mapping for unicast forwarding
3. **Broadcast detection** — identifies packets with `dst == ff:ff:ff:ff:ff:ff`
4. **Threshold enforcement** — allows up to 5 broadcasts per source MAC, then installs a DROP rule
5. **Selective forwarding** — installs unicast flow rules for known destinations

### Broadcast Control Threshold

```python
BROADCAST_THRESHOLD = 5
```

When a host exceeds 5 broadcasts, a flow rule is installed:
```
priority=10, dl_src=<MAC>, dl_dst=ff:ff:ff:ff:ff:ff → actions=drop
```
The rule has a `hard_timeout=30` seconds, after which it expires and the counter resets.

---

## Test Scenarios

### Scenario 1 — Normal Unicast Traffic (Should Work)

```bash
mininet> h1 ping -c 5 h2
```

**Expected output:**
```
5 packets transmitted, 5 received, 0% packet loss
rtt min/avg/max/mdev = 0.066/0.704/2.923/1.114 ms
```

Unicast traffic is unaffected by broadcast control. 

### Scenario 2 — Broadcast Flood (Should Be Blocked)

```bash
mininet> h1 python3 /home/seed/sdn_project/flood_test.py
```

**Expected Ryu terminal output:**
```
BROADCAST from ca:d8:a9:93:51:d4 on port 1 | count=1/5
BROADCAST from ca:d8:a9:93:51:d4 on port 1 | count=2/5
BROADCAST from ca:d8:a9:93:51:d4 on port 1 | count=3/5
BROADCAST from ca:d8:a9:93:51:d4 on port 1 | count=4/5
BROADCAST from ca:d8:a9:93:51:d4 on port 1 | count=5/5
BLOCKED broadcast from ca:d8:a9:93:51:d4 (too many broadcasts)
DROPPED broadcast from ca:d8:a9:93:51:d4
```

Broadcasts from h1 are blocked after threshold. 

---

## Performance Metrics

### Flow Table (after broadcast flood)

```bash
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1
```

**Key rule installed:**
```
priority=10,dl_src=ca:d8:a9:93:51:d4,dl_dst=ff:ff:ff:ff:ff:ff actions=drop
```

### Throughput (iperf)

```bash
mininet> h2 iperf -s &
mininet> h1 iperf -c h2
```

**Result:**
```
Transfer: 22.8 GBytes
Bandwidth: 19.5 Gbits/sec
```

### Latency (ping)

```bash
mininet> h1 ping -c 5 h2
```

**Result:**
```
0% packet loss
avg latency: 0.704 ms
```

---

## Expected Output Summary

| Test | Expected Result |
|---|---|
| h1 ping h2 (unicast) | 0% packet loss |
| Broadcast flood (10 packets) | Blocked after packet 5 |
| dump-flows after flood | DROP rule visible at priority 10 |
| iperf h1 → h2 | High throughput, unaffected |

---

## SDN Concepts Demonstrated

- **Controller-Switch interaction** via OpenFlow 1.3
- **packet_in event handling** in Ryu
- **Match-Action flow rules** (match on src+dst MAC, action=drop)
- **MAC learning table** for unicast forwarding
- **Dynamic flow installation** based on network behavior
- **Hard timeout** for automatic rule expiry

---

## References

- [Ryu SDN Framework Documentation](https://ryu.readthedocs.io/)
- [Mininet Documentation](http://mininet.org/docs/)
- [OpenFlow 1.3 Specification](https://opennetworking.org/wp-content/uploads/2014/10/openflow-spec-v1.3.0.pdf)
- [Open vSwitch Documentation](https://docs.openvswitch.org/)


sudo mn -c
