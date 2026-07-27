# Project Check remeasurement

Status: `MEASURED_FALSE_WARNING_RISK_REDUCTION`.

- Frozen exact-SHA repositories: **60**.
- Complete observations: **60** (100.0%).
- Missing-test reasons removed by a declared nested command: **8** (13.3%).
- Resolutions with complete bounded nested discovery: **7** (11.7%).
- Bounded nested discovery complete: **58/60** (96.7%); incomplete: **2**.
- Root test commands detected: **0**.
- No supported runnable command detected after bounded discovery: **52**.
- Previously adjudicated definite test surfaces with a supported command: **5/12** (41.7%).
- The same metric with complete bounded discovery: **4/12**.

The comparison is against the frozen root-only AOS warning corpus.
Only metadata and path structure were reconstructed; repository code
and dependencies were not executed. A visible test file does not prove
a runnable command, and this result does not measure user acceptance,
retention, decision change, business severity, or superiority over
another product.

Manifest: `sha256:ec204dbe2f94272876678284a810fc58e8482535b0b59c15d28550f1c06e79dc`.
