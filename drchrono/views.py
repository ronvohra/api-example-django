from django.contrib.auth import logout as user_logout
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from drchrono.forms import CheckinForm, DemographicsForm, WalkinForm
from dateutil import parser as date_parser

from drchrono.models import Doctor, Patient, Appointment, Arrival

import json
import requests
import datetime
import pytz
import logging

log = logging.getLogger(__name__)

logging.basicConfig(format='%(asctime)s %(levelname)s %(module)s.%(funcName)s %(message)s', level=logging.INFO)


def login_page(request):
    if request.user.is_authenticated():
        return redirect(index)
    else:
        return render(request, 'login-page.html')


def logout(request):
    user_logout(request)
    return redirect(login_page)


@login_required(login_url=login_page)
def index(request):
    curr_date = get_local_datetime(request)
    auth_header = get_auth_header(request)
    # if doctor_id not in DB, create entry
    try:
        doctor = Doctor.objects.get(user=request.user)
        log.info("Found doctor")
    except ObjectDoesNotExist:
        log.info("Calling API")
        doctor = Doctor(user=request.user)
        doctor.doctor_id = get_doctor_id(auth_header)
        doctor.save()

    # updated patient objects to DB
    _ = get_all_patients(auth_header)
    curr_appointments = get_appointments_on_date_for_doctor(doctor.doctor_id, curr_date, auth_header)
    content = {}
    average_wait_time = get_average_wait_time(doctor.doctor_id)
    if average_wait_time:
        content['average_wait_time'] = average_wait_time

    content['curr_appointments'] = curr_appointments
    return render(request, 'index.html', content)


# work in doctor timezone
def get_local_datetime(request):
    user_timezone = request.COOKIES.get('tzname_from_user', 'UTC')
    return datetime.datetime.now(pytz.timezone(user_timezone))


def get_auth_header(request):
    access_token = request.user.social_auth.get(provider='drchrono').extra_data['access_token']
    headers = {
        'Authorization': 'Bearer ' + access_token
    }
    return headers


def get_doctor_id(auth_header):
    users_url = 'https://drchrono.com/api/users/current'
    resp = requests.get(users_url, headers=auth_header)
    resp.raise_for_status()
    return resp.json()['doctor']


# fetch all appointments for doctor from API, and persist them to database
def get_appointments_on_date_for_doctor(doctor_id, curr_date, auth_header):

    appointments = []
    appointments_url = 'https://drchrono.com/api/appointments?doctor=' + str(doctor_id) + '&date=' + str(curr_date)
    while appointments_url:

        resp = requests.get(appointments_url, headers=auth_header)
        resp.raise_for_status()
        data = resp.json()

        # If retrieved appointment isn't in the database, create an appointment record
        for appointment in data['results']:

            appointment_obj, created_now = Appointment.objects.get_or_create(
                appointment_id=appointment['id'],
                patient=Patient.objects.get(patient_id=appointment['patient']),
                doctor_id=appointment['doctor']
            )
            if created_now:
                appointment_obj.time_waited = None

            appointment_obj.status = appointment['status']
            appointment_obj.scheduled_time = appointment['scheduled_time']
            appointment_obj.save()
            appointment_obj.scheduled_time = date_parser.parse(appointment['scheduled_time'])

            appointments.append(appointment_obj)

        # last page returns a null for appointments_url
        appointments_url = data['next']
    return appointments


# fetch completed or ongoing appointments from database; get average of time waited (floor)
def get_average_wait_time(doctor_id):

    completed_appointments = Appointment.objects.filter(
        (Q(status='Complete') | Q(status='In Session')) & Q(doctor_id=doctor_id)
    )
    if not completed_appointments:
        return None

    completed_appointments = [appointment.time_waited for appointment in completed_appointments]

    avg = sum(completed_appointments, datetime.timedelta()) / len(completed_appointments)
    avg = str(avg).split('.')[0]  # remove fractions smaller than a second from timedelta object

    return avg


# get specific patient by matching entered form data from API call; return first match if found else None
def get_patient_info(first_name, last_name, doctor_id, social_security_number, auth_header):
    patients_url = 'https://drchrono.com/api/patients?doctor=' + str(doctor_id) + \
                   '&first_name=' + first_name + '&last_name=' + last_name
    while patients_url:
        resp = requests.get(patients_url, headers=auth_header)
        resp.raise_for_status()
        data = resp.json()

        for patient in data['results']:  # find patient matching name and ssn

            # don't validate on social security number since it isn't in the test DB
            if patient['first_name'] == first_name and patient['last_name'] == last_name:
                return patient

        patients_url = data['next']  # a JSON null on the last page

    # no patient matched first name, last name and ssn
    return None


