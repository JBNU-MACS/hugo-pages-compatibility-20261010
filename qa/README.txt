Compatibility audit scope

The original Profile commit was pushed from a fresh Download ZIP directory and deployed with its generated workflow.
All 311 themes were extracted using macOS ditto, prepared through the interactive Python CLI, initialized on main, connected to this remote and committed locally.
Prepared release archives contain those exact Git-tracked trees. Each archive hash and tree ID is in manifest.json. The bulk workflow builds those snapshots on GitHub-hosted Ubuntu using their generated Python build helper.
All resulting sites are published in four batches under separate slug paths to stay within Pages site-size limits. Live HTTP checks run before the next batch replaces the previous batch.
This is batch coverage of the Mac-generated content, hosted build and Pages serving. It is not 311 separate repositories or 311 individual main-branch pushes.
The student workflow was temporarily disabled during batch deployments. It is enabled again for a final ordinary main-push deployment of Hugo Profile. Only the most recently deployed batch/site is live; the four deployment evidence artifacts preserve the checks for all 311 themes.
Original missing demo images and optional external services are reported separately from deployment failure.
