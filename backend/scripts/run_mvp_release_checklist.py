"""Static MVP release readiness checklist (artifacts/docs markers only)."""

from __future__ import annotations

from pathlib import Path

_REQUIRED_SCRIPTS = (
    "scripts/run_mvp_release_preflight.py",
    "scripts/run_mvp_config_doctor.py",
    "scripts/run_postgres_mvp_smoke_local.py",
)
_REQUIRED_DOCS = (
    "docs/mvp_release_readiness_runbook.md",
    "docs/postgres_mvp_smoke_runbook.md",
    "docs/telegram_access_resend_runbook.md",
    "docs/admin_support_internal_read_gate_runbook.md",
)
_RELEASE_RUNBOOK_MARKERS = (
    "mvp_release_preflight: ok",
    "mvp_config_doctor: ok",
    "/healthz",
    "/readyz",
    "ADM-01",
    "ADM-02",
    "dry-run",
    "OPERATIONAL_RETENTION_DELETE_ENABLE",
    "public billing ingress",
    "provider SDK",
    "real credential/config delivery",
)
_WEBHOOK_DOC_MARKERS = (
    "TELEGRAM_WEBHOOK_SECRET_TOKEN",
    "TELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL",
)
_ADMIN_DOC_MARKERS = (
    "ADM02_ENSURE_ACCESS_ENABLE",
    "audit",
    "readback",
)
_SMOKE_DOC_MARKERS = (
    "python scripts/run_mvp_release_preflight.py",
    "python scripts/run_postgres_mvp_smoke_local.py",
    "no real Docker smoke",
)


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _missing_file_issue_code(rel_path: str) -> str:
    lowered = rel_path.replace("\\", "/").lower()
    if "run_mvp_release_preflight.py" in lowered:
        return "missing_preflight_script"
    if "run_mvp_config_doctor.py" in lowered:
        return "missing_config_doctor_script"
    if "run_postgres_mvp_smoke_local.py" in lowered:
        return "missing_local_smoke_script"
    if "mvp_release_readiness_runbook.md" in lowered:
        return "missing_release_runbook"
    if "postgres_mvp_smoke_runbook.md" in lowered:
        return "missing_smoke_runbook"
    if "telegram_access_resend_runbook.md" in lowered:
        return "missing_webhook_runbook"
    if "admin_support_internal_read_gate_runbook.md" in lowered:
        return "missing_admin_runbook"
    return "missing_required_artifact"


def _missing_marker_issue_code(group: str) -> str:
    if group == "release_runbook":
        return "missing_release_runbook_marker"
    if group == "webhook_doc":
        return "missing_webhook_policy_doc"
    if group == "admin_doc":
        return "missing_adm02_policy_doc"
    if group == "smoke_doc":
        return "missing_smoke_separation_doc"
    return "missing_required_marker"


def run_release_checklist(*, base_dir: Path | None = None) -> tuple[bool, tuple[str, ...]]:
    root = _backend_dir() if base_dir is None else base_dir
    issues: list[str] = []
    seen: set[str] = set()

    def _append_issue(code: str) -> None:
        if code not in seen:
            issues.append(code)
            seen.add(code)

    for rel in (*_REQUIRED_SCRIPTS, *_REQUIRED_DOCS):
        if not (root / rel).exists():
            _append_issue(_missing_file_issue_code(rel))

    release_runbook = root / "docs/mvp_release_readiness_runbook.md"
    telegram_doc = root / "docs/telegram_access_resend_runbook.md"
    admin_doc = root / "docs/admin_support_internal_read_gate_runbook.md"
    smoke_doc = root / "docs/postgres_mvp_smoke_runbook.md"

    if release_runbook.exists():
        body = release_runbook.read_text(encoding="utf-8")
        if any(marker not in body for marker in _RELEASE_RUNBOOK_MARKERS):
            _append_issue(_missing_marker_issue_code("release_runbook"))

    if telegram_doc.exists():
        body = telegram_doc.read_text(encoding="utf-8")
        if any(marker not in body for marker in _WEBHOOK_DOC_MARKERS):
            _append_issue(_missing_marker_issue_code("webhook_doc"))

    if admin_doc.exists():
        body = admin_doc.read_text(encoding="utf-8")
        if any(marker not in body for marker in _ADMIN_DOC_MARKERS):
            _append_issue(_missing_marker_issue_code("admin_doc"))

    if smoke_doc.exists():
        body = smoke_doc.read_text(encoding="utf-8")
        if any(marker not in body for marker in _SMOKE_DOC_MARKERS):
            _append_issue(_missing_marker_issue_code("smoke_doc"))

    return len(issues) == 0, tuple(issues)


def main() -> int:
    ok, issues = run_release_checklist()
    if ok:
        print("mvp_release_checklist: ok")
        return 0
    print("mvp_release_checklist: fail")
    for issue in issues:
        print(f"issue_code={issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
