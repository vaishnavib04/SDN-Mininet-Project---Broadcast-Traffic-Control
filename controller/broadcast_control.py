from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet

# Max broadcasts allowed per source MAC before blocking
BROADCAST_THRESHOLD = 5 

class BroadcastControl(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(BroadcastControl, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        # Track broadcast count per (dpid, src_mac)
        self.broadcast_count = {}
        # Track blocked MACs
        self.blocked_macs = set()

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        # Default rule: send unknown packets to controller
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER)]
        self.add_flow(datapath, 0, match, actions)
        self.logger.info("Switch %s connected", datapath.id)

    def add_flow(self, datapath, priority, match, actions, hard_timeout=0):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            hard_timeout=hard_timeout
        )
        datapath.send_msg(mod)

    def install_block_rule(self, datapath, src_mac):
        """Install a DROP rule for broadcasts from this src MAC"""
        parser = datapath.ofproto_parser
        match = parser.OFPMatch(eth_src=src_mac, eth_dst="ff:ff:ff:ff:ff:ff")
        # Empty actions = DROP
        self.add_flow(datapath, 10, match, [], hard_timeout=30)
        self.logger.info("BLOCKED broadcast from %s (too many broadcasts)", src_mac)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocol(ethernet.ethernet)
        dst = eth.dst
        src = eth.src
        dpid = datapath.id

        self.mac_to_port.setdefault(dpid, {})
        # Learn source MAC
        self.mac_to_port[dpid][src] = in_port

        # ---- BROADCAST DETECTION & CONTROL ----
        if dst == "ff:ff:ff:ff:ff:ff":
            key = (dpid, src)
            self.broadcast_count[key] = self.broadcast_count.get(key, 0) + 1
            count = self.broadcast_count[key]

            self.logger.info(
                "BROADCAST from %s on port %s | count=%d/%d",
                src, in_port, count, BROADCAST_THRESHOLD
            )

            if count >= BROADCAST_THRESHOLD:
                # Install drop rule and block
                self.install_block_rule(datapath, src)
                self.blocked_macs.add(src)
                self.logger.info("DROPPED broadcast from %s", src)
                return  # Drop this packet too

            # Under threshold: allow flooding
            actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
            out = parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=msg.buffer_id,
                in_port=in_port,
                actions=actions,
                data=msg.data
            )
            datapath.send_msg(out)
            return

        # ---- NORMAL UNICAST LEARNING SWITCH ----
        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        # Install flow rule for known destinations
        if out_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_dst=dst)
            self.add_flow(datapath, 1, match, actions)

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=msg.data
        )
        datapath.send_msg(out)

