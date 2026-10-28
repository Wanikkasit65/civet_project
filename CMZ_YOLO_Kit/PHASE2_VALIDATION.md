# Validation of the Phase 2 code

- 17 automated tests passed: 11 Phase 2 tests plus 6 scout tests.
- Tests cover Unknown versus Inactive, absent classes remaining blank, interval union without double counting, conflicting-label rejection without changing annotation history, human-label provenance, grouping camera views by recording clock, joining explicit events across blocks, crossing-block intervals, training without fabricated scores, and one-time independent-test exposure.
- Streamlit AppTest exercised all six pages, imported annotation state, confirmed tables, report ZIP creation, actual CCTV preview, crop controls, interval trimming and saving a manual label.
- The six human-confirmed Feeding annotations supplied for local QA produced 60 seconds of reviewed intervals; no Resting/Sleeping seconds were invented. Personal annotations and videos are not included in this repository.
- A 4-second section of a real supplied CCTV review clip decoded successfully and produced 18 finite optical-flow features.
- Random Forest training/evaluation control flow was exercised on synthetic fixtures. These are software tests, not project model results.
- Merging insufficient detector annotations kept original files unchanged and refused dataset readiness using the existing guards.
- Windows batch files, RTX 3070 Laptop training and real project model accuracy have not been executed or verified in this environment.
- No complete end-to-end YOLO-to-behavior accuracy is claimed. The behavior pilot uses human-reviewed crops, and its unconfirmed proposals stay Unknown.
- Interval corrections append a superseding record without editing the original annotation file; current totals exclude the old interval. Dataset signatures prevent using stale/legacy models after labels change. AppTest verified correcting three full 10-second intervals to 2, 2 and 3 seconds while keeping 9 current annotations.
