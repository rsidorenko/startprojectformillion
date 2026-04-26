"""Run safe MVP config doctor checks for runtime readiness profiles."""

from __future__ import annotations

import argparse
import os
from collections.abc import Mapping

from app.internal_admin.adm01_http_config import load_adm01_internal_http_config_from_env
from app.internal_admin.adm02_mutation_opt_in_config import load_adm02_ensure_access_opt_in_from_env
from app.runtime.telegram_webhook_ingress import _is_local_app_env
from app.security.config import ConfigurationError

_PROFILE_POLLING = "polling"
_PROFILE_WEBHOOK = "webhook"
_PROFILE_INTERNAL_ADMIN = "internal-admin"
_PROFILE_RETENTION = "retention"
_PROFILE_ALL = "all"
_SUPPORTED_PROFILES = {
    _PROFILE_POLLING,
    _PROFILE_WEBHOOK,
    _PROFILE_INTERNAL_ADMIN,
    _PROFILE_RETENTION,
    _PROFILE_ALL,
}
_TRUTHY_VALUES = {"1", "true", "yes"}
_FALSEY_VALUES = {"", "0", "false", "no"}
_DEFAULT_PROFILE = _PROFILE_ALL


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_VALUES


def _looks_like_postgres_dsn(raw: str) -> bool:
    return raw.startswith(("postgresql://", "postgres://"))


def _has_sslmode(raw: str) -> bool:
    return "sslmode=" in raw.lower()


def _env_value(env: Mapping[str, str], name: str) -> str:
    return env.get(name, "").strip()


def _check_polling_profile(env: Mapping[str, str]) -> list[str]:
    issues: list[str] = []
    bot_token = _env_value(env, "BOT_TOKEN")
    if not bot_token:
        issues.append("missing_bot_token")
    elif len(bot_token) < 10:
        issues.append("invalid_bot_token_shape")

    app_env = _env_value(env, "APP_ENV") or "development"
    database_url = _env_value(env, "DATABASE_URL")
    if database_url:
        if not _looks_like_postgres_dsn(database_url):
            issues.append("invalid_database_url_shape")
        elif not _is_local_app_env(app_env) and not _has_sslmode(database_url):
            issues.append("database_url_sslmode_required")
    return issues


def _check_webhook_profile(env: Mapping[str, str]) -> list[str]:
    issues: list[str] = []
    if not _is_truthy(env.get("TELEGRAM_WEBHOOK_HTTP_ENABLE")):
        issues.append("webhook_http_not_enabled")
        return issues

    app_env = _env_value(env, "APP_ENV") or "development"
    secret_token = _env_value(env, "TELEGRAM_WEBHOOK_SECRET_TOKEN")
    insecure_local_opt_in = _is_truthy(env.get("TELEGRAM_WEBHOOK_ALLOW_INSECURE_LOCAL"))
    if _is_local_app_env(app_env):
        if not secret_token and not insecure_local_opt_in:
            issues.append("webhook_insecure_local_opt_in_required")
    elif not secret_token:
        issues.append("webhook_secret_required")
    return issues


def _check_internal_admin_profile(env: Mapping[str, str]) -> list[str]:
    issues: list[str] = []
    try:
        adm01_cfg = load_adm01_internal_http_config_from_env(env)
    except ConfigurationError:
        return ["invalid_adm01_internal_http_config"]

    try:
        adm02_mutation_opt_in = load_adm02_ensure_access_opt_in_from_env(env)
    except ConfigurationError:
        return ["invalid_adm02_mutation_opt_in"]

    if adm01_cfg.enabled:
        allowlist = _env_value(env, "ADM01_INTERNAL_HTTP_ALLOWLIST")
        if not allowlist:
            issues.append("missing_adm01_internal_http_allowlist")
        bot_token = _env_value(env, "BOT_TOKEN")
        if not bot_token:
            issues.append("missing_bot_token")
        database_url = _env_value(env, "DATABASE_URL")
        if not database_url:
            issues.append("missing_database_url")

    if adm02_mutation_opt_in:
        if not adm01_cfg.enabled:
            issues.append("adm02_mutation_requires_internal_admin_http_enabled")
        allowlist = _env_value(env, "ADM01_INTERNAL_HTTP_ALLOWLIST")
        if not allowlist:
            issues.append("missing_adm01_internal_http_allowlist")
        if not _env_value(env, "DATABASE_URL"):
            issues.append("missing_database_url")
    return issues


def _check_retention_profile(env: Mapping[str, str]) -> list[str]:
    issues: list[str] = []
    retention_days = _env_value(env, "ADM02_AUDIT_RETENTION_DAYS")
    if retention_days:
        try:
            parsed = int(retention_days)
        except ValueError:
            return ["invalid_adm02_audit_retention_days"]
        if parsed <= 0:
            issues.append("invalid_adm02_audit_retention_days")

    delete_opt_in_raw = _env_value(env, "OPERATIONAL_RETENTION_DELETE_ENABLE")
    normalized = delete_opt_in_raw.lower()
    if normalized and normalized not in _TRUTHY_VALUES and normalized not in _FALSEY_VALUES:
        issues.append("invalid_operational_retention_delete_opt_in")
    return issues


def run_config_doctor(*, profile: str, env: Mapping[str, str] | None = None) -> tuple[bool, tuple[str, ...]]:
    effective_env: Mapping[str, str] = os.environ if env is None else env
    if profile not in _SUPPORTED_PROFILES:
        return False, ("unknown_profile",)

    checks = {
        _PROFILE_POLLING: _check_polling_profile,
        _PROFILE_WEBHOOK: _check_webhook_profile,
        _PROFILE_INTERNAL_ADMIN: _check_internal_admin_profile,
        _PROFILE_RETENTION: _check_retention_profile,
    }

    selected = (
        (_PROFILE_POLLING, _PROFILE_WEBHOOK, _PROFILE_INTERNAL_ADMIN, _PROFILE_RETENTION)
        if profile == _PROFILE_ALL
        else (profile,)
    )
    collected: list[str] = []
    seen: set[str] = set()
    for name in selected:
        for issue in checks[name](effective_env):
            if issue not in seen:
                collected.append(issue)
                seen.add(issue)
    return len(collected) == 0, tuple(collected)


def main(argv: list[str] | None = None, *, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default=_DEFAULT_PROFILE)
    args = parser.parse_args(argv)

    ok, issues = run_config_doctor(profile=args.profile.strip().lower(), env=env)
    if ok:
        print("mvp_config_doctor: ok")
        return 0
    print("mvp_config_doctor: fail")
    for issue in issues:
        print(f"issue_code={issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
