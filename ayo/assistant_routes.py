"""Private conversations with durable pre-dispatch read plans and replay fences."""
import asyncio
import json
import os
import secrets

from fastapi import Depends, Form, Request
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from ayo.assistant import AssistantService, ToolResult
from ayo.identity import IdentityError
from ayo.intelligence import IntelligenceError
from ayo.provider_usage import budget_context


def install_routes(mod, context, protected, guard):
    app = mod.app

    def page(request, sess, conversation_id=None):
        user, business = protected(request, sess)
        service = AssistantService(sess)
        conversation, messages = None, []
        if conversation_id:
            conversation = service.get(user.id, business.id, conversation_id)
            service.expire_pending(user.id, business.id, conversation_id)
            sess.commit()
            for row in service.messages(user.id, business.id, conversation_id):
                runs = service.tool_runs(user.id, business.id, row) if row.role == 'assistant' else []
                messages.append({'record': row, 'analysis': json.loads(row.result_json),
                    'plan': json.loads(row.plan_json),
                    'tools': [ToolResult.model_validate_json(run.result_json) for run in runs]})
        return mod.render(request, 'assistant.html', user=user, business=business,
            active_page='ayo', conversations=service.list(user.id, business.id),
            conversation=conversation, messages=messages,
            capabilities=service.capabilities(user.id, business.id), request_id=secrets.token_urlsafe(24))

    @app.get('/ayo')
    def assistant_home(request: Request, sess=Depends(mod.db)):
        if not mod.session_user(request, sess):
            return RedirectResponse('/login', 303)
        return page(request, sess)

    @app.post('/ayo/conversations')
    def create_conversation(request: Request, csrf: str = Form(...), request_id: str = Form(...),
                            title: str = Form('New conversation'), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        try:
            row = AssistantService(sess).create(user.id, business.id, request_id, title)
            sess.commit()
        except IdentityError:
            sess.rollback()
            raise
        return RedirectResponse('/ayo/conversations/' + row.id, 303)

    @app.get('/ayo/conversations/{conversation_id}')
    def conversation(conversation_id: str, request: Request, sess=Depends(mod.db)):
        return page(request, sess, conversation_id)

    @app.post('/ayo/conversations/{conversation_id}/messages')
    async def message(conversation_id: str, request: Request, csrf: str = Form(...),
                      request_id: str = Form(...), question: str = Form(...), sess=Depends(mod.db)):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        service = AssistantService(sess)
        try:
            record, dispatch = service.begin(user.id, business.id, conversation_id, request_id, question)
            # Persist the request, exact tools and source snippets before inference.
            sess.commit()
        except IdentityError:
            sess.rollback()
            raise
        if not dispatch:
            return RedirectResponse('/ayo/conversations/' + conversation_id, 303)
        message_id = record.id
        try:
            ctx = service.inference_context(user.id, business.id, record)
            sess.commit()  # No open DB transaction during model/provider I/O.
            orchestrator = app.state.intelligence_factory()
            configured_provider = getattr(orchestrator, 'provider', None)
            if ((configured_provider is not None and configured_provider.name != 'gemini') or
                    (configured_provider is None and os.getenv('AYO_AI_PROVIDER', 'gemini').lower() != 'gemini')):
                raise IntelligenceError('assistant_provider_not_supported', 'This assistant requires Gemini; no alternative provider was called.')
            with budget_context(mod.DbSession, scope_id='business:' + business.id,
                                request_id='assistant:' + record.id, dispatch_prefix='assistant:' + record.id):
                async with asyncio.timeout(45):
                    result = await orchestrator.analyze(ctx)
            service.finish(user.id, business.id, message_id, result=result)
            sess.commit()
        except IntelligenceError as exc:
            sess.rollback()
            # Codes are controlled identifiers. Raw provider exceptions and user
            # content never enter a persisted error or a browser response.
            code = exc.code if isinstance(exc.code, str) and len(exc.code) <= 80 and exc.code.replace('_', '').isalnum() else 'analysis_unavailable'
            service.finish(user.id, business.id, message_id, error_code=code,
                uncertain=code in {'provider_timeout', 'provider_failure', 'budget_storage_unavailable'},
                failed=code.startswith(('unsupported_', 'invalid_', 'unauthorized_', 'unverified_', 'missing_citation')))
            sess.commit()
        except (TimeoutError, ValidationError):
            sess.rollback()
            service.finish(user.id, business.id, message_id, error_code='analysis_unavailable', uncertain=True)
            sess.commit()
        except Exception:
            sess.rollback()
            service.finish(user.id, business.id, message_id, error_code='analysis_unavailable', uncertain=True)
            sess.commit()
        return RedirectResponse('/ayo/conversations/' + conversation_id, 303)
