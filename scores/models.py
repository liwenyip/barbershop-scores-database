from django.db import models
from autoslug import AutoSlugField

#################################################################
# Models for Person, Group, and Song names
#################################################################


class Person(models.Model):
    """
    A unique person, who may be known by several names
    """
    name = models.CharField(max_length=100)
    slug = AutoSlugField(populate_from='name', always_update=True, unique=True)
    alias_of = models.ForeignKey("self", blank=True, null=True, on_delete=models.PROTECT)

    def __str__(self):
        return self.name


class Contestant(models.Model):
    """
    A unique quartet or chorus, who may be known by several names
    """
    name = models.CharField(max_length=100)
    assoc = models.CharField(max_length=100)
    type = models.CharField(max_length=1, choices=(
        ('c', 'Chorus'),
        ('q', 'Quartet'),
    ))
    slug = AutoSlugField(populate_from='name', always_update=True, unique=True)
    alias_of = models.ForeignKey("self", blank=True, null=True, on_delete=models.PROTECT)

    def __str__(self):
        return self.name


class Song(models.Model):
    """
    A unique song, which may be known by several names
    """
    name = models.CharField(max_length=100)
    slug = AutoSlugField(populate_from='name', always_update=True, unique=True)
    alias_of = models.ForeignKey("self", blank=True, null=True, on_delete=models.PROTECT)

    def __str__(self):
        return self.name


#################################################################
# Models for more interesting stuff
#################################################################

STREAM_CHOICES = (
    ('I', 'International'),
    ('N', 'National'),
    ('Y', 'Youth'),
    ('S', 'Senior'),
)

class Contest(models.Model):
    """
    A contest object
    """
    # Object attributes
    assoc = models.CharField(max_length=100)
    contest = models.CharField(max_length=100)
    date = models.DateField()
    location = models.CharField(max_length=100)
    raw_text = models.TextField(blank=True, null=True)
    stream = models.CharField('Stream', max_length=1, blank=True, null=True, choices=STREAM_CHOICES)
    type = models.CharField(max_length=1, choices=(
        ('q', 'Quartet'),
        ('c', 'Chorus'),
    ))
    year = models.CharField(max_length=20)

    # Methods
    def __str__(self):
        return " / ".join((self.assoc, self.contest, self.date.strftime('%x')))


class ContestURL(models.Model):
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    url = models.URLField()


class Judge(models.Model):
    """
    Represents a person's appearance as a judge at a contest
    One Contest --< Many Judges >-- One Person
    """
    # Foreign Keys
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    # Name as recorded on the scoresheet
    name = models.CharField(max_length=100)
    # Relationship Attributes
    cat = models.CharField('Category', max_length=1, choices=(
        ('m', 'Music'),
        ('s', 'Singing'),
        ('p', 'Presentation'),
        ('a', 'Administration'),
    ))

    # Methods
    def __str__(self):
        return '%s (%s)' % (self.person.name, self.cat)


class ContestantApp(models.Model):
    """
    Represents a contestant's appearance in a contest
    One Contest --< Many ContestantApps >-- One Contestant
    """
    # Foreign Keys
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE)
    contestant = models.ForeignKey(Contestant, on_delete=models.CASCADE)
    # Name as recorded on the scoresheet
    name = models.CharField(max_length=100)
    # Relationship Attributes
    rank = models.IntegerField()
    rank_m = models.IntegerField('Music Rank', blank=True, null=True)
    rank_p = models.IntegerField('Performance Rank', blank=True, null=True)
    rank_s = models.IntegerField('Singing Rank', blank=True, null=True)
    m = models.IntegerField('Music')
    p = models.IntegerField('Performance')
    s = models.IntegerField('Singing')
    tot_score = models.IntegerField('Total')
    m_pc = models.DecimalField('Music %', max_digits=4, decimal_places=1)
    p_pc = models.DecimalField('Presentation %', max_digits=4, decimal_places=1)
    s_pc = models.DecimalField('Singing %', max_digits=4, decimal_places=1)
    pc_score = models.DecimalField('Total %', max_digits=4, decimal_places=1)
    n = models.IntegerField('Number of songs')
    size = models.IntegerField(blank=True, null=True)     # chorus only

    # Methods
    def __str__(self):
        return "%s - %s" % (self.contestant.name, self.contest.date)

    # check if quartet or chorus
    def type(self):
        return self.contest.type[0]


class Stream(models.Model):
    contestantapp = models.ForeignKey(ContestantApp, on_delete=models.CASCADE)
    stream = models.CharField('Stream', max_length=1, choices=STREAM_CHOICES)
    rank = models.IntegerField(blank=True, null=True)


class SongApp(models.Model):
    """
    Models the appearance (the singing) of a Song during a ContestantApp
    One ContestantApp --< Many SongApps >-- One Song
    """
    # Foreign Keys
    contestantapp = models.ForeignKey(ContestantApp, on_delete=models.CASCADE)
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    # Name as recorded on the scoresheet
    name = models.CharField(max_length=100)
    # Relationship attributes (i.e. score for the song)
    m = models.IntegerField('Music')
    mr = models.IntegerField('Music Penalty', blank=True, null=True)
    p = models.IntegerField('Performance')
    pr = models.IntegerField('Performance Penalty', blank=True, null=True)
    s = models.IntegerField('Singing')
    tot_score = models.IntegerField('Total')
    m_pc = models.DecimalField('Music %', max_digits=4, decimal_places=1)
    p_pc = models.DecimalField('Presentation %', max_digits=4, decimal_places=1)
    s_pc = models.DecimalField('Singing %', max_digits=4, decimal_places=1)
    pc_score = models.DecimalField('Total %', max_digits=4, decimal_places=1)
    n = models.IntegerField('Number of songs')

    def __str__(self):
        return "%s - %s" % (self.song.name, self.contestantapp.contest.date)

    # def contest_type(self):
    #     return self.contestantapp.contest.type
    #
    # def get_contest_type_display(self):
    #     return self.contestantapp.contest.get_type_display()

class Member(models.Model):
    """
    Models a person's participation in a contestant's appearance
    """
    # Foreign Keys
    contestantapp = models.ForeignKey(ContestantApp, on_delete=models.CASCADE)
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    # Name as recorded on the scoresheet
    name = models.CharField(max_length=100)
    # Relationship attributes
    part = models.CharField('Category', max_length=5, choices=(
        ('tenor', 'T'),
        ('lead', 'L'),
        ('bari', 'Br'),
        ('bass', 'Bs'),
        ('director', 'Dir'),
    ))

    def __str__(self):
        return self.person.name


class Video(models.Model):
    """
    Video of a song performance
    """
    songapp = models.ForeignKey(SongApp, on_delete=models.CASCADE)
    link = models.URLField()
