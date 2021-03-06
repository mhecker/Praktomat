# -*- coding: utf-8 -*-
from os import *
from os.path import *
import subprocess
import shutil
import sys
from django.conf import settings
from django.db import models
from praktomat.tasks.models import Task
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from django.utils.translation import ugettext_lazy as _
from praktomat.utilities import encoding, file_operations

import string
	
def execute(command, working_directory, environment_variables={}, use_default_user_configuration=True):
	""" Wrapper to execute Commands with the praktomat testuser. """
	if isinstance(command, list):
		command = ' '.join(command)
	script = join(join(dirname(__file__),'scripts'),'execute')
	command = script + ' ' + command
	environment = environ
	environment.update(environment_variables)
	if (settings.USEPRAKTOMATTESTER and use_default_user_configuration):
		environment['USEPRAKTOMATTESTER'] = 'TRUE'
	else:
		environment['USEPRAKTOMATTESTER'] = 'False'

	process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=working_directory, env=environment, shell=True)
	[output, error] = process.communicate()
	return [output, error, process.returncode]




class CheckerFileField(models.FileField):
    """ Custom filefield with with greater path length and default upload location. Use this in all checker subclasses!"""
    
    def get_storage_path(instance, filename):
        """ Use this function as upload_to parameter for filefields. """
        return 'CheckerFiles/Task_%s/%s/%s' % (instance.task.pk, instance.__class__.__name__, filename)

    def __init__(self, verbose_name=None, name=None, upload_to=get_storage_path, storage=None, **kwargs):
        # increment filename legth from 100 to 500
        kwargs['max_length'] = kwargs.get('max_length', 500)
        super(CheckerFileField, self).__init__(verbose_name, name, upload_to, storage, **kwargs)

# Tell South how to handle this field
from south.modelsinspector import add_introspection_rules
add_introspection_rules([], ["^praktomat\.checker\.models\.CheckerFileField"])    



class Checker(models.Model):
	""" A Checker implements some quality assurance.
	 
	A Checker has three indicators:
		1. It is *public* - the results are presented to the user
It is *required* - it must be passed for submission
		3. It is run .

	If a Checker is not run always, it is only run if a *task_maker*
	starts the complete rerun of all Checkers. """

	created = models.DateTimeField(auto_now_add=True)
	order = models.IntegerField(help_text = _('Determines the order in wich the checker will start. Not necessary continuously!'))
	
	task = models.ForeignKey(Task)
	
	public = models.BooleanField(default=True, help_text = _('Test results are displayed to the submitter.'))
	required = models.BooleanField(default=False, help_text = _('The test must be passed to submit the solution.'))
	always = models.BooleanField(default=True, help_text = _('The test will run on submission time.'))
	
	class Meta:
		abstract = True
		app_label = 'checker'
		
	def __unicode__(self):
		return self.title()

	def result(self):
		""" Creates a new result.
		May be overloaded by subclasses."""
		return CheckerResult(checker=self)
		
	def run(self, env):
		""" Runs tests in a special environment.
		Returns a CheckerResult. """
		assert isinstance(env, CheckerEnvironment)
		return self.result()

	def title(self):
		""" Returns the title for this checker category. To be overloaded in subclasses. """
		return u"Prüfung"

	@staticmethod
	def description():
		""" Returns a description for this Checker. """
		return u" no description "

	def requires(self):
		""" Returns the list of passed Checkers required by this checker.
		Overloaded by subclasses. """ 
		return []	


