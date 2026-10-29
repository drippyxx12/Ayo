"""Research history and correction-review work over immutable saved reports.

This module never fetches a URL, asks a model, changes a report, or establishes
business ownership. All access is scoped to the caller's selected workspace.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from datetime import date, datetime, timezone
from decimal import Decimal
import re
import time
from urllib.parse import urlencode, urlsplit

from sqlalchemy import func, or_, select

from ayo.identity import IdentityError, IdentityService
from ayo.merchant_models import Task
from ayo.merchant_work import TaskService, text_value
from ayo.models import AuditEvent, ResearchReportRecord, User
from ayo.research import ResearchReport
from ayo.website_research import normalize_public_url

FRESHNESS_DAYS = 14
PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
REPORT_ID = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
CORRECTION_REASONS = {'inaccurate': 'Inaccurate statement', 'outdated': 'Outdated information',
                      'wrong_business': 'Wrong business identity', 'missing_context': 'Missing context'}


def _invalid(message):
    return IdentityError('invalid_research_query', message, 400)


def canonical_target(value: str) -> str:
    """A syntax-only exact target key; never infer an organization from a host.

    Preserve paths and numeric profile identity. Common www/http aliases and a
    trailing slash are normalized for history, not as proof of a redirect.
    """
    from ayo.merchant_evidence import OWNER_TARGET, INPUT_TARGET
    if isinstance(value, str) and (OWNER_TARGET.fullmatch(value) or INPUT_TARGET.fullmatch(value)):
        return value
    try:
        parsed = urlsplit(normalize_public_url(value))
    except (ValueError, TypeError) as exc:
        raise _invalid('Enter a valid public target URL.') from exc
    host = (parsed.hostname or '').removeprefix('www.')
    if host == 'm.facebook.com':
        host = 'facebook.com'
    # Preserve explicitly non-default protocol/port combinations.
    if parsed.port and ((parsed.scheme == 'http' and parsed.port != 80) or
                        (parsed.scheme == 'https' and parsed.port != 443)):
        host += ':' + str(parsed.port)
    return host + (parsed.path.rstrip('/') or '/') + ('?' + parsed.query if parsed.query else '')


def _identifier(value):
    if not isinstance(value, str) or not REPORT_ID.fullmatch(value):
        raise _invalid('Choose a saved report using its report identifier.')
    return value


@dataclass(frozen=True)
class LibraryFilters:
    q: str = ''
    target: str = ''
    status: str = ''
    freshness: str = ''
    date_from: str = ''
    date_to: str = ''
    page: int = 1
    page_size: int = PAGE_SIZE

    @classmethod
    def parse(cls, values):
        allowed = set(cls.__dataclass_fields__)
        if set(values) - allowed:
            raise _invalid('An unsupported research filter was supplied.')
        data = {}
        for key in ('q', 'target', 'status', 'freshness', 'date_from', 'date_to'):
            raw = values.get(key, '')
            if not isinstance(raw, str) or any(ord(c) < 32 or ord(c) == 127 for c in raw):
                raise _invalid('Research filters must contain plain text.')
            data[key] = raw.strip()
        if len(data['q']) > 120 or len(data['target']) > 2048:
            raise _invalid('Search is limited to 120 characters and target URLs to 2048 characters.')
        if data['target']:
            canonical_target(data['target'])
        if data['status'] not in {'', 'PARTIAL', 'SUCCEEDED'}:
            raise _invalid('Choose a saved-report status.')
        if data['freshness'] not in {'', 'fresh', 'stale', 'unknown'}:
            raise _invalid('Choose fresh, stale or unknown evidence freshness.')
        for key in ('date_from', 'date_to'):
            if data[key]:
                try:
                    if len(data[key]) != 10 or date.fromisoformat(data[key]).isoformat() != data[key]:
                        raise ValueError()
                except ValueError as exc:
                    raise _invalid('Use calendar dates in YYYY-MM-DD format.') from exc
        if data['date_from'] and data['date_to'] and data['date_from'] > data['date_to']:
            raise _invalid('The start date must be on or before the end date.')
        for key, default, maximum in (('page', 1, 100000), ('page_size', PAGE_SIZE, MAX_PAGE_SIZE)):
            raw = values.get(key, default)
            if isinstance(raw, bool) or not re.fullmatch(r'[0-9]{1,6}', str(raw)) or not 1 <= int(raw) <= maximum:
                raise _invalid('Page must be positive; show between 1 and 50 reports per page.')
            data[key] = int(raw)
        return cls(**data)

    def query(self, **changes):
        data = {key: getattr(self, key) for key in self.__dataclass_fields__}
        data.update(changes)
        return urlencode({key: value for key, value in data.items() if value != ''})


def source_freshness(captured_at, now):
    """Future timestamps are unknown, rather than evidence of fresh coverage."""
    age = now - captured_at.timestamp()
    if age < 0:
        return 'unknown'
    return 'stale' if age >= FRESHNESS_DAYS * 86400 else 'fresh'


def report_freshness(report, now):
    values = [source_freshness(source.retrieved_at, now) for source in report.source_documents]
    if not values or 'unknown' in values:
        return 'unknown'
    return 'stale' if 'stale' in values else 'fresh'


def _citations(evidence_ids, sources):
    ids = tuple(evidence_ids)
    available = {source.id for source in sources}
    missing = tuple(value for value in ids if value not in available)
    numbers = {source.id: number for number, source in enumerate(sources, 1)}
    return {'ids': ids, 'missing': missing,
            'links': tuple({'id': value, 'number': numbers.get(value)} for value in ids),
            'status': 'missing' if missing else 'linked' if ids else 'uncited'}


def _redact(value, field=None):
    # Evidence identity must survive redaction exactly, even if an opaque source
    # ID happens to look like a phone number. Never rewrite a hash or citation.
    if field in {'id', 'report_id', 'evidence_ids', 'source_hash', 'html_source_hash',
                 'created_at', 'retrieved_at', 'generated_at', 'observed_at',
                 'listed_price', 'schema', 'policy_version'}:
        return value
    if isinstance(value, str):
        value = re.sub(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', '[email redacted]', value, flags=re.I)
        return re.sub(r'(?<!\w)\+?\d[\d ()-]{7,}\d(?!\w)', '[phone redacted]', value)
    if isinstance(value, dict):
        return {key: _redact(item, key) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_redact(item) for item in value]
    return value


class ResearchWorkspace:
    def __init__(self, session, clock=time.time):
        self.session, self.clock = session, clock

    def _scope(self, user_id, business_id):
        IdentityService(self.session, self.clock).require_membership(user_id, business_id)

    def _saved(self, business_id):
        return select(ResearchReportRecord).where(
            ResearchReportRecord.business_id == business_id,
            ResearchReportRecord.owner_user_id.is_not(None),
            ResearchReportRecord.status.in_(['PARTIAL', 'SUCCEEDED']),
            ResearchReportRecord.expires_at.is_(None),
            ResearchReportRecord.anonymous_session_hash.is_(None),
        )

    def _load(self, user_id, business_id, report_id):
        self._scope(user_id, business_id)
        row = self.session.scalar(self._saved(business_id).where(ResearchReportRecord.id == _identifier(report_id)))
        if row is None:
            raise IdentityError('report_unavailable', 'Saved research not found in this workspace.', 404)
        try:
            report = ResearchReport.model_validate_json(row.report_json)
            if report.analysis_status == 'pending' or report.status != row.status:
                raise ValueError('Unpublished or mismatched report')
        except ValueError as exc:
            raise IdentityError('report_unavailable', 'This saved evidence record is unavailable.', 409) from exc
        return row, report

    def library(self, user_id, business_id, filters=None):
        self._scope(user_id, business_id)
        filters = LibraryFilters.parse({}) if filters is None else LibraryFilters.parse(
            {key: getattr(filters, key) for key in filters.__dataclass_fields__})
        base = self._saved(business_id)
        total = self.session.scalar(select(func.count()).select_from(base.subquery()))
        query = base
        if filters.q:
            escaped = filters.q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            query = query.where(or_(ResearchReportRecord.title.ilike('%' + escaped + '%', escape='\\'),
                                   ResearchReportRecord.target_url.ilike('%' + escaped + '%', escape='\\')))
        if filters.status:
            query = query.where(ResearchReportRecord.status == filters.status)
        if filters.date_from:
            query = query.where(ResearchReportRecord.created_at >= datetime.combine(
                date.fromisoformat(filters.date_from), datetime.min.time(), timezone.utc).timestamp())
        if filters.date_to:
            # A strict next-day bound works for subsecond records and UTC dates.
            end = datetime.combine(date.fromisoformat(filters.date_to), datetime.min.time(), timezone.utc).timestamp()
            query = query.where(ResearchReportRecord.created_at < end + 86400)
        query = query.order_by(ResearchReportRecord.created_at.desc(), ResearchReportRecord.id.desc())
        # Freshness and canonical identity belong to validated retained evidence,
        # not the latest request time or a database-specific JSON expression.
        # Stream in bounded batches; return at most page_size full record cards.
        matched = unreadable = source_count = partial_count = stale_count = 0
        items, targets = [], set()
        now = self.clock()
        start = (filters.page - 1) * filters.page_size
        for row in self.session.scalars(query.execution_options(yield_per=100)):
            try:
                report = ResearchReport.model_validate_json(row.report_json)
                if report.analysis_status == 'pending' or row.status != report.status:
                    raise ValueError()
                target = canonical_target(report.target_url)
            except ValueError:
                unreadable += 1
                continue
            freshness = report_freshness(report, now)
            if filters.target and target != canonical_target(filters.target):
                continue
            if filters.freshness and freshness != filters.freshness:
                continue
            targets.add(target)
            source_count += len(report.source_documents)
            partial_count += report.status == 'PARTIAL'
            stale_count += freshness == 'stale'
            if start <= matched < start + filters.page_size:
                items.append({'id': row.id, 'title': report.business_name, 'origin': report.origin, 'target_url': report.target_url,
                    'canonical_target': target, 'status': report.status, 'freshness': freshness,
                    'analysis_status': report.analysis_status, 'created_at': self._time(row.created_at),
                    'source_count': len(report.source_documents), 'claim_count': len(report.claims),
                    'recommendation_count': len(report.opportunities) + (len(report.analysis.recommendations) if report.analysis else 0)})
            matched += 1
        return {'total': total, 'matched': matched, 'items': items, 'page': filters.page,
                'page_size': filters.page_size, 'page_count': max(1, (matched + filters.page_size - 1) // filters.page_size),
                'unreadable': unreadable, 'source_count': source_count, 'partial_count': partial_count,
                'stale_count': stale_count, 'target_count': len(targets), 'freshness_days': FRESHNESS_DAYS,
                'checked_at': self._time(now), 'filters': filters}

    @staticmethod
    def _time(value):
        return datetime.fromtimestamp(value, timezone.utc).strftime('%d %b %Y · %H:%M UTC')

    def _history(self, business_id, target):
        query = self._saved(business_id).with_only_columns(ResearchReportRecord.id,
            ResearchReportRecord.title, ResearchReportRecord.target_url,
            ResearchReportRecord.created_at, ResearchReportRecord.status,
            ResearchReportRecord.report_json).order_by(
                ResearchReportRecord.created_at.desc(), ResearchReportRecord.id.desc())
        history, total = [], 0
        for row in self.session.execute(query.execution_options(yield_per=100)):
            try:
                stored = ResearchReport.model_validate_json(row.report_json)
                matches = (stored.analysis_status != 'pending' and stored.status == row.status and
                           canonical_target(stored.target_url) == target)
            except ValueError:
                matches = False
            if matches:
                total += 1
                if len(history) < MAX_PAGE_SIZE:
                    history.append({'id': row.id, 'title': row.title,
                                    'created_at': self._time(row.created_at), 'status': row.status})
        return history, total

    def inspect(self, user_id, business_id, report_id):
        row, report = self._load(user_id, business_id, report_id)
        result = self._view(row, report)
        result['history'], result['history_count'] = self._history(business_id, result['canonical_target'])
        member = IdentityService(self.session, self.clock).require_membership(user_id, business_id)
        user = self.session.get(User, user_id)
        result['can_request_correction'] = bool(user.email_verified_at and member.role in {'owner', 'admin', 'editor'})
        result['correction_reasons'] = CORRECTION_REASONS
        result['correction_requests'] = self.correction_requests(user_id, business_id, report_id)
        return result

    def request_correction(self, user_id, business_id, report_id, *, source_id, reason, details):
        """Create internal review work; never promote a merchant statement to evidence."""
        tasks = TaskService(self.session, self.clock)
        tasks._write_access(user_id, business_id)
        row, report = self._load(user_id, business_id, report_id)
        if reason not in CORRECTION_REASONS:
            raise _invalid('Choose a correction reason from the form.')
        source = next((item for item in report.source_documents if item.id == source_id), None)
        if source is None:
            raise IdentityError('source_not_found', 'Choose a retained source from this saved report.', 404)
        details = text_value(details, 'correction_details', 1500, minimum=10)
        description = ('MERCHANT_PROVIDED_UNVERIFIED — correction review request\n'
                       + CORRECTION_REASONS[reason] + '\nSource ID: ' + source.id
                       + '\nCaptured: ' + source.retrieved_at.isoformat()
                       + '\nContent SHA-256: ' + source.source_hash + '\n\n' + details
                       + '\n\nReview against permitted evidence. Task completion does not verify a correction or refresh the report.')
        task = tasks.create(user_id, business_id, title='Review evidence correction: ' + CORRECTION_REASONS[reason],
                            description=description, source_report_id=row.id)
        IdentityService(self.session, self.clock).audit('research.correction_requested', user_id=user_id,
            business_id=business_id, resource_type='task', resource_id=task.id,
            details={'report_id': row.id, 'source_id': source.id, 'source_hash': source.source_hash,
                     'reason': reason, 'classification': 'MERCHANT_PROVIDED_UNVERIFIED',
                     'evidence_reverified': False})
        self.session.flush()
        return task

    def correction_requests(self, user_id, business_id, report_id):
        self._load(user_id, business_id, report_id)
        records = self.session.execute(select(Task, AuditEvent).join(AuditEvent,
            (AuditEvent.resource_id == Task.id) & (AuditEvent.business_id == Task.business_id)).where(
                Task.business_id == business_id, Task.source_report_id == report_id,
                AuditEvent.action == 'research.correction_requested', AuditEvent.resource_type == 'task',
            ).order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(50)).all()
        return [{'task': task, 'provenance': json.loads(event.details_json),
                 'requested_at': self._time(event.created_at)} for task, event in records]

    def _view(self, row, report):
        now, sources = self.clock(), report.source_documents
        products, categories, channels = [], [], []
        source_views = []
        for number, source in enumerate(sources, 1):
            source_views.append({'id': source.id, 'number': number, 'url': source.url, 'title': source.title,
                'excerpt': source.excerpt, 'content': source.content, 'hash': source.source_hash,
                'html_hash': source.html_source_hash, 'provider': source.provider, 'classification': source.source_type,
                'retrieved_at': source.retrieved_at.isoformat(), 'freshness': source_freshness(source.retrieved_at, now),
                'page_key': canonical_target(source.url)})
            for product in source.product_observations:
                products.append({**product.model_dump(), 'source_id': source.id, 'source_url': source.url,
                                 'captured_at': source.retrieved_at.isoformat(), 'kind': 'OBSERVED'})
            # Only explicit retained source labels qualify as category observations.
            # No taxonomy is generated from a name, product or AI hypothesis.
            for match in list(re.finditer(r'(?im)^\s*(?:product )?categor(?:y|ies)\s*:\s*([^\r\n]{1,120})$', source.content))[:20]:
                categories.append({'text': match.group(0).strip(), 'source_id': source.id, 'kind': 'OBSERVED'})
            channels.extend({'text': value, 'source_id': source.id, 'kind': 'OBSERVED'}
                            for value in source.channel_observations)
        claims = [{'text': claim.text, 'kind': claim.kind, 'origin': 'source observation' if claim.kind == 'OBSERVED' else 'rules-based report',
                   'citations': _citations(claim.evidence_ids, sources), 'quote': '',
                   'observed_at': claim.observed_at.isoformat() if claim.observed_at else None}
                  for claim in report.claims]
        if report.analysis:
            claims.extend({'text': claim.text, 'kind': claim.kind, 'origin': 'AI-generated',
                           'quote': claim.quote, 'observed_at': None,
                           'citations': _citations(claim.evidence_ids, sources)} for claim in report.analysis.claims)
        recommendations = [{'title': item.title, 'text': item.description, 'next_step': item.next_step,
                            'origin': 'Rules-based hypothesis', 'kind': 'INFERRED',
                            'citations': _citations(item.evidence_ids, sources)} for item in report.opportunities]
        if report.analysis:
            recommendations.extend({'title': 'AI-suggested next step', 'text': item.text,
                                    'next_step': 'Review the cited evidence, confirm the situation and decide whether to create a task.',
                                    'origin': 'AI-generated proposal', 'kind': 'INFERRED',
                                    'citations': _citations(item.evidence_ids, sources)} for item in report.analysis.recommendations)
        conflicts = []
        for index, left in enumerate(products):
            for right in products[index + 1:]:
                if (left['name'].casefold().strip() == right['name'].casefold().strip() and
                        canonical_target(left['source_url']) != canonical_target(right['source_url']) and
                        left['currency'] and left['currency'] == right['currency'] and
                        left['listed_price'] is not None and right['listed_price'] is not None and
                        Decimal(left['listed_price']) != Decimal(right['listed_price'])):
                    conflicts.append({'kind': 'potential_listed_price_disagreement', 'name': left['name'],
                        'left': left, 'right': right,
                        'explanation': 'Distinct captured pages list different prices for the same product label. Variants, capture time or stale pages may explain this; product identity and current selling price are unverified.'})
        comparisons = []
        for index, left in enumerate(source_views):
            for right in source_views[index + 1:]:
                comparisons.append({'left_id': left['id'], 'right_id': right['id'],
                    'distinct_pages': left['page_key'] != right['page_key'],
                    'content_match': left['hash'] == right['hash'],
                    'label': 'Identical retained text' if left['hash'] == right['hash'] else 'Different retained text; difference alone does not establish a factual conflict'})
        return {'record_id': row.id, 'report': report, 'title': report.business_name, 'merchant_provided': report.origin == 'merchant_provided',
            'target_url': report.target_url, 'canonical_target': canonical_target(report.target_url),
            'created_at': self._time(row.created_at), 'freshness': report_freshness(report, now),
            'freshness_days': FRESHNESS_DAYS, 'checked_at': self._time(now), 'sources': source_views,
            'source_indices': {source.id: number for number, source in enumerate(sources, 1)},
            'products': products, 'categories': categories, 'channels': channels, 'claims': claims,
            'recommendations': recommendations, 'conflicts': conflicts, 'source_comparisons': comparisons,
            'unknowns': tuple(claim['text'] for claim in claims if claim['kind'] == 'UNKNOWN'),
            'work_url': '/work?' + urlencode({'source_report_id': row.id})}

    def compare(self, user_id, business_id, left_id, right_id, label=''):
        if left_id == right_id:
            raise _invalid('Choose exactly two different saved reports.')
        if label not in {'', 'merchant_assessed_competitor'}:
            raise _invalid('Choose the optional merchant assessment label from the form.')
        left_row, left_report = self._load(user_id, business_id, left_id)
        right_row, right_report = self._load(user_id, business_id, right_id)
        left, right = self._view(left_row, left_report), self._view(right_row, right_report)
        same = left['canonical_target'] == right['canonical_target']
        if same and label:
            raise _invalid('Competitor assessment applies only to distinct research targets.')
        hashes = []
        if same:
            left_pages, right_pages = {}, {}
            for source in left['sources']:
                left_pages.setdefault(source['page_key'], []).append(source)
            for source in right['sources']:
                right_pages.setdefault(source['page_key'], []).append(source)
            for key in sorted(left_pages.keys() | right_pages.keys()):
                before, after = left_pages.get(key, []), right_pages.get(key, [])
                # Duplicate captures of one page do not identify a unique pair.
                comparable = len(before) == len(after) == 1
                hashes.append({'page': key, 'left_ids': tuple(item['id'] for item in before),
                    'right_ids': tuple(item['id'] for item in after),
                    'status': ('unchanged' if before[0]['hash'] == after[0]['hash'] else 'changed') if comparable else 'not_comparable',
                    'reason': '' if comparable else 'A unique captured page is required on both sides; missing coverage is not a change.'})
        def difference(key, identity):
            before = {identity(item): item for item in left[key]}
            after = {identity(item): item for item in right[key]}
            return {'left_only': [before[value] for value in sorted(before.keys() - after.keys())],
                    'right_only': [after[value] for value in sorted(after.keys() - before.keys())],
                    'shared_count': len(before.keys() & after.keys())}
        deltas = {'products': difference('products', lambda item: (item['name'].casefold(), item['currency'] or '', item['listed_price'] or '')),
                  'channels': difference('channels', lambda item: item['text'].casefold()),
                  'categories': difference('categories', lambda item: item['text'].casefold())}
        price_differences = []
        for before in left['products']:
            for after in right['products']:
                if (before['name'].casefold() == after['name'].casefold() and before['currency'] and
                        before['currency'] == after['currency'] and before['listed_price'] is not None and
                        after['listed_price'] is not None and Decimal(before['listed_price']) != Decimal(after['listed_price'])):
                    price_differences.append({'name': before['name'], 'left': before, 'right': after})
        return {'left': left, 'right': right, 'mode': 'history' if same else 'distinct_targets',
                'merchant_assessment': label == 'merchant_assessed_competitor', 'hash_comparison': hashes,
                'deltas': deltas, 'price_differences': price_differences,
                'left_is_earlier': left_row.created_at < right_row.created_at,
                'chronology_equal': left_row.created_at == right_row.created_at,
                'freshness_days': FRESHNESS_DAYS}

    def export(self, user_id, business_id, report_id):
        row, report = self._load(user_id, business_id, report_id)
        # Explicit public-evidence projection. No raw page bodies, anonymous
        # capabilities, account/workspace IDs, provider receipts or usage ledger.
        payload = {'schema': 'ayo-saved-research-export-v1', 'report_id': row.id,
            'business_name': report.business_name, 'target_url': report.target_url, 'country': report.country,
            'status': report.status, 'origin': report.origin, 'created_at': report.created_at.isoformat(),
            'analysis_status': report.analysis_status, 'ownership_verified': False,
            'claims': [item.model_dump(mode='json') for item in report.claims],
            'opportunities': [item.model_dump(mode='json') for item in report.opportunities],
            'limitations': list(report.limitations),
            'sources': [{'id': item.id, 'url': item.url, 'title': item.title, 'excerpt': item.excerpt,
                         'retrieved_at': item.retrieved_at.isoformat(), 'source_hash': item.source_hash,
                         'html_source_hash': item.html_source_hash, 'provider': item.provider,
                         'classification': item.source_type, 'input_origin': getattr(item, 'origin', None),
                         'input_field': getattr(item, 'input_field', None),
                         'products': [product.model_dump(mode='json') for product in item.product_observations],
                         'channels': list(item.channel_observations)} for item in report.source_documents],
            'notice': ('Merchant inputs remain OWNER_PROVIDED_UNVERIFIED; no independent evidence was acquired.' if report.origin == 'merchant_provided' else 'Public source statements remain unverified.') + ' AI inferences and recommendations are proposals. Saving does not establish ownership or authorize actions.'}
        if report.analysis:
            payload['analysis'] = report.analysis.model_dump(mode='json', exclude={'usage', 'summary'})
        return _redact(payload)
