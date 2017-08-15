from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.conf import settings

import json
import logging
from botticelli import slack

logger = logging.getLogger('botticelli')

_slack = slack.Slack(settings.SLACK_OATH_TOKEN)

@csrf_exempt
@require_POST
def slack_slash(request):
    logger.info(request.POST.urlencode())
    try:
        _slack.handle_slash(request.POST)
    except slack.SlackException as e:
        _slack.reply_ephemeral_text('Error: ' + str(e), request.POST['response_url'])
    return HttpResponse()

@csrf_exempt
@require_POST
def slack_action(request):
    payload = json.loads(request.POST['payload'])
    logger.info(payload)
    _slack.handle_action(payload)
    return HttpResponse()

def ping(request):
    return HttpResponse()
