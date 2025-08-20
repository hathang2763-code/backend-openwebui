import logging
from typing import List, Dict, Any, Optional

log = logging.getLogger(__name__)


class VendorCommandService:
    """
    厂商命令生成服务

    - 根据节点内容与厂商，给出排障/检查命令建议
    - 模板来源对齐 Flask 版实现，并做轻量改造
    - 支持通过 context 替换命令中的占位符（如 {interface} / {target_ip} / {destination}）
    """

    def __init__(self) -> None:
        self._load_command_templates()

    def _load_command_templates(self) -> None:
        self.command_templates: Dict[str, Dict[str, List[str]]] = {
            "Huawei": {
                "basic_check": [
                    "display version",
                    "display device",
                    "display interface brief",
                ],
                "ospf_troubleshoot": [
                    "display ospf peer",
                    "display interface brief",
                    "display ospf interface",
                    "display ospf database",
                    "display ospf routing",
                ],
                "bgp_troubleshoot": [
                    "display bgp peer",
                    "display bgp routing-table",
                    "display ip routing-table bgp",
                    "display bgp network",
                ],
                "interface_check": [
                    "display interface {interface}",
                    "display interface {interface} statistics",
                    "ping -c 5 {target_ip}",
                    "tracert {target_ip}",
                ],
                "mtu_check": [
                    "display interface {interface}",
                    "ping -s 1472 -c 5 {target_ip}",
                    "ping -s 1500 -c 5 {target_ip}",
                ],
                "routing_check": [
                    "display ip routing-table",
                    "display ip routing-table {destination}",
                    "display arp all",
                ],
            },
            "Cisco": {
                "basic_check": [
                    "show version",
                    "show inventory",
                    "show interfaces brief",
                ],
                "ospf_troubleshoot": [
                    "show ip ospf neighbor",
                    "show interfaces brief",
                    "show ip ospf interface",
                    "show ip ospf database",
                    "show ip route ospf",
                ],
                "bgp_troubleshoot": [
                    "show bgp summary",
                    "show bgp",
                    "show ip route bgp",
                    "show bgp neighbors",
                ],
                "interface_check": [
                    "show interface {interface}",
                    "show interface {interface} statistics",
                    "ping {target_ip} repeat 5",
                    "traceroute {target_ip}",
                ],
                "mtu_check": [
                    "show interface {interface}",
                    "ping {target_ip} size 1472 repeat 5",
                    "ping {target_ip} size 1500 repeat 5",
                ],
                "routing_check": [
                    "show ip route",
                    "show ip route {destination}",
                    "show arp",
                ],
            },
            "Juniper": {
                "basic_check": [
                    "show version",
                    "show chassis hardware",
                    "show interfaces terse",
                ],
                "ospf_troubleshoot": [
                    "show ospf neighbor",
                    "show interfaces terse",
                    "show ospf interface",
                    "show ospf database",
                    "show route protocol ospf",
                ],
                "bgp_troubleshoot": [
                    "show bgp summary",
                    "show route protocol bgp",
                    "show bgp neighbor",
                    "show bgp group",
                ],
                "interface_check": [
                    "show interfaces {interface}",
                    "show interfaces {interface} statistics",
                    "ping {target_ip} count 5",
                    "traceroute {target_ip}",
                ],
                "mtu_check": [
                    "show interfaces {interface}",
                    "ping {target_ip} size 1472 count 5",
                    "ping {target_ip} size 1500 count 5",
                ],
                "routing_check": [
                    "show route",
                    "show route {destination}",
                    "show arp",
                ],
            },
            "H3C": {
                "basic_check": [
                    "display version",
                    "display device",
                    "display interface brief",
                ],
                "ospf_troubleshoot": [
                    "display ospf peer",
                    "display interface brief",
                    "display ospf interface",
                    "display ospf lsdb",
                    "display ip routing-table protocol ospf",
                ],
                "bgp_troubleshoot": [
                    "display bgp peer",
                    "display bgp routing-table",
                    "display ip routing-table protocol bgp",
                    "display bgp network",
                ],
                "interface_check": [
                    "display interface {interface}",
                    "display interface {interface} counters",
                    "ping -c 5 {target_ip}",
                    "tracert {target_ip}",
                ],
                "mtu_check": [
                    "display interface {interface}",
                    "ping -s 1472 -c 5 {target_ip}",
                    "ping -s 1500 -c 5 {target_ip}",
                ],
                "routing_check": [
                    "display ip routing-table",
                    "display ip routing-table {destination}",
                    "display arp all",
                ],
            },
        }

    def get_supported_vendors(self) -> List[str]:
        return list(self.command_templates.keys())

    def generate_commands(
        self,
        content_text: str,
        title: Optional[str],
        vendor: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        try:
            if vendor not in self.command_templates:
                log.warning(f"Unsupported vendor: {vendor}")
                return []

            problem_type = self._analyze_problem_type(content_text or "", title or "")
            template_key = self._map_problem_to_template(problem_type)
            commands = self.command_templates[vendor].get(
                template_key, self.command_templates[vendor]["basic_check"]
            )
            if context:
                commands = self._apply_context(commands, context)
            return commands
        except Exception as e:
            log.error(f"Vendor command generation error: {e}")
            return self.command_templates.get(vendor, {}).get("basic_check", [])

    def _analyze_problem_type(self, content_text: str, title: str) -> str:
        text = f"{content_text} {title}".lower()
        if any(k in text for k in ["ospf", "neighbor", "exstart", "lsa"]):
            return "ospf"
        if any(k in text for k in ["bgp", "peer", "session", "as "]):
            return "bgp"
        if any(k in text for k in ["mtu", "fragmentation", "packet size"]):
            return "mtu"
        if any(k in text for k in ["interface", "down", "up", "link"]):
            return "interface"
        if any(k in text for k in ["route", "routing", "destination", "reachability"]):
            return "routing"
        return "basic"

    def _map_problem_to_template(self, problem_type: str) -> str:
        mapping = {
            "ospf": "ospf_troubleshoot",
            "bgp": "bgp_troubleshoot",
            "mtu": "mtu_check",
            "interface": "interface_check",
            "routing": "routing_check",
            "basic": "basic_check",
        }
        return mapping.get(problem_type, "basic_check")

    def _apply_context(self, commands: List[str], context: Dict[str, Any]) -> List[str]:
        out: List[str] = []
        for cmd in commands:
            try:
                out.append(cmd.format(**context))
            except Exception:
                out.append(cmd)
        return out


vendor_command_service = VendorCommandService()
