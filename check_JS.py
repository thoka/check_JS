#!/usr/bin/env python
#-*- coding:utf-8 -*-

import sys,codecs
import pygments,pygments.lexers.web , pygments.formatters 

from pygments.token import Token
from pygments.filter import Filter

import re

from StringIO import StringIO

import logging as logger

DEBUG = False
PDEBUG = False

WHITESPACE = [Token.Text]
DO_NOT_REPORT = [u'ReferenceError',u'TypeError']

class PyFilter(Filter):

    def __init__(self, filename = 'stdin', **options):
        Filter.__init__(self, **options)
        self.filename = filename

    def filter(self, lexer, stream):
        
        s  = [i for i in stream]

        mode = 0
        
        count = -1
        line = 1
        
        for ttype, value in s:
            count += 1
            if PDEBUG: print "%",mode,ttype,repr(value)
            
            if value == u'\n': line +=1
                
            if ttype == Token.Name and value == 'JS' and s[count+1][1] == u'(':
                start = count+2
                end = start
                while not ( s[end][0] == Token.Punctuation and s[end][1] == u')'):
                    end += 1
                
                js = u''.join( [ i[1] for i in s[start+1:end-1] ] )
                
                
                check = check_JS(js)
                
                if check.filter.untranslated:
                    print "-"*70
                    print "%s:%i" % (self.filename,line)
                    print
                    # print " not escaped:",check.filter.untranslated
                    print check.out
                    print
                
                #print java_src
            
        if False:
            yield ttype,value


def check_py(code,filename='stdin'):
    """
    tries to catch all JS(src) calls inside python code and run them through check_JS
    """

    lexer = pygments.lexers.PythonLexer()
    lexer.encoding = 'utf8'
    
    filter = PyFilter(filename)
    lexer.add_filter(filter)
    
    fmter = pygments.formatters.get_formatter_by_name('text')
    fmter.encoding = 'utf8'
    
    outfile = sys.stdout    
    pygments.highlight(code, lexer, fmter, outfile)
    

indent = 0

def show_pos(tokens,count):
    res = u''.join( [ repr(i[1])[2:-1] for i in tokens[count-5:count] ] )
    res += u'!'
    res += u''.join( [ repr(i[1])[2:-1] for i in tokens[count:count+5] ] )
    return res


def log(fn):
    if DEBUG:
        def helper(*a,**kw):
            global indent
            print "  "*indent + "enter",fn.__name__,a,show_pos(a[0].tokens,a[1])
            indent +=1
            res = fn(*a,**kw)
            indent -= 1
            print "  "*indent + "leave",fn.__name__,res,show_pos(a[0].tokens,res)
            return res
        return helper
    else:
        return fn
    
