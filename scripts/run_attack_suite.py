#!/usr/bin/env python3
"""批量运行攻击用例并输出简要报告。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from attack_cases.test_attacks import ATTACK_CASES, run_attack_case


def main() -> None:
    print("Agent 工具调用权限边界 — 攻击用例回归\n")
    passed = 0
    for case in ATTACK_CASES:
        result = run_attack_case(case, auto_approve_hitl=False)
        status = "PASS" if result["passed"] else "FAIL"
        if result["passed"]:
            passed += 1
        print(f"[{status}] {case.name}: {case.description}")
        if not result["passed"]:
            for msg in result["trace"]:
                print(f"       -> {msg.get('content')}")

    print(f"\n合计: {passed}/{len(ATTACK_CASES)} 通过")


if __name__ == "__main__":
    main()
