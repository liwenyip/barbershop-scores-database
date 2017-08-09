from django.contrib import admin
import nested_admin
from . models import *

admin.AdminSite.site_header = 'British Barbershop Scores'

class SongAppInline(nested_admin.NestedTabularInline):
    model = SongApp
    extra = 0

class MemberInline(nested_admin.NestedTabularInline):
    model = Member
    extra = 0

class ContestantAppInline(nested_admin.NestedTabularInline):
    model = ContestantApp
    inlines = [SongAppInline, MemberInline]
    extra = 0

class JudgeInline(nested_admin.NestedTabularInline):
    model = Judge
    extra = 0

class ContestAdmin(nested_admin.NestedModelAdmin):
    model = Contest
    inlines = [ContestantAppInline, JudgeInline]
    extra = 0

admin.site.register(Contest, ContestAdmin)
admin.site.register(Judge)
admin.site.register(Person)
admin.site.register(Contestant)
admin.site.register(ContestantApp)
admin.site.register(Song)
admin.site.register(SongApp)

