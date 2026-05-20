# OUTPUT CONTRACT

## Claude must always output:
1. FILE_TREE
2. apply_phase_XX.py  (full patch script)
3. VERIFY_PHASE_XX.md (in Persian, right-aligned)
4. CHANGED_FILES
5. UPDATED_CURRENT_STATE.md (full updated file content, with this phase checked off and Next Phase incremented)

## The patch script must:
- Use pathlib only
- Create all missing parent directories
- Write files in UTF-8
- Overwrite existing files (idempotent)
- Print each created/updated file path at end
- BASE_DIR computed relative to script location (__file__.parent)
- Also write the updated CURRENT_STATE.md to the prompt bank directory
  (ask user for prompt bank path at top of script, default: "./NEW_PROMPT_BANK")

## Claude must never:
- Output "add this line manually"
- Output partial code snippets
- Output TODO or placeholder implementations
- Split output across multiple messages without completing the phase
- Ask clarifying questions mid-phase
- Forget to include migration files in the patch script
- Use HttpRequest in services.py
- Use Django Signals