# fetch all patients of doctor from API, and persist them to database
def get_all_patients(auth_header):
    patients = []
    patients_url = 'https://drchrono.com/api/patients'
    while patients_url:
        resp = requests.get(patients_url, headers=auth_header)
        resp.raise_for_status()

        for patient in resp.json()['results']:
            # If retrieved patient isn't in the database, create an patient record
            patient_obj, created = Patient.objects.get_or_create(patient_id=patient['id'], doctor_id=patient['doctor'])
            if created:
                patient_obj.gender = patient['gender']
                patient_obj.first_name = patient['first_name']
                patient_obj.last_name = patient['last_name']
                patient_obj.email = patient['email']
                patient_obj.save()
            patients.append(patient_obj)

        patients_url = resp.json()['next']  # A JSON null on the last page

    return patients


# look up scheduled appointments on current date for patient ID from API
def get_appointment_on_date_for_patient(patient_id, curr_date, auth_header):

    appointments_url = "https://drchrono.com/api/appointments?date=" + str(curr_date) + "&patient=" + str(patient_id)

    resp = requests.get(appointments_url, headers=auth_header)
    resp.raise_for_status()
    results = resp.json().get('results')

    return results[0] if results else None  # either return the first appointment found or the patient has none


@login_required(login_url=login_page)
def register_walkin_patient(request):

    if request.method == 'POST':

        walkin_form = WalkinForm(request.POST)

        if walkin_form.is_valid():

            first_name = walkin_form.cleaned_data['first_name'].strip()
            last_name = walkin_form.cleaned_data['last_name'].strip()
            social_security_number = walkin_form.cleaned_data['social_security_number'].strip()
            gender = walkin_form.cleaned_data['gender'].strip()
            doctor_id = Doctor.objects.get(user=request.user).doctor_id

            curr_date = get_local_datetime(request)
            auth_header = get_auth_header(request)
            patient_info = get_patient_info(first_name, last_name, doctor_id, social_security_number, auth_header)

            if patient_info:
                # get patient info from API
                patient_appointment = get_appointment_on_date_for_patient(patient_info['id'], curr_date, auth_header)

                if patient_appointment:
                    # Initial data from API; if found, update demographics form pre-fill
                    initial_data = {
                        'patient_id': patient_info['id'],
                        'appointment_id': patient_appointment['id'],
                        'cell_phone': patient_info['cell_phone'],
                        'email': patient_info['email'],
                        'zip_code': patient_info['zip_code'],
                        'address': patient_info['address'],
                        'emergency_contact_phone': patient_info['emergency_contact_phone'],
                        'emergency_contact_name': patient_info['emergency_contact_name']
                    }

                    initial_data['initial_form_data'] = json.dumps(initial_data, ensure_ascii=False)
                    demographics_form = DemographicsForm(initial=initial_data)

                    return render(request, 'update-demographics.html', {'demographics_form': demographics_form})

                else:
                    # no appointments today for patient
                    walkin_form.add_error('first_name', 'You have no appointments scheduled for today')
                    # TODO: add appointment creation for walk-in patient

            else:  # no appointments found for patient with given name and/or SSN
                create_patient(request, doctor_id, first_name, last_name, social_security_number, gender)
                # TODO: add appointment creation for walk-in patient

        return render(request, 'kiosk-walkin.html', {'walkin_form': walkin_form})

    # if GET request, render kiosk page with empty form
    walkin_form = WalkinForm()
    return render(request, 'kiosk-walkin.html', {'walkin_form': walkin_form})


