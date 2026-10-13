# DPF with Argo CD — customer deployment kit

Deploy the **DPF 26.4.0 management platform** to an existing, connected Kubernetes
cluster. Edit one settings file. Helm renders the bundled charts locally; Argo CD
then applies and reconciles the resulting YAML from your Git repository.

This installs cert-manager, Node Feature Discovery, Maintenance Operator, Kamaji
and its etcd store, and the DPF Operator. Site-specific operator configuration
is optional and disabled in the committed baseline. Argo CD is
installed once with Helm or reused. Local Path Provisioner is optional when you
already have a suitable StorageClass.

The outcome is the management platform. DPU discovery, BMC credentials, DPU
clusters/VIPs, BFB selection, hardware provisioning and HBN/Argus service bundles
require a separate site-specific configuration. Nothing in this kit reboots or
provisions a physical DPU. Monitoring add-ons are not installed by this minimum
platform package.

## Quick start

Use a **fresh management cluster**. This kit lives under `DPF/`; the generated
Application reads `DPF/rendered` on this repository's `main` branch.

```bash
git clone git@github.com:kirson-git/openshell-dpu.git
cd openshell-dpu/DPF
```

For customer-specific changes, fork or copy this repository into a customer-owned
Git repository and change `git.repoURL` before rendering. Keep `git.path` as
`DPF/rendered` when keeping this layout. The SSH URL requires repository access
on the administration machine and separate read access configured in Argo CD.
Do not copy lab kubeconfigs, passwords, logs or inventory.

The administration machine needs Bash, Python with PyYAML, Helm, kubectl and Git.
The package was checked with Python 3.12, PyYAML 6.0.1 and Helm 4.2.4. The Kubernetes
version in `site.yaml` must match your management cluster and DPF's supported
platform matrix. Nodes must have working CNI/DNS, time, registry access and the
`node-role.kubernetes.io/control-plane` label used by NVIDIA's supplied affinities.
Cluster-admin access is needed to install the platform's CRDs and RBAC.

1. Check the target cluster and edit `site.yaml`:

   ```bash
   kubectl config current-context
   kubectl version
   kubectl get nodes
   vi site.yaml
   ```

   Set `git.repoURL` if using a fork and set `kubernetesVersion` to your cluster's
   actual version. Review storage. The committed `operator.enabled: false`
   installs the prerequisites and DPF Operator without DPFOperatorConfig.
   For Zero Trust configuration, set `operator.enabled: true` and the reachable
   management API host in `operator.apiServerHost`. No password belongs here.

2. Generate all deployment YAMLs:

   ```bash
   ./dpf-argo.sh --render
   ```

3. Commit the reviewed files to your repository, on the branch in `git.revision`:

   ```bash
   git add .gitignore README.md site.yaml dpf-argo.sh tools values charts tests \
     LICENSE.dpf LICENSE.local-path SOURCES.txt VALIDATION.txt QUICKSTART.txt SHA256SUMS \
     rendered application.yaml argo-bootstrap-values.yaml images.txt render-report.json
   git commit -m "Add DPF management platform"
   git push
   ```

   Your Git remote/upstream must already be configured. `git.path` must point to
   the committed `rendered` directory. If the package is in a subdirectory, include
   that prefix in `git.path`. Argo CD must be able to read this repository and
   revision; local files alone are not enough. For this SSH repository, register
   its credentials with Argo CD using your normal secret-management process after
   bootstrapping it and before `--apply`. Never put credentials in `site.yaml` or the Git URL.

4. Bootstrap Argo CD, then submit the single Application:

   ```bash
   ./dpf-argo.sh --bootstrap-argo
   # Configure repository access in Argo CD: Settings > Repositories.
   # Use the URL in site.yaml and a customer-managed read-only deploy key.
   ./dpf-argo.sh --apply
   ./dpf-argo.sh --status
   ```

   If Argo CD already exists, the bootstrap command verifies its configuration
   without upgrading its release. It must meet the requirements below.

