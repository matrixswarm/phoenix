from ..constraint.autogen_constraint import AutoGenConstraint
class DeploymentCompiler:

    def __init__(self, ir_map, root_gid):
        self.ir = ir_map
        self.root = root_gid
        self.certs = {}   # uid → signing/symmetric/connection_cert bundles

    def compile(self):
        agents_section = self._build_private_tree(self.root)
        return {
            "agents": agents_section,
            "certs": self.certs,
        }

    def _build_private_tree(self, gid):
        agent_ir = self.ir[gid]
        node = {
            "universal_id": agent_ir.universal_id,
            "name": agent_ir.name,
            "serial": agent_ir.node.get("serial"),
            "security-tag": agent_ir.node.get("security-tag"),
            "config": {},
            "children": []
        }

        # Commander Edition – integrate autogen certs and preserve connections
        node["connection"] = agent_ir.node.get("connection", {})  # keep what we already have

        for con in agent_ir.resolved.values():
            try:
                # Preserve existing connection block instead of overwriting
                editor = getattr(con, "handler", None)
                if editor and hasattr(editor, "is_connection") and editor.is_connection():
                    node["connection"].update(con.fields)
                    continue

                # Route certs & crypto bundles into certs section
                base = self.certs.setdefault(agent_ir.universal_id, {})
                if hasattr(con, "path") and con.path:
                    AutoGenConstraint.set_nested(base, con.path, con.fields)
                else:
                    base.update(con.fields)

            except Exception as e:
                print(f"[DEPLOY][WARN] Connection/cert injection error for {agent_ir.name}: {e}")

        for child_gid in agent_ir.children:
            node["children"].append(self._build_private_tree(child_gid))

        return node

    # -----------------------------
    def _private_security(self, agent_ir):
        cfg = {}
        sec = cfg.setdefault("security", {})
        for cir in agent_ir.resolved.values():
            if cir.category in ("signing", "symmetric_encryption"):
                sec.setdefault(cir.category, {}).update(cir.full)
        return cfg