class CheckerEnvironment:
	""" The environment for running a checker. """

	def __init__(self, solution):
		""" Constructor: Creates a standard environment. """
		# Temporary build directory
		sandbox = join(settings.UPLOAD_ROOT, "SolutionSandbox")
		self._tmpdir = file_operations.create_tempfolder(sandbox)
		# Sources as [(name, content)...]
		self._sources = []   
		for file in solution.solutionfile_set.all(): 
			self._sources.append((file.path(),file.content()))
		# Submitter of this program
		self._user = solution.author	
		# Executable program
		self._program = None 

	def tmpdir(self):
		""" Returns the path name of temporary build directory. """
		return self._tmpdir

	def sources(self):
		""" Returns the list of source files. [(name, content)...] """
		return self._sources

	def add_source(self, path, content):
		""" Add source to the list of source files. [(name, content)...] """
		self._sources.append((path,content))

	
	def user(self):
		""" Returns the submitter of this program (class User). """
		return self._user
	
	def program(self):
		""" Returns the name of the executable program, if allready set. """
		return self._program

	def set_program(self, program):
		""" Sets the name of the executable program. """
		self._program = program






class CheckerResult(models.Model):
	""" A CheckerResult returns the result of a Checker.
	It contains:
		- A flag that indicates if the check passed.
		- A flag that indicates if the check is *required* to pass.
		- A flag that indicates it the check is *public*.
		- The title of the check.
		- The log of the run.
		- The time of the run. """
	
	from praktomat.solutions.models import Solution
	solution = models.ForeignKey(Solution)
	content_type = models.ForeignKey(ContentType) 
	object_id = models.PositiveIntegerField() 
	checker = generic.GenericForeignKey('content_type','object_id') 
	
	passed = models.BooleanField(default=True,  help_text=_('Indicates whether the test has been passed'))
	log = models.TextField(help_text=_('Text result of the checker'))
	creation_date = models.DateTimeField(auto_now_add=True)
	
	def title(self):
		""" Returns the title of the Checker that did run. """
		return self.checker.title()

	def required(self):
		""" Checks if the Checker is *required* to be passed. """
		return self.checker.required

	def public(self):
		""" Checks if the results of the Checker are *public*. """
		return self.checker.public

	def set_log(self, log):
		""" Sets the log of the Checker run. """
		self.log = log

	def set_passed(self, passed):
		""" Sets the passing state of the Checker. """
		assert isinstance(passed, int)
		self.passed = passed


def check(solution, run_secret = 0): 
	"""Builds and tests this solution."""
	
	# Delete previous results if the checker have allready been run
	solution.checkerresult_set.all().delete()
	# set up environment
	env = CheckerEnvironment(solution)
	
	try:			
		solution.copySolutionFiles(env.tmpdir())
		run_checks(solution, env, run_secret)
	finally:
		# Delete temporary directory
		if not settings.DEBUG:
			try:
				shutil.rmtree(env.tmpdir())
			except IOError:
				pass
	
	

def run_checks(solution, env, run_all):		
	"""  """

	passed_checkers = set()
	
	# Run all checkers of task
	checker_classes = filter(lambda x:issubclass(x,Checker), models.get_models())
	unsorted_checker = sum(map(lambda x: list(x.objects.filter(task=solution.task)), checker_classes),[])
	checkers = sorted(unsorted_checker, key=lambda checker: checker.order)
	
	for checker in checkers:
		if (checker.always or run_all):
		
			# Check dependencies -> This requires the right order of the checkers			
			can_run_checker = True
			for requirement in checker.requires():
				passed_requirement = False
				for passed_checker in passed_checkers:
					passed_requirement = passed_requirement or issubclass(passed_checker, requirement)
				can_run_checker = can_run_checker and passed_requirement
								
			if can_run_checker: 
				# Invoke Checker 
				if settings.DEBUG or 'test' in sys.argv:
					result = checker.run(env)
				else:
					try:
						result = checker.run(env)
					except:
						result = checker.result()
						result.set_log(u"The Checker caused an unexpected internal error.")
						result.set_passed(False)
						#TODO: Email Admins
			else:
				# make non passed result
				# this as well as the dependency check should propably go into checker class
				result = checker.result()
				result.set_log(u"Checker konnte nicht ausgeführt werden, da benötigte Checker nicht bestanden wurden.")
				result.set_passed(False)
				
			result.solution = solution
			result.save()

			if not result.passed and checker.public:
				if checker.required:
					solution.accepted = False
				else:
					solution.warnings= True
					
			if result.passed:
				passed_checkers.add(checker.__class__)
	solution.save()