class JSFilter(Filter):

    def __init__(self, **options):
        Filter.__init__(self, **options)
        self.js_locals = []
        self.vars = []
        self.errors = []

    def skip(self,count,skiptokens=WHITESPACE):
        while count<len(self.tokens) and self.tokens[count][0] in skiptokens:
            count += 1
        return count
    
    def ttype(self,count): return self.tokens[count][0]
    def value(self,count): return self.tokens[count][1]
    def token(self,count): return self.tokens[count]
    def eof(self,count): return count>=len(self.tokens)

    def mark_error(self,i): 
        self.tokens[i] = (Token.Error, self.value(i))

    @log
    def parse_expression(self,count):
        count = self.skip(count)
        if self.ttype(count) == Token.Name.Other and self.value(count) not in self.js_locals:
            self.vars.append( (self.value(count), count) )
        count = self.skip(count+1)
        while True:
            if self.eof(count) or self.value(count) in  [u';',u'}']:
                return count
            if self.value(count) == u'.':
                count = self.skip(count+1,WHITESPACE+[Token.Name.Other])
                continue
            if self.value(count) in [ u'[', u'(' ] :
                count = self.parse_expression(count+1)
                count = self.skip(count+1,WHITESPACE+[Token.Punctuation])
                continue
            return count

    @log
    def parse_var(self,count):

        while True:
            count = self.skip(count)
            if not self.ttype(count) == Token.Name.Other:
                print self.tokens
                self.errors.append( count )
                logger.error('Token.Name.Other expected, got %s instead', (self.token(count)) )
                return count+1
            self.js_locals.append(self.value(count))
            count = self.skip(count+1)
            if self.eof(count): 
                return count
            if self.value(count) in  [u';',u'}']: 
                return count+1
            if self.value(count) == u'=':
                count = self.parse_expression(count+1)
                count = self.skip(count)
            if self.eof(count): 
                return count
            if self.value(count) in  [u';',u'}']:
                return count+1
            if self.value(count) == u',':
                count += 1
                continue
                
            print "!!",count,self.ttype(count),self.value(count)
            self.mark_error(count)

            return count
        

    def filter(self, lexer, stream):
        
        self.tokens  = [i for i in stream]

        count =  0


        mode = 0
        name = []

        while count<len(self.tokens):
            
            ttype, value = self.tokens[count]
            
            if DEBUG: print "!",mode,ttype,repr(value)

            # 0: wait for Name.Other
            if mode == 0: 
                if ttype  == Token.Name.Other :
                    if DEBUG: print ">>",value, value in self.js_locals
                    if not value in self.js_locals:
                        self.vars.append( (value,count) )
                    mode = 1
                elif ttype == Token.Keyword.Declaration and value == u'var':
                    count = self.parse_var(count+1)
                    mode = 0
                elif ttype == Token.Name.Builtin:
                    mode = 1
                elif ttype == Token.Keyword.Declaration and value == u'function':
                    mode = 3
                elif ttype == Token.Punctuation and value == u'.':
                    # this is a hack, while [] and () is not handled correctly
                    mode = 1
                elif ttype == Token.Keyword and value == u'catch':
                    mode = 3
                elif ttype == Token.Keyword and value == u'for':
                    mode = 4
                    
            # 1: skip property access         
            elif mode == 1: 
                if ttype == Token.Text:
                    pass
                elif ttype == Token.Punctuation and value == u'.':
                    pass
                elif ttype == Token.Name.Other:
                    pass 
                else:
                    mode = 0
                    
            # 2: var definition       
            elif mode == 2: 
                if ttype == Token.Text:
                    pass
                elif ttype == Token.Punctuation and value == u',':
                    pass
                elif ttype == Token.Name.Other:
                    self.js_locals.append( value )
                    if DEBUG: print "> local",value
                else:
                    mode = 0
                    
            # 3: function parameter names, catch var 
            elif mode == 3:
                if ttype == Token.Name.Other:
                    self.js_locals.append( value )
                    if DEBUG: print "> local",value
                elif ttype == Token.Punctuation and value == u')':
                    mode = 0
            
            # 4: for         
            elif mode == 4: 
                if ttype == Token.Name.Other:
                    self.js_locals.append( value )
                    if DEBUG: print "> local",value
                elif value in [u')',u';']:
                    mode = 0

            count += 1

            #TODO for
            #TODO (eventually): variable scope (func pars only valid inside func etc)
            
        self.untranslated = []

        for v in self.vars:
            vn = v[0]
            if not (vn.endswith(u'XXX') or vn.startswith(u'$') or vn in DO_NOT_REPORT):
                self.untranslated.append(v)
        
        for i in [j[1] for j in self.untranslated]:
            self.mark_error(i)
            
        for i in self.errors:
            self.mark_error(i)

        for ttype, value in self.tokens:
            if ttype == Token.Name.Other and value.endswith('XXX'):
                pass
                value = "@{{%s}}" % value[:-3]
            yield ttype, value


def addXXX(match):
    return match.group(0)[3:-2]+"XXX"

class check_JS:

    def __init__(self,code):
        
        self.code = re.sub(r'@{{[A-Za-z_]+}}',addXXX,code)
       
        lexer = pygments.lexers.web.JavascriptLexer()
        lexer.encoding = 'utf8'

        self.filter = JSFilter()
        lexer.add_filter(self.filter)
        
        fmter = pygments.formatters.get_formatter_by_name('console')
        fmter.encoding = 'utf8'
        
        self.out = StringIO()
        pygments.highlight(self.code, lexer, fmter, self.out)
        self.out = self.out.getvalue()
        
        if self.filter.errors:
            print self.out
        
        
def main(args=sys.argv):

    if len(args)==1:
        args.append("test/tests.py")

    for fn in args[1:]:
        code = codecs.open(fn,'r','utf8').read()
        check_py(code,fn)
            
    
if __name__ == '__main__':
    sys.exit(main())

    

