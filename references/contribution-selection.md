# Choose a contribution before committing to a full draft

Use this note when the repository supports several angles or the first idea looks like a polished restatement. Make the choice in the current conversation from actual source and primary-body reading. This is a short reasoning aid, not an extra review, required file, model call or approval gate.

Compare two or three plausible questions, then select one. For each, identify:

- The practitioner decision and why choosing differently matters.
- Exact available source behavior, guards, cases and relevant primary work; distinguish retained observations from work still needed.
- The strongest existing answer, including its actual assumptions and guarantees.
- What this repository lets the article add: a supported distinction, counterexample, integration obligation or worked decision that existing advice does not already settle.
- Whether a worthwhile answer is achievable within the user's execution and evidence limits.

A compact table can have columns `question`, `available evidence`, `strongest existing answer`, `additional decision value`, `remaining work`, and `choice`. Explain the choice in a few sentences. Do not assign fabricated numerical novelty scores or collect whole literatures for candidates already ruled out. Draft one article from the chosen question; do not write competing complete articles to choose a winner.

## Worked selection example

The following is an illustrative planning example, not a new study or a claim about an uninspected repository. Suppose retained source shows installation records, shared configuration, cleanup and recovery. Execution and new measurements are outside scope.

| Candidate question | Evidence available | Strong existing answer | Additional decision value | Choice |
| --- | --- | --- | --- | --- |
| Is this tool faster than alternatives? | Implementation source; no comparable measurements | Established benchmarking procedures require representative workloads and comparable runs | No supported performance result yet | Set aside under current scope |
| Does the code use transactions? | Planning, journal and commit paths | Transaction protocols already explain in-flight consistency | Merely listing transaction features adds little | Narrow or set aside |
| Which obligations survive a successful command and must constrain later cleanup? | Retained records, normal no-change path, restoration guards and worked command histories | Read tracking and ownership mechanisms address different lifetimes and participant boundaries | A source-grounded distinction may change which records a maintainer must consult | Investigate this angle if the actual witnesses establish it |

The selected angle still needs the closest primary work, normal reachability, meaningful guards and counterexamples. If those show that existing work already settles the decision, revise the question briefly or report the modest contribution. Missing reading is an evidence gap; it does not establish the project's intrinsic maximum.

## Keep the draft centered on the selected value

State the decision and the supported additional answer early. Carry the argument through concrete cases and the fair strongest comparison. Add explanations where they change what the reader can verify or do; avoid a longer implementation inventory that displaces the contribution.

If further work requires a new case, runtime measurements or human observations, identify it and respect the authorized scope. A narrow useful article or a finding that no worthwhile article is supported is preferable to invented generality. End the authorized pass with the actual result instead of restarting selection or scoring automatically.
