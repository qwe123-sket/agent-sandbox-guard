#!/usr/bin/env python3
"""运行确定性 Harness 评测并输出可复现 JSON 报告。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent_guard.eval import run_eval_suite, write_report


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent Guard Harness 评测")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "harness_eval.json",
    )
    parser.add_argument("--iterations", type=int, default=500)
    args = parser.parse_args()

    report = run_eval_suite(benchmark_iterations=args.iterations)
    write_report(report, args.output)

    suite = report["suite"]
    metrics = report["metrics"]
    latency = report["preflight_latency"]
    overhead = report["gate_overhead"]
    print("Agent Guard Harness Eval")
    print(f"用例: {suite['passed']}/{suite['total_cases']} 通过")
    print(f"攻击拦截率: {_percent(metrics['attack_block_rate'])}")
    print(f"正常任务成功率: {_percent(metrics['benign_success_rate'])}")
    print(f"误拦率: {_percent(metrics['false_positive_rate'])}")
    print(
        "策略预检延迟: "
        f"P50={latency['p50_ms']:.4f}ms, P95={latency['p95_ms']:.4f}ms"
    )
    print(
        "本地只读工具 Gate 附加开销: "
        f"P50={overhead['overhead_p50_ms']:.4f}ms, "
        f"P95={overhead['overhead_p95_ms']:.4f}ms"
    )
    print(f"报告: {args.output}")

    if suite["passed"] != suite["total_cases"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