@login_required(login_url=login_page)
def checkin_patient(request):

    if request.method == 'POST':

        checkin_form = CheckinForm(request.POST)

        if checkin_form.is_valid():

            first_name = checkin_form.cleaned_data['first_name'].strip()
            last_name = checkin_form.cleaned_data['last_name'].strip()
            social_security_number = checkin_form.cleaned_data['social_security_number'].strip()
            doctor_id = Doctor.objects.get(user=request.user).doctor_id

            curr_date = get_local_datetime(request)
            auth_header = get_auth_header(request)
            patient_info = get_patient_info(first_name, last_name, doctor_id, social_security_number, auth_header)

            if patient_info:
                # get patient info from API
                patient_appointment = get_appointment_on_date_for_patient(patient_info['id'], curr_date, auth_header)

                if patient_appointment:
                    # Initial data from API; if found, update demographics form pre-fill
                    initial_data = {
                        'patient_id': patient_info['id'],
                        'appointment_id': patient_appointment['id'],
                        'cell_phone': patient_info['cell_phone'],
                        'email': patient_info['email'],
                        'zip_code': patient_info['zip_code'],
                        'address': patient_info['address'],
                        'emergency_contact_phone': patient_info['emergency_contact_phone'],
                        'emergency_contact_name': patient_info['emergency_contact_name']
                    }

                    initial_data['initial_form_data'] = json.dumps(initial_data, ensure_ascii=False)
                    demographics_form = DemographicsForm(initial=initial_data)

                    return render(request, 'update-demographics.html', {'demographics_form': demographics_form})

                else:
                    # no appointments today for patient
                    checkin_form.add_error('first_name', 'You have no appointments scheduled for today')

            else:  # no appointments found for patient with given name and/or SSN
                checkin_form.add_error('first_name', 'No patient found; please check that your name and '
                                                     'social security number have been entered correctly')

        return render(request, 'kiosk-base.html', {'checkin_form': checkin_form})

    # if GET request, render kiosk page with empty form
    checkin_form = CheckinForm()
    return render(request, 'kiosk-base.html', {'checkin_form': checkin_form})


@login_required(login_url='/login_page')
def update_demographics(request):

    if request.method == 'POST':

        # update form with initial data from check-in page
        initial_data = json.loads(request.POST['initial_form_data'])
        initial_data['initial_form_data'] = json.dumps(initial_data, ensure_ascii=False)

        # update demographics form with initial data and supplied data
        demographics_form = DemographicsForm(request.POST, initial=initial_data)

        if demographics_form.is_valid():

            auth_header = get_auth_header(request)

            # if supplied data differs from initial checkin data, remove initial data
            if 'initial_form_data' in demographics_form.changed_data:
                demographics_form.changed_data.remove('initial_form_data')

            if demographics_form.has_changed():
                log.info("The following fields changed: %s" % ", ".join(demographics_form.changed_data))

                updated = submit_update(demographics_form, auth_header)
                # if updating the demographics via API fails
                if not updated:
                    demographics_form.add_error('mobile', 'Sorry, we are unable to update '
                                                          'your demographics data right now - please try again')
                    return render(request, 'update-demographics.html', {'demographics_form': demographics_form})

            # change appointment status to 'arrived' via the API
            changed = change_appointment_status(demographics_form.cleaned_data['appointment_id'], auth_header, "Arrived")
            # if changing the appointment status via API fails
            if not changed:
                demographics_form.add_error('mobile', 'Sorry, we are unable to update '
                                                      'your appointment status right now - please try again')
                return render(request, 'update-demographics.html', {'demographics_form': demographics_form})

            patient_queue = len(Appointment.objects.filter(Q(status='Arrived') | Q(status='In Session')))

            # change appointment status to 'arrived' via the DB
            appointment_obj = Appointment.objects.get(appointment_id=demographics_form.cleaned_data['appointment_id'])
            appointment_obj.status = "Arrived"
            appointment_obj.arrival_time = get_local_datetime(request)
            appointment_obj.save()
            log.info("New arrival time: %s" % str(appointment_obj.arrival_time))

            content = {'patient_queue': patient_queue}

            # alert doctor that this patient has arrived and has checked-in with updated demographics
            # add patient to arrival queue and add to poll
            add_to_arrivals(appointment_obj)
            return render(request, 'completed-checkin.html', content)

        # demographics form is invalid, retry
        return render(request, 'update-demographics.html', {'demographics_form': demographics_form})
    else:
        checkin_form = CheckinForm()
        return render(request, 'kiosk-base.html', {'checkin_form': checkin_form})


