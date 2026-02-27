We need to produce a Python program that generates random Asian fruits with quantities between 10 and 100. "Number of generators 10 out of 20" unclear. Maybe they want to generate 10 random fruit entries out of a list of 20 possible fruits. So we have a list of 20 Asian fruits, choose 10 randomly, each with quantity 10-100. Provide code. Also maybe they want to generate 10 random fruit-quantity pairs. Provide explanation. Let's produce code. Use random module. Provide list of 20 fruits: mango, lychee, rambutan, durian, jackfruit, guava, papaya, dragonfruit, starfruit, longan, pomelo, lychee, etc. Ensure unique. Provide code. Also maybe they want to generate 10 random fruit-quantity pairs. Provide output. Provide function. Provide main guard. Provide optional seed. Provide printing. Provide ability to run. Provide explanation.Below is a **stand‑alone Python script** that

1. Keeps a list of **20 Asian fruits**.  
2. Randomly selects **10 distinct fruits** from that list.  
3. Assigns each selected fruit a random **quantity between 10 and 100** (inclusive).  
4. Prints the result in a readable table.

Feel free to copy‑paste the code into a file (e.g. `asian_fruits.py`) and run it with `python asian_fruits.py`.



### How it works

| Step | What happens | Why |
|------|--------------|-----|
| 1 | `ASIAN_FRUITS` holds 20 fruit names | Provides a realistic pool of Asian fruits |
| 2 | `generate_fruit_quantities` | Uses `random.sample` to pick 10 unique fruits and `random.randint` for quantities |
| 3 | `main()` | Calls the helper, then prints a neat table |
| 4 | `if __name__ == "__main__":` | Allows the script to be run directly or imported without side effects |

### Customization

- **Change the number of fruits**: modify `num_to_select` in the `generate_fruit_quantities` call.  
- **Adjust quantity range**: change `min_qty` and `max_qty`.  
- **Reproducible results**: pass an integer to `seed` (e.g., `seed=123`).  

Enjoy experimenting with the script!