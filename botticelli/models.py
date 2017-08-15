
from django.db import models
from django.db.models import Max
import logging

class State(object):
    Stump = 0
    PendingStump = 1
    Question = 2
    PendingQuestion = 3
    Done = 4
    Cancelled = 5

class Game(models.Model):
    creator = models.CharField(max_length=64)
    letter = models.CharField(max_length=1)
    person = models.CharField(max_length=64)
    channel = models.CharField(max_length=16)
    state = models.IntegerField(default=State.Stump)
    date_updated = models.DateTimeField(auto_now=True)
    date_created = models.DateTimeField(auto_now_add=True)

    def get_active_stump(self):
        stumps = self.stump_set.filter(answer=None)
        if stumps:
            return stumps[0]
        return None

    def get_active_question(self):
        questions = self.question_set.filter(answer=None)
        if questions:
            return questions[0]
        return None

    def get_most_recent_stump(self):
        return self.stump_set.all().order_by('-date_created')[0]

    @staticmethod
    def get_active(channel_id):
        games = Game.objects.filter(channel=channel_id) \
            .exclude(state__in=(State.Done, State.Cancelled))
        if not games:
            return None
        return games[0]

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return ', '.join(['Creator: ' + self.creator,
                          'Letter: '  + self.letter,
                          'Channel: ' + self.channel,
                          'person: '  + self.person,
                          'state: '   + repr(self.state),
                          'Updated: ' + repr(self.date_updated),
                          'Created: ' + repr(self.date_created)])

class Question(models.Model):
    creator = models.CharField(max_length=64)
    text = models.CharField(max_length=1024)
    answer = models.NullBooleanField(default=None)
    game = models.ForeignKey(Game)
    thread_ts = models.CharField(max_length=32, default='')
    date_updated = models.DateTimeField(auto_now = True)
    date_created = models.DateTimeField(auto_now_add = True)

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return ', '.join(['Creator: ' + self.creator,
                          'Text: '    + self.text,
                          'Answer: '  + repr(self.answer),
                          'Updated: ' + repr(self.date_updated),
                          'Created: ' + repr(self.date_created)])

class Stump(models.Model):
    creator = models.CharField(max_length=64)
    text = models.CharField(max_length=1024)
    answer = models.NullBooleanField(default=None)
    game = models.ForeignKey(Game)
    thread_ts = models.CharField(max_length=32, default='')
    date_updated = models.DateTimeField(auto_now = True)
    date_created = models.DateTimeField(auto_now_add = True)

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return ', '.join(['Creator: ' + self.creator,
                          'Text: '    + self.text,
                          'Answer: '  + repr(self.answer),
                          'Updated: ' + repr(self.date_updated),
                          'Created: ' + repr(self.date_created)])

