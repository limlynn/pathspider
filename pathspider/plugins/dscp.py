
import logging
import subprocess
import socket

from pathspider.base import PluggableSpider
from pathspider.base import CONN_OK
from pathspider.base import CONN_SKIPPED
from pathspider.sync import SynchronizedSpider
from pathspider.helpers.tcp import connect_tcp
from pathspider.helpers.tcp import connect_http
from pathspider.observer import Observer
from pathspider.observer.base import BasicChain
from pathspider.observer.tcp import TCPChain
from pathspider.observer.dscp import DSCPChain

class DSCP(SynchronizedSpider, PluggableSpider):

    name = "dscp"
    description = "Differentiated Services Codepoints"
    chains = [BasicChain, DSCPChain, TCPChain]
    connect_supported = ["http", "tcp"]

    def config_no_dscp(self):
        """
        Disables DSCP marking via iptables.
        """

        logger = logging.getLogger('dscp')
        for iptables in ['iptables', 'ip6tables']:
            subprocess.check_call([iptables, '-t', 'mangle', '-F'])
        logger.debug("Configurator disabled DSCP marking")

    def config_dscp(self):
        """
        Enables DSCP marking via iptables.
        """
        logger = logging.getLogger('dscp')
        for iptables in ['iptables', 'ip6tables']:
            subprocess.check_call([iptables, '-t', 'mangle', '-A', 'OUTPUT',
                                   '-p', 'tcp', '-m', 'tcp',
                                   '-j', 'DSCP',
                                   '--set-dscp', str(self.args.codepoint)])
        logger.debug("Configurator enabled DSCP marking")

    configurations = [config_no_dscp, config_dscp]

    def combine_flows(self, flows):
        conditions = []

        # discard non-observed flows
        for f in flows:
            if not f['observed']:
                return ['pathspider.not_observed']

        baseline = 'dscp.' + str(flows[0]['dscp_mark_syn_fwd']) + '.'
        test = 'dscp.' + str(flows[1]['dscp_mark_syn_fwd']) + '.'

        if flows[0]['spdr_state'] == CONN_OK and flows[1]['spdr_state'] == CONN_OK:
            cond_conn = test + 'connectivity.works'
        elif flows[0]['spdr_state'] == CONN_OK and not flows[1]['spdr_state'] == CONN_OK:
            cond_conn = test + 'connectivity.broken'
        elif not flows[0]['spdr_state'] == CONN_OK and flows[1]['spdr_state'] == CONN_OK:
            cond_conn = test + 'connectivity.transient'
        else:
            cond_conn = test + 'connectivity.offline'
        conditions.append(cond_conn)

        conditions.append(test + 'replymark:' + str(flows[0]['dscp_mark_syn_rev']))
        conditions.append(baseline + 'replymark:' + str(flows[1]['dscp_mark_syn_rev']))

        return conditions

    @staticmethod
    def extra_args(parser):
        parser.add_argument("--codepoint", type=int, choices=range(0, 64), default='48',
                            metavar="[0-63]", help="DSCP codepoint to send (Default: 48)")
