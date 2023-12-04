import csv
import datetime

from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.views import generic
from edc_appointment.models import Appointment
from edc_base.view_mixins import EdcBaseViewMixin
from edc_navbar import NavbarViewMixin

from .model_wrappers import ParticipantNoteModelWrapper, ReminderModelWrapper
from .models import ParticipantNote, Reminder
from .utils import AppointmentHelper, CustomCalendar, DateHelper
from .utils.export_helper import children_appointment_cls, collect_events, \
    extract_cohort_name


class CalendarView(NavbarViewMixin, EdcBaseViewMixin, generic.ListView):
    navbar_name = 'flourish_calendar'
    navbar_selected_item = 'calendar'
    model = Appointment
    template_name = 'flourish_calendar/calendar.html'

    @property
    def new_reminder_wrapper(self):
        reminder = Reminder()
        reminder_wrapper = ReminderModelWrapper(model_obj=reminder)
        return reminder_wrapper

    @property
    def new_participant_wrapper(self):
        participant_note = ParticipantNote()
        participant_note_wrapper = ParticipantNoteModelWrapper(
            model_obj=participant_note
        )
        return participant_note_wrapper

    def get(self, request, *args, **kwargs):

        subject_identifier = request.GET.get('subject_identifier', None)
        visit_code = request.GET.get('visit_code', None)
        color = request.GET.get('choice', None)
        date = request.GET.get('date', None)

        AppointmentHelper.change_color(
            subject_identifier=subject_identifier,
            visit_code=visit_code,
            color=color,
            appt_date=date
        )

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        month = self.request.GET.get('month', None)

        # use today's date for the calendar
        d = DateHelper.get_date(month)

        search_filter = self.request.GET.get('filter', None)
        search_term = self.request.GET.get('search_term', None)

        if search_filter:
            self.request.session['filter'] = search_filter
        elif search_filter == 'all':
            del self.request.session['filter']

        if search_filter:
            search_term = search_term.strip()
            self.request.session['search_term'] = search_term.strip()
        else:
            if self.request.session.get('search_term', None):
                del self.request.session['search_term']

        # Instantiate our calendar class with today's year and date
        cal = CustomCalendar(d.year, d.month, self.request)

        # Call the formatmonth method, which returns our calendar as a table

        html_cal = cal.formatmonth(withyear=True)

        appointment_search_results = AppointmentHelper.all_search_appointments(
            subject_identifier=search_term,
            type=search_filter)

        notes_search_results = AppointmentHelper.all_notes(search_term=search_term)

        context.update(
            prev_month=DateHelper.prev_month(d),
            next_month=DateHelper.next_month(d),
            calendar=mark_safe(html_cal),
            filter=search_filter,
            search_term=search_term,
            appointment_search_results=appointment_search_results,
            notes_search_results=notes_search_results,
            new_reminder_url=self.new_reminder_wrapper.href,
            new_participant_note_url=self.new_participant_wrapper.href)

        return context


def export_events_as_csv(request):
    csv_headers = ['Event Type', 'Event Date and Time', 'Details', 'Subject Identifier',
                   'Visit Code', 'Cohort', 'Schedule Name']

    # Generate datetime stamp for file name
    timestamp_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    # Generate HTTP Response Object
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = (f'attachment; filename="appointments_from_'
                                       f'{timestamp_str}.csv"')

    writer = csv.writer(response)
    writer.writerow(csv_headers)

    events = collect_events(request)

    unified_list = list()

    for event in events:
        if isinstance(event, children_appointment_cls):
            unified_list.append({
                'Event Type': 'Appointment',
                'Date': event.appt_datetime,
                'subject_identifier': event.subject_identifier,
                'visit_code': event.visit_code,
                'cohort': extract_cohort_name(event.subject_identifier),
                'schedule_name': event.schedule_name,
            })
        elif isinstance(event, ParticipantNote):
            unified_list.append({
                'Event Type': 'Participant Note',
                'Date': event.date,
                'subject_identifier': event.subject_identifier,
                'Details': f'{event.title}: {event.description}'
            })

    for obj in unified_list:
        writer.writerow([obj['Event Type'], obj['Date'], obj.get('Details', ''),
                         obj.get('subject_identifier', ''), obj.get('visit_code', ''),
                         obj.get('cohort', ''), obj.get('schedule_name', ''), ])

    return response
