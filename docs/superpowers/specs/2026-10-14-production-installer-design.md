# Production installer design

Status: proposed design for the first production release; implementation and
production qualification are incomplete. Reviewed against repository commit
`ad03b71`, NICo v2.2.1 and the bundled DPF v26.4.0 kit on 2026-10-14.

## Goal and scope

Provide one installer for an existing Kubernetes management cluster. Customers
choose standalone DPF or NICo with DPF, answer site-specific questions, and retain
an editable configuration. Argo CD reconciles the platform. The installer handles
prerequisites, reports progress, records commands without secrets, and verifies
the actual resulting system.

Both modes are release requirements. Their qualification records are separate.
The initial design assumes connected clusters with private-registry and custom
CA support. Fully disconnected installation remains a scope decision pending
customer requirements; do not advertise air-gap support without a complete
artifact bundle and a disconnected installation test.

Kubernetes provisioning, arbitrary migration of existing installations, and
automatic server wiping are outside the first installer interface. A complete
management-cluster rebuild is an acceptance exercise using a separate, reviewed
reset procedure. Installing the platform does not implicitly authorize physical
DPU reprovisioning or tenant workload disruption.

## Evidence from the existing kit

| Area | Observed implementation | Required production change |
| --- | --- | --- |
| Validation | 22 local tests passed again on 2026-10-14; no live GitOps installation qualification in `DPF/VALIDATION.txt`. | Exercise actual admission, synchronization, storage and hardware behavior. |
| Modes | `DPF/` is executable; `NICo/` is documentation. | Implement and qualify the NICo profile. |
| Argo roles | One `argoNamespace` controls both the platform Application and the DPF service override. | Separate configuration, compatibility and ownership for both roles. |
| Storage | Local Path is enabled in the example settings. | Require an explicitly selected, qualified persistent storage design in production. Keep local-path examples labeled as lab profiles. |
| Git source | The example Application tracks `main` and uses the default AppProject. | Pin promoted commits and use projects with explicit repository, destination and resource permissions. |
| Processes | `render.run` logs command arguments and captures output without a subprocess timeout. | Bounded execution, live output, cancellation and typed secret redaction. |
| Verification | Requires overall DPFOperatorConfig readiness; cannot distinguish an empty platform from operational DPUs. | Separate platform, enrollment and service/dataplane checks, including heartbeat freshness. |
| Recovery | Existing collision checks reject unrelated resources. | Preserve those checks; add durable resume state and tested recovery without deleting data. |

The installed lab also demonstrates a health-check failure case: DPF phase and
old pod states can appear successful while a tenant node has stopped renewing
its lease. Qualification must catch this. Lab addresses and access credentials
belong in local diagnostic records, not this public repository.

## Architecture and alternatives

Recommended: retain a Bash entrypoint and use a tested Python orchestration
library for validation, rendering, subprocess handling and state. Extend the
existing renderer rather than introduce a second renderer with different rules.
Keep platform and NICo manifests in `DPF/` and `NICo/`; common installer logic
and release metadata live in a dedicated `installer/` directory.

A Bash-only orchestrator would duplicate YAML validation, secret handling and
resume logic already better served by the Python foundation. A custom Kubernetes
operator would add another controller and CRD lifecycle before the customer can
install DPF. Neither is justified for this first release.

The release workflow is: collect settings, validate, show an installation plan,
bootstrap/reuse platform Argo CD, publish reviewed desired state to customer Git,
reconcile dependencies, initialize required services, verify, and export a
redacted support bundle. Git write credentials remain local; Argo receives
read-only repository access. Existing customer Git approval processes must be
supported without treating an unmerged revision as deployed.

The exact CLI/schema contract will be specified and tested during implementation.
It must provide the requested flag-based workflow, interactive questions,
configuration-file reruns, prerequisite-only execution, status and verification.
Noninteractive execution must fail clearly on missing required inputs, never
wait for a prompt. The existing DPF CLI remains available during development.

## Ownership and two Argo roles

