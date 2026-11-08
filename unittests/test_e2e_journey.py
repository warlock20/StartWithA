# StartWithA
# Copyright (C) 2024-2026 Kiran Mathews
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""End-to-end journey through the core flow, on real routes (#337).

One user walks the product the way the vision describes it:

    idea -> Kill Screen -> research -> buy decision -> transaction
         -> thesis + checkpoint -> journal -> mistake -> learning pages

Every step goes through the Flask test client, so routes, services, models and
templates are exercised together. Each step asserts what the user would see:
the page renders, the record exists, the status moved on.

No LLM is ever called, nothing reaches Celery/Redis and nothing goes online:
all three are intercepted (market data is a fixed stub), and the journey fails
if anything tries to spend tokens or call out.

This file is the place to extend when a feature changes the core flow. Unit
tests stay for behaviour that is cheaper to pin down in isolation.
"""

import socket
from datetime import date, timedelta
from urllib.parse import urlparse

import pytest
from celery.app.task import Task
from curl_cffi import requests as curl_requests

from app import db
from app.models import (
    DestinationCheckpoint, IdeaPipeline, JournalEntry, KillChecklist,
    LearningNote, MistakeLog, PortfolioPosition, ResearchProject,
    ResearchOutcome, ResearchTemplate, ThesisEvolution, Transaction, User,
)
from app.services.ai.ai_service import AIService
from app.services.company_state import company_state
from app.services.financial_data import FinancialDataService
from app.services.too_hard_service import TooHardBasketService


# =========================================================================
# Guards: no tokens spent, nothing queued
# =========================================================================

class _QueuedTask:
    """Stands in for the AsyncResult a real .delay() returns."""
    id = 'journey-fake-task-id'


_LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}


@pytest.fixture
def guards(monkeypatch):
    """Intercept every LLM call, every Celery enqueue and all outbound network.

    LLM calls raise (and are recorded, because many routes swallow
    exceptions into a flash). Enqueued tasks are recorded and never sent, so
    a local dev worker can't pick them up against the scratch DB's ids.
    Market data comes from a fixed stub; any other connection off this machine is
    refused and recorded, so the journey runs offline and deterministically.
    """
    calls = {'ai': [], 'tasks': [], 'net': []}

    real_connect = socket.socket.connect

    def _local_only(sock, address):
        host = address[0] if isinstance(address, tuple) else address
        if isinstance(host, str) and host not in _LOCAL_HOSTS and not host.startswith('/'):
            calls['net'].append(host)
            raise OSError(f'journey must stay offline (tried {host})')
        return real_connect(sock, address)

    monkeypatch.setattr(socket.socket, 'connect', _local_only)

    # yfinance fetches through curl_cffi (libcurl), which never touches
    # Python's socket module, so it needs its own gate.
    def _no_curl(session, method, url, *args, **kwargs):
        calls['net'].append(url)
        raise OSError(f'journey must stay offline (tried {url})')

    monkeypatch.setattr(curl_requests.Session, 'request', _no_curl)
    # Market data: one fixed price, no history (so no run-up warning on a buy).
    monkeypatch.setattr(FinancialDataService, 'get_current_price_with_currency',
                        lambda self, ticker: {'price': 750.0, 'currency': 'USD'})
    monkeypatch.setattr(FinancialDataService, 'get_historical_prices_bulk',
                        lambda self, ticker, start_date, end_date: {})

    def _no_ai(name):
        def _raise(self, *args, **kwargs):
            calls['ai'].append(name)
            raise RuntimeError(f'journey must not call the LLM ({name})')
        return _raise

    for name in ('generate_text', 'generate_json', 'generate_with_tools'):
        monkeypatch.setattr(AIService, name, _no_ai(name))

    def _record(self, *args, **kwargs):
        calls['tasks'].append(self.name)
        return _QueuedTask()

    monkeypatch.setattr(Task, 'apply_async', _record)
    return calls


# =========================================================================
# Helpers
# =========================================================================

def _assert_quiet(guards):
    assert guards['ai'] == [], f'the journey called the LLM: {guards["ai"]}'
    assert guards['net'] == [], f'the journey went online: {guards["net"]}'


def _open(client, url):
    """GET a page the user can see; it must render, not error or bounce."""
    resp = client.get(url)
    assert resp.status_code == 200, f'GET {url} -> {resp.status_code}'
    return resp.get_data(as_text=True)


def _lands_on(resp, path):
    """A form POST that redirects to the expected page."""
    assert resp.status_code in (301, 302, 303), (
        f'expected a redirect to {path}, got {resp.status_code}')
    assert urlparse(resp.location).path == path, (
        f'redirected to {resp.location}, expected {path}')


def _create_company(client, name, ticker):
    resp = client.post('/companies/api/companies/create',
                       json={'name': name, 'ticker_symbol': ticker})
    body = resp.get_json()
    assert body['success'], body
    return body['company']['id']


def _capture_idea(client, name, ticker, company_id, thesis):
    resp = client.post('/ideas/add', data={
        'name': name, 'idea_type': 'company', 'idea_purpose': 'investment',
        'ticker_symbol': ticker, 'company_id': company_id,
        'source': 'Annual report', 'thesis_summary': thesis,
    })
    _lands_on(resp, '/ideas/inbox')
    idea = IdeaPipeline.query.filter_by(name=name).one()
    assert idea.status == 'inbox'
    return idea.id


def _kill_screen(client, user_id, idea_id, fail_first=False):
    """Answer every kill criterion; optionally fail the first one."""
    checklist = KillChecklist.query.filter_by(user_id=user_id, is_default=True).one()
    criteria = checklist.criteria.all()
    assert criteria, 'the default kill checklist has no criteria'
    answers = [{'criterion_id': c.id, 'passed': not (fail_first and i == 0)}
               for i, c in enumerate(criteria)]
    resp = client.post(f'/ideas/{idea_id}/kill', json={'answers': answers})
    assert resp.status_code == 200
    return resp.get_json()


def _run_checklist_step(client, project_id, step_index):
    """A checklist step: open it, answer every item, return to the project.

    Opening the step starts a checklist run and lands on its first item; each
    save hands back the next item, the last one the summary.
    """
    resp = client.get(f'/research/workflow/projects/{project_id}/execute/{step_index}')
    assert resp.status_code == 302, f'checklist step did not start a run ({resp.status_code})'
    item_url = urlparse(resp.location).path
    assert '/research/workflow/checklist/' in item_url, item_url
    _open(client, item_url)

    answered = 0
    while True:
        resp = client.post(f'{item_url}/save_and_next', json={
            'content': f'Answer {answered + 1}', 'satisfaction_status': 'satisfied'})
        body = resp.get_json()
        assert body['success'], body
        answered += 1
        if body['is_last_item']:
            break
        item_url = item_url.rsplit('/', 1)[0] + f"/{body['next_item_id']}"
    assert answered > 1, 'the checklist ran but had a single item'

    summary = _open(client, urlparse(body['summary_url']).path)
    back = f'/research/workflow/projects/{project_id}/complete-research-step/{step_index}'
    assert back in summary, 'the checklist summary does not link back to the project step'
    _lands_on(client.get(back), f'/research/workflow/projects/{project_id}')


def _login_client(app, email):
    user = User(email=email, ai_consent_given=True)
    db.session.add(user)
    db.session.commit()
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    return client, user.id


# =========================================================================
# The journey
# =========================================================================

def _run_journey(client, user_id):
    """Idea to lesson for one company. Returns the ids the checks need."""
    today = date.today()

    # --- 1. First visit to the inbox sets up the Kill Screen --------------
    # A new user is sent to review the default checklist before evaluating.
    resp = client.get('/ideas/inbox')
    assert resp.status_code == 302
    assert '/ideas/kill-checklists/' in resp.location
    _open(client, resp.location)
    _open(client, '/ideas/inbox')

    # --- 2. Capture an idea -----------------------------------------------
    _open(client, '/ideas/add')
    company_id = _create_company(client, 'ASML Holding', 'ASML')
    idea_id = _capture_idea(client, 'ASML Holding', 'ASML', company_id,
                            'Lithography monopoly with pricing power.')
    assert 'ASML Holding' in _open(client, '/ideas/inbox')
    _open(client, f'/ideas/{idea_id}/edit')

    # --- 3. The idea survives the Kill Screen ------------------------------
    result = _kill_screen(client, user_id, idea_id)
    assert result['outcome'] == 'survived'
    assert urlparse(result['promote_url']).path == f'/ideas/{idea_id}/promote'
    assert db.session.get(IdeaPipeline, idea_id).status == 'survived'

    # --- 4. Promote it into a research project ----------------------------
    _open(client, f'/ideas/{idea_id}/promote')
    template = ResearchTemplate.query.filter_by(user_id=user_id, is_active=True).one()
    resp = client.post(f'/ideas/{idea_id}/promote', data={
        'action': 'create_research_project', 'template_id': template.id})
    project = ResearchProject.query.filter_by(user_id=user_id, company_id=company_id).one()
    _lands_on(resp, f'/research/workflow/projects/{project.id}')
    assert project.status == 'active'
    assert project.idea_id == idea_id
    assert db.session.get(IdeaPipeline, idea_id).status == 'promoted'
    _open(client, f'/research/workflow/projects/{project.id}')
    assert 'ASML' in _open(client, '/research/workflow/my-projects')

    # --- 5. Work through every research step ------------------------------
    steps = project.workflow_steps
    assert steps, 'the default template has no steps'
    assert steps[-1]['type'] != 'checklist', 'the last step must be a form step'
    for index, step in enumerate(steps):
        if step['type'] == 'checklist':
            _run_checklist_step(client, project.id, index)
            continue
        _open(client, f'/research/workflow/projects/{project.id}/execute/{index}')
        notes = ('Thesis: EUV demand compounds for a decade.'
                 if step['type'] == 'thesis_writing'
                 else f"Notes for {step['name']}")
        resp = client.post(f'/research/workflow/projects/{project.id}/complete-step',
                           data={'step_index': index, 'notes': notes})
        last = index == len(steps) - 1
        expected = (f'/research/workflow/projects/{project.id}/summary' if last
                    else f'/research/workflow/projects/{project.id}')
        _lands_on(resp, expected)

    db.session.expire_all()
    project = db.session.get(ResearchProject, project.id)
    assert project.status == 'completed'
    assert sorted(project.completed_steps) == list(range(len(steps)))
    # The thesis step seeds the first thesis version for the position.
    assert ThesisEvolution.query.filter_by(company_id=company_id, version=0).one()
    _open(client, f'/research/workflow/projects/{project.id}/summary')

    # --- 6. Decide to invest ----------------------------------------------
    resp = client.post(f'/research/workflow/projects/{project.id}/save-decision', data={
        'decision': 'invest', 'confidence': '8',
        'decision_notes': 'Buying a starter position.'})
    assert resp.get_json()['success']
    project = db.session.get(ResearchProject, project.id)
    assert project.decision == 'invest'
    assert JournalEntry.query.filter_by(company_id=company_id,
                                        title='Decision: Invest').one()

    # --- 7. Buy -----------------------------------------------------------
    _open(client, f'/portfolio/transaction/add?company_id={company_id}')
    resp = client.post('/portfolio/transaction/add', data={
        'type': 'BUY', 'company_id': company_id,
        'date': (today - timedelta(days=1)).isoformat(),
        'quantity': '10', 'price_per_share': '700', 'fees': '5',
        'currency': 'USD', 'notes': 'Starter position'})
    _lands_on(resp, '/portfolio/')
    assert Transaction.query.filter_by(user_id=user_id, company_id=company_id).count() == 1
    position = PortfolioPosition.query.filter_by(user_id=user_id, company_id=company_id).one()
    assert position.total_shares == 10
    # The buy is recorded for outcome learning, linked back to the research.
    outcome = ResearchOutcome.query.filter_by(user_id=user_id, company_id=company_id).one()
    assert outcome.project_id == project.id
    assert 'ASML' in _open(client, '/portfolio/')
    _open(client, '/portfolio/transactions')

    # --- 8. Track it: thesis version and a checkpoint ---------------------
    _open(client, f'/portfolio/position/{company_id}/thesis/new')
    resp = client.post(f'/portfolio/position/{company_id}/thesis/new', data={
        'thesis': 'EUV demand compounds; High-NA extends the lead.',
        'change_summary': 'Position opened', 'conviction_level': '8',
        'bull_case_1': 'High-NA adoption', 'bear_case_1': 'Export controls'})
    _lands_on(resp, f'/companies/{company_id}')
    current = ThesisEvolution.query.filter_by(company_id=company_id, is_current=True).all()
    assert [t.version for t in current] == [1], 'exactly one current thesis, v1'

    resp = client.post(f'/companies/{company_id}/add_checkpoint', data={
        'metric': 'Gross margin', 'expectation': 'Above 50%',
        'target_date': (today + timedelta(days=90)).isoformat()})
    _lands_on(resp, f'/companies/{company_id}/destination_analysis')
    assert DestinationCheckpoint.query.filter_by(company_id=company_id).count() == 1
    assert 'Gross margin' in _open(client, f'/companies/{company_id}/destination_analysis')

    # --- 9. Journal -------------------------------------------------------
    _open(client, '/journal/entry/new')
    resp = client.post('/journal/entry/new', data={
        'entry_category': 'research', 'title': 'Q3 call notes',
        'entry_type': 'observation', 'company_id': company_id,
        'content': 'Backlog held up; China share falling as expected.',
        'hashtags': '#earnings #asml', 'sentiment': 'bullish', 'conviction': '7'})
    assert resp.status_code in (301, 302, 303)
    entry = JournalEntry.query.filter_by(user_id=user_id, title='Q3 call notes').one()
    assert entry.company_id == company_id
    _open(client, f'/journal/entry/{entry.id}')

    # --- 10. Log a mistake, which becomes a lesson ------------------------
    resp = client.post('/journal/entry/new', data={
        'entry_category': 'mistake', 'title': 'Sized before reading the 10-K',
        'description': 'Bought before finishing the risk section.',
        'lesson_learned': 'Finish the filings before sizing.',
        'mistake_type': 'position_sizing', 'severity': '4',
        'company_id': company_id})
    _lands_on(resp, '/learning/mistakes')  # redirect carries ?suggest_for=<id> (kill criterion banner)
    assert MistakeLog.query.filter_by(user_id=user_id).count() == 1
    assert LearningNote.query.filter_by(user_id=user_id).count() >= 1

    # --- 11. Everything shows up where the user looks ---------------------
    assert 'ASML' in _open(client, f'/companies/{company_id}')
    _open(client, f'/journal/thesis-evolution/{company_id}')
    assert 'Q3 call notes' in _open(client, '/journal/knowledge-hub')
    _open(client, '/learning/mistakes')
    for page in ('/dashboard/', '/portfolio/thesis-reality', '/portfolio/checkpoints',
                 '/portfolio/intelligence', '/portfolio/decision-journal',
                 '/portfolio/learning-insights', '/analytics/dashboard'):
        _open(client, page)

    # --- 12. Sell out; the outcome closes ---------------------------------
    resp = client.post('/portfolio/transaction/add', data={
        'type': 'SELL', 'company_id': company_id, 'date': today.isoformat(),
        'quantity': '10', 'price_per_share': '800', 'fees': '5',
        'currency': 'USD', 'notes': 'Thesis played out'})
    assert resp.status_code in (301, 302, 303), resp.status_code
    assert '/portfolio/sell-postmortem/' in resp.location, resp.location
    _open(client, urlparse(resp.location).path)
    db.session.expire_all()
    outcome = ResearchOutcome.query.filter_by(user_id=user_id, company_id=company_id).one()
    assert outcome.exit_date == today
    assert outcome.realized_return_pct > 0

    return {
        'company_id': company_id, 'idea_id': idea_id, 'project_id': project.id,
        'entry_id': entry.id,
    }


def test_an_idea_becomes_a_tracked_position_and_a_lesson(client_logged_in, guards):
    client, user_id = client_logged_in

    _run_journey(client, user_id)

    _assert_quiet(guards)


def test_a_killed_idea_lands_in_the_too_hard_basket(client_logged_in, guards):
    client, user_id = client_logged_in
    client.get('/ideas/inbox')  # first visit sets up the Kill Screen

    company_id = _create_company(client, 'Hype Robotics', 'HYPE')
    idea_id = _capture_idea(client, 'Hype Robotics', 'HYPE', company_id,
                            'Story stock with no moat.')
    result = _kill_screen(client, user_id, idea_id, fail_first=True)

    assert result['outcome'] == 'killed'
    idea = db.session.get(IdeaPipeline, idea_id)
    assert idea.status == 'killed' and idea.kill_reason
    assert company_state(user_id, company_id).is_dead
    basket = TooHardBasketService.get_all_too_hard_companies(user_id)
    assert [item.company_id for item in basket] == [company_id]
    # The kill is journaled against the company.
    assert JournalEntry.query.filter_by(company_id=company_id,
                                        source='kill_evaluation').count() == 1
    _open(client, '/dashboard/')
    _assert_quiet(guards)


def test_another_user_sees_none_of_it(client_logged_in, guards, _app):
    client, user_id = client_logged_in
    ids = _run_journey(client, user_id)

    # Requests reuse the test's app context, and Flask-Login caches the user
    # on its `g`; without a fresh context the intruder would be served as the
    # owner and every check below would be meaningless.
    with _app.app_context():
        intruder, _ = _login_client(_app, 'intruder@example.com')
        _assert_nothing_leaks(intruder, ids)
    _assert_quiet(guards)


def _assert_nothing_leaks(intruder, ids):
    private_pages = [
        f"/companies/{ids['company_id']}",
        f"/companies/{ids['company_id']}/destination_analysis",
        f"/ideas/{ids['idea_id']}/edit",
        f"/ideas/{ids['idea_id']}/promote",
        f"/research/workflow/projects/{ids['project_id']}",
        f"/research/workflow/projects/{ids['project_id']}/summary",
        f"/journal/entry/{ids['entry_id']}",
        f"/journal/thesis-evolution/{ids['company_id']}",
        f"/portfolio/position/{ids['company_id']}/thesis/new",
    ]
    for url in private_pages:
        resp = intruder.get(url)
        assert resp.status_code in (302, 403, 404), f'{url} -> {resp.status_code}'
        assert 'ASML' not in resp.get_data(as_text=True), f'{url} leaked the company'

    for url in ('/ideas/inbox', '/portfolio/', '/journal/knowledge-hub',
                '/research/workflow/my-projects', '/learning/mistakes'):
        resp = intruder.get(url, follow_redirects=True)
        assert resp.status_code == 200, f'{url} -> {resp.status_code}'
        body = resp.get_data(as_text=True)
        for secret in ('ASML', 'Q3 call notes', 'Sized before reading'):
            assert secret not in body, f'{url} leaked {secret!r}'
