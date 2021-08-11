# -*- coding: utf-8 -*-
#
"""
websocket - WebSocket client library for Python

Copyright (C) 2010 Hiroki Ohtani(liris)

    This library is free software; you can redistribute it and/or
    modify it under the terms of the GNU Lesser General Public
    License as published by the Free Software Foundation; either
    version 2.1 of the License, or (at your option) any later version.

    This library is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public
    License along with this library; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

"""

import os
import os.path
import websocket as ws
from websocket._http import proxy_info, read_headers, _start_proxied_socket, _tunnel, _get_addrinfo_list, connect
import sys
import unittest
import ssl
import websocket
from python_socks.sync import Proxy
from python_socks._errors import *
import socket
sys.path[0:0] = [""]

# Skip test to access the internet.
TEST_WITH_INTERNET = os.environ.get('TEST_WITH_INTERNET', '0') == '1'
TEST_WITH_PROXY = os.environ.get('TEST_WITH_PROXY', '0') == '1'


class SockMock(object):
    def __init__(self):
        self.data = []
        self.sent = []

    def add_packet(self, data):
        self.data.append(data)

    def gettimeout(self):
        return None

    def recv(self, bufsize):
        if self.data:
            e = self.data.pop(0)
            if isinstance(e, Exception):
                raise e
            if len(e) > bufsize:
                self.data.insert(0, e[bufsize:])
            return e[:bufsize]

    def send(self, data):
        self.sent.append(data)
        return len(data)

    def close(self):
        pass


class HeaderSockMock(SockMock):

    def __init__(self, fname):
        SockMock.__init__(self)
        path = os.path.join(os.path.dirname(__file__), fname)
        with open(path, "rb") as f:
            self.add_packet(f.read())


class OptsList():

    def __init__(self):
        self.timeout = 1
        self.sockopt = []
        self.sslopt = {"cert_reqs": ssl.CERT_NONE}


