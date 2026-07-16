from agent_guard.config import AppConfig, load_config
from agent_guard.eval import run_eval_suite


def test_eval_suite_reports_security_and_reliability_metrics(tmp_path):
    base = load_config()
    config = AppConfig(
        project_root=tmp_path,
        sandbox_root=tmp_path / "sandbox",
        workspace_dir=tmp_path / "sandbox" / "workspace",
        data_dir=tmp_path / "sandbox" / "data",
        policies_path=base.policies_path,
        audit_log_path=tmp_path / "logs" / "audit.jsonl",
    )

    report = run_eval_suite(config, benchmark_iterations=20)

    assert report["suite"]["attack_cases"] >= 10
    assert report["suite"]["benign_cases"] >= 8
    assert report["suite"]["passed"] == report["suite"]["total_cases"]
    assert report["metrics"]["attack_block_rate"] == 1.0
    assert report["metrics"]["benign_success_rate"] == 1.0
    assert report["metrics"]["false_positive_rate"] == 0.0
    assert report["preflight_latency"]["p95_ms"] >= 0
    assert report["gate_overhead"]["overhead_p95_ms"] >= 0
