# Adding LangSmith tracing (optional, not done yet)

Not wired up currently - no `LANGSMITH_API_KEY`/`LANGCHAIN_TRACING_V2`
anywhere in this codebase or `.env.example`. This is how to add it
yourself when you want it; nothing here has been done for you.

## Steps

1. Go to https://smith.langchain.com and sign up (there's a free tier).
2. In Settings → API Keys, create a key and copy it.
3. Add these three lines to `services/api/.env` - the same file you've
   already been adding `GROQ_API_KEY`, `GOOGLE_PLACES_API_KEY`, etc. to:

   ```
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=<paste your key here>
   LANGCHAIN_PROJECT=wanderplan-dev
   ```

   (`LANGCHAIN_PROJECT` is just a label - traces group under this name
   in the LangSmith dashboard. Call it whatever you want.)

4. Nothing to `pip install` - the `langsmith` package is already sitting
   in `services/api/.venv` (pulled in as a dependency of `langgraph`
   itself), just currently inert because those env vars aren't set.
5. Restart `uvicorn` (the API process) so it picks up the new `.env`
   values, then plan a trip as normal.

## What you'll actually see, and what you won't

**Automatic, from just the env vars above:** every graph run - the full
IntentAgent → BudgetGate → ResearchAgent → BudgetAgent → SchedulingAgent
→ VerificationAgent sequence - shows up as a trace in your LangSmith
project, with per-node timing and the state each node added. This part
is genuinely zero extra code: LangGraph has built-in LangSmith
integration for its own graph execution.

**NOT automatic:** the actual prompt/response text of the Groq or OpenAI
calls inside IntentAgent and SchedulingAgent. `app/core/llm.py` calls
the Groq/OpenAI SDKs directly (`client.chat.completions.create(...)`),
not through LangChain's own LLM wrapper - deliberately, so this project
doesn't need a LangChain dependency (see the "no langchain dependency"
note in `requirements.txt`). LangSmith's automatic tracing hooks into
LangChain's runnables, not a raw SDK call, so without one more change
you'll see that a "call_llm"-shaped step happened and how long it took,
but not the exact prompt/completion text inside it.

If/when you want that level of detail too, it's a small, optional
addition to `app/core/llm.py`'s `_get_client()` - wrapping the
constructed client with `from langsmith.wrappers import wrap_openai`
(this works for the Groq client too, since Groq's SDK is an
OpenAI-compatible fork). Ask if you want that added - it's a few lines,
not a redesign.