class HttpTest(unittest.TestCase):

    def testReadHeader(self):
        status, header, status_message = read_headers(HeaderSockMock("data/header01.txt"))
        self.assertEqual(status, 101)
        self.assertEqual(header["connection"], "Upgrade")
        # header02.txt is intentionally malformed
        self.assertRaises(ws.WebSocketException, read_headers, HeaderSockMock("data/header02.txt"))

    def testTunnel(self):
        self.assertRaises(ws.WebSocketProxyException, _tunnel, HeaderSockMock("data/header01.txt"), "example.com", 80, ("username", "password"))
        self.assertRaises(ws.WebSocketProxyException, _tunnel, HeaderSockMock("data/header02.txt"), "example.com", 80, ("username", "password"))

    @unittest.skipUnless(TEST_WITH_INTERNET, "Internet-requiring tests are disabled")
    def testConnect(self):
        # Not currently testing an actual proxy connection, so just check whether proxy errors are raised. This requires internet for a DNS lookup
        self.assertRaises(ProxyTimeoutError, _start_proxied_socket, "wss://example.com", OptsList(), proxy_info(http_proxy_host="example.com", http_proxy_port="8080", proxy_type="socks4", timeout=1))
        self.assertRaises(ProxyTimeoutError, _start_proxied_socket, "wss://example.com", OptsList(), proxy_info(http_proxy_host="example.com", http_proxy_port="8080", proxy_type="socks4a", timeout=1))
        self.assertRaises(ProxyTimeoutError, _start_proxied_socket, "wss://example.com", OptsList(), proxy_info(http_proxy_host="example.com", http_proxy_port="8080", proxy_type="socks5", timeout=1))
        self.assertRaises(ProxyTimeoutError, _start_proxied_socket, "wss://example.com", OptsList(), proxy_info(http_proxy_host="example.com", http_proxy_port="8080", proxy_type="socks5h", timeout=1))
        self.assertRaises(TypeError, _get_addrinfo_list, None, 80, True, proxy_info(http_proxy_host="127.0.0.1", http_proxy_port="9999", proxy_type="http"))
        self.assertRaises(TypeError, _get_addrinfo_list, None, 80, True, proxy_info(http_proxy_host="127.0.0.1", http_proxy_port="9999", proxy_type="http"))
        self.assertRaises(ProxyConnectionError, connect, "wss://example.com", OptsList(), proxy_info(http_proxy_host="127.0.0.1", http_proxy_port=9999, proxy_type="socks4", timeout=1), None)
        self.assertRaises(socket.timeout, connect, "wss://google.com", OptsList(), proxy_info(http_proxy_host="8.8.8.8", http_proxy_port=9999, proxy_type="http", timeout=1), None)
        self.assertEqual(
            connect("wss://google.com", OptsList(), proxy_info(http_proxy_host="8.8.8.8", http_proxy_port=8080, proxy_type="http"), True),
            (True, ("google.com", 443, "/")))
        # The following test fails on Mac OS with a gaierror, not an OverflowError
        # self.assertRaises(OverflowError, connect, "wss://example.com", OptsList(), proxy_info(http_proxy_host="127.0.0.1", http_proxy_port=99999, proxy_type="socks4", timeout=2), False)

    @unittest.skipUnless(TEST_WITH_INTERNET, "Internet-requiring tests are disabled")
    @unittest.skipUnless(TEST_WITH_PROXY, "This test requires a HTTP proxy to be running on port 8899")
    def testProxyConnect(self):
        ws = websocket.WebSocket()
        ws.connect("ws://echo.websocket.org", http_proxy_host="127.0.0.1", http_proxy_port="8899", proxy_type="http")
        ws.send("Hello, Server")
        server_response = ws.recv()
        self.assertEqual(server_response, "Hello, Server")
        # self.assertEqual(_start_proxied_socket("wss://api.bitfinex.com/ws/2", OptsList(), proxy_info(http_proxy_host="127.0.0.1", http_proxy_port="8899", proxy_type="http"))[1], ("api.bitfinex.com", 443, '/ws/2'))
        self.assertEqual(_get_addrinfo_list("api.bitfinex.com", 443, True, proxy_info(http_proxy_host="127.0.0.1", http_proxy_port="8899", proxy_type="http")),
                         (socket.getaddrinfo("127.0.0.1", 8899, 0, socket.SOCK_STREAM, socket.SOL_TCP), True, None))
        self.assertEqual(connect("wss://api.bitfinex.com/ws/2", OptsList(), proxy_info(http_proxy_host="127.0.0.1", http_proxy_port=8899, proxy_type="http"), None)[1], ("api.bitfinex.com", 443, '/ws/2'))
        # TODO: Test SOCKS4 and SOCK5 proxies with unit tests

    @unittest.skipUnless(TEST_WITH_INTERNET, "Internet-requiring tests are disabled")
    def testSSLopt(self):
        ssloptions = {
            "cert_reqs": ssl.CERT_NONE,
            "check_hostname": False,
            "server_hostname": "ServerName",
            "ssl_version": ssl.PROTOCOL_TLS,
            "ciphers": "TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:\
                        TLS_AES_128_GCM_SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:\
                        ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384:\
                        ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:\
                        DHE-RSA-CHACHA20-POLY1305:ECDHE-ECDSA-AES128-GCM-SHA256:\
                        ECDHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA256:\
                        ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES256-SHA384:\
                        DHE-RSA-AES256-SHA256:ECDHE-ECDSA-AES128-SHA256:\
                        ECDHE-RSA-AES128-SHA256:DHE-RSA-AES128-SHA256:\
                        ECDHE-ECDSA-AES256-SHA:ECDHE-RSA-AES256-SHA",
            "ecdh_curve": "prime256v1"
        }
        ws_ssl1 = websocket.WebSocket(sslopt=ssloptions)
        ws_ssl1.connect("wss://api.bitfinex.com/ws/2")
        ws_ssl1.send("Hello")
        ws_ssl1.close()

        ws_ssl2 = websocket.WebSocket(sslopt={"check_hostname": True})
        ws_ssl2.connect("wss://api.bitfinex.com/ws/2")
        ws_ssl2.close

    def testProxyInfo(self):
        self.assertEqual(proxy_info(http_proxy_host="127.0.0.1", http_proxy_port="8080", proxy_type="http").proxy_protocol, "http")
        self.assertRaises(ProxyError, proxy_info, http_proxy_host="127.0.0.1", http_proxy_port="8080", proxy_type="badval")
        self.assertEqual(proxy_info(http_proxy_host="example.com", http_proxy_port="8080", proxy_type="http").proxy_host, "example.com")
        self.assertEqual(proxy_info(http_proxy_host="127.0.0.1", http_proxy_port="8080", proxy_type="http").proxy_port, "8080")
        self.assertEqual(proxy_info(http_proxy_host="127.0.0.1", http_proxy_port="8080", proxy_type="http").auth, None)
        self.assertEqual(proxy_info(http_proxy_host="127.0.0.1", http_proxy_port="8080", proxy_type="http", http_proxy_auth=("my_username123", "my_pass321")).auth[0], "my_username123")
        self.assertEqual(proxy_info(http_proxy_host="127.0.0.1", http_proxy_port="8080", proxy_type="http", http_proxy_auth=("my_username123", "my_pass321")).auth[1], "my_pass321")


if __name__ == "__main__":
    unittest.main()
