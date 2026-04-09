#!/usr/bin/env python3
"""
Test Parsley grammar step by step
"""

from parsley import makeGrammar

# Test simple identifier grammar first
test_grammar = makeGrammar("""
ident = <letter (letter | digit | '_')*>
letter = <[a-zA-Z]>
digit = <[0-9]>
""", {})

print("Testing identifier grammar...")
try:
    result = test_grammar("hello_world123").ident()
    print(f"Success: {result}")
except Exception as e:
    print(f"Error: {e}")

# Test string grammar
string_grammar = makeGrammar("""
string = '"' <(~'"' anything)*> '"' -> ''.join
""", {})

print("\nTesting string grammar...")
try:
    result = string_grammar('"hello world"').string()
    print(f"Success: {result}")
except Exception as e:
    print(f"Error: {e}")

# Test parameter list
test_param_grammar = makeGrammar("""
param_list = param (',' param)* -> list
param = ident
ident = <letter (letter | digit | '_')*>
letter = <[a-zA-Z]>
digit = <[0-9]>
""", {})

print("\nTesting parameter list grammar...")
try:
    result = test_param_grammar("param1, param2, param3").param_list()
    print(f"Success: {result}")
except Exception as e:
    print(f"Error: {e}")

# Test full macro definition
test_macro_grammar = makeGrammar("""
macro_def = 'def' name:ident '(' params:param_list? ')' '=' template:string -> (name, params or [], template)
param_list = param (',' param)* -> list
param = ident
ident = <letter (letter | digit | '_')*>
letter = <[a-zA-Z]>
digit = <[0-9]>
string = '"' <(~'"' anything)*> '"' -> ''.join
""", {})

print("\nTesting full macro definition grammar...")
try:
    test_line = 'def language_expert(type) = "You are an expert in {type} language"'
    result = test_macro_grammar(test_line).macro_def()
    print(f"Success: {result}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()