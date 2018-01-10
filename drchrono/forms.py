from django import forms
from localflavor.us.forms import USSocialSecurityNumberField
from phonenumber_field.formfields import PhoneNumberField


class CheckinForm(forms.Form):
    first_name = forms.CharField(max_length=100, label='First Name',
                                 widget=forms.TextInput(attrs={'required': True, 'class': 'form-control'}))

    last_name = forms.CharField(max_length=100, label='Last Name',
                                widget=forms.TextInput(attrs={'required': True, 'class': 'form-control'}))

    social_security_number = USSocialSecurityNumberField(label='Social Security Number',
                                                         error_messages={'invalid': 'Must enter valid US Social '
                                                                                    'Security Number XXX-XX-XXXX'},
                                                         widget=forms.TextInput(attrs={'required': True,
                                                                                       'class': 'form-control'}))

    # Handling form filled with only white spaces
    def clean(self):
        cleaned_data = super(CheckinForm, self).clean()
        first_name = cleaned_data.get("first_name")
        last_name = cleaned_data.get("last_name")
        social_security_number = cleaned_data.get("social_security_number")

        msg = "Must not be only white spaces."

        if first_name and first_name.strip() == "":
            self.add_error('first_name', msg)
        if last_name and last_name.strip() == "":
            self.add_error('last_name', msg)
        if social_security_number and social_security_number.strip() == "":
            self.add_error('social_security_number', msg)


class WalkinForm(CheckinForm):
    gender = forms.ChoiceField(required=True, choices=[("Male", "Male"), ("Female", "Female"), ("Other", "Other")])


class DemographicsForm(forms.Form):
    patient_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    appointment_id = forms.CharField(required=False, widget=forms.HiddenInput())

    cell_phone = forms.RegexField(label='Cell Phone Number',
                                  regex=r'^\+?1?\d{9,15}$',
                                  error_messages={
                                      "invalid": "Phone numbers must be entered in the "
                                                 "format: '+999999999999999'. Up to 15 digits allowed."
                                  },
                                  widget=forms.TextInput(attrs={'class': 'form-control'}))

    email = forms.EmailField(required=False, label='Email', widget=forms.EmailInput(attrs={'class': 'form-control'}))

    zip_code = forms.RegexField(required=False, regex='^\d{5}$', label='Zip Code',
                                error_messages={'invalid': 'Enter a valid US zip code in the format 99999'},
                                widget=forms.TextInput(attrs={'class': 'form-control'}))

    address = forms.CharField(required=False, label='Address', widget=forms.TextInput(attrs={'class': 'form-control'}))

    emergency_contact_phone = forms.RegexField(label='Emergency Phone Number',
                                               regex=r'^\+?1?\d{9,15}$',
                                               error_messages={
                                                   "invalid": "Phone numbers must be entered in the "
                                                              "format: '+999999999999999'. Up to 15 digits allowed."
                                               },
                                               widget=forms.TextInput(attrs={'class': 'form-control'}))

    emergency_contact_name = forms.CharField(required=False, max_length=250, label='Emergency Contact Name',
                                             widget=forms.TextInput(attrs={'class': 'form-control'}))

    initial_form_data = forms.CharField(required=False, widget=forms.HiddenInput())
