$( document ).ready(function() {

	var timezone = jstz.determine();
	var tzname = timezone.name();

	Cookies.set('tzname_from_user', tzname);

});
