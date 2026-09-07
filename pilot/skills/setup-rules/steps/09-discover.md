## Step 9: Discover New Rules

1. List undocumented areas (comparing Step 2 + Step 5)
2. For each candidate area, find the actual patterns before drafting:
   ```bash
   # With Semble (preferred)
   semble search "how is [pattern] implemented across the codebase" ./
   semble find-related src/example.ts 42 ./

   # Without Semble (fallback)
   # Grep(pattern="[pattern]", head_limit=10)
   # Read representative files directly
   ```
3. Prioritize by: frequency, uniqueness, mistake likelihood
4. Select useful, non-obvious guidance within the requested scope; do not generate a rule for every observed pattern
5. Draft from verified source and project contracts when updates are authorized. Ask only about a consequential ambiguity
6. **Place in correct directory** based on scope:
   - Repo-wide → matching section in `AGENTS.md`
   - Path-specific, single-product repo → `.claude/rules/{slug}-{pattern-name}.md` with `paths` frontmatter
   - Product-specific → `.claude/rules/{product}/{slug}-{product}-{pattern-name}.md` with `paths` frontmatter
   - Team-specific → `.claude/rules/{product}/{team}/{slug}-{team}-{pattern-name}.md` (**must** have `paths` frontmatter)
   - Follow established ownership and matching paths in nested directories; ask only if the intended scope is unresolved
   - Create product/team directories as needed (`mkdir -p`)

Add every detailed file to the `AGENTS.md` matching-rule index. Use this rule format: Standard Name → When to Apply → The Pattern (code examples) → Why (if not obvious) → Common Mistakes → Good/Bad examples.
