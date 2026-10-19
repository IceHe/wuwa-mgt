# Agent Workflow

Apply this checklist at the end of every conversation that changes project files:

1. Redeploy the project after changes by running `npm run build` in `frontend/` when frontend files changed, then run `./scripts/restart_services.sh`. This script rebuilds the backend, publishes the frontend, restarts the backend service, reloads Nginx, and checks both production endpoints.
2. Run the relevant tests for the changed code, including `go test ./...` from `backend/` for backend changes. Commit and push the conversation's changes to the current branch only after the relevant tests and deployment both succeed. If either fails, report the blocker and leave the worktree changes intact.
3. Preserve unrelated user changes. Stage and commit only changes belonging to the work being completed; never discard other worktree changes.
