# Reviewed-source CI receipts

Run45843650844 at head582b74c uses the implementation from7f5c859.
`python-linux312/ci-python.xml` is the current run's generated result:
161passes,21skips (18 native executable checks run in the Rust job,3platform skips).
`python-linux312/python-tests.xml` is a tracked historical phase-two baseline
included by the workflow artifact glob:67passes/4skips, not a new rerun.
Do not aggregate both or count those18native skips as failures/passes here.
`rust-job.log` is the actual completed strict Rust job log; its contract step
executes the18native checks. `dependencies/` holds the completed advisory scan.
`completed-jobs.json` is a snapshot while the mandatory browser soak is active,
not a completion assertion. Final metadata is in final-run.json/final-jobs.json and browser/ contains the
successful47browser/38runtime+2skip/1,801.468second688cycle soak receipts. All
eleven engineering jobs passed; Sonar is a separate unsuppressed failing gate.
