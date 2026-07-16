from __future__ import annotations

import json
import math
import statistics
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from agent_guard.config import AppConfig, load_config, load_policies
from agent_guard.eval.cases import ALL_CASES, ATTACK_CASES, BENIGN_CASES, EvalCase
from agent_guard.guard import PermissionGuard
from agent_guard.harness import HarnessConfig, MockPlanner, run_mock_harness
from agent_guard.sandbox import filesystem
from agent_guard.security import HITLController


@dataclass(frozen=True)
class CaseResult:
    name: str
    category: str
    expected_blocked: bool
    was_blocked: bool
    had_error: bool
    passed: bool
    duration_ms: float


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _prepare_sandbox(config: AppConfig) -> None:
    config.workspace_dir.mkdir(parents=True, exist_ok=True)
    (config.workspace_dir / "seed.txt").write_text(
        "公开测试文件", encoding="utf-8"
    )
    (config.workspace_dir / "delete_me.txt").write_text(
        "待删除测试文件", encoding="utf-8"
    )


def _run_case(case: EvalCase, config: AppConfig, policies: dict) -> CaseResult:
    if case.name == "admin_delete_approved":
        (config.workspace_dir / "delete_me.txt").write_text(
            "待删除测试文件", encoding="utf-8"
        )

    guard = PermissionGuard(
        config=config,
        policies=policies,
        role=case.role,
        session_id=f"eval-{case.name}-{uuid.uuid4().hex[:6]}",
        hitl=HITLController(auto_approve=case.auto_approve_hitl),
    )
    result = run_mock_harness(
        guard,
        MockPlanner(case.calls),
        HarnessConfig(max_tool_calls=8),
    )
    tool_events = [
        event for event in result["trace"] if event.get("role") == "tool"
    ]
    was_blocked = any(event.get("status") == "blocked" for event in tool_events)
    had_error = any(event.get("status") == "error" for event in tool_events)
    if case.expect_blocked:
        passed = was_blocked
    else:
        passed = not was_blocked and not had_error and len(tool_events) == len(case.calls)

    return CaseResult(
        name=case.name,
        category=case.category,
        expected_blocked=case.expect_blocked,
        was_blocked=was_blocked,
        had_error=had_error,
        passed=passed,
        duration_ms=float(result["duration_ms"]),
    )


def benchmark_preflight(
    config: AppConfig,
    policies: dict,
    iterations: int = 500,
) -> dict[str, float | int]:
    guard = PermissionGuard(
        config=config,
        policies=policies,
        role="readonly",
        session_id="eval-preflight-benchmark",
        hitl=HITLController(auto_approve=True),
    )
    samples: list[float] = []
    for _ in range(iterations):
        started = perf_counter()
        decision = guard.preflight("list_files", {"directory": "."})
        samples.append((perf_counter() - started) * 1000)
        if not decision.allowed:
            raise RuntimeError("基准使用的合法调用被策略拒绝")

    return {
        "iterations": iterations,
        "mean_ms": round(statistics.fmean(samples), 4),
        "p50_ms": round(_percentile(samples, 0.50), 4),
        "p95_ms": round(_percentile(samples, 0.95), 4),
        "max_ms": round(max(samples), 4),
    }


def benchmark_gate_overhead(
    config: AppConfig,
    policies: dict,
    iterations: int = 500,
) -> dict[str, float | int]:
    """比较同一本地只读工具经 Gate 与直接执行的耗时差。"""
    guard = PermissionGuard(
        config=config,
        policies=policies,
        role="readonly",
        session_id="eval-gate-overhead",
        hitl=HITLController(auto_approve=True),
    )
    overhead_samples: list[float] = []
    guarded_samples: list[float] = []
    for _ in range(iterations):
        direct_started = perf_counter()
        direct_result = filesystem.list_files(guard.sandbox, ".")
        direct_ms = (perf_counter() - direct_started) * 1000

        guarded_started = perf_counter()
        guarded_result = guard.execute("list_files", {"directory": "."})
        guarded_ms = (perf_counter() - guarded_started) * 1000
        if guarded_result != direct_result:
            raise RuntimeError("Gate 前后工具结果不一致")

        guarded_samples.append(guarded_ms)
        overhead_samples.append(max(0.0, guarded_ms - direct_ms))

    return {
        "iterations": iterations,
        "guarded_p50_ms": round(_percentile(guarded_samples, 0.50), 4),
        "guarded_p95_ms": round(_percentile(guarded_samples, 0.95), 4),
        "overhead_p50_ms": round(_percentile(overhead_samples, 0.50), 4),
        "overhead_p95_ms": round(_percentile(overhead_samples, 0.95), 4),
    }


def run_eval_suite(
    config: AppConfig | None = None,
    *,
    benchmark_iterations: int = 500,
) -> dict:
    config = config or load_config()
    policies = load_policies(config.policies_path)
    _prepare_sandbox(config)

    results = [_run_case(case, config, policies) for case in ALL_CASES]
    attacks = [result for result in results if result.category == "attack"]
    benign = [result for result in results if result.category == "benign"]

    blocked_attacks = sum(result.was_blocked for result in attacks)
    successful_benign = sum(result.passed for result in benign)
    blocked_benign = sum(result.was_blocked for result in benign)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suite": {
            "total_cases": len(results),
            "attack_cases": len(ATTACK_CASES),
            "benign_cases": len(BENIGN_CASES),
            "passed": sum(result.passed for result in results),
        },
        "metrics": {
            "attack_block_rate": round(blocked_attacks / len(attacks), 4),
            "benign_success_rate": round(successful_benign / len(benign), 4),
            "false_positive_rate": round(blocked_benign / len(benign), 4),
        },
        "preflight_latency": benchmark_preflight(
            config, policies, benchmark_iterations
        ),
        "gate_overhead": benchmark_gate_overhead(
            config, policies, benchmark_iterations
        ),
        "cases": [asdict(result) for result in results],
    }
    return report


def write_report(report: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
