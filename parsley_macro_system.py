#!/usr/bin/env python3
"""
Parsley-based Macro System - Minimal Working Version
Starts with simplest possible grammar and builds up complexity
"""

import sys
from parsley import makeGrammar

# Step 1: Test the absolute simplest Parsley grammar
print("Testing simplest Parsley grammar...")
try:
    simple_grammar = makeGrammar("""
    hello = 'hello' -> 'world'
    """, {})
    result = simple_grammar("hello").hello()
    print(f"Simple grammar works: {result}")
except Exception as e:
    print(f"Simple grammar failed: {e}")
    sys.exit(1)

# Step 2: Test identifier parsing
print("\nTesting identifier grammar...")
try:
    ident_grammar = makeGrammar("""
    ident = 'hello'
    """, {})
    result = ident_grammar("hello").ident()
    print(f"Identifier grammar works: {result}")
except Exception as e:
    print(f"Identifier grammar failed: {e}")
    sys.exit(1)

# Step 3: Test variable identifier
print("\nTesting variable identifier...")
try:
    var_grammar = makeGrammar("""
    ident = <'hello'>
    """, {})
    result = var_grammar("hello").ident()
    print(f"Variable identifier works: {result}")
except Exception as e:
    print(f"Variable identifier failed: {e}")
    sys.exit(1)

# Step 4: Test character class
print("\nTesting character class...")
try:
    char_grammar = makeGrammar("""
    letter = 'a'
    """, {})
    result = char_grammar("a").letter()
    print(f"Character class works: {result}")
except Exception as e:
    print(f"Character class failed: {e}")
    sys.exit(1)

# Step 5: Test alternative
print("\nTesting alternative...")
try:
    alt_grammar = makeGrammar("""
    letter = 'a' | 'b'
    """, {})
    result1 = alt_grammar("a").letter()
    result2 = alt_grammar("b").letter()
    print(f"Alternative works: {result1}, {result2}")
except Exception as e:
    print(f"Alternative failed: {e}")
    sys.exit(1)

# Step 6: Test repetition
print("\nTesting repetition...")
try:
    rep_grammar = makeGrammar("""
    letters = 'a'+
    """, {})
    result = rep_grammar("aaa").letters()
    print(f"Repetition works: {result}")
except Exception as e:
    print(f"Repetition failed: {e}")
    sys.exit(1)

# Step 7: Test combined pattern
print("\nTesting combined pattern...")
try:
    combined_grammar = makeGrammar("""
    ident = <('a' | 'b' | 'c')+>
    """, {})
    result = combined_grammar("abc").ident()
    print(f"Combined pattern works: {result}")
except Exception as e:
    print(f"Combined pattern failed: {e}")
    sys.exit(1)

# Step 8: Test with return value
print("\nTesting with return value...")
try:
    return_grammar = makeGrammar("""
    ident = <('a' | 'b' | 'c')+> -> 'ID:'
    """, {})
    result = return_grammar("abc").ident()
    print(f"Return value works: {result}")
except Exception as e:
    print(f"Return value failed: {e}")
    sys.exit(1)

print("\nAll basic Parsley tests passed!")

# Now try a simple macro definition grammar
print("\nTesting simple macro definition...")
try:
    macro_grammar = makeGrammar("""
    macro_def = 'def' name:ident '(' param:ident ')' '=' string:ident -> (name, param, string)
    ident = <('a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z')+>
    """, {})
    
    test_line = 'def test(param) = template'
    result = macro_grammar(test_line).macro_def()
    print(f"Simple macro definition works: {result}")
    
except Exception as e:
    print(f"Simple macro definition failed: {e}")
    import traceback
    traceback.print_exc()

print("\nParsley macro system test complete!")