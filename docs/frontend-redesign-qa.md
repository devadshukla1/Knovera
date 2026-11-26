# Knovera frontend redesign — QA

24 November 2026

## Delivered

- Centralized charcoal/navy and violet colors, readable typography, refined surfaces, focus states, and reduced-motion support. Fixed semantic Tailwind color opacity modifiers.
- Updated shell, mobile navigation, shared controls, dialogs, workspace cards, document library/upload, chat, study screens, analytics, hierarchical mind map, settings, topic cards, landing, and error states.
- Dashboard uses actual workspace/document counts and existing read-only APIs for recent documents, conversations, and learning activity. Removed hard-coded service availability claims.
- Keyboard access for mobile navigation, document upload, graph selection, and flashcards. Mobile chat history starts collapsed; citations remain accessible. Graph initial framing shows the root while preserving its hierarchy, pan/zoom, and expansion controls.

Skills used: ui-ux-pro-max, redesign-skill, and emil-design-eng. Figma connectivity was verified; no relevant project file was supplied or found in project references, and no Figma assets were edited.

## Executed verification

| Check | Result |
| --- | --- |
| TypeScript and production build | Passed, including final `npm run build` |
| Existing Vitest suite | 78 passed, 25 failed; untouched source snapshot has the same 25 failing test names and one unhandled error |
| Flashcard tests after keyboard changes | 4/4 passed |
| Existing Playwright suite | 3 passed, 7 failed; failures include absent routes and outdated UI/fixture expectations |
| ESLint | Unavailable: project has no lint script |
| Responsive sweep | 98 checks across 14 routes at 1920, 1440, 1366, 1024, 768, 390, and 375px; no horizontal overflow or browser page errors |
| Populated-page sweep | 35 additional checks; quiz-results footer overflow at 375/390px was fixed and both failing cases rerun successfully |
| Mobile controls | Navigation open/Escape dismissal, create-dialog fit, flashcard fit and keyboard flipping passed |
| Knowledge graph | Keyboard selection, details, pan, zoom, expand, and collapse passed |
| Themes | Light/dark selection passed; screenshots inspected |
| Diff whitespace | Passed |

Visual verification used screenshots and browser layout assertions. No approved pixel baseline was available; this is not a claim of automated pixel regression coverage or complete WCAG certification.

## Real backend workflows

A temporary workspace and text document were created through the UI. Real checks passed for workspace creation, rename, upload, ingestion to `ready`, source-grounded chat, conversation persistence after reload, quiz generation, flashcard generation/flipping, revision-note generation, and analytics rendering.

Submitting five unanswered quiz questions returned 0% and five unanswered items. This verifies that scoring case, not every evaluation branch. The temporary workspace was deleted through the UI and confirmed absent afterward.

## Remaining test/tooling limitations

The installed Vitest esbuild host/binary versions mismatch (0.21.5 versus 0.28.2). Tests ran with a matching temporary binary using process-scoped ESBUILD_BINARY_PATH. Dependency manifests and environment files were not changed.

Installed Playwright is incomplete (missing playwright-core/lib/coreBundle). Existing tests were executed using a temporary standalone runner. Several reference `/study`, absent research-intelligence routes, or old landing/UI assumptions. Tests were not rewritten to hide failures.

The untouched-source Vitest comparison confirms the same failures, including missing IntersectionObserver support, incomplete workspace mocks/providers, and stale expectations. Those remain unresolved within this presentation-only scope.

Cleanup of generated root `test-results` artifacts was rejected by command policy; those artifacts remain. The temporary application test workspace was successfully removed separately through the UI.

## Source safety and changed files

The checkout already contained substantial staged, unstaged, and untracked work. Changes were compared against a pre-edit source snapshot rather than treating all Git changes as this redesign.

Hash comparison found no changes to backend files or existing frontend API clients, hooks, contexts, types, or router definitions. Existing mutation handlers, schemas, migrations, provider configuration, and algorithms were preserved. No commit or push was made.

Changed 38 existing presentation source files, added `frontend/src/features/dashboard/components/WorkspaceActivity.tsx`, and updated the Tailwind presentation color mapping. Main locations are `frontend/src/styles/globals.css`, `frontend/src/components/layout`, `frontend/src/components/ui`, and feature presentation pages/components. This report is the only added project documentation.

Detailed logs, screenshots, source snapshot, and isolated redesign diff are under `%TEMP%/knovera-*` for this session.
