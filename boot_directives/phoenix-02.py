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
    "children": [  # MATRIX PROTECTION LAYER 4 SENTINELS
        # 4th SENTINEL WATCHES MATRIX, REST WATCH SENTINEL IN FRONT
        # ONLY WAY TO KILL MATRIX WOULD BE TO KILL THEM ALL, MATRIX INCLUSIVE, TAKING ANY COMBO OF 4 OUT DOES NOTHING
        {
            "universal_id": "guardian-1",
            "name": "sentinel",
            "app": "matrix-core",
            "filesystem": {},
            "config": {
                "matrix_secure_verified": 1,
                "ui": {
                    "agent_tree": {"emoji": "🛡️"},
                },
            },
            "children": [
                {
                    "universal_id": "guardian-2",
                    "name": "sentinel",
                    "app": "matrix-core",
                    "filesystem": {},
                    "config": {
                        "matrix_secure_verified": 1,
                        "ui": {
                            "agent_tree": {"emoji": "🛡️"},
                        },
                    },
                    "children": [
                        {
                            "universal_id": "guardian-3",
                            "name": "sentinel",
                            "app": "matrix-core",
                            "filesystem": {},
                            "config": {
                                "matrix_secure_verified": 1,
                                "ui": {
                                    "agent_tree": {"emoji": "🛡️"},
                                },
                            },
                            "children": [
                                {
                                    "universal_id": "guardian-4",
                                    "name": "sentinel",
                                    "app": "matrix-core",
                                    "filesystem": {},
                                    "config": {
                                        "matrix_secure_verified": 1,
                                        "watching": "the Queen",
                                        "universal_id_under_watch": "matrix",
                                        "ui": {
                                            "agent_tree": {"emoji": "🛡️"},
                                        },
                                    }
                                }
                            ]
                        }
                    ]
                }
            ]
        },
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
            "universal_id": "slack-it-out-1",
            "name": "slack_relay",
            "enabled": False,
            "tags": {
                "connection": {
                    "proto": "slack"
                },
            },
            "config": {

                "ui": {
                    "agent_tree": {"emoji": "💬"},
                },
                "service-manager": [{
                    "role": ["hive.alert@cmd_send_alert_msg"],
                    "scope": ["parent", "any"],
                }]
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
            "universal_id": "npc-simulator-1",
            "name": "npc_simulator",
            "app": "swarm-core",
            "enabled": False,
            "tags": {
                "packet_signing": {
                    "in": True,
                    "out": True
                }
            },
            "config": {
                "grid_size": 20,
                "npc_count": 100,
                "tick_interval_sec": 1,
                "ui": {
                    "agent_tree": {"emoji": "🎮", "icon": ":path_to_icon"},
                    "panel": [
                        "npc_simulator.gameboard",
                        "npc_simulator.config"
                    ],
                },
                "service-manager": [{
                    "role": [
                        "npc.swarm.control@cmd_control_npcs",
                        "npc.swarm.status@cmd_report_status",
                        "npc.swarm.stream.start@cmd_start_npc_stream",
                        "npc.swarm.stream.stop@cmd_stop_npc_stream"
                    ],
                    "scope": ["parent", "any"],
                    "priority": {
                        "npc.swarm.control": 1,
                        "npc.swarm.status": 1,
                        "npc.swarm.stream.start": 1,
                        "npc.swarm.stream.stop": 1,
                        "default": 10
                    },
                    "exclusive": False
                }]
            }
        },
        {
            "universal_id": "apache_watchdog-1",
            "name": "apache_watchdog",
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "🧭️"},
                },
                "check_interval_sec": 10,
                "service_name": "httpd",  # change to "httpd" for RHEL/CentOS
                "ports": [80, 443],
                "restart_limit": 3,
                "always_alert": 1,
                "alert_cooldown": 300,
                "alert_to_role": "hive.alert",
                "report_to_role": "hive.forensics.data_feed",
            },
        },
        {
            "universal_id": "mysql-red-phone",
            "name": "mysql_watchdog",
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "🛢️"},
                },
                "mysql_port": 3306,
                "socket_path": "/var/run/mysqld/mysqld.sock",
                "service_name": "mariadb",
                "check_interval_sec": 20,
                "restart_limit": 3,
                "alert_thresholds": {
                    "uptime_pct_min": 90,
                    "slow_restart_sec": 10
                },
                "alert_to_role": "hive.alert",
                "report_to_role": "hive.forensics.data_feed",
            }

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
            "universal_id": "discord-delta-5",
            "name": "discord_relay",
            "tags": {
                "connection": {
                    "proto": "discord"
                },
            },
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "💬"},
                    "panel": [
                        "discord_relay.security_2fa",
                    ],
                },
                "service-manager": [{
                    "role": ["hive.alert@cmd_send_alert_msg"],
                    "scope": ["parent", "any"],

                }]
            }
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
            }
            # It will automatically receive reports from agents using its role
        },
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
            }
        },
        {
            "universal_id": "nginx-sentinel",
            "name": "nginx_watchdog",
            "enabled": False,
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "🎉"},
                },
                "check_interval_sec": 10,
                "always_alert": 1,
                "restart_limit": 3,
                "service_name": "nginx",
                "ports": [85],
                "alert_cooldown": 300,
                "alert_to_role": "hive.alert",  # They both send alerts, but report_to_role - a little more
                "report_to_role": "hive.forensics.data_feed"
            }
        },
        {
            "universal_id": "redis-hammer",
            "name": "redis_watchdog",
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "🎭"},
                },
                "check_interval_sec": 10,
                "restart_limit": 3,
                "redis_port": 6379,
                "always_alert": 1,
                "socket_path": "/var/run/redis/redis-server.sock",
                "alert_to_role": "hive.alert",
                "report_to_role": "hive.forensics.data_feed",
                "service_name": "redis"
            }
            ,
            "children": []
        },
        {
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
        },
        {
            "universal_id": "wordpress-plugin-guard-1",
            "name": "wordpress_plugin_guard",
            "enabled": False,
            "tags": {
                "packet_signing": {"in": True, "out": True}
            },
            "config": {
                "ui": {
                    "agent_tree": {"emoji": "🧼"},
                    "panel": ["wordpress_plugin_guard.plugin_guard"]
                },
                "plugin_dir": "/var/www/html/wordpress/wp-content/plugins",
                "quarantine_dir": "/opt/quarantine/wp_plugins",
                "trusted_plugins_path": "/opt/swarm/guard/trusted_plugins.json",
                "enforce": False,
                "interval": 15,
                "restart_php_after_quarantine": False,
                "alert_to_role": "hive.alert",
                # "report_to_role": "hive.forensics.data_feed",
                "service-manager": [{
                    "role": [
                        "plugin.guard.snapshot@cmd_snapshot_plugins",
                        "plugin.guard.status@cmd_list_alert_status",
                        "plugin.guard.list_plugins@cmd_list_plugins",
                        "plugin.guard.snapshot_plugin@cmd_snapshot_plugin",
                        "plugin.guard.snapshot_untracked@cmd_snapshot_untracked",
                        "plugin.guard.disapprove_plugin@cmd_disapprove_plugin",
                        "plugin.guard.enforce@cmd_enforce",
                        "plugin.guard.restore_plugin@cmd_restore_plugin",
                        "plugin.guard.block@cmd_toggle_block",
                        "plugin.guard.quarantine@cmd_quarantine_plugin",
                        "plugin.guard.delete_quarantined@cmd_delete_quarantined_plugin"
                    ],
                    "scope": ["parent", "any"],
                    "priority": {"default": 10}
                }]
            }
        },
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
            }

        },
    ]
}