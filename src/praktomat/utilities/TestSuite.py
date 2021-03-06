from django.test.simple import DjangoTestSuiteRunner
from django.test import TestCase as DjangoTestCase
from django.conf import settings
from os.path import dirname, join
from shutil import rmtree

class TestSuiteRunner(DjangoTestSuiteRunner):
	testSuiteUploadRoot = join(settings.UPLOAD_ROOT, 'TestSuite')
	
	def setup_test_environment(self, **kwargs):
		""" Change the upload root to not mess up the production folder """
		super(TestSuiteRunner, self).setup_test_environment(**kwargs)
		settings.UPLOAD_ROOT = self.testSuiteUploadRoot	
		settings.MEDA_ROOT = self.testSuiteUploadRoot # just in case
		# storage object is lazy and is not updated by simply updating the settings
		from django.core.files.storage import default_storage
		default_storage.location = self.testSuiteUploadRoot
		
	def setup_databases(self, **kwargs):
		""" Prefill database with some testdata. Rollbacks ensure that the database is in the state after create_test_data().
		Rollbacks need to be suported by the database otherwise the db will be flushed after every test. 
		This is much quicker than creating everything in setUp() and more flexeble than fixtures as u can use files. """
		x = super(TestSuiteRunner, self).setup_databases(**kwargs)
		create_test_data()
		return x

	def teardown_test_environment(self, **kwargs):
		super(TestSuiteRunner, self).teardown_test_environment(**kwargs)
		try:
			rmtree(self.testSuiteUploadRoot)
		except:
			pass



class TestCase(DjangoTestCase):
	
	def assertRedirectsToView(self, response, view):
		""" Asserts whether the request was redirected to a specifivc view function. """
		from urlparse import urlparse
		from django.core.urlresolvers import resolve
		if hasattr(response, 'redirect_chain'):
			url = response.redirect_chain[-1][0]
		else:
			url = response['Location']
		self.assertEquals(resolve(urlparse(url)[2])[0].__name__, view)


from praktomat.accounts.models import User, Tutorial
from django.contrib.auth.models import Group
from praktomat.tasks.models import Task
from praktomat.solutions.models import Solution, SolutionFile
from praktomat.attestation.models import Attestation

from datetime import datetime
from datetime import timedelta

from django.core.files import File

def create_test_data():
	""" Fills the test db with objects needed in the unit tests. """
	
	# Users & Tutorials
	trainer = User.objects.create_user('trainer', 'trainer@praktomat.com', 'demo')
	trainer.groups.add(Group.objects.get(name='Trainer'))
	trainer.is_staff = True
	trainer.save()
	
	tutor = User.objects.create_user('tutor', 'trainer@praktomat.com', 'demo')
	tutor.groups.add(Group.objects.get(name='Tutor'))
	
	tutorial = Tutorial.objects.create(name='Tutorial 1')
	tutorial.tutors.add(tutor)
	
	user = User.objects.create_user('user', 'user@praktomat.com', 'demo')
	user.groups.add(Group.objects.get(name='User'))
	user.tutorial = tutorial
	user.save()

	# Tasks
	task = Task.objects.create(
			title = 'Test task',
			description = 'Test description.',
			publication_date = datetime.now(),
			submission_date =  datetime.now() + timedelta(hours=5)
			#model_solution
			#all_checker_finished = False
			#final_grade_rating_scale =
		)

	# Solutions
	solution = Solution.objects.create(	task = task, author = user )

	solution_file = SolutionFile.objects.create (solution = solution)
	solution_file.file.save('GgT.java', File(open(join(dirname(dirname(dirname(dirname(__file__)))), 'examples', 'Tasks', 'GGT', 'solutions', 'GgT.java'))))
			
	# Attestation
	attestation = Attestation.objects.create(solution = solution, author=tutor) # final, published
	
def dump(obj):
	""" Kinda like obj.__meta__ but shows more, very usefull for testcase debuging. """
	for attr in dir(obj):
		print "obj.%s = %s" % (attr, getattr(obj, attr))

