from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe
import re
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name,guess_lexer, guess_lexer_for_filename, ClassNotFound

register = template.Library()

def get_lexer(value,arg):
    if arg is None:
        return guess_lexer(value)
    return guess_lexer_for_filename(arg,value) #get_lexer_by_name(arg)

@register.filter(name='highlight')
@stringfilter
def colorize(value, arg=None):
    try:
        return mark_safe(highlight(value,get_lexer(value,arg),HtmlFormatter()))
    except ClassNotFound:
        return value


@register.filter(name='highlight_table')
@stringfilter
def colorize_table(value,arg=None):
    try:
        return mark_safe(highlight(value,get_lexer(value,arg),HtmlFormatter(linenos='table')))
    except ClassNotFound:
        return value


rx_diff = re.compile('^(<span class=".*?">)?(\+|-|\?).*$')   
@register.filter
def highlight_diff(value):
	"enclose highlighted lines beginning with an +-? in a span"
	result = map(lambda line: "<div class='changed'>" + line + "</div>" if bool(rx_diff.match(line)) else line,  value.splitlines(1))
	return mark_safe("".join(result))
