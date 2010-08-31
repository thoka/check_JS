#!/usr/bin/env python
#-*- coding:utf-8 -*-

import sys,codecs
import pygments,pygments.lexers.web , pygments.formatters 

from pygments.token import Token
from pygments.filter import Filter

import re

from StringIO import StringIO

import logging as logger
from optparse import OptionParser
import os.path
from cStringIO import StringIO

from subprocess import call

DEBUG = False
PDEBUG = False

WHITESPACE = [Token.Text]
DO_NOT_REPORT = u'ReferenceError,TypeError,pyjslib'.split(u',')

class PyFilter(Filter):

    def __init__(self, options, filename = 'stdin' ):
        Filter.__init__(self)
        self.filename = filename
        self.options = options
        self.conversions = 0 # counts converted vars
        
    def filter(self, lexer, stream):
        
        s  = [i for i in stream]

        mode = 0
        
        count = 0
        line = 1
        
        convert_only_one = self.options.convert_only_one
        
        while count < len(s):
            ttype, value = s[count]

            if PDEBUG: print "%",mode,ttype,repr(value)
            
            if value == u'\n': line +=1
                
            if not (convert_only_one and self.conversions>0) \
               and ttype == Token.Name and value == 'JS' and s[count+1][1] == u'(':
    
                startline = line

                start = count+2

                # skip whitespace
                while s[start][0] == Token.Text: start += 1
                start+=1                 
                # print "@@",repr(s[count:start+1])
                # skip whitespace again, since pygments seems to remove it from the begining of a stream
                while ( s[start][1] in [ u'',u'\n' ] ):  start += 1
                
                # scan for end of parameter string
                end = start
                while not ( s[end][0] == Token.Punctuation and s[end][1] == u')'):
                    end += 1
                end -= 1
                
                # call js checker for joined text
                js = u''.join( [ i[1] for i in s[start:end] ] )
                check = check_JS(self.options,js)
                
                if self.options.outpy:
                    if self.options.replace:
                        #do conversion
                        for i in [ j[1] for j in check.filter.untranslated ]:
                            v = "@{{%s}}" % check.filter.value(i)
                            check.filter.set_value(i,v)
                            self.conversions += 1
 
                    #output js tokens in stead of the python strings
                    for t in s[count:start]: yield t
                    for t in check.filter.tokens: yield t
                else:    
                    if check.filter.untranslated:
                        print "-"*70
                        print "%s:%i" % (self.filename,line)
                        print
                        print check.out
                        print
                
                value = check.out           
                count = end            
            else:
                if self.options.outpy:
                    yield ttype,value
                count += 1


class check_py:
    
    def __init__(self,code,options, filename='stdin',outfile = sys.stdout):
        """
        tries to catch all JS(src) calls inside python code and run them through check_JS

        
        """
        
        
        lexer = pygments.lexers.PythonLexer()
        lexer.encoding = 'utf8'
        
        filter = PyFilter(options,filename)
        lexer.add_filter(filter)
        
        fmter = pygments.formatters.get_formatter_by_name(options.format)
        fmter.encoding = 'utf8'
            
        pygments.highlight(code, lexer, fmter, outfile)
        self.conversions = filter.conversions
    

#debug helper
indent = 0
def show_pos(tokens,count):
    res = u''.join( [ repr(i[1])[2:-1] for i in tokens[count-5:count] ] )
    res += u'!'
    res += u''.join( [ repr(i[1])[2:-1] for i in tokens[count:count+5] ] )
    return res

#debug helper
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

    def __init__(self, options):
        Filter.__init__(self)
        self.options = options
        self.js_locals = []
        self.vars = []
        self.errors = []

    def skip(self,count,skiptokens=WHITESPACE):
        while count<len(self.tokens) and self.tokens[count][0] in skiptokens:
            count += 1
        return count

    def expect(self,count,expected):
        if self.ttype(count) not in expected:
            logger.error(
                'error, %s expected but %s found at %i',expected,self.token(count),count
            )
            self.mark_error(count)
    
    def ttype(self,count): return self.tokens[count][0]
    def value(self,count): return self.tokens[count][1]
    def token(self,count): return self.tokens[count]
    def eof(self,count): return count>=len(self.tokens)

    def set_token(self,i,t): self.tokens[i] = ( t , self.value(i) )
    def set_value(self,i,v): self.tokens[i] = ( self.token(i), v )

    def mark_error(self,i): 
        self.set_token(i,Token.Error)

    @log
    def parse_expression(self,count):
        # basic idea: return on ',' ';' '}' ')' , if parents are matched
        
        end = count
        level = 0
        while True:
            if level ==0 and self.value(end) in [u',',u';',u'}',u')',u']']:
                break
            if self.value(end) in [ u'(', u'[' ]:
                level += 1
            elif self.value(end) in [ u')', u']' ]:
                level -= 1
            end += 1
        
        self.parse(count,end)
        return end

    @log
    def parse_var(self,count):

        while True:
            count = self.skip(count)
            if not self.ttype(count) == Token.Name.Other:
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
                
            logger.error("!! not expecting %s/%s at %i",self.ttype(count),self.value(count),count)
            self.mark_error(count)

            return count
        
    @log
    def parse(self,start,end):

        mode = 0
        name = []

        count =  start
        while count<end:
            
            ttype, value = self.tokens[count]
            
            if DEBUG: print "! %3i" % count,mode,ttype,repr(value)

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
            
        return end

    def filter(self, lexer, stream):
        
        self.tokens  = [ i for i in stream ]

        self.parse(0,len(self.tokens))

        self.untranslated = []

        for v in self.vars:
            vn = v[0]
            if not (vn.endswith(u'XXX') or vn.startswith(u'$') or vn in DO_NOT_REPORT):
                self.untranslated.append(v)
        
        for i in xrange(len(self.tokens)):
            if self.ttype(i) == Token.Name.Other and self.value(i).endswith('XXX'):
                vname = self.value(i)[:-3]
                if vname.endswith('XXX'):
                    vname = '!'+vname[:-3]
                self.set_value(i, "@{{%s}}" % vname )

        for i in [j[1] for j in self.untranslated]:
            self.mark_error(i)
            
        for i in self.errors: 
            self.mark_error(i)

        for t in self.tokens: 
            yield t
   