5. When synchronization finishes, verify:

   ```bash
   ./dpf-argo.sh --verify
   ```

   A nonzero exit means a check failed or the installation is still progressing.
   The command checks the Application and management workloads. Review the DPF
   configuration conditions as well; verification waits for Ready and checks its
   observed generation. Passing these checks does not prove that a
   DPU has been provisioned or that tenant traffic works.

If PyYAML is missing, install it in a local virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install PyYAML==6.0.1
```

## Files and settings

| Path | Purpose |
| --- | --- |
| `site.yaml` | Customer Git, Kubernetes, storage and DPF configuration inputs. |
| `values/` | Pinned NVIDIA prerequisite values; optional site adaptations go here. |
| `charts/` | Bundled versioned charts; no Helm repository setup is required. |
| `tools/render.py` | Generates YAML and translates reviewed hooks into Argo sync waves. |
| `rendered/platform.yaml` | Generated platform resources; this is Argo's source directory. |
| `application.yaml` | Generated Argo Application that points to your Git repository. |
| `argo-bootstrap-values.yaml` | Generated values for installing Argo CD once with Helm. |
| `images.txt` | Generated inventory of images visible in rendered platform resources. |
| `render-report.json` | Generated settings and content hash; detects stale local output. |
| `.runtime/` | Local command logs, excluded from Git and the customer archive. |

`images.txt` includes Deployments, Jobs, CronJobs and init containers from the
rendered platform. It excludes bootstrap Argo images and images later selected by
DPF controllers; it is not a complete air-gap mirror manifest.

The committed generated YAML installs the baseline without site-specific operator
configuration. It contains no lab inventory or credentials. Edit `site.yaml` or `values/`, render again, review the
YAML, then commit/push. Argo watches the configured revision. A branch follows
new commits; a commit SHA stays pinned. Do not hand-edit generated YAML.

| Setting | Contract |
| --- | --- |
| `git.repoURL` | Required real HTTPS or `ssh://` Git URL; no embedded password/token. |
| `git.revision` | Branch, tag or commit; default `main`. Must exist remotely. |
| `git.path` | Required relative path to generated YAML in Git; supplied `DPF/rendered`. No `..`. |
| `argoNamespace` | Argo installation/Application namespace; default `dpf-operator-system`. |
| `kubernetesVersion` | Actual management version, `major.minor.patch`; example `1.34.0`. Used for Helm rendering; does not install Kubernetes. |
| `storage.installLocalPath` | Boolean, default `true`; installs the bundled local-node provisioner. |
| `storage.className` | `local-path` when installing it; otherwise the name of an existing class. |
| `operator.enabled` | Required boolean; supplied `false` installs the operator without DPFOperatorConfig. Set `true` to emit the selected site configuration. |
| `operator.mode` | `zero-trust` (default) or `host-trusted`; controls operator configuration, not physical NIC/DPU mode. |
| `operator.apiServerHost` | Required for enabled Zero Trust configuration: management API IP/DNS, without scheme or port. Not a DPU tenant VIP. |
| `operator.apiServerPort` | Integer 1–65535, default `6443`; used for Zero Trust configuration. |

Local Path Provisioner stores data on individual nodes. For production storage,
set `installLocalPath: false` and supply the customer-approved StorageClass.
Kamaji's chart creates three etcd members; this kit does not certify storage,
scheduling, backup or recovery availability.

## What Argo CD does, in order

```text
Customer Git repository
        |
        v
Argo Application: dpf-platform
        |
        +-- -30 namespaces
        +-- -20 CRDs (server-side apply)
        +--   0 cert-manager and its webhook
        +--  10 storage, if requested
        +--  20 persistent Kamaji job RBAC/config
        +--  21 etcd certificate bootstrap job
        +--  30 Kamaji controller, webhook certificates and etcd
        +--  31 etcd authentication bootstrap job
        +--  32 default DataStore
        +--  40 NFD and Maintenance Operator
        +--  41 MaintenanceOperatorConfig
        +--  50 DPF Operator
        +--  60 DPFOperatorConfig, if enabled
```

Argo advances sync waves after the preceding resources become healthy. The etcd
jobs are explicit Sync hooks and run again on synchronization; their certificate
and authentication operations are designed for repeat execution. Completed/failed
jobs remain available for diagnosis until the next sync replaces them. Runtime
certificates are created in Kubernetes, not generated into Git.

