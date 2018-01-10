from django.db import models
from django.contrib.auth.models import User
from localflavor.us.models import USSocialSecurityNumberField
from phonenumber_field.modelfields import PhoneNumberField


class Doctor(models.Model):
    user = models.OneToOneField(User)
    doctor_id = models.IntegerField()

MALE = 'M'
FEMALE = 'F'
OTHER = 'O'
GENDER_CHOICES = (
    (MALE, 'Male'),
    (FEMALE, 'Female'),
    (OTHER, 'Undisclosed or non-binary'),
)


class Patient(models.Model):

    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, default=OTHER)
    patient_id = models.IntegerField(unique=True)
    doctor_id = models.IntegerField()
    first_name = models.CharField(max_length=250)
    last_name = models.CharField(max_length=250)
    email = models.EmailField()
    social_security_number = USSocialSecurityNumberField()
    cell_phone = PhoneNumberField(blank=True)

    def __str__(self):
        return 'Patient :: Name: %s %s, Patient ID: %s' % (self.first_name,
                                                           self.last_name,
                                                           str(self.patient_id))


class Appointment(models.Model):

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    appointment_id = models.CharField(unique=True, max_length=100)
    doctor_id = models.IntegerField()
    scheduled_time = models.DateTimeField(auto_now=False, auto_now_add=False, null=True)
    arrival_time = models.DateTimeField(auto_now=False, auto_now_add=False, null=True, default=None)
    time_waited = models.DurationField(null=True)
    status = models.CharField(max_length=100, default='')

    def __str__(self):
        return 'Appointment :: Patient name: %s %s, Scheduled time: %s' % (self.patient.first_name,
                                                                           self.patient.last_name,
                                                                           str(self.scheduled_time))


class Arrival(models.Model):
    appointment_id = models.CharField(unique=True, max_length=100)
    doctor_id = models.IntegerField()

    def __str__(self):
        return 'Arrival :: Appointment ID: %s' % self.appointment_id
