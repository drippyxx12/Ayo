"""Server-scoped, durable reservations at the chargeable dispatch boundary.

No prices are inferred here. Reviewed conservative upper bounds are debited
before dispatch and held even if a worker crashes or the provider times out.
The debit is a budget reservation, never a provider invoice or measured spend.
"""
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import secrets
from sqlalchemy.exc import SQLAlchemyError

from ayo.budgets import BudgetError, BudgetPolicy, UsageLedger


@dataclass
class _Scope:
    ledger: UsageLedger
    scope_id: str
    request_id: str
    dispatch_prefix: str
    sequence: int = 0


@dataclass
class OperationUsage:
    usage: dict[str, int] = field(default_factory=dict)


_active: ContextVar[_Scope | None] = ContextVar('ayo_provider_budget', default=None)


def _storage_failure():
    return BudgetError('budget_storage_unavailable', 'Persistent provider budget storage is unavailable; no further dispatch is authorized.')


def _settle(ledger, reservation_id, *, outcome, usage):
    try:
        ledger.settle(reservation_id, outcome=outcome, usage=usage)
    except SQLAlchemyError:
        raise _storage_failure() from None


@contextmanager
def budget_context(factory, *, scope_id: str, request_id: str, dispatch_prefix: str | None = None):
    """Only trusted HTTP/worker code supplies identity; no model/browser IDs."""
    scope = _Scope(UsageLedger(factory), scope_id, request_id, dispatch_prefix or secrets.token_hex(16))
    token = _active.set(scope)
    try:
        yield
    finally:
        _active.reset(token)


@asynccontextmanager
async def metered_operation(provider: str, operation: str):
    """Reserve in its own committed transaction before any chargeable POST.

    Each dispatch is distinct. Re-entering the same worker-attempt sequence
    refuses dispatch rather than accidentally charging the same operation twice.
    No database transaction remains open during provider network I/O.
    """
    scope = _active.get()
    if scope is None:
        raise BudgetError('budget_not_configured', 'Provider dispatch requires a persistent server budget context.')
    policy = BudgetPolicy.from_env(provider, operation)
    scope.sequence += 1
    dispatch_id = f'{scope.dispatch_prefix}:{scope.sequence}:{provider}:{operation}'
    try:
        reservation = scope.ledger.reserve(scope_id=scope.scope_id, request_id=scope.request_id,
                                          dispatch_id=dispatch_id, policy=policy)
    except SQLAlchemyError:
        raise _storage_failure() from None
    if not reservation.dispatched_now:
        raise BudgetError('dispatch_already_reserved', 'This dispatch was already reserved; reconcile its outcome before retrying.')
    record = OperationUsage()
    try:
        yield record
    except BaseException:
        # An error is not proof that an accepted provider operation was free.
        # Keep the full debit; cancellation/process loss is uncertain as well.
        _settle(scope.ledger, reservation.id, outcome='uncertain', usage=record.usage)
        raise
    else:
        _settle(scope.ledger, reservation.id, outcome='succeeded', usage=record.usage)
