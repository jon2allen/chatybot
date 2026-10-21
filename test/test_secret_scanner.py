"""
SecretScanner generic-rule precision: code that *references* a credential must not
trigger a prompt; values that look like real secrets must.
"""

from pathlib import Path

import pytest

from chatybot.security.secret_scanner import SecretScanner, looks_like_secret_value

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def scanner():
    return SecretScanner(known_secrets={})  # pattern rules only


CODE_REFERENCES = [
    "API_KEY = os.environ['OPENAI_API_KEY']",
    "password = getpass()",
    'api_key = os.getenv("MISTRAL_API_KEY")',
    "self.api_key = api_key_from_settings",
    'token = response.json()["access_token"]',
    "GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}",
    "export OPENAI_API_KEY=$(security find-generic-password -s openai -w)",
    "API_KEY=your_api_key_here",
    "secret_key = settings.SECRET_KEY",
    "auth_token = request.headers.get('Authorization')",
    "password=None",
    "max_tokens = 4096",
    "MAX_TOKENS=128000",
    'tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")',
    'api_key: str = ""',
    "token: Optional[str] = None",
    "PWD=/Users/someone/github/chatybot",
    'headers = {"Authorization": f"Bearer {api_key}"}',
    'password_field = "new_password"',
    "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    'secret = "abcdabcdabcdabcd1"',
    'api_key = "<YOUR KEY>"',
    "if token == expected_token:",
    "PASSWORD_MIN_LENGTH = 12",
    "Set OPENAI_API_KEY=<your key here> in .env",
    'api_key="fake-api-key-122333"',
    "conn = connect(user=user, password=password)",  # kwarg passing a variable
    "password = new_password",                        # code assignment of a variable
    "db_password := user_password",
]

SECRET_LITERALS = [
    "ACME_API_KEY=Zq8wE7rT6yU5iO4pA3sD2fG1hJ0kL9",
    # Fixtures are split so the source never contains a provider-format literal
    # (GitHub push protection flags them; at runtime the scanner sees the joined value).
    "export MISTRAL" + "_API_KEY=" + "Xk9mQ2vR7tY4pL8w" + "N3zB6cJ1hF5dG0sA",
    '{"api_key": "Zq8wE7rT6yU5iO4pA3sD2fG1hJ0kL9"}',
    "api_key: Zq8wE7rT6yU5iO4pA3sD2fG1hJ0kL9",
    "client_secret = 'a8F3kL9mQ2xR7tY4pW6zN1bV5cD0eG3h'",
    "DB_PASSWORD=S3cretPassw0rd",
    'password: "hunter22x"',
    "machine api.github.com login jon password Pa55w0rdHere",
    "Authorization: Bearer a8F3kL9mQ2xR7tY4pW6zN1bV5cD0eG3h",
    "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYzQ8w2rT6y",
    "STRIPE_SECRET_KEY=" + "rk_" + "live_51H8xKjL2mN3oP4qR5sT6uV7wX",
    'auth_token := "9f8e7d6c5b4a39281706f5e4d3c2b1a0"',
]


@pytest.mark.parametrize("text", CODE_REFERENCES)
def test_code_references_and_placeholders_do_not_prompt(scanner, text):
    assert scanner.scan(text) is None


@pytest.mark.parametrize("text", SECRET_LITERALS)
def test_secret_literals_are_caught(scanner, text):
    hit = scanner.scan(text)
    assert hit is not None
    assert hit[0].value == "ask"


def test_secret_hidden_after_a_rejected_candidate_on_the_same_line(scanner):
    # The first candidate is code; the second is a real-looking secret. finditer must keep looking.
    text = "token = get_token()  # fallback: ACME_TOKEN=Zq8wE7rT6yU5iO4pA3sD2fG1hJ0kL9"
    assert scanner.scan(text) is not None


@pytest.mark.parametrize("value, password, expected", [
    ("Zq8wE7rT6yU5iO4pA3sD2fG1hJ0kL9", False, True),
    ("short1", False, False),                          # too short for a token
    ("abcdefghijklmnopqrstuvwx", False, False),       # no digits
    ("aaaaaaaaaaaaaaaa1111", False, False),           # too little randomness
    ("os.environ", False, False),                      # dotted name
    ("getpass()", True, False),                        # code
    ("new_password", True, False),                     # variable name (code style, see below)
    ("S3cretPassw0rd", True, True),
    ('"hunter22x"', True, True),                       # quoted literal
    ("${{ secrets.X }}", False, False),
    ("/usr/local/bin/python3.12", False, False),       # path
])
def test_looks_like_secret_value(value, password, expected):
    style = "code" if value == "new_password" else "prose"
    assert looks_like_secret_value(value, password=password, style=style) is expected


@pytest.mark.parametrize("style, expected", [("code", False), ("env", True), ("prose", True)])
def test_bare_word_password_depends_on_assignment_style(style, expected):
    assert looks_like_secret_value("hunterhunter", password=True, style=style) is expected


