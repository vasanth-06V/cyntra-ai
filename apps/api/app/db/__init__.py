"""The only package that talks to Supabase tables and RPCs.

Services (keys, chat, rag, ats, interviews, llm) call these functions and
never import the Supabase client themselves; tests/test_architecture.py
enforces that. Ownership scoping (`user_id`) lives here, in one place, so a
query can't forget it.
"""
