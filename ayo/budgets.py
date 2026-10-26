"""Durable, fail-closed authorization budgets, not invented provider invoices.

The operator must review a conservative maximum cost per bounded operation and
configure all limits. A committed reservation debits that full upper bound even
when a worker crashes or a provider result is ambiguous. No timeout automatically
refunds money or makes the same dispatch safe to retry. Provider billing and an
independent pricing review remain external requirements.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
import re
import time

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ayo.models import ProviderBudgetAccount, ProviderBudgetLock, ProviderUsageReservation
from ayo.provider_config import MODEL_INPUT_MAX_BYTES, model_budget_fingerprint, valid_model_id


class BudgetError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _positive(value, *, maximum=10**12):
    return type(value) is int and 0 < value <= maximum


@dataclass(frozen=True)
class BudgetPolicy:
    provider: str
    operation: str
    reservation_microusd: int
    request_limit_microusd: int
    provider_daily_limit_microusd: int
    scope_daily_limit_microusd: int
    request_call_limit: int
    provider_daily_call_limit: int
    scope_daily_call_limit: int
    policy_version: str
    policy_valid_until: int
    configuration_fingerprint: str = ''

    def __post_init__(self):
        if not isinstance(self.configuration_fingerprint, str) or (self.configuration_fingerprint and
                not re.fullmatch(r'[0-9a-f]{64}', self.configuration_fingerprint)):
            raise BudgetError('invalid_budget_input', 'Invalid reviewed provider configuration.')
        if not all(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,29}', value)
                   for value in (self.provider, self.operation)):
            raise BudgetError('invalid_budget_input', 'Invalid provider budget identity.')
        if not isinstance(self.policy_version, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', self.policy_version):
            raise BudgetError('invalid_budget_input', 'A reviewed provider budget version is required.')
        amounts = (self.reservation_microusd, self.request_limit_microusd,
                   self.provider_daily_limit_microusd, self.scope_daily_limit_microusd)
        calls = (self.request_call_limit, self.provider_daily_call_limit, self.scope_daily_call_limit)
        if not all(_positive(value) for value in amounts) or not all(_positive(value, maximum=10**7) for value in calls):
            raise BudgetError('invalid_budget_input', 'Budget limits must be positive bounded integers.')
        if not _positive(self.policy_valid_until) or self.reservation_microusd > min(amounts[1:]):
            raise BudgetError('invalid_budget_input', 'The reservation must fit every reviewed budget limit.')

    @classmethod
    def from_env(cls, provider, operation, *, environ=None, clock=time.time):
        env = os.environ if environ is None else environ
        if not isinstance(provider, str) or not isinstance(operation, str):
            raise BudgetError('budget_not_configured', 'Provider budget configuration is incomplete.')
        prefix = 'AYO_' + provider.upper() + '_'
        fields = {
            'reservation_microusd': prefix + operation.upper() + '_RESERVATION_MICROUSD',
            'request_limit_microusd': 'AYO_REQUEST_BUDGET_MICROUSD',
            'provider_daily_limit_microusd': prefix + 'DAILY_BUDGET_MICROUSD',
            'scope_daily_limit_microusd': prefix + 'SCOPE_DAILY_BUDGET_MICROUSD',
            'request_call_limit': 'AYO_REQUEST_CALL_LIMIT',
            'provider_daily_call_limit': prefix + 'DAILY_CALL_LIMIT',
            'scope_daily_call_limit': prefix + 'SCOPE_DAILY_CALL_LIMIT',
            'policy_valid_until': prefix + 'BUDGET_POLICY_VALID_UNTIL',
        }
        try:
            values = {field: int(env[name]) for field, name in fields.items()
                      if isinstance(env[name], str) and re.fullmatch(r'[0-9]{1,13}', env[name])}
            if len(values) != len(fields):
                raise ValueError
            if provider in {'gemini', 'claude'} and operation == 'analyze':
                actual_model = env['GEMINI_MODEL' if provider == 'gemini' else 'ANTHROPIC_MODEL']
                reviewed_model = env[prefix + 'BUDGET_MODEL']
                input_bytes = int(env[prefix + 'BUDGET_MAX_INPUT_BYTES'])
                output_tokens = int(env[prefix + 'BUDGET_MAX_OUTPUT_TOKENS'])
                actual_output = int(env.get('GEMINI_MAX_OUTPUT_TOKENS' if provider == 'gemini' else 'ANTHROPIC_MAX_OUTPUT_TOKENS', '1500'))
                actual_thinking = (env.get('GEMINI_THINKING_LEVEL', '') or 'provider_default') if provider == 'gemini' else 'provider_default'
                reviewed_thinking = env[prefix + 'BUDGET_THINKING_LEVEL'] if provider == 'gemini' else 'provider_default'
                if (not valid_model_id(actual_model) or actual_model != reviewed_model
                        or input_bytes != MODEL_INPUT_MAX_BYTES or not 64 <= output_tokens <= 4000 or output_tokens != actual_output
                        or type(env[prefix + 'BUDGET_MAX_INPUT_BYTES']) is not str
                        or type(env[prefix + 'BUDGET_MAX_OUTPUT_TOKENS']) is not str
                        or not re.fullmatch(r'[0-9]{1,6}', env[prefix + 'BUDGET_MAX_INPUT_BYTES'])
                        or not re.fullmatch(r'[0-9]{1,6}', env[prefix + 'BUDGET_MAX_OUTPUT_TOKENS'])
                        or reviewed_thinking not in {'provider_default', 'MINIMAL', 'LOW', 'MEDIUM', 'HIGH'}
                        or reviewed_thinking != actual_thinking):
                    raise ValueError
                values['configuration_fingerprint'] = model_budget_fingerprint(provider, actual_model,
                    input_bytes, output_tokens, None if reviewed_thinking == 'provider_default' else reviewed_thinking)
            policy = cls(provider=provider, operation=operation, policy_version=env[prefix + 'BUDGET_POLICY_VERSION'], **values)
        except (KeyError, ValueError, TypeError, BudgetError):
            raise BudgetError('budget_not_configured', 'Provider budget configuration is incomplete or invalid.') from None
        if policy.policy_valid_until <= clock():
            raise BudgetError('budget_policy_expired', 'Provider budget policy review has expired.')
        return policy


@dataclass(frozen=True)
class Reservation:
    id: str
    dispatched_now: bool


def _hash(*parts):
    return hashlib.sha256(json.dumps(parts, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', value):
        raise BudgetError('invalid_budget_input', 'A server-generated budget identity is required.')
    return value


def _usage(value):
    """Keep only bounded numeric counters, never provider bodies or prompt text."""
    if not isinstance(value, dict):
        return {}
    allowed = {'input_tokens', 'output_tokens', 'total_tokens', 'prompt_tokens',
               'completion_tokens', 'thoughts_tokens', 'cached_tokens', 'credits_used',
               'pages', 'searches', 'promptTokenCount', 'candidatesTokenCount',
               'totalTokenCount', 'thoughtsTokenCount', 'cachedContentTokenCount',
               'toolUsePromptTokenCount', 'cache_creation_input_tokens', 'cache_read_input_tokens'}
    return {key: number for key, number in value.items()
            if key in allowed and type(number) is int and 0 <= number <= 10**12}


class UsageLedger:
    def __init__(self, factory, clock=time.time):
        self.factory, self.clock = factory, clock

    @staticmethod
    def _lock(session):
        # The INSERT also takes SQLite's database write lock before any read.
        # In PostgreSQL, ON CONFLICT safely initializes create_all test schemas;
        # the following row lock serializes all budget decisions across workers.
        dialect = session.get_bind().dialect.name
        if dialect == 'postgresql':
            # Admission decisions cannot wait indefinitely behind another
            # worker. The caller sanitizes database failures and never dispatches.
            session.execute(text("SET LOCAL lock_timeout = '2000ms'"))
            session.execute(text("SET LOCAL statement_timeout = '5000ms'"))
        insert = {'postgresql': pg_insert, 'sqlite': sqlite_insert}.get(dialect)
        if insert is None:
            raise BudgetError('budget_not_configured', 'This database cannot enforce provider budgets.')
        session.execute(insert(ProviderBudgetLock).values(id=1).on_conflict_do_nothing(index_elements=['id']))
        session.scalar(select(ProviderBudgetLock).where(ProviderBudgetLock.id == 1).with_for_update())

    def reserve(self, *, scope_id, request_id, dispatch_id, policy):
        scope_id, request_id, dispatch_id = map(_identifier, (scope_id, request_id, dispatch_id))
        if not isinstance(policy, BudgetPolicy):
            raise BudgetError('invalid_budget_input', 'A reviewed provider budget policy is required.')
        now = self.clock()
        if policy.policy_valid_until <= now:
            raise BudgetError('budget_policy_expired', 'Provider budget policy review has expired.')
        day = int(now // 86400)
        scope_hash, request_hash = _hash('scope', scope_id), _hash('request', scope_id, request_id)
        dispatch_hash = _hash('dispatch', scope_id, request_id, dispatch_id)
        policy_hash = _hash(asdict(policy))
        buckets = [
            ('request', 0, _hash('request', scope_id, request_id), policy.request_limit_microusd, policy.request_call_limit),
            ('provider_day', day, _hash('provider_day', policy.provider, day), policy.provider_daily_limit_microusd, policy.provider_daily_call_limit),
            ('scope_day', day, _hash('scope_day', policy.provider, scope_id, day), policy.scope_daily_limit_microusd, policy.scope_daily_call_limit),
        ]
        with self.factory() as session:
            self._lock(session)
            existing = session.scalar(select(ProviderUsageReservation).where(ProviderUsageReservation.dispatch_hash == dispatch_hash))
            if existing is not None:
                if existing.policy_hash != policy_hash:
                    raise BudgetError('duplicate_dispatch_mismatch', 'An existing dispatch cannot change its budget policy.')
                # A reserved-but-never-sent crash remains uncertain. A duplicate
                # is never permission to send a second potentially billed call.
                result = Reservation(existing.id, False)
                session.commit()
                return result
            for kind, window_day, key_hash, limit, call_limit in buckets:
                account = session.get(ProviderBudgetAccount, key_hash)
                if account is None:
                    account = ProviderBudgetAccount(key_hash=key_hash, kind=kind, window_day=window_day,
                        limit_microusd=limit, call_limit=call_limit, reserved_microusd=0, calls=0, updated_at=now)
                    session.add(account)
                if account.limit_microusd != limit or account.call_limit != call_limit:
                    raise BudgetError('budget_policy_changed', 'Active budget limits differ from the reviewed policy.')
                if account.reserved_microusd + policy.reservation_microusd > limit or account.calls + 1 > call_limit:
                    raise BudgetError('budget_exceeded', 'The authorized provider usage budget is exhausted.')
                account.reserved_microusd += policy.reservation_microusd
                account.calls += 1
                account.updated_at = now
            record = ProviderUsageReservation(dispatch_hash=dispatch_hash, scope_hash=scope_hash,
                request_hash=request_hash, provider=policy.provider, operation=policy.operation,
                policy_version=policy.policy_version, policy_hash=policy_hash,
                reserved_microusd=policy.reservation_microusd, outcome='reserved', usage_json='{}', created_at=now)
            session.add(record)
            session.flush()
            result = Reservation(record.id, True)
            session.commit()  # The caller must dispatch only after this succeeds.
            return result

    def settle(self, reservation_id, *, outcome, usage=None):
        _identifier(reservation_id)
        if outcome not in {'succeeded', 'failed', 'uncertain'}:
            raise BudgetError('invalid_budget_input', 'Invalid provider usage outcome.')
        encoded = json.dumps(_usage(usage), sort_keys=True, separators=(',', ':'))
        with self.factory() as session:
            self._lock(session)
            row = session.get(ProviderUsageReservation, reservation_id)
            if row is None:
                raise BudgetError('invalid_budget_input', 'Provider usage reservation is unavailable.')
            if row.outcome != 'reserved':
                if row.outcome == outcome and row.usage_json == encoded:
                    session.commit()
                    return
                raise BudgetError('duplicate_dispatch_mismatch', 'A settled usage outcome cannot be replaced.')
            row.outcome, row.usage_json, row.settled_at = outcome, encoded, self.clock()
            # Deliberately never release or lower authorization debits here.
            session.commit()
