#
# views.py:
# Views for TheyWorkForYou election quiz Django project
#
# Copyright (c) 2010 UK Citizens Online Democracy. All rights reserved.
# Email: francis@mysociety.org; WWW: http://www.mysociety.org/
#

from google.appengine.api import urlfetch
from google.appengine.api.datastore_types import Key
from google.appengine.ext import db

from django.forms.formsets import formset_factory
from django.shortcuts import render_to_response, get_object_or_404
from django.http import HttpResponseRedirect

from ratelimitcache import ratelimit

import forms

from models import Seat, RefinedIssue, Candidacy

# Front page of election site
def index(request):
    return render_to_response('index.html', {})

# Authenticate a candidate
def _check_auth(post, ip_address):
    form = forms.AuthCandidacyForm(post or None)

    if not post:
        return render_to_response('survey_candidacy_auth.html', { 'form': form })

    token = post['token']
    candidacy = Candidacy.find_by_token(token)
    
    if not candidacy:
        # XXX add error message
        return render_to_response('survey_candidacy_auth.html', { 'form': form, 'error': True })

    if 'auth_submitted' in post:
        if not candidacy.survey_token_use_count:
            candidacy.survey_token_use_count = 0
        candidacy.survey_token_use_count += 1
        candidacy.log('Survey token authenticated from IP %s' % ip_address)

    return candidacy

# Survey a candidate
@ratelimit(minutes = 2, requests = 40) # stop brute-forcing of token 
def survey_candidacy(request, token = None):
    post = request.POST or {}
    if token:
        post['token'] = token

    # Check they have the token
    response = _check_auth(post, request.META['REMOTE_ADDR'])
    if not isinstance(response, Candidacy):
        return response
    candidacy = response

    # Have they tried to post an answer?
    submitted = 'questions_submitted' in post

    # Construct array of forms containing all local issues
    issues_for_seat = candidacy.seat.refinedissue_set.fetch(1000)
    issue_forms = []
    valid = True
    for issue in issues_for_seat:
        form = forms.LocalIssueQuestionForm(submitted and post or None, refined_issue=issue, candidacy=candidacy)
        valid = valid and form.is_valid()
        issue_forms.append(form)

    # Save the answers to all questions in a transaction 
    if submitted and valid:
        db.run_in_transaction(forms._form_array_save, issue_forms)
        candidacy.log('Survey form completed successfully')
        return render_to_response('survey_candidacy_thanks.html', { 'candidate' : candidacy.candidate })

    # Otherwise log if they submitted an incomplete form
    if submitted and not valid:
        amount_done = forms._form_array_amount_done(issue_forms)
        amount_max = len(issue_forms)
        candidacy.log('Survey form submitted incomplete, %d/%d questions answered' % (amount_done, amount_max))

    return render_to_response('survey_candidacy_questions.html', {
        'issue_forms': issue_forms,
        'unfinished': submitted and not valid,
        'token': candidacy.survey_token,
        'candidacy' : candidacy,
        'candidate' : candidacy.candidate,
        'seat' : candidacy.seat
    })

# Administrator functions
def admin(request):
    pass





