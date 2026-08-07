# Global subagent rules

## Parallelization
- **One agent per task.** Never assign multiple independent tasks to a single subagent. Each independent task gets its own dedicated `@agent-name` invocation.
- **Parallelize independent work.** When tasks are independent (e.g., checking separate sources, writing unrelated scripts), invoke subagents concurrently using separate parallel `@agent-name` calls.

## Subagent roster
- `@grounding-1` (DeepSeek V4 Flash Free), `@grounding-2` (MiMo V2.5 Free), `@grounding-3` (Big Pickle): online source verification, fact-checking, evidence tracing. Read-only + websearch/webfetch.
- `@scripting` (North Mini Code Free): bash commands, automation, data processing, file manipulation scripts. Full bash and edit access.

## Invocation
- The parent agent chooses which subagent to use based on task type and provides instructions at invocation time. Subagents have no built-in prompt.
- Use grounding-1 for general verification, grounding-2 as alternative, grounding-3 for stealth/rotating-capability tasks.
- Use scripting for any lightweight code execution or shell work.

## Operative guidelines — minimize inline tool use

To reduce context consumption and maximize parallelism:

- **Delegate shell commands to `@scripting`.** Instead of running `bash` inline, invoke `@scripting` with the command as instruction. This keeps shell output out of the parent context and allows parallel execution.
- **Delegate search/verification to `@grounding-*`.** Instead of using `websearch`, `webfetch`, `grep`, or `glob` inline, invoke the appropriate grounding agent. This isolates heavy output and enables concurrent fact-checking.
- **Prefer subagent invocation over inline tools** for any task that is self-contained, long-running, or produces large output. Only use inline tools for quick, low-output operations that block subsequent work.
- **Subagent output stays in the subagent's context.** The parent receives only the summary/final message from the subagent, not the full tool output trace.