# send updated demographic information upstream
def submit_update(demographics_form, auth_header):
    data = {}
    changed_fields = demographics_form.changed_data
    for field in changed_fields:
        data[field] = demographics_form.cleaned_data[field]

    url = 'https://drchrono.com/api/patients/' + str(demographics_form.cleaned_data['patient_id'])

    r = requests.patch(url, data=data, headers=auth_header)
    r.raise_for_status()
    logging.info("REQ: Update patient demographic details :: REQ_DETAILS: %s :: RESP:-> Status code: %d, TEXT: %s" %
                 (r.request, r.status_code, r.text))

    if r.status_code == 204:  # TODO: Check if r.ok includes 204
        return True

    return False


# send updated appointment information upstream
def change_appointment_status(appointment_id, auth_header, status):
    data = {'status': status}
    url = "https://drchrono.com/api/appointments/" + str(appointment_id)

    r = requests.patch(url, data=data, headers=auth_header)
    r.raise_for_status()
    logging.info("REQ: Change appointment status :: REQ_DETAILS: %s :: RESP:-> Status code: %d, TEXT: %s" %
                 (r.request, r.status_code, r.text))

    if r.status_code == 204:  # Successful patch returns a 204
        return True

    return False


# add appointments as arrival objects to database
def add_to_arrivals(appointment_obj):
    _, _ = Arrival.objects.get_or_create(appointment_id=appointment_obj.appointment_id,
                                         doctor_id=appointment_obj.doctor_id)


# if appointments exist, this will be called from index.js. Allows patient to be marked
# as arrived, starts wait timer and enables action for doctor to see patient
def poll_for_updates(request):
    if request.method == 'POST':
        try:
            log.debug('polling...')
            doctor_id = Doctor.objects.get(user=request.user).doctor_id
            updates = Arrival.objects.filter(doctor_id=doctor_id)
            updates = map(lambda x: x.appointment_id, updates)

            Arrival.objects.all().delete()
            return JsonResponse({'status': 'success', 'updates': updates})
        except:
            return JsonResponse({'status': 'fail', 'message': 'Failed to poll'})


# triggered from front-end; stops wait timer when patient is called in and updates
# patient appointment status to 'in session'. Returns update to avg wait time
def call_in_patient(request):

    if request.method == 'POST':

        appointment_id = request.POST['appointment_id']
        datetime_patient_called_in = request.POST['current_date_time']
        datetime_patient_called_in = date_parser.parse(datetime_patient_called_in)

        appointment = Appointment.objects.get(appointment_id=appointment_id)
        appointment.status = "In Session"

        delta = datetime_patient_called_in - appointment.arrival_time

        appointment.time_waited = delta
        appointment.save()

        auth_header = get_auth_header(request)
        change_appointment_status(appointment_id, auth_header, "In Session")

        doctor_id = appointment.doctor_id
        avg_wait_time = get_average_wait_time(doctor_id)

        return JsonResponse({'status': 'success', 'avg_wait_time': avg_wait_time})


# triggered from index.js to complete appointment
def appointment_completed(request):

    if request.method == 'POST':

        appointment_id = request.POST['appointment_id']
        appointment = Appointment.objects.get(appointment_id=appointment_id)
        appointment.status = "Complete"
        appointment.save()

        auth_header = get_auth_header(request)
        change_appointment_status(appointment_id, auth_header, 'Complete')

        return HttpResponse('ok')


def create_patient(request, doctor_id, first_name, last_name, social_security_number, gender):

    patients_url = 'https://drchrono.com/api/patients'
    auth_header = get_auth_header(request)
    auth_header['Content-Type'] = "application/json"
    payload = {
        'doctor': int(doctor_id),
        'first_name': first_name,
        'last_name': last_name,
        'gender': gender,
        'social_security_number': social_security_number
    }

    resp = requests.post(patients_url,  json=payload, headers=auth_header)
    resp.raise_for_status()
    patient_obj, created = Patient.objects.get_or_create(patient_id=resp.json()['id'], doctor_id=doctor_id)
    if created:
        patient_obj.gender = gender
        patient_obj.first_name = first_name
        patient_obj.last_name = last_name
        patient_obj.save()

    return True


# TODO: Complete this by fetching office information and a way to check overlaps
def create_appointment(request, doctor_id, first_name, last_name, social_security_number, gender):

    appointments_url = 'https://drchrono.com/api/appointments'
    auth_header = get_auth_header(request)
    auth_header['Content-Type'] = "application/json"
    payload = {}

    resp = requests.post(appointments_url,  json=payload, headers=auth_header)

    resp.raise_for_status()

    return True