Automated sync and self-heal are enabled. Automated pruning and cascade-deletion
finalizers are disabled. Removing files or deleting the Application therefore is
not an uninstall procedure. Storage cleanup, removal of cluster-wide components,
and migration of an existing deployment require an explicit reviewed procedure.
Do not use this kit to adopt or upgrade an existing Helm-based DPF deployment.

## Existing Argo CD

Set `argoNamespace` to its actual namespace. The same installation will deliver
the platform and DPF service Applications. Its administrator must configure:

- Annotation resource tracking: `application.resourceTrackingMethod: annotation`
  in the Argo CD configuration ConfigMap. This preserves the charts' release labels.
- Application watching for `dpf-operator-system` when Argo runs elsewhere, using
  `application.namespaces` in the Argo command-parameters configuration. The
  helper requires the literal namespace in the comma-separated ConfigMap value;
  wildcard-only or startup-flag-only configurations must be adapted by the Argo
  administrator before using this helper.
- Repository access and suitable project/RBAC policies. The generated platform
  Application uses project `default` and needs cluster-scoped deployment access.

The generated DPFOperatorConfig sets `spec.overrides.argoCDNamespace` accordingly.
The helper checks the required configuration; it does not reconfigure a shared
Argo installation. Follow the Argo migration guidance before changing tracking
on an existing installation.

## Underlying commands

The script logs every Helm/kubectl command it executes. Run commands below from
`DPF/`. Argo must watch `DPF/rendered`, not the whole `DPF` directory: the latter
also contains settings and Helm values that are not Kubernetes resources. For a fresh Argo install
using the default namespace, its installation command is:

```bash
helm install argo-cd charts/argo-cd-9.4.1.tgz \
  --namespace dpf-operator-system --create-namespace \
  --values argo-bootstrap-values.yaml --wait --timeout 600s
kubectl apply -f application.yaml
kubectl get application dpf-platform -n dpf-operator-system -o wide
```

`--apply` performs configuration and collision checks before the `kubectl apply`.
Manual application skips those checks. DPF components are then applied by Argo;
they do not appear as separate `helm list` releases.

Exactly one action is required. Optional `--config PATH` selects another site YAML;
it defaults to the `site.yaml` beside the script. Actions use kubectl's current
context. `--render` needs no Kubernetes access and makes no cluster writes.
`--bootstrap-argo` can create the Argo namespace and release; `--apply` creates or
updates the Application and thereby authorizes reconciliation. `--status` and
`--verify` only read cluster state. Failures return nonzero and remain in the log.
`--help` lists the interface. There is no uninstall/reset action.

For troubleshooting, use Argo's resource tree and these commands:

```bash
kubectl get application dpf-platform -n dpf-operator-system -o yaml
kubectl get pods,pvc -n dpf-operator-system
kubectl get events -n dpf-operator-system --sort-by=.lastTimestamp
kubectl logs -n dpf-operator-system job/kamaji-etcd-setup-1 --all-containers
kubectl logs -n dpf-operator-system job/kamaji-etcd-setup-2 --all-containers
kubectl logs -n dpf-operator-system deployment/dpf-operator-controller-manager --all-containers
```

Use your Argo namespace for the Application command if different. A named job may
not exist until its sync wave is reached. Local logs contain the wrapper's
commands; Argo's controller logs and resource tree describe its reconciliation.

## Sources and validation

See `SOURCES.txt` for exact chart versions, upstream provenance and GitOps
adaptations. See `VALIDATION.txt` for checks actually performed and the live-test
boundary. This package is a project-authored GitOps adaptation, not an NVIDIA
published installer or production qualification.

- [NVIDIA prerequisites](https://networking-docs.nvidia.com/dpf/26.4.0/helm-prerequisites)
- [DPF Zero Trust](https://networking-docs.nvidia.com/dpf/26.4.0/zero-trust-deployment)
- [Argo sync waves](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/)
- [Argo Helm hook semantics](https://argo-cd.readthedocs.io/en/stable/user-guide/helm/)
- [Argo private repositories](https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories/)
