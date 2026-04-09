from parsley import makeGrammar
grammar = makeGrammar("""
        macro_def = 'def' ws ident:name ws '(' ws param_list?:params ws ')' ws '=' ws string:template -> (name, params or [], template)
        param_list = param:p (ws ',' ws param)*:ps -> [p] + ps
        param = ident
        ident = <letter (letter | digit | '_')*>
        letter = 'a' | 'b' | 'c' | 'd' | 'e' | 'f' | 'g' | 'h' | 'i' | 'j' | 'k' | 'l' | 'm' | 'n' | 'o' | 'p' | 'q' | 'r' | 's' | 't' | 'u' | 'v' | 'w' | 'x' | 'y' | 'z' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F' | 'G' | 'H' | 'I' | 'J' | 'K' | 'L' | 'M' | 'N' | 'O' | 'P' | 'Q' | 'R' | 'S' | 'T' | 'U' | 'V' | 'W' | 'X' | 'Y' | 'Z'
        digit = '0' | '1' | '2' | '3' | '4' | '5' | '6' | '7' | '8' | '9'
        string = '"' <(~'"' anything)*> '"' -> ''.join
        ws = ' '*
""", {})
test_line = 'def language_expert(type) = "You are an expert in {type} programming language."'
try:
    result = grammar(test_line).macro_def()
    print(f"SUCCESS: {result}")
except Exception as e:
    print(f"FAILURE: {e}")
    import traceback
    traceback.print_exc()