def addXXX(match):
    vname = match.group(1)
    if vname.startswith("!"):
        return vname[1:] + "XXXXXX" 
    else:
        return vname+"XXX"

class check_JS:

    def __init__(self,options,code):

        #print "check_JS",repr(code)
        self.code = re.sub(r'@{{(!?[A-Za-z_]+)}}',addXXX,code)

        #workaround for pygments adding/removing "/n" to last token
        add_nl = self.code.endswith(u'\n')
       
        lexer = pygments.lexers.web.JavascriptLexer(ensurenl=False)
        lexer.encoding = 'utf8'

        self.filter = JSFilter(options)
        lexer.add_filter(self.filter)
        
        fmter = pygments.formatters.get_formatter_by_name(options.format)
        fmter.encoding = 'utf8'
        
        self.out = StringIO()
        pygments.highlight(self.code, lexer, fmter, self.out)
        self.out = self.out.getvalue()

        #workaround for pygments adding/removing "\n" to last token
        if add_nl:
            i = len(self.filter.tokens)-1
            v = self.filter.value(i)+u'\n'
            self.filter.set_value(i,v)

        if self.filter.errors:
            print self.out
        
                            
        
def main():

    parser = OptionParser(usage="%prog [options] filename...")
    parser.add_option("--check", dest="action" , action ="store_const", const="check", default="check" 
                      ,help="show not escapend js code (default behaviour)")
    parser.add_option("--convert", dest="action" , action ="store_const", const="convert" 
                      ,help="output py src with converted JS fragments")
    parser.add_option("-1","--one", dest="convert_only_one" , action ="store_true", default=False 
                      ,help="stop after first convertet JS(...) fragment")
    parser.add_option("-o","--overwrite", dest="overwrite" , action ="store_true", default=False 
                      ,help="overwrite input files, implies --convert")
    parser.add_option("-a","--autocommit", dest="autocommit" , action ="store_true", default=False 
                      ,help="auto commit changes, implies --convert --overwrite")

    #parser.add_option("-r", "--recurse", dest="recurse" , action ="store_true", default = False ,help="recurse directories")
 
    options, args  = parser.parse_args()

    if options.autocommit:
        options.overwrite = True

    if options.overwrite:
        options.action = "convert"
 
    if options.action == "check":
        options.format = "terminal"
        options.replace = False
        options.outpy = False
    elif options.action == "convert":
        options.replace = True
        options.outpy = True
        options.format = 'text'
        
    
        
    if len(args)<1:
        parser.print_help()

    allfiles = set()
    
    for fn in args:
        
        if os.path.isdir(fn):
            for dirname, subdirs, files in os.walk(fn):
                allfiles.update([ os.path.join(fn,f) for f in files if f.endswith('.py') ])
        else:
            allfiles.add(fn)
       
    allfiles = [i for i in allfiles]
    allfiles.sort()
    
    outfile = sys.stdout
        
    for fn in allfiles:

        while True:
            if options.overwrite:
                outfile = StringIO()
              
            code = codecs.open(fn,'r','utf8').read()
            check = check_py(code,options,fn,outfile=outfile)

            if check.conversions>0:
                if options.overwrite:
                    outfile.seek(0)
                    f = codecs.open(fn,'w','utf8')
                    f.write(outfile.read())
                    f.close()
            
                if options.convert_only_one and not options.autocommit:
                    sys.exit()

                if options.autocommit:
                    d = os.path.abspath(os.path.dirname(fn))
                    print "commit",d,fn
                    call([ 'git','add', os.path.basename(fn) ], cwd = d )
                    call([ 'git','commit','-m','check_JS conversion' ], cwd = d )

            if not options.autocommit:
                break
            if check.conversions==0:
                break


def shell(cmd):
    print 'SHELL:',cmd

if __name__ == '__main__':
    sys.exit(main())

    

