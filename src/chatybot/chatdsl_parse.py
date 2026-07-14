#!/usr/bin/env python3
#
#ChatDSL Recursive Descent Parser - parser_main2.py
# Updated for compatibility with latest ChatDSL features (if/then, wait, multiline set)

import argparse
import dataclasses
import enum
import logging
import sys
import json
from typing import List, Dict, Optional, Union, Any, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class TokenType(enum.Enum):
    EOF = "EOF"
    WHITESPACE = "WHITESPACE"
    NEWLINE = "NEWLINE"
    IDENTIFIER = "IDENTIFIER"
    STRING = "STRING"
    NUMBER = "NUMBER"
    SYMBOL = "SYMBOL"
    COMMENT = "COMMENT"
    ESCAPE = "ESCAPE"
    TERMINATOR = "TERMINATOR"

@dataclasses.dataclass
class Token:
    type: TokenType
    value: Any
    line: int
    column: int
    raw: str

class ParseError(Exception):
    def __init__(self, message: str, line: int, column: int):
        self.line = line
        self.column = column
        super().__init__(f"Parse error at {line}:{column}: {message}")

class Tokenizer:
    def __init__(self):
        self.tokens = []
        self.pos = 0
        self.line = 1
        self.col = 1

    def tokenize(self, text: str) -> List[Token]:
        self.tokens = []
        self.pos = 0
        self.line = 1
        self.col = 1
        
        while self.pos < len(text):
            char = text[self.pos]

            if char in '\r\n':
                start_line, start_col = self.line, self.col
                raw = char
                if char == '\r' and self.pos + 1 < len(text) and text[self.pos+1] == '\n':
                    raw = '\r\n'
                    self.pos += 1
                self.tokens.append(Token(TokenType.NEWLINE, '\n', start_line, start_col, raw))
                self.pos += 1; self.line += 1; self.col = 1
                continue

            if char in ' \t':
                start_col = self.col
                val = ""
                while self.pos < len(text) and text[self.pos] in ' \t':
                    val += text[self.pos]
                    self.pos += 1; self.col += 1
                self.tokens.append(Token(TokenType.WHITESPACE, val, self.line, start_col, val))
                continue

            if text[self.pos:self.pos+2] == ';;':
                self.tokens.append(Token(TokenType.TERMINATOR, ';;', self.line, self.col, ';;'))
                self.pos += 2; self.col += 2
                continue
            
            # Comparison operators
            if text[self.pos:self.pos+2] in ['==', '!=']:
                op = text[self.pos:self.pos+2]
                self.tokens.append(Token(TokenType.SYMBOL, op, self.line, self.col, op))
                self.pos += 2; self.col += 2
                continue

            if char == '/':
                start_col = self.col
                start_pos = self.pos
                self.pos += 1; self.col += 1
                while self.pos < len(text) and (text[self.pos].isalnum() or text[self.pos] == '_'):
                    self.pos += 1; self.col += 1
                val = text[start_pos:self.pos]
                self.tokens.append(Token(TokenType.ESCAPE, val, self.line, start_col, val))
                continue

            if char == '#':
                start_col = self.col
                start_pos = self.pos
                while self.pos < len(text) and text[self.pos] not in '\r\n':
                    self.pos += 1; self.col += 1
                val = text[start_pos:self.pos]
                self.tokens.append(Token(TokenType.COMMENT, val, self.line, start_col, val))
                continue

            if text[self.pos:self.pos+2] == '${':
                self.tokens.append(Token(TokenType.SYMBOL, '${', self.line, self.col, '${'))
                self.pos += 2; self.col += 2; continue
            
            if text[self.pos:self.pos+3] == '-->':
                self.tokens.append(Token(TokenType.SYMBOL, '-->', self.line, self.col, '-->'))
                self.pos += 3; self.col += 3; continue

            if char == '"':
                start_col = self.col
                start_line = self.line
                start_pos = self.pos
                self.pos += 1; self.col += 1
                while self.pos < len(text) and text[self.pos] != '"':
                    if text[self.pos] == '\n':
                        self.line += 1
                        self.col = 1
                    else:
                        self.col += 1
                    self.pos += 1
                if self.pos >= len(text):
                    raise ParseError("Unterminated string literal", start_line, start_col)
                self.pos += 1; self.col += 1
                val = text[start_pos:self.pos]
                self.tokens.append(Token(TokenType.STRING, val[1:-1], start_line, start_col, val))
                continue

            if char.isalpha() or char == '_' or char == "'":
                start_col = self.col
                start_pos = self.pos
                while self.pos < len(text) and (text[self.pos].isalnum() or text[self.pos] in "_'"):
                    self.pos += 1; self.col += 1
                val = text[start_pos:self.pos]
                self.tokens.append(Token(TokenType.IDENTIFIER, val, self.line, start_col, val))
                continue

            if char.isdigit() or (char == '-' and self.pos + 1 < len(text) and text[self.pos+1].isdigit()):
                start_col = self.col
                start_pos = self.pos
                if text[self.pos] == '-': self.pos += 1; self.col += 1
                while self.pos < len(text) and text[self.pos].isdigit():
                    self.pos += 1; self.col += 1
                if self.pos < len(text) and text[self.pos] == '.':
                    self.pos += 1; self.col += 1
                    while self.pos < len(text) and text[self.pos].isdigit():
                        self.pos += 1; self.col += 1
                val = text[start_pos:self.pos]
                self.tokens.append(Token(TokenType.NUMBER, float(val) if '.' in val else int(val), self.line, start_col, val))
                continue

            self.tokens.append(Token(TokenType.SYMBOL, char, self.line, self.col, char))
            self.pos += 1; self.col += 1

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.col, ""))
        return self.tokens

class TParser:
    VALID_ESCAPE_COMMANDS: Set[str] = {
        "help", "prompt", "file", "showfile", "clearfile", "filebank",
        "model", "listmodels", "logging", "save", "codeonly", "codeoff",
        "system", "temp", "maxtokens", "top_p", "top_k", "freq_penalty",
        "pres_penalty", "reasoning", "effort", "seed", "stream", "script", "quit",
        "setdb", "dblist", "searchdb", "dblog", "dbprint", "loadvar",
        "savevar", "setvar", "notemode", "mem", "dump", "trace", "thinking",
        "filebank1", "filebank2", "filebank3", "filebank4", "filebank5",
        "imagebank", "imagebank1", "imagebank2", "imagebank3", "imagebank4", "imagebank5",
        # Phase 2: Image generation commands
        "imagine", "imagesize", "imagequality", "saveimage", "imagedir",
        "listimages", "showimage", "loadimage",
        "multiline", "echo", "thoughtstyle", "def",
        # Semantic reranking commands
        "documents", "rerank",
        # Shell execution commands
        "run", "run_safe", "run_unsafe", "tool", "profile"
    }

    def __init__(self, tokens: List[Token], verbose: bool = False):
        self.tokens = tokens
        self.idx = 0
        self.verbose = verbose

    @property
    def current(self) -> Token:
        return self.tokens[self.idx]

    def advance(self):
        if self.current.type != TokenType.EOF:
            self.idx += 1

    def match(self, t_type: TokenType, val: Any = None) -> bool:
        if self.current.type != t_type: return False
        if val is not None and self.current.raw != val: return False
        return True

    def expect(self, t_type: TokenType, val: Any = None) -> Token:
        if not self.match(t_type, val):
            expected = f"{t_type.value}" + (f" ({val})" if val else "")
            raise ParseError(f"Expected {expected}, got {self.current.type.value} '{self.current.raw}'", self.current.line, self.current.column)
        tok = self.current
        self.advance()
        return tok

    def parse(self) -> List[Dict[str, Any]]:
        units = []
        while not self.match(TokenType.EOF):
            if self.match(TokenType.ESCAPE, "/multiline"):
                units.append(self.parse_multiline_block())
            elif self.match(TokenType.NEWLINE) or self.match(TokenType.WHITESPACE):
                self.advance()
            else:
                units.append(self.parse_line())
        return units

    def parse_multiline_block(self) -> Dict[str, Any]:
        start_tok = self.expect(TokenType.ESCAPE, "/multiline")
        self.expect(TokenType.NEWLINE)
        
        body = []
        while not self.match(TokenType.TERMINATOR, ";;"):
            if self.match(TokenType.EOF):
                raise ParseError("Unclosed multiline block", start_tok.line, start_tok.column)
            
            if self.match(TokenType.SYMBOL, "${"):
                body.append(self.parse_var_ref())
            else:
                body.append({"type": "text", "val": self.current.raw})
                self.advance()

        self.expect(TokenType.TERMINATOR, ";;")
        while self.match(TokenType.NEWLINE) or self.match(TokenType.WHITESPACE):
            self.advance()
        self.expect(TokenType.ESCAPE, "/multiline")
        return {"type": "multiline_block", "content": body}

    def parse_line(self) -> Dict[str, Any]:
        if self.match(TokenType.COMMENT):
            tok = self.expect(TokenType.COMMENT)
            return {"type": "comment", "val": tok.raw}
        
        if self.match(TokenType.IDENTIFIER, "set"):
            return self.parse_set()
        
        if self.match(TokenType.IDENTIFIER, "def"):
            return self.parse_macro_def()
        
        if self.match(TokenType.SYMBOL, "%"):
            return self.parse_macro_call()
        
        if self.match(TokenType.IDENTIFIER, "if"):
            return self.parse_if()
        
        if self.match(TokenType.IDENTIFIER, "wait"):
            return self.parse_wait()
            
        return self.parse_command_or_chat()

    def parse_macro_def(self) -> Dict[str, Any]:
        self.expect(TokenType.IDENTIFIER, "def")
        self.expect(TokenType.WHITESPACE)
        name = self.expect(TokenType.IDENTIFIER).raw
        self.expect(TokenType.SYMBOL, "(")
        params = []
        if not self.match(TokenType.SYMBOL, ")"):
            params.append(self.expect(TokenType.IDENTIFIER).raw)
            while self.match(TokenType.SYMBOL, ","):
                self.advance()
                self.parse_opt_ws()
                params.append(self.expect(TokenType.IDENTIFIER).raw)
        self.expect(TokenType.SYMBOL, ")")
        self.parse_opt_ws()
        self.expect(TokenType.SYMBOL, "=")
        self.parse_opt_ws()
        template = self.expect(TokenType.STRING).value
        return {"type": "macro_definition", "name": name, "params": params, "template": template}

    def parse_macro_call(self) -> Dict[str, Any]:
        self.expect(TokenType.SYMBOL, "%")
        name = self.expect(TokenType.IDENTIFIER).raw
        self.expect(TokenType.SYMBOL, "(")
        args = []
        if not self.match(TokenType.SYMBOL, ")"):
            args.append(self.parse_macro_arg())
            while self.match(TokenType.SYMBOL, ","):
                self.advance()
                self.parse_opt_ws()
                args.append(self.parse_macro_arg())
        self.expect(TokenType.SYMBOL, ")")
        return {"type": "macro_call", "name": name, "args": args}

    def parse_macro_arg(self) -> Any:
        if self.match(TokenType.SYMBOL, "${"):
            return self.parse_var_ref()
        if self.match(TokenType.STRING):
            tok = self.expect(TokenType.STRING)
            return {"type": "string", "val": tok.raw}
        if self.match(TokenType.NUMBER):
            tok = self.expect(TokenType.NUMBER)
            return {"type": "number", "val": tok.value}
        if self.match(TokenType.IDENTIFIER):
            tok = self.expect(TokenType.IDENTIFIER)
            return {"type": "literal", "val": tok.raw}
        raise ParseError(f"Unexpected token in macro argument: {self.current.type.value}", self.current.line, self.current.column)

    def parse_set(self) -> Dict[str, Any]:
        self.expect(TokenType.IDENTIFIER, "set")
        self.expect(TokenType.WHITESPACE)
        var_name = self.expect(TokenType.IDENTIFIER).raw
        
        # Look ahead for [] suffix
        is_array = False
        lookahead_idx = self.idx
        while lookahead_idx < len(self.tokens) and self.tokens[lookahead_idx].type == TokenType.WHITESPACE:
            lookahead_idx += 1
        if lookahead_idx < len(self.tokens) and self.tokens[lookahead_idx].type == TokenType.SYMBOL and self.tokens[lookahead_idx].raw == '[':
            lookahead_idx += 1
            while lookahead_idx < len(self.tokens) and self.tokens[lookahead_idx].type == TokenType.WHITESPACE:
                lookahead_idx += 1
            if lookahead_idx < len(self.tokens) and self.tokens[lookahead_idx].type == TokenType.SYMBOL and self.tokens[lookahead_idx].raw == ']':
                # Suffix [] is present
                self.parse_opt_ws()
                self.expect(TokenType.SYMBOL, "[")
                self.parse_opt_ws()
                self.expect(TokenType.SYMBOL, "]")
                is_array = True
                var_name += "[]"

        self.parse_opt_ws()
        self.expect(TokenType.SYMBOL, "=")
        self.parse_opt_ws()
        val = self.parse_value_or_list()
        return {"type": "set_command", "var": var_name, "val": val}

    def parse_value_or_list(self) -> Any:
        self.parse_opt_ws()
        if self.match(TokenType.SYMBOL, "["):
            self.advance()
            self.parse_opt_ws()
            elements = []
            if not self.match(TokenType.SYMBOL, "]"):
                elements.append(self.parse_list_element())
                self.parse_opt_ws()
                while self.match(TokenType.SYMBOL, ","):
                    self.advance()
                    self.parse_opt_ws()
                    elements.append(self.parse_list_element())
                    self.parse_opt_ws()
            self.expect(TokenType.SYMBOL, "]")
            return elements
        else:
            val = self.current.value
            self.advance()
            return val

    def parse_list_element(self) -> Any:
        if self.match(TokenType.STRING):
            tok = self.expect(TokenType.STRING)
            return tok.value
        elif self.match(TokenType.NUMBER):
            tok = self.expect(TokenType.NUMBER)
            return tok.value
        elif self.match(TokenType.IDENTIFIER):
            tok = self.expect(TokenType.IDENTIFIER)
            return tok.raw
        else:
            raise ParseError(f"Expected string, number, or identifier in array literal, got {self.current.type.value} '{self.current.raw}'", self.current.line, self.current.column)


    def parse_wait(self) -> Dict[str, Any]:
        self.expect(TokenType.IDENTIFIER, "wait")
        self.expect(TokenType.WHITESPACE)
        val = self.expect(TokenType.NUMBER).value
        return {"type": "wait_command", "seconds": val}

    def parse_if(self) -> Dict[str, Any]:
        start_tok = self.expect(TokenType.IDENTIFIER, "if")
        self.expect(TokenType.WHITESPACE)
        condition_tokens = []
        while not self.match(TokenType.IDENTIFIER, "then"):
            if self.match(TokenType.EOF) or self.match(TokenType.NEWLINE):
                    raise ParseError("Missing 'then' or unexpected end of line in if statement", start_tok.line, start_tok.column)
            condition_tokens.append(self.current.raw)
            self.advance()
        self.expect(TokenType.IDENTIFIER, "then")
        self.expect(TokenType.WHITESPACE)
        then_command = self.parse_line()
        return {"type": "if_command", "condition": " ".join(condition_tokens).strip(), "then": then_command}

    def parse_command_or_chat(self) -> Dict[str, Any]:
        if self.match(TokenType.ESCAPE):
            tok = self.expect(TokenType.ESCAPE)
            cmd_name = tok.raw[1:].lower() 
            if cmd_name not in self.VALID_ESCAPE_COMMANDS:
                raise ParseError(f"Invalid escape command: /{cmd_name}", tok.line, tok.column)
            args = []
            while not self.match(TokenType.NEWLINE) and not self.match(TokenType.EOF):
                if self.match(TokenType.WHITESPACE): self.advance(); continue
                if self.match(TokenType.SYMBOL, "${"):
                    args.append(self.parse_var_ref())
                else:
                    args.append(self.current.raw); self.advance()
            return {"type": "command", "name": tok.raw, "args": args}
        
        content = []
        while not self.match(TokenType.NEWLINE) and not self.match(TokenType.EOF):
            if self.match(TokenType.SYMBOL, "${"):
                content.append(self.parse_var_ref())
            else:
                content.append(self.current.raw); self.advance()
        return {"type": "chat_input", "content": content}

    def parse_var_ref(self) -> Dict[str, Any]:
        self.expect(TokenType.SYMBOL, "${")
        name = self.expect(TokenType.IDENTIFIER).raw
        self.expect(TokenType.SYMBOL, "}")
        return {"type": "variable_reference", "name": name}

    def parse_opt_ws(self):
        while self.match(TokenType.WHITESPACE): self.advance()

def main():
    parser = argparse.ArgumentParser(description="ChatDSL Parser")
    parser.add_argument("--file", help="Input .chatdsl file", required=True)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
        tokenizer = Tokenizer()
        tokens = tokenizer.tokenize(text)
        tparser = TParser(tokens, verbose=args.verbose)
        ast = tparser.parse()
        print(json.dumps(ast, indent=2))
        sys.exit(0)
    except ParseError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        import traceback
        if args.verbose: traceback.print_exc()
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
