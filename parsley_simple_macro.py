#!/usr/bin/env python3
"""
Simplest possible Parsley macro system
Based exactly on Parsley tutorial examples
"""

import sys
from parsley import makeGrammar

# Test 1: Simple identifier matching (from tutorial)
print("Testing simple identifier...")
try:
    ident_grammar = makeGrammar("""
    ident = 'hello' -> 'world'
    """, {})
    result = ident_grammar("hello").ident()
    print(f"Simple identifier works: {result}")
except Exception as e:
    print(f"Simple identifier failed: {e}")

# Test 2: Variable capture (from tutorial)
print("\nTesting variable capture...")
try:
    var_grammar = makeGrammar("""
    ident = <'hello'> -> 'got:'
    """, {})
    result = var_grammar("hello").ident()
    print(f"Variable capture works: {result}")
except Exception as e:
    print(f"Variable capture failed: {e}")

# Test 3: Character alternatives (from tutorial)
print("\nTesting character alternatives...")
try:
    char_grammar = makeGrammar("""
    letter = 'a' | 'b' | 'c'
    """, {})
    result = char_grammar("b").letter()
    print(f"Character alternatives work: {result}")
except Exception as e:
    print(f"Character alternatives failed: {e}")

# Test 4: Repetition (from tutorial)
print("\nTesting repetition...")
try:
    rep_grammar = makeGrammar("""
    letters = 'a'+
    """, {})
    result = rep_grammar("aaa").letters()
    print(f"Repetition works: {result}")
except Exception as e:
    print(f"Repetition failed: {e}")

# Test 5: Combined identifier (from tutorial)
print("\nTesting combined identifier...")
try:
    combined_grammar = makeGrammar("""
    ident = <('a' | 'b' | 'c')+>
    """, {})
    result = combined_grammar("abc").ident()
    print(f"Combined identifier works: {result}")
except Exception as e:
    print(f"Combined identifier failed: {e}")

# Test 6: Simple macro-like pattern
print("\nTesting simple macro-like pattern...")
try:
    simple_macro_grammar = makeGrammar("""
    macro = 'def' name:ident '(' param:ident ')' '=' template:ident -> (name, param, template)
    ident = <('a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z')+>
    """, {})
    
    test_line = 'def test(param) = template'
    result = simple_macro_grammar(test_line).macro()
    print(f"Simple macro pattern works: {result}")
    
except Exception as e:
    print(f"Simple macro pattern failed: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Macro with string template
print("\nTesting macro with string template...")
try:
    string_macro_grammar = makeGrammar("""
    macro = 'def' name:ident '(' param:ident ')' '=' template:string -> (name, param, template)
    ident = <('a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z')+>
    string = '"' <(~'"' anything)*> '"' -> ''.join
    """, {})
    
    test_line = 'def test(param) = "Hello {param}"'
    result = string_macro_grammar(test_line).macro()
    print(f"String macro works: {result}")
    
except Exception as e:
    print(f"String macro failed: {e}")
    import traceback
    traceback.print_exc()

print("\nParsley tests complete!")