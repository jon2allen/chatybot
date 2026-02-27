import re

def parse_sonnets(filepath):
    """
    Parses a large text file containing sonnets separated by Roman numerals and blank lines.

    Args:
        filepath (str): The path to the text file.

    Yields:
        tuple: A tuple containing the Roman numeral identifier (e.g., "I", "II") and the text of the sonnet.
    """

    with open(filepath, 'r', encoding='utf-8') as f:  # Specify encoding for broader compatibility
        text = f.read()

    # Regular expression to find Roman numeral followed by text until a blank line
    pattern = re.compile(r"([IVXLCDM]+)\s*\n(.*?)(?=\n[IVXLCDM]+\s*\n|\Z)", re.DOTALL)

    matches = pattern.finditer(text)

    for match in matches:
        roman_numeral = match.group(1)
        sonnet_text = match.group(2).strip()  # Remove leading/trailing whitespace
        yield roman_numeral, sonnet_text


if __name__ == '__main__':
    # Example Usage (create a dummy file for testing)
    dummy_file_content = """I
This is the first sonnet.
It has multiple lines.
And some more text.

II
Another sonnet here.
With different content.
This one is shorter.

III
A third sonnet for testing.
This demonstrates the generator.
It yields one sonnet at a time.

IV
The final sonnet.
Just to show it works with more than three.
"""

    with open("sonnets.txt", "w", encoding="utf-8") as f:
        f.write(dummy_file_content)

    # Parse the sonnets from the file
    sonnet_generator = parse_sonnets("sonnets.txt")

    # Iterate through the sonnets and print them
    try:
        while True:
            roman_numeral, sonnet_text = next(sonnet_generator)
            print(f"Sonnet {roman_numeral}:\n{sonnet_text}\n---")
    except StopIteration:
        print("No more sonnets.")
