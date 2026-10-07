# NetHeal study and presentation deliverables

These exports accompany the tested simulator and source in this repository.

| File | Purpose |
| --- | --- |
| [NetHeal-Study-Companion.html](NetHeal-Study-Companion.html) | Self-contained lessons, current numbered source, worked calculations and recall quiz. Download and open in Chrome or Edge; no installation or server is needed. |
| [NetHeal-Detection-RCA-Evaluation.pptx](NetHeal-Detection-RCA-Evaluation.pptx) | Eight editable presentation slides with speaker notes, a native recovery chart and a native stress-results table. |
| [NetHeal-Live-Demo.webm](NetHeal-Live-Demo.webm) | A 75-second recording of the actual local simulator workflow. |
| [verification.json](verification.json) | Evidence and limits for Python, browser, export, restart and final repair checks. |

The HTML packages an identified source snapshot. Generated exports are excluded from
their own source index to avoid recursive copies. Full measured per-scenario results
remain in [docs/evaluation.json](../docs/evaluation.json); definitions and scope are in
[docs/EVALUATION.md](../docs/EVALUATION.md) and [docs/LIMITATIONS.md](../docs/LIMITATIONS.md).

Only public project source and demo information are included. Private `.env` values,
dependencies, runtime state, audit databases, build caches and private event documents
remain local. Demo accounts are deliberate simulator accounts and must not be reused
for production identity or credentials.

The verified environment uses the native simulator and offline explanation/reporting.
The live Qualcomm provider and Docker/Mininet runtime were not verified in that run.
