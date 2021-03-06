# -*- coding: utf-8 -*-

import os, string

from django.db import models
from django.utils.translation import ugettext_lazy as _
from praktomat.checker.models import Checker, CheckerResult, CheckerFileField
from praktomat.utilities.file_operations import *
from praktomat.utilities.encoding import *

class CreateFileChecker(Checker):
	
	file = CheckerFileField(help_text=_("The file that is copied into the temporary test directory"))
	path = models.CharField(max_length=500, blank=True, help_text=_("Subfolder in the sandbox which shall contain the file."))
	
	def title(self):
		""" Returns the title for this checker category. """
		return "Copy File"
	
	@staticmethod
	def description():
		""" Returns a description for this Checker. """
		return u"Diese Prüfung wird immer bestanden."
	
	def run(self, env):
		""" Runs tests in a special environment. Here's the actual work. 
		This runs the check in the environment ENV, returning a CheckerResult. """
		path = os.path.join(os.path.join(env.tmpdir(),string.lstrip(self.path,"/ ")),os.path.basename(self.file.path))
		overridden = os.path.exists(path)
		copy_file(self.file.path, path)
		result = CheckerResult(checker=self)
		if not overridden:
			result.set_log("")
			result.set_passed(True)
		else:
			result.set_log("The file '%s' was overridden" % os.path.join(self.path, os.path.basename(self.file.path)))
			result.set_passed(False)
		source_path = os.path.join(string.lstrip(self.path,"/ "), os.path.basename(self.file.path))
		env.add_source(source_path, get_unicode(self.file.read()))
		return result
	
from praktomat.checker.admin import	CheckerInline, AlwaysChangedModelForm

class CopyForm(AlwaysChangedModelForm):
	def __init__(self, **args):
		""" override public and required """
		super(CopyForm, self).__init__(**args)
		self.fields["public"].initial = False
		self.fields["required"].initial = False

class CreateFileCheckerInline(CheckerInline):
	model = CreateFileChecker
	form = CopyForm

