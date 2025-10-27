CERT_INJECTION_MAP = {
    "packet_signing": {
        "target": ["config", "security", "signing"],
        "fields": {
            "in": ["remote_pubkey"],
            "out": ["privkey"],
        },
        "include_serial": True
    },
    "symmetric_encryption": {
        "target": ["config", "security", "symmetric_encryption"],
        "fields": {
            "key": None,
            "type": "aes"
        },
        "include_serial": False
    },
    "connection_cert": {
        "target": ["config", "security", "connection"],
        "fields": {
            "server_cert": ["cert", "key", "serial", "spki_pin"],
            "client_cert": ["cert", "key", "serial", "spki_pin"],
            "ca_root": ["cert", "key", "serial"]
        },
        "proto_required": ["https", "wss"]
    },
    "connection": {
        'wss':{
            "target": ["config"],
            "fields": ["port"]
        },
        'https':{
            "target": ["config"],
            "fields": ["port"]
        },
        'discord':{
            "target": ["config"],
            "fields": ["bot_token", "channel_id"],
        },
        'telegram':{
            "target": ["config"],
            "fields": ["bot_token", "chat_id"],
        },
        'openai': {
            "target": ["config"],
            "fields": ["api_key"],
        },
        "slack": {
            "target": ["config"],
            "fields": ["webhook_url"],
        },
    },

}