def test_custom_rules_can_use_validators():
    s = SecretScanner(
        rules=[{"pattern": r"MYCO_KEY\s*=\s*(?P<val>\S+)", "validator": "token_value", "verdict": "ask", "reason": "MyCo key"}],
        known_secrets={},
    )
    assert s.scan("MYCO_KEY = settings.key") is None
    assert s.scan("MYCO_KEY = Zq8wE7rT6yU5iO4pA3sD2fG1hJ0kL9") is not None
    # Unknown validator names are ignored: the rule behaves as a plain regex.
    plain = SecretScanner(rules=[{"pattern": r"MYCO_KEY", "validator": "nope", "verdict": "ask"}], known_secrets={})
    assert plain.scan("MYCO_KEY = anything") is not None


def test_known_secrets_still_caught_regardless_of_shape():
    s = SecretScanner(known_secrets={"plainlowercasesecretvalue": "MY_SERVICE_KEY"})
    hit = s.scan("config: plainlowercasesecretvalue")
    assert hit is not None and "MY_SERVICE_KEY" in hit[1]


def test_reading_chatybot_source_and_docs_does_not_prompt(scanner):
    """Regression guard for prompt fatigue: no source file or doc in the repo should
    trigger an output prompt just by being read (test fixtures with fake keys are excluded)."""
    files = sorted(REPO.glob("src/chatybot/**/*.py")) + sorted(REPO.glob("doc/*.md")) + sorted(REPO.glob("*.md"))
    if not files:
        pytest.skip("repository sources not available")
    flagged = []
    for f in files:
        hit = scanner.scan(f.read_text(encoding="utf-8", errors="ignore"))
        if hit is not None:
            flagged.append(f"{f.relative_to(REPO)}: {hit[1]}")
    assert flagged == []


# --------------------------------------------------------------------------- redaction
# Fake keys are assembled at runtime so this file never contains a provider-format
# literal (GitHub push protection scans the source).

def _fake(prefix: str, body: str) -> str:
    return prefix + body


GROQ = _fake("gsk_", "aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789ABCDEFGHIJKLMN")
HF = _fake("hf_", "aBcDeFgHiJkLmNoPqRsTuVwXyZ01234567")
GOOGLE = _fake("AIza", "SyA1b2C3d4E5f6G7h8I9j0KlMnOpQrStUv")
JWT = _fake("eyJhbGciOiJIUzI1NiJ9", ".eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U")
UNPREFIXED = _fake("Zq8wE7rT6yU5", "iO4pA3sD2fG1hJ0kL9")
PEM_BODY = _fake("b3BlbnNzaC1r", "ZXktdjEAAAAA")


@pytest.mark.parametrize("text, secret, kept", [
    (f"groq-cli --key {GROQ} chat", GROQ, "groq-cli --key"),
    (f"huggingface-cli login --token {HF}", HF, "huggingface-cli login --token"),
    (f'curl "https://example.googleapis.com/v1/models?key={GOOGLE}"', GOOGLE, "googleapis.com"),
    (f'curl -H "X-Auth: {JWT}" https://api.example.com', JWT, "X-Auth:"),
    (f"mytool --password {UNPREFIXED} --verbose", UNPREFIXED, "--verbose"),
    ("psql postgres://admin:" + "S3cretPassw0rd@db:5432/x", "S3cretPassw0rd", "postgres://admin:"),
    ("Authorization: Basic " + "dXNlcjpwYXNzd29yZA==", "dXNlcjpwYXNzd29yZA==", "Authorization: Basic"),
    (f"ACME_API_KEY={UNPREFIXED} ./run.sh", UNPREFIXED, "ACME_API_KEY="),
])
def test_redact_removes_secret_keeps_context(scanner, text, secret, kept):
    out, n = scanner.redact(text)
    assert secret not in out
    assert kept in out
    assert n >= 1


def test_redact_private_key_block(scanner):
    text = "cat <<EOF > k.pem\n-----BEGIN OPENSSH PRIVATE KEY-----\n" + PEM_BODY + "\n-----END OPENSSH PRIVATE KEY-----\nEOF"
    out, _ = scanner.redact(text)
    assert PEM_BODY not in out
    assert "<redacted-private-key>" in out and out.startswith("cat <<EOF")


def test_redact_known_secret_any_shape():
    s = SecretScanner(known_secrets={UNPREFIXED: "MISTRAL_API_KEY"})
    out, n = s.redact(f'mistral chat --model large --x "{UNPREFIXED}"')
    assert UNPREFIXED not in out and "<redacted:MISTRAL_API_KEY>" in out and n == 1


@pytest.mark.parametrize("text", [
    "git push origin main",
    "python -m pytest test/ -q --maxfail 1",
    "mytool --max-tokens 4096 --token-limit 128000",
    "ssh -i ~/.ssh/id_ed25519 host",
    'grep -rn "api_key" src/',
    "export OPENAI_API_KEY=$(security find-generic-password -s openai -w)",
    "docker run -e API_KEY=${API_KEY} img",
    'curl -H "Authorization: Bearer $TOKEN" https://api.example.com',
    "This is a basic configuration example",
    "API_KEY = os.environ['OPENAI_API_KEY']",
])
def test_redact_leaves_ordinary_commands_and_code_alone(scanner, text):
    assert scanner.redact(text) == (text, 0)
