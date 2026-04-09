#!/usr/bin/env python3
"""
Working Parsley grammar test
"""

from parsley import makeGrammar

# Working identifier grammar
test_grammar = makeGrammar("""
ident = <letter (letter | digit | '_')*>
letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
""", {})

print("Testing identifier grammar...")
try:
    result = test_grammar("hello_world123").ident()
    print(f"Success: {result}")
except Exception as e:
    print(f"Error: {e}")

# Working string grammar
string_grammar = makeGrammar("""
string = '"' <(~'"' anything)*> '"' -> ''.join
""", {})

print("\nTesting string grammar...")
try:
    result = string_grammar('"hello world"').string()
    print(f"Success: {result}")
except Exception as e:
    print(f"Error: {e}")

# Working parameter list
param_grammar = makeGrammar("""
param_list = param (',' param)* -> list
param = ident
ident = <letter (letter | digit | '_')*>
letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
""", {})

print("\nTesting parameter list grammar...")
try:
    result = param_grammar("param1, param2, param3").param_list()
    print(f"Success: {result}")
except Exception as e:
    print(f"Error: {e}")

# Working macro definition
macro_grammar = makeGrammar("""
macro_def = 'def' name:ident '(' params:param_list? ')' '=' template:string -> (name, params or [], template)
param_list = param (',' param)* -> list
param = ident
ident = <letter (letter | digit | '_')*>
letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
string = '"' <(~'"' anything)*> '"' -> ''.join
""", {})

print("\nTesting full macro definition grammar...")
try:
    test_line = 'def language_expert(type) = "You are an expert in {type} language"'
    result = macro_grammar(test_line).macro_def()
    print(f"Success: {result}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()