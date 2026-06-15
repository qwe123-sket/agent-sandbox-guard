"""攻击用例回归。"""

from attack_cases.test_attacks import ATTACK_CASES, run_attack_case


def test_attack_cases_regression():
    for case in ATTACK_CASES:
        result = run_attack_case(case)
        assert result["passed"], f"{case.name} 未达预期"
