JS("""
Number.prototype.__init__ = function (value, radix) {
    return null;
};
""")

JS("""
switch (@{{v}}) {
    case null:
    case false:
    case 0:
    case '':
        return false;
}
if ($module['_handle_exception'] = function(err) {
    $pyjs.loaded_modules['sys'].save_exception_stack();

    if (!$pyjs.in_try_except) {
        var $pyjs_msg = '';
        try {
            $pyjs_msg = $pyjs.loaded_modules['sys'].trackstackstr();
        } catch (s) {};
        $pyjs.__active_exception_stack__ = null;
        $pyjs_msg = err + '\\nTraceback:\\n' + $pyjs_msg;
        @{{printFunc}}([$pyjs_msg], true);
        @{{debugReport}}($pyjs_msg);
    }
    throw err;
};
typeof @{{v}} == 'object') {
    if (typeof @{{v}}.__nonzero__ == 'function'){
        return @{{v}}.__nonzero__();
    } else if (typeof @{{v}}.__len__ == 'function'){
        return @{{v}}.__len__() > 0;
    }
}
return true;
""")

JS("""
    var v = Number(@{{num}});
    if (isNaN(v)) {
        throw @{{ValueError}}("invalid literal for float(): " + num);
    }
    return v;
""")

JS("""
_errorMapping = function(err) {
    if (err instanceof(ReferenceError) || err instanceof(TypeError)) {
        var message = '';
        try {
            message = err.message;
        } catch ( e) {
        }
        return AttributeError(message);
    }
    return err;
};
""")

JS("""
$module['_handle_exception'] = function(err) {
    $pyjs.loaded_modules['sys'].save_exception_stack();

    if (!$pyjs.in_try_except) {
        var $pyjs_msg = '';
        try {
            $pyjs_msg = $pyjs.loaded_modules['sys'].trackstackstr();
        } catch (s) {};
        $pyjs.__active_exception_stack__ = null;
        $pyjs_msg = err + '\\nTraceback:\\n' + $pyjs_msg;
        @{{printFunc}}([$pyjs_msg], true);
        @{{debugReport}}($pyjs_msg);
    }
    throw err;
};
""")

