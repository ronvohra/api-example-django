# drchrono-kiosk

This is a doctor dashboard and patient check-in kiosk built with Django and the 
DrChrono API. The user is intended to be a doctor who can see his daily scheduled 
appointments, monitor and call in waiting patients and mark them as seen. 
On the patient side of things, patients with scheduled appointments can check themselves
in and update their demographics. Walk-in patients can also sign themselves in, go through
the check-in process and update their demographics as well **(this feature is incomplete
since appointment scheduling still needs to be built)**.

### Future Work

* Change datetimes from naive to aware
* Finish walk-in appointment scheduling
* Create front-end from scratch

### Requirements
- [pip](https://pip.pypa.io/en/stable/)
- [python virtual env](https://packaging.python.org/installing/#creating-and-using-virtual-environments)

### Setup
``` bash
$ pip install -r requirements.txt
$ python manage.py runserver
```

`social_auth_drchrono/` contains a custom provider for [Python Social Auth](http://python-social-auth.readthedocs.io/en/latest/) that handles OAUTH for drchrono. To configure it, set these fields in your `drchrono/settings.py` file:

```
SOCIAL_AUTH_DRCHRONO_KEY
SOCIAL_AUTH_DRCHRONO_SECRET
SOCIAL_AUTH_DRCHRONO_SCOPE
LOGIN_REDIRECT_URL
```

