#!/usr/bin/env python
#-*- coding:utf-8 -*-

import sys,codecs
import pygments,pygments.lexers.web , pygments.formatters 

from pygments.token import Token
from pygments.filter import Filter

import re

DEBUG = False
PDEBUG = not True

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
                
                print "javascript (%s:%i):" % (self.filename,line)
                
                check_JS(js)
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
    

class JSFilter(Filter):

    def __init__(self, **options):
        Filter.__init__(self, **options)
        self.js_locals = []
        self.vars = []

    def filter(self, lexer, stream):
        
        s  = [i for i in stream]

        mode = 0
        
        name = []
        
        count = -1
        for ttype, value in s:
            count += 1
            if DEBUG: print "!",mode,ttype,repr(value)

            # 0: wait for Name.Other
            if mode == 0: 
                if ttype  == Token.Name.Other :
                    if DEBUG: print ">>",value, value in self.js_locals
                    if not value in self.js_locals:
                        self.vars.append( (value,count) )
                    mode = 1
                elif ttype == Token.Keyword.Declaration and value == u'var':
                    mode = 2
                elif ttype == Token.Name.Builtin:
                    mode = 1
                elif ttype == Token.Keyword.Declaration and value == u'function':
                    mode = 3
                elif ttype == Token.Punctuation and value == u'.':
                    # this is a hack, while [] and () is not handled correctly
                    mode = 1
                elif ttype == Token.Keyword and value == u'catch':
                    mode = 3
                    
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
                elif ttype == Token.Name.Other:
                    self.js_locals.append( value )
                    if DEBUG: print "> local",value
                    mode = 0
                    
            # 3: function parameter names, catch var 
            elif mode == 3:
                if ttype == Token.Name.Other:
                    self.js_locals.append( value )
                    if DEBUG: print "> local",value
                elif ttype == Token.Punctuation and value == u')':
                    mode = 0

            #TODO catch
            #TODO (eventually): variable scope (func pars only valid inside func etc)


        for ttype, value in s:
            if ttype == Token.Name.Other and value.endswith('XXX'):
                value = "@{{%s}}" % value[:-3]
            yield ttype, value


def addXXX(match):
    return match.group(0)[3:-2]+"XXX"

def check_JS(code):
    code = re.sub(r'@{{[A-Za-z_]+}}',addXXX,code)
   
    lexer = pygments.lexers.web.JavascriptLexer()
    lexer.encoding = 'utf8'
    filter = JSFilter()
    lexer.add_filter(filter)
    
    fmter = pygments.formatters.get_formatter_by_name('text')
    fmter.encoding = 'utf8'
    
    outfile = sys.stdout
    pygments.highlight(code, lexer, fmter, outfile)
    
    print "used vars",filter.vars
    print "js locals",filter.js_locals
    print
    print
    

def main(args=sys.argv):
   
    fn = "test/tests.py"
    code = codecs.open(fn,'r','utf8').read()
    check_py(code,fn)

    sys.exit()

    if len(args)>1:
        code = [ codecs.open(fn,'r','utf8').read() for fn in args[1:] ]
    else:    
        code = []
        
    for c in code:
        check_JS(c)
            
    
if __name__ == '__main__':
    sys.exit(main())

    

