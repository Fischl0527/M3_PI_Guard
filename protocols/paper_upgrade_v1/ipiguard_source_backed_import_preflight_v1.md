# IPIGuard source-backed import preflight v1

- Status: `completed_import_preflight_only`
- Checks: 7/7
- Network calls: `False`
- Benchmark cases: `0`
- Formal result eligible: `False`

## Boundary

Import/build qualification only. It proves that the pinned IPIGuard source-backed adapter can be constructed in a fresh subprocess without Vertex dependencies or network access. Subprocess isolation prevents the older fork from contaminating the main project runtime. It is not a model smoke, benchmark result, or formal effect estimate.