| Object or function | Owner |
| --- | --- |
| Platform Argo bootstrap | Installer or detected customer installation, with one recorded owner. |
| Argo CRDs shared in the management cluster | One recorded owner, with compatibility tested for both controller versions. |
| DPF prerequisites, DPF Operator and site platform configuration | Platform Argo CD. |
| Dedicated DPF service Argo installation, when selected | Platform Argo CD; it does not also reconcile that instance's generated service Applications. |
| NICo installation and explicit site settings | Platform Argo CD. |
| NICo-generated DPU inventory/deployment/software/service resources | NICo controllers. |
| Applications generated by DPF for DPU services | DPF; reconciled by DPF service Argo CD. |
| Customer-supplied standalone DPF deployment/service resources | Customer Git through the platform deployment profile. |

Separate Argo instances must have distinct releases, namespaces, installation
identities and non-overlapping Application watches. DPF's Argo namespace override
and service repository credentials point at the service instance. CRD upgrades
are cluster-wide and must not be attempted independently by both instances.
Shared-instance reuse is allowed only for a tested version/configuration pairing.
If a combination cannot coexist safely, reject it; namespaces do not solve CRD
incompatibility. Do not automatically move a customer's existing Applications.

## Prerequisites and bootstrap

Inventory versions, API schemas, storage, ownership and health before mutation.
Each component gets an explicit install or reuse decision. Reuse requires a
validated compatible configuration, not merely a deployment with a matching name.
Conflicts produce an actionable report without automatically adopting resources.

The DPF profile covers its release-specific cert-manager, Node Feature Discovery,
Maintenance Operator, Kamaji/datastore, storage and Argo requirements. NICo adds
its selected Core database, credential/PKI and networking requirements. A full
NICo customer workflow also needs a qualified REST/control-plane profile and its
dependencies; development identity-provider defaults do not qualify for production.
Core-only support must not be presented as the complete customer workflow.

Readiness gates protect dependency boundaries: CRDs before CRs, working webhook
services before dependent certificates, persistent datastores before control
planes, and required identity/credential initialization before consumers.
Do not assume sync-wave numbers alone guarantee cross-Application readiness.

Port NICo v2.2.1's bootstrap semantics from the pinned setup source, including
database/credential initialization and staged DPF enablement. Use bounded,
idempotent Jobs with least-privilege service accounts for necessary bootstrap
actions. Repeated sync must not regenerate CAs, erase data, repeat destructive
database operations or rotate credentials unexpectedly.

## Configuration, credentials and artifact integrity

Use a versioned schema that rejects unknown fields, duplicate YAML keys,
ambiguous types, invalid combinations and missing production requirements before
cluster writes. Record stack mode, release selection, separate Argo roles,
storage, site networks, identity configuration and secret references.

Never store passwords in desired-state YAML, command-line arguments, Git or
support bundles. Interactive secret entry must be hidden. Supply secrets through
protected input channels or existing secret references; preserve file permissions
and validate references in the intended namespace. Kubernetes Secrets alone do
not provide encryption at rest: document and verify the customer's RBAC and
encryption controls. Support trusted private CAs rather than silently disabling
TLS verification. Inspect command output as well as arguments for secret leakage.

Release metadata must pin source revisions, charts/checksums, image digests and
architectures, and track chart versions separately from application versions.
Include the two Argo roles, their CRD compatibility, DPF, NICo, Kubernetes, DPU
generation/firmware, provisioning artifacts and selected DPU services in the
qualified compatibility record. NICo's v26.4.0 DPF default is a candidate input,
not proof of compatibility for every BF3/BF4 configuration.

Publish build provenance, artifact inventory, SBOMs and vulnerability review
results with the release. Missing or unqualified artifacts block production
selection. The build server is reserved for builds and artifact publication;
cluster tests, backups and recovery archives run elsewhere.

## Availability, state and recovery

Production profiles require tested availability for stateful services, scheduling
across failure domains, suitable resource requests, disruption budgets where
supported, and durable storage. Validate capacity and scheduling constraints
against the actual management cluster. Replica counts alone are not proof of HA.

Capture cluster identity, selected Git commit, configuration/artifact hashes and
stage outcomes. Acquire a per-installation lock and reject concurrent conflicting
runs. Resume must inspect live state and ownership before retrying; a local
checkpoint alone is not proof a stage remains healthy. Detect a changed target
cluster even if its kubeconfig context name is unchanged.

