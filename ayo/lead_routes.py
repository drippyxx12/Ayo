"""HTTP boundary for the private prospect library; no outreach execution routes."""
from datetime import date

from fastapi import Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError

from ayo.identity import IdentityError
from ayo.lead_management import LeadManagementService


def install_routes(mod, context, protected, guard):
    app = mod.app

    def mutate(request, csrf, sess, operation):
        user, business = protected(request, sess)
        guard(request, csrf, sess)
        try:
            result = operation(LeadManagementService(sess), user.id, business.id)
            sess.commit()
            return result
        except IdentityError:
            sess.rollback()
            raise
        except IntegrityError:
            sess.rollback()
            raise HTTPException(409, 'This record changed. Reopen it and try again.') from None

    @app.get('/leads/{lead_id}')
    def lead_detail(lead_id: str, request: Request, sess=Depends(mod.db)):
        user, business = protected(request, sess)
        return mod.render(request, 'lead_detail.html', user=user, business=business,
                          **LeadManagementService(sess).detail(user.id, business.id, lead_id))

    @app.post('/leads/lists')
    def create_list(request: Request, name: str = Form(...), description: str = Form(''),
                    csrf: str = Form(...), sess=Depends(mod.db)):
        row = mutate(request, csrf, sess, lambda service, user, business:
            service.create_list(user, business, name=name, description=description))
        return RedirectResponse('/leads?list_id=' + row.id, 303)

    @app.post('/leads/lists/{list_id}/items')
    def add_list_item(list_id: str, request: Request, lead_id: str = Form(...),
                      csrf: str = Form(...), sess=Depends(mod.db)):
        mutate(request, csrf, sess, lambda service, user, business:
            service.add_to_list(user, business, list_id, lead_id))
        return RedirectResponse('/leads/' + lead_id, 303)

    @app.post('/leads/lists/{list_id}/items/{lead_id}/remove')
    def remove_list_item(list_id: str, lead_id: str, request: Request,
                         csrf: str = Form(...), sess=Depends(mod.db)):
        mutate(request, csrf, sess, lambda service, user, business:
            service.remove_from_list(user, business, list_id, lead_id))
        return RedirectResponse('/leads/' + lead_id, 303)

    @app.post('/leads/{lead_id}/notes')
    def append_note(lead_id: str, request: Request, body: str = Form(...),
                    csrf: str = Form(...), sess=Depends(mod.db)):
        mutate(request, csrf, sess, lambda service, user, business:
            service.add_note(user, business, lead_id, body=body))
        return RedirectResponse('/leads/' + lead_id, 303)

    @app.post('/leads/{lead_id}/followups')
    def add_followup(lead_id: str, request: Request, title: str = Form(...),
                     description: str = Form(''), due_date: str = Form(''),
                     csrf: str = Form(...), sess=Depends(mod.db)):
        try:
            parsed_date = date.fromisoformat(due_date).isoformat() if due_date else None
        except ValueError:
            raise HTTPException(400, 'Choose a valid follow-up date.') from None
        mutate(request, csrf, sess, lambda service, user, business:
            service.add_followup(user, business, lead_id, title=title, description=description, due_date=parsed_date))
        return RedirectResponse('/leads/' + lead_id, 303)

    @app.post('/leads/{lead_id}/drafts')
    def create_draft(lead_id: str, request: Request, offer: str = Form(...),
                     source_url: str = Form(...), source_excerpt: str = Form(...),
                     csrf: str = Form(...), sess=Depends(mod.db)):
        mutate(request, csrf, sess, lambda service, user, business:
            service.save_draft(user, business, lead_id, offer=offer, source_url=source_url, source_excerpt=source_excerpt))
        return RedirectResponse('/leads/' + lead_id + '#outreach-draft', 303)

    @app.post('/leads/{lead_id}/drafts/{draft_id}')
    def edit_draft(lead_id: str, draft_id: str, request: Request, offer: str = Form(...),
                   source_url: str = Form(...), source_excerpt: str = Form(...),
                   subject: str = Form(...), body: str = Form(...), version: int = Form(...),
                   csrf: str = Form(...), sess=Depends(mod.db)):
        mutate(request, csrf, sess, lambda service, user, business:
            service.save_draft(user, business, lead_id, offer=offer, source_url=source_url, source_excerpt=source_excerpt,
                               subject=subject, body=body, version=version, draft_id=draft_id))
        return RedirectResponse('/leads/' + lead_id + '#outreach-draft', 303)
