from app.services.graph.ast_parser import ASTParser


def test_ast_parser_python():
    parser = ASTParser()
    code = """
import os

class AuthManager:
    def login(self):
        pass
        
def verify():
    pass
"""
    nodes, edges = parser.parse_file(code, "auth.py", "python")

    assert len(nodes) >= 3  # AuthManager, login, verify
    node_names = [n.name for n in nodes]
    assert "AuthManager" in node_names
    assert "login" in node_names
    assert "verify" in node_names

    # Test edges (module or class -> DEFINES -> login)
    defines_edge = next(
        (e for e in edges if e.edge_type == "defines" and "login" in e.target_qualified_name), None
    )
    assert defines_edge is not None
