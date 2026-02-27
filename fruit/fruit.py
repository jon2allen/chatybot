#!/usr/bin/env python3
"""
Generate 10 random Asian fruits with quantities between 10 and 100.

Author: ChatGPT
"""

import random
from typing import List, Tuple

# --------------------------------------------------------------------------- #
# 1. List of 20 Asian fruits
# --------------------------------------------------------------------------- #
ASIAN_FRUITS: List[str] = [
    "Mango",          # India, Thailand, etc.
    "Lychee",         # China, Vietnam
    "Rambutan",       # Malaysia, Indonesia
    "Durian",         # Thailand, Malaysia
    "Jackfruit",      # India, Bangladesh
    "Guava",          # India, Philippines
    "Papaya",         # Thailand, Philippines
    "Dragonfruit",    # Thailand, Vietnam
    "Starfruit",      # Thailand, Malaysia
    "Longan",         # China, Vietnam
    "Pomelo",         # China, Thailand
    "Kiwano",         # Kenya (but also grown in Asia)
    "Soursop",        # Philippines, Thailand
    "Mangosteen",     # Thailand, Malaysia
    "Cempedak",       # Malaysia, Indonesia
    "Buddha’s Hand",  # China, Thailand
    "Persimmon",      # China, Japan
    "Satsuma",        # Japan
    "Kumquat",        # China, Japan
    "Tamarind",       # India, Thailand
]

# --------------------------------------------------------------------------- #
# 2. Helper function to generate the random list
# --------------------------------------------------------------------------- #
def generate_fruit_quantities(
    fruits: List[str], 
    num_to_select: int = 10, 
    min_qty: int = 10, 
    max_qty: int = 100,
    seed: int | None = None
) -> List[Tuple[str, int]]:
    """
    Randomly pick `num_to_select` distinct fruits from `fruits` and assign
    each a random quantity between `min_qty` and `max_qty`.

    Parameters
    ----------
    fruits : List[str]
        The pool of available fruit names.
    num_to_select : int, default 10
        How many distinct fruits to pick.
    min_qty : int, default 10
        Minimum quantity (inclusive).
    max_qty : int, default 100
        Maximum quantity (inclusive).
    seed : int | None, default None
        Optional seed for reproducibility.

    Returns
    -------
    List[Tuple[str, int]]
        List of (fruit_name, quantity) tuples.
    """
    if seed is not None:
        random.seed(seed)

    if num_to_select > len(fruits):
        raise ValueError("num_to_select cannot exceed the number of available fruits.")

    selected = random.sample(fruits, num_to_select)
    result = [(fruit, random.randint(min_qty, max_qty)) for fruit in selected]
    return result

# --------------------------------------------------------------------------- #
# 3. Main routine
# --------------------------------------------------------------------------- #
def main() -> None:
    # You can set a seed for deterministic output (e.g. seed=42)
    fruit_quantities = generate_fruit_quantities(
        ASIAN_FRUITS,
        num_to_select=10,
        min_qty=10,
        max_qty=100,
        seed=None  # change to an int for reproducibility
    )

    # Pretty‑print the results
    print(f"{'Fruit':<20} | {'Quantity':>8}")
    print("-" * 31)
    for fruit, qty in fruit_quantities:
        print(f"{fruit:<20} | {qty:>8}")

# --------------------------------------------------------------------------- #
# 4. Entry point
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    main()
