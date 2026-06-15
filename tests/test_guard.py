import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_guard.config import load_config, load_policies
from agent_guard.guard import PermissionGuard
from agent_guard.security import PolicyViolation


def test_readonly_cannot_delete(tmp_path):
    config = load_config()
    policies = load_policies(config.policies_path)
    guard = PermissionGuard(
        config=config,
        policies=policies,
        role="readonly",
        session_id="unit-delete",
    )
    try:
        guard.execute("delete_file", {"path": "a.txt"})
        assert False, "应当被拒绝"
    except PolicyViolation:
        pass


def test_path_traversal_blocked():
    config = load_config()
    policies = load_policies(config.policies_path)
    guard = PermissionGuard(
        config=config,
        policies=policies,
        role="operator",
        session_id="unit-traversal",
    )
    decision = guard.preflight("read_file", {"path": "../../etc/passwd"})
    assert not decision.allowed
