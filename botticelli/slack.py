import re
import json
import logging
import requests
import slackclient

from botticelli.models import Game, Question, Stump, State

logger = logging.getLogger('botticelli')

class SlackException(Exception):
    pass

class Slack(object):
    def __init__(self, token):
        self.client = slackclient.SlackClient(token)

    def handle_slash(self, data):
        action, params = parse_slash_command(data['text'])

        func = {
            'status': self.handle_status,
            'help': self.handle_help,
            'ask': self.handle_question,
            'stump': self.handle_stump,
            'start': self.handle_start,
            'cancel': self.handle_cancel
        }.get(action)

        logger.info('action %s, params %s' % (action, params))

        if not func:
            raise SlackException('could not recognize command ' + action)

        func(data, params)

    def handle_action(self, data):
        callback_id = json.loads(data['callback_id'])

        func = {
            'stump': self.handle_stump_action,
            'question': self.handle_question_action,
        }[callback_id['type']](data, callback_id)

    def handle_status(self, data, submode):
        channel = data['channel_id']
        url = data['response_url']

        games = Game.get_active(channel)
    
        if not games:
            text = 'No active game of Botticelli'
        else:
            game = games[0]
            if game.state == State.Stump:
                waiting_on, to_do = 'anyone', 'ask a stumper'
            elif game.state == State.PendingStump:
                waiting_on = game.creator
                to_do = 'respond to stumper: ' + game.get_active_stump().text
            elif game.state == State.Question:
                stump = game.get_most_recent_stump()
                waiting_on, to_do = stump.creator, 'ask a question'
            elif game.state == State.PendingQuestion:
                waiting_on = game.creator
                to_do = 'respond to question: ' + game.get_active_question().text

            text = "*********** *Current Status* ***********\n"
            text += 'Botticelli game created by *%s* for letter *%s*.\nCurrently waiting on *%s* to *%s*\n\n' \
                % (game.creator, game.letter, waiting_on, to_do)

            questions = game.question_set.all().order_by('date_created')

            if questions:
                text += '\nPrevious questions:\n'
                for question in questions:
                    if question.answer is None:
                        status = 'Pending'
                    elif question.answer:
                        status = 'Yes'
                    else:
                        status = 'No'

                    text += '%s: %s\n' % (question.text, status)
                    if not question.answer:
                        text += '\n'

            text += "**************************************"

        self.reply_text(text, url)

    def handle_cancel(self, data, type):
        channel_id = data['channel_id']
        url = data['response_url']
        username = data['user_name']

        if type == 'game':
            games = Game.get_active(channel_id).update(state=State.Cancelled)
            text = '*%s* cancelled current game' % username
            self.reply_text(text, url)
        elif type == 'stump':
            pass
        elif type == 'question':
            pass
        else:
            raise SlackException("No cancel argument provided")

    def handle_help(self, data, _):
        text = """
        Commands:
        *status* - Print current game status to channel
        *start* - Start a game
            Ex: /botticelli start Mike Tyson
        *stump* - Ask a round 1 stumper
            Ex: /botticelli stump did you write some dumb book?
        *ask* - Ask a round 2 question
            Ex: /botticelli ask are you alive?
        *cancel* - Cancel the game
            Ex: /botticell cancel game
        """
        self.reply_ephemeral_text(text, data['response_url'])


    def handle_start(self, data, person):
        if not person:
            raise SlackException("Must start botticelli by providing a person!")

        letter = person.split(' ')[-1][0].upper()
        channel_id = data['channel_id']
        username = data['user_name']
        url = data['response_url']

        # Get active games
        games = Game.get_active(channel_id)

        # Validate state
        if games:
            raise SlackException("You already have an active botticelli game for this channel")

        # Create new game
        game = Game(creator=username, 
                    channel=channel_id,
                    person=person,
                    letter=letter)
        game.save()

        # Send reply
        text = '*%s* has begun a game of Botticelli for letter *%s*... Begin!' % (username, letter)
        self.reply_text(text, url)


    def handle_stump(self, data, stump_text):
        if not stump_text:
            raise SlackException("Ya gotta ask a dang stumper!")

        channel_id = data['channel_id']
        username = data['user_name']
        url = data['response_url']

        # Get active games
        games = Game.get_active(channel_id)

        # Validate the game state
        if not games:
            raise SlackException("No active game")

        game = games[0]

        if game.state == State.PendingStump:
            raise SlackException("Pending stump needs to be resolved before asking another")

        if game.state == State.PendingQuestion or game.state == State.Question:
            raise SlackException("We're asking stumps, not questions!")

        # Create stump
        stump = game.stump_set.create(creator=username, text=stump_text)

        # Change state
        game.state = State.PendingStump
        game.save()

        # Send stump message attachment
        text = '*%s* asks stumper:\n*%s*' % (username, stump_text)
        footer = '<@%s|user>, Are you stumped? If not, prove it!' % game.creator
        callback_id = json.dumps({'type': 'stump', 'id': stump.id})
        self.send_yesno(text, footer, callback_id, url)

    def handle_question(self, data, question_text):
        if not question_text:
            raise SlackException("Ya gotta ask a dang question!")

        channel_id = data['channel_id']
        username = data['user_name']
        url = data['response_url']

        # Get active games
        games = Game.get_active(channel_id)

        # Validate the game state
        if not games:
            raise SlackException("No active game")

        game = games[0]

        if game.state == State.PendingQuestion:
            raise SlackException("Pending question needs to be resolved before asking another")

        if game.state == State.PendingStump or game.state == State.Stump:
            raise SlackException("We're asking questions, not stumps!")

        #TODO: validate user

        # Create question
        question = game.question_set.create(creator=username, text=question_text)

        # Change state
        game.state = State.PendingQuestion
        game.save()

        # Send question message attachment
        text = '*%s* asks yes/no question for <@%s|user>:\n*%s*' \
            % (username, game.creator, question_text)
        callback_id = json.dumps({'type': 'question', 'id': question.id})
        self.send_yesno(text, '', callback_id, url)

    def reply_text(self, text, url):
        payload = {
            "response_type": "in_channel",
            "text": text
        }

        self.respond_to_url(payload, url)

    def reply_ephemeral_text(self, text, url):
        payload = {
            "response_type": "ephemeral",
            "text": text
        }

        self.respond_to_url(payload, url)

    def respond_to_url(self, data, url):
        logger.info('posting %s to %s' % (data, url))
        headers = {'Content-Type': 'application/json'}
        result = requests.post(url, json=data, headers=headers)
        result.raise_for_status()

    def send_yesno(self, stump_text, footer, callback_id, url):
        data = {
            "text": stump_text,
            "response_type": "in_channel",
            "attachments": [{
                "text": "",
                "fallback": "",
                "footer": footer,
                "color": "#3AA3E3",
                "attachment_type": "default",
                "callback_id": callback_id,
                "actions": [
                    {"name": "yes", "text": "Yes", "type": "button", "value": "yes"},
                    {"name": "no", "text": "No", "type": "button", "value": "no"}
                ]}
            ]
        }

        self.respond_to_url(data, url)


    def handle_stump_action(self, data, callback_id):
        # TODO: validate user

        url = data['response_url']
        stump_id = callback_id['id']
        original_text = data['original_message']['text']

        # Update stump record
        stump = Stump.objects.get(id=stump_id)
        stump.answer = data['actions'][0]['value'] == 'yes'
        stump.save()

        # Update game state
        new_state = State.Question if stump.answer else State.Stump
        stump.game.state=new_state
        stump.game.save()

        # send a message reply
        if stump.answer:
            text = '%s\n\n*%s* was stumped. *<@%s|user> can now ask questions*.' \
                % (original_text, stump.game.creator, stump.creator)
        else:
            text = '%s\n\n*%s* wasn\'t stumped. *Make sure he proves it*, then try again <@channel|user>!' \
                % (original_text, stump.game.creator)
        self.reply_text(text, url)

    def handle_question_action(self, data, callback_id):
        # TODO: validate user

        url = data['response_url']
        question_id = callback_id['id']
        original_text = data['original_message']['text']

        # Update question record
        question = Question.objects.get(id=question_id)
        question.answer = data['actions'][0]['value'] == 'yes'
        question.save()

        # Update game state
        new_state = State.Question if question.answer else State.Stump
        question.game.state=new_state
        question.game.save()

        # send a message reply
        if question.answer:
            text = '%s\n\n*Correct!* <@%s|user> can ask again.' \
                % (original_text, question.creator)
        else:
            text = '%s\n\n*Nope!* Time for <@channel|user> to stump.' \
                % (original_text)
        self.reply_text(text, url)

def parse_slash_command(text):
    match = re.match('(\w+)(.*)', text)
    if not match:
        return '', ''
    groups = match.groups()
    return groups[0].strip(), groups[1].strip()