Use bounded retries and report the failed stage, diagnostic evidence and resume
action. Do not automatically uninstall a partially completed production stack.
Pruning of stateful data, namespaces and shared CRDs is disabled by default.
An upgrade needs a tested source-to-target path, backup evidence and service
maintenance policy. Git rollback does not reverse database migrations or DPU
firmware changes; each stateful recovery procedure must be tested separately.

Back up and restore Kamaji data/PKI and NICo databases/credential state as well as
Argo configuration. Store lab recovery files on the administration host under
`/images`, never on the build server. Customer RPO/RTO targets must be recorded
and demonstrated before that site's production acceptance.

## Qualification and release gates

| Gate | Required evidence before release |
| --- | --- |
| Input/command tests | Invalid settings fail before writes; secret canaries never appear in logs; timeouts and interruptions have deterministic outcomes. |
| Render/admission | Repeatable output, exact source identity, chart/image checksums, server-side admission and CRD validation for each supported Kubernetes release. |
| Argo coexistence | Two compatible versions operate simultaneously with one CRD owner, no cross-instance reconciliation, and correctly scoped DPF service Applications. Test incompatible pair rejection too. |
| Fresh standalone installation | Empty qualified management cluster reaches platform readiness, enrolls an authorized DPU and deploys the selected services. |
| Fresh NICo + DPF installation | Initialization, inventory, DPU service deployment and an authorized host lifecycle complete through the intended NICo APIs. |
| Retry/reuse | Repeat installation, second sync, interrupted bootstrap, registry failure and credential rotation preserve datastore contents and identities. |
| Availability/recovery | Exercise node loss, controller restart, datastore backup/restore and each supported upgrade path; retain timings and checksums. |
| DPU health | Fresh lease/heartbeat, expected node enrollment, reachable management endpoints, current Ready conditions, expected services and explicit dataplane traffic tests. Zero desired pods or stale Running status cannot pass this gate. |
| Clean rebuild | Retain a verified recovery set and baseline, reset the explicitly identified lab cluster, reinstall from the release package and reproduce the expected results. |
| Operator handoff | Reviewed CLI help, copyable instructions, failure/recovery runbooks and redacted evidence bundle match the shipped release. |

Health output must distinguish platform-ready, awaiting-hardware, DPU-ready and
service/dataplane-ready outcomes. Waiting for expected hardware is visible and
must not be labeled a complete production installation. Test production hardware
models explicitly; simulator output and a BF3 lab do not qualify BF4.

The later cluster deletion needs a separate plan that identifies the target,
scope (management Kubernetes versus host/DPU disks), retained data, verified
restore paths and intended effects on running workloads. No reset is part of
this design-review task. Resolve the current DPU reachability failure before
using the lab as the successful baseline for a clean rebuild.

## Delivery sequence

1. Implement the schema, artifact lock, execution/logging layer and prerequisite
   inventory with tests. Preserve the existing kit while the new path matures.
2. Implement Argo role separation and qualify standalone DPF in a disposable
   management cluster, including interruption and repeated-sync tests.
3. Implement NICo bootstrap and runtime ownership boundaries; qualify the full
   NICo + DPF profile against authorized test hardware.
4. Exercise availability, recovery, upgrades and the planned complete lab
   rebuild. Publish only the combinations whose evidence passes every gate.

## Sources

- [Existing validation boundary](../../../DPF/VALIDATION.txt)
- [NICo v2.2.1 setup source](https://github.com/dsx-ai-factory/infra-controller/blob/v2.2.1/helm-prereqs/setup.sh)
- [DPF 26.4.0 prerequisites](https://networking-docs.nvidia.com/dpf/26.4.0/helm-prerequisites)
- [Argo CD availability](https://argo-cd.readthedocs.io/en/stable/operator-manual/high_availability/)
- [Argo CD upgrade guidance](https://argo-cd.readthedocs.io/en/stable/operator-manual/upgrading/overview/)
- [Argo CD recovery](https://argo-cd.readthedocs.io/en/stable/operator-manual/disaster_recovery/)

Argo documentation links explain the design considerations. The actual release
must bind its procedures and tests to the chosen controller/chart versions.
