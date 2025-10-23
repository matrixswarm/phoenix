########
######## THIS IS A TEMPLATE, IT'S NOT MEANT TO BE USED DIRECTLY. YOU LOAD THIS TEMPLATE INTO PHOENIX GUI (DIRECTIVE SECTION), AND USE IT AS A SUBSTRATE TO ASSEMBLE CRYPTOGRAPHIC PACKAGED DEPLOYMENTS.
########
matrix_directive = {
    "universal_id": "matrix",
    "name": "matrix",
    "tags": {
        "packet_signing": {
            "in": True,
            "out": True
        }
    },
    "ui": {
        "agent_tree": {"emoji": "🧬"},
    },
    "children": [
        {
            "universal_id": "matrix-https",
            "name": "matrix_https",
            "tags": {
                "packet_signing": {
                    "in": True,
                    "out": True
                },
                "connection": {
                    "proto": "https"
                },
                "connection_cert": {
                    "proto": "https"
                },
            },
            "config": {
                "service-manager": [],
                "role": ["hive.2fa@cmd_2fa_transport"],
                "ui": {
                    "agent_tree": {"emoji": "🌐"},
                    "panel": [
                        "matrix_https.config"
                    ],
                },

            }
        },

        {
            "universal_id": "websocket-relay",
            "name": "matrix_websocket",
            "tags": {
                "packet_signing": {
                    "in": True,
                    "out": True
                },
                "connection": {
                    "proto": "wss"
                },
                "connection_cert": {
                    "proto": "wss"
                }
            },
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "🛰️"},
                },
                "service-manager": [
                    {
                        "role": [
                            "hive.alert@cmd_send_alert_msg",
                            "hive.rpc@cmd_rpc_route"
                        ],
                        "scope": [
                            "parent",
                            "any"
                        ],
                        "priority": {
                            "hive.log.delivery": -1,
                            "hive.proxy.route": 5,
                            "default": 10
                        }
                    }]
            },
        },


        {
            "universal_id": "log_sentinel",
            "name": "log_sentinel",
            "tags": {
                "packet_signing": {
                    "in": True,
                    "out": True
                },
            },
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "📜️"},
                },
                "service-manager": [{
                    "role": ["hive.log@cmd_stream_log"],
                    "scope": ["parent", "any"],  # who it serves
                    "priority": {  # lower = more preferred
                        "hive.log.delivery": -1,
                        "hive.proxy.route": 5,
                        "default": 10
                    },
                }],

            },
        },
        {
            "universal_id": "terminal-1",
            "name": "terminal_streamer",
            "tags": {
                "packet_signing": {
                    "in": True,
                    "out": True
                }
            },
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "🐚"},
                    "panel": ["terminal_streamer.stream_viewer"]
                },
                "safe_shell_mode": True,
                "whitelist": ["uptime", "df -h", "free -m", "whoami", "top -b -n 1 -c",
                              "ps -eo pid,user,%cpu,%mem,etime,cmd --sort=-%cpu"],
                "service-manager": [
                    {
                        "role": ["terminal.stream.start@cmd_start_stream_terminal",
                                 "terminal.stream.stop@cmd_stop_stream_terminal",
                                 "terminal.allowed.list@cmd_get_allowed_commands"],
                        "scope": ["parent", "any"],
                        "priority": {
                            "hive.proxy.route": 5,
                            "default": 10
                        }
                    }
                ]
            }
        },
        {
            "universal_id": "invisible-man",
            "name": "ghost_wire",
            "enabled": False,
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "👻️"},
                },
                "tick_rate": 5,
                "watch_paths": [
                    "/etc/passwd",
                    "/etc/shadow",
                    "/root/.ssh",
                    "/var/www",
                    "/home"
                ],
                "command_patterns": [
                    "rm -rf",
                    "scp",
                    "curl",
                    "wget",
                    "nano /etc",
                    "vi /etc",
                    "vim /etc",
                    "sudo",
                    "su",
                    "chmod 777"
                ]
            }
        },
        {
            "universal_id": "gatekeeper",
            "name": "gatekeeper",
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "🚪"},
                },
                "log_path": "/var/log/auth.log",
                "maxmind_db": "GeoLite2-City.mmdb",
                "geoip_enabled": 1,
                "always_alert": 1,
                "alert_to_role": "hive.alert",  # They both send alerts, but report_to_role - a little more
                # "report_to_role": "hive.forensics.data_feed"
            }
            ,
            "children": []
        },

        {
            "universal_id": "forensic-detective-1",
            "name": "forensic_detective",
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "🕵️"},
                },
                "service-manager": [{
                    "role": ["hive.forensics.data_feed@cmd_ingest_status_report"],
                }],
                "oracle_analysis": {
                    "enable_oracle": 1,
                    "role": "hive.oracle"
                }
            },
            "children": [

                    {
                                # Our new, config-driven system health monitor
                                "universal_id": "system-health-1",
                                "name": "system_health",
                                "config": {
                                    "ui": {
                                        "agent_tree": {"emoji": "🖥️"},
                                    },
                                    "check_interval_sec": 60,
                                    "mem_threshold_percent": 90.0,  # Custom threshold
                                    "cpu_threshold_percent": 85.0,  # Custom threshold
                                    "disk_threshold_percent": 95.0,
                                    # It reports to the same data feed as the other watchdogs
                                    "report_to_role": "hive.forensics.data_feed",
                                }
                            },
                            {
                                "universal_id": "network-health-1",
                                "name": "network_health",
                                "config": {
                                    "ui": {
                                        "agent_tree": {"emoji": "📶"},
                                    },
                                    "check_interval_sec": 30,  # Check network status every 30 seconds
                                    "exclude_interfaces": [],  # List of interfaces to skip (e.g. ["lo"])
                                    "tx_threshold_mbps": 100,  # Warn if outbound rate exceeds 100 Mbps
                                    "rx_threshold_mbps": 100,  # Warn if inbound rate exceeds 100 Mbps
                                    "conn_threshold": 1000,  # Warn if active TCP/UDP conns > 1000
                                    "top_n_procs": 5,  # Include top 5 process hogs in report
                                    "report_to_role": "hive.forensics.data_feed",
                                },
                                "children": [
{
            "universal_id": "golden-child-4",
            "name": "oracle",
            "tags": {
                "connection": {"proto": "openai"}
            },
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "🔮"},
                },
                "service-manager": [{
                    "role": ["hive.oracle@cmd_msg_prompt", "external.gateway.config@cmd_external_gateway_config"],
                }]
            },

    "children": [{
            "universal_id": "telegram-bot-father-2",
            "name": "telegram_relay",
            "tags": {
                "connection": {
                    "proto": "telegram"
                },
            },
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "📡"},
                },
                "service-manager": [{
                    "role": [
                        "comm",
                        "comm.security",
                        "comm.*",
                        "hive.alert@cmd_send_alert_msg"
                    ],
                    "scope": ["parent", "any"],
                    "auth": {"sig": True},
                    "priority": 10,
                    "exclusive": False
                }]
            }
        },]

},

                                ]
                            },

            ]
        },






    ]
}