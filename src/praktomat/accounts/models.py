import datetime
import re
import hashlib
import random

from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.db import models, utils
from django.contrib.auth.models import User as BasicUser, UserManager
from django.db.models import signals
from django.core.validators import RegexValidator
from django.core import serializers
from django.db import transaction

from praktomat.accounts.templatetags.in_group import in_group
from praktomat.configuration import get_settings


class User(BasicUser):
	
	# all fields need to be null-able in order to create user 
	tutorial = models.ForeignKey('Tutorial', null=True, blank=True, help_text = _("The tutorial the student belongs to."))
	def validate_mat_number(value):
		regex = get_settings().mat_number_validation_regex
		if regex:
			RegexValidator("^"+regex+"$", message="This is not a valid student number.", code="")(value)
	mat_number = models.IntegerField( null=True, blank=True, unique=True, validators=[validate_mat_number]) # special blank and unique validation in forms
	final_grade = models.CharField( null=True, blank=True, max_length=100,  help_text = _('The final grade for the whole class.'))
	
	activation_key=models.CharField(_('activation key'), max_length=40, editable=False)
	
	# Use UserManager to get the create_user method, etc.
	objects = UserManager()
	
	def __unicode__(self):
		
		return self.get_full_name() or self.username
	
	def set_new_activation_key(self):
		# The activation key will be a SHA1 hash, generated from a combination of the username and a random salt.
		sha = hashlib.sha1()
		sha.update( str(random.random()) + self.username)
		self.activation_key = sha.hexdigest()
		self.save()
	
	def activation_key_expired(self):
		"""
		Determine whether the activation key has expired, returning a boolean 
		-- ``True`` if the key has expired.
		
		Key expiration is determined by a two-step process:
		
		1. 	If the user has already activated, the key will have been
			reset to the string ``ALREADY_ACTIVATED``. Re-activating is
			not permitted, and so this method returns ``True`` in this
			case.
			
		2. 	Otherwise, the date the user signed up is incremented by
			the number of days specified in the setting
			''ACCOUNT_ACTIVATION_DAYS`` (which should be the number of
			days after signup during which a user is allowed to
			activate their account); if the result is less than or
			equal to the current date, the key has expired and this
			method returns ``True``.
		"""
		expiration_date = datetime.timedelta(days=settings.ACCOUNT_ACTIVATION_DAYS)
		return self.activation_key == u"ALREADY_ACTIVATED" or \
			(self.user.date_joined + expiration_date <= datetime.datetime.now())
	activation_key_expired.boolean = True
	
	def activate_user(activation_key):
		"""
		Validate an activation key and activate the corresponding
		''User`` if valid.
		
		If the key is valid and has not expired, return the ``User``
		after activating.
		
		If the key is not valid or has expired, return ``False``.
		
		If the key is valid but the ``User`` is already active,
		return ``False``.
		
		To prevent reactivation of an account which has been
		deactivated by site administrators, the activation key is
		reset to the string ``ALREADY_ACTIVATED`` after successful
		activation.
		
		"""
		# Make sure the key we're trying conforms to the pattern of a
		# SHA1 hash; if it doesn't, no point trying to look it up in
		# the database.
		SHA1_RE = re.compile('^[a-f0-9]{40}$')
		if SHA1_RE.search(activation_key):
			try:
				user = User.objects.get(activation_key=activation_key)
			except User.DoesNotExist:
				return False
			if not user.activation_key_expired():
				user.is_active = True
				user.activation_key = u"ALREADY_ACTIVATED"
				user.save()
				return user
			return False
	activate_user = staticmethod(activate_user)

	@classmethod
	def export_user(cls, queryset):
		""" Serializes a user queryset and related objects to xml """
		users = list(queryset)
		django_users = list(BasicUser.objects.filter(user__in = queryset))
		return serializers.serialize("xml", django_users + users) # order does matter!
	
	@classmethod
	@transaction.commit_on_success		# May not work with MySQL: see django docu
	def import_user(cls, xml_data):
		basicUser_id_map = {}
		imported_user_ids = []
		for deserialized_object in serializers.deserialize("xml", xml_data):
			object = deserialized_object.object
			if isinstance(object, User):
				try:
					object.tutorial = None
					object.final_grade = None
					object.user_ptr = basicUser_id_map[int(object.pk)]	# object.id is null! so parse id.
					deserialized_object.save()
					imported_user_ids.append(object.pk)
				except KeyError:
					pass # basicUser_id_map key not found because user allredy existed
			else: # brach BasicUser
				try:
					old_id = object.id
					object.id = None
					deserialized_object.save()
					basicUser_id_map[old_id] = object
				except utils.IntegrityError:
					pass # unique username validation - user allredy existed
		return User.objects.filter(id__in = imported_user_ids) 	# get them fresh from the db, otherwise the user object won't have basicUser attributes set
				
				


	
#	def save(self, force_insert=False, force_update=False, *args, **kwargs):
#		""" prevent redundancy: staff iff. superuser or trainer """
#		# the the instance needs to have a primary key value before a many-to-many relationship groups can be used so save it twice
#		super(User, self).save(force_insert=force_insert, force_update=force_update, *args, **kwargs)
#		# Bug: groups are not saved at this point!
#		self.is_staff = (self.is_superuser or in_group(self,'Trainer'))
#		super(User, self).save(force_insert=False, force_update=force_update, *args, **kwargs)
	
def create_user_for_basicuser(sender, **kwargs):
	""" Model inheritance is archived through joining of the base- and subclass's tables. to prevent inconsistencies a User is created every time a BaseUser is created. (ex. manage.py create_superuser)"""
	if kwargs['created']:
		u = User() 
		u.__dict__.update(kwargs['instance'].__dict__)
		u.save()
signals.post_save.connect(create_user_for_basicuser, sender=BasicUser)

class Tutorial(models.Model):
	name = models.CharField(max_length=100, blank=True, help_text=_("The name of the tutorial"))
	# A Tutorial may have many tutors as well as a Tutor may have multiple tutorials
	tutors = models.ManyToManyField('User', limit_choices_to = {'groups__name': 'Tutor'}, related_name='tutored_tutorials', help_text = _("The tutors in charge of the tutorium."))

	def tutors_flat(self):
		return reduce(lambda x, y: x.get_full_name() + ', ' + y.get_full_name(), self.tutors.all())
	tutors_flat.short_description = _('Tutors')

	def __unicode__(self):
		return("%s: %s" % (self.name, self.tutors_flat()))

	


	
	