# Optional Europe and Asia tenant control planes

Enable two Kamaji-backed DPUClusters through the same `dpf-platform` Argo
Application. Each has a separate namespace, Kubernetes API endpoint and control
plane. The Kamaji controller and backing etcd service remain shared in
`dpf-operator-system`.

```text
Git: DPF/site.yaml -> render -> DPF/rendered/platform.yaml -> Argo CD
                                                           |
                           +-------------------------------+
                           |
                  DPF + shared Kamaji/etcd
                           |
              +------------+------------+
              |                         |
       tenant-europe              tenant-asia
       Europe API VIP             Asia API VIP
       Europe control plane       Asia control plane
       0 DPU nodes initially      0 DPU nodes initially
```

This creates tenant control planes, not a complete tenant security policy.
Management-cluster RBAC, tenant data-plane separation and HBN networking need
separate configuration. This step creates no DPUSet, DPU, BFB or HBN resources.
It does not assign DPUs, flash firmware, or install a server OS.

## Configure

Use a customer-owned fork for customer-specific settings. Run these commands
from `DPF/` on the administration machine. Edit `site.yaml`:

```bash
vi site.yaml
```

1. Set `operator.enabled: true`. For Zero Trust, set `operator.apiServerHost`
   to the management Kubernetes API address.
2. Set `tenants.enabled: true`.
3. Set each tenant's `vip` and `interface`. Reserve two different usable IPv4
   addresses in the management subnet, outside DHCP allocation. They must differ
   from the management API address and other assigned addresses.
4. Confirm the VRRP IDs are unused on the management L2 network. The supplied
   `126` and `127` are examples, not allocated network resources.
5. Check both tenant names and `maxNodes`. The supplied capacity of one DPU per
   tenant does not select which DPU joins it.

The `interface` is the management control-plane node's OOB interface, such as
`ens192`, not the DPU's `p0` or `p1`. This kit selects keepalived nodes with
`node-role.kubernetes.io/control-plane: ""`; the interface name must exist on
each selected node. Those nodes must share the appropriate L2 network and permit
VRRP multicast. DPUs must be able to reach the tenant API endpoints. Validate
these site conditions with your network administrator; the renderer cannot
check address reservations, routing, interfaces, or external VRRP conflicts.

Each tenant gets one API VIP. These are additional to the management Kubernetes
API endpoint. This configuration uses keepalived and does not require MetalLB.
See NVIDIA's [DPUCluster reference](https://networking-docs.nvidia.com/dpf/26.4.0/dpucluster)
and [network prerequisites](https://networking-docs.nvidia.com/dpf/26.4.0/dpf-system-prerequisites-for-host-trusted).

## Render and deploy through Argo CD

```bash
./dpf-argo.sh --render
git diff -- site.yaml rendered/platform.yaml render-report.json
git add site.yaml rendered/platform.yaml application.yaml \
  argo-bootstrap-values.yaml images.txt render-report.json
git commit -m "Configure Europe and Asia DPF tenant control planes"
git push
```

For a first installation, follow the main [CLI installation](../README.md#cli-installation-argo-cd--dpf)
to bootstrap Argo CD, configure Git access, and run `--apply`. If the platform
Application is already installed and follows your branch, Argo automatically
synchronizes the committed change. No second Application is required.

```bash
./dpf-argo.sh --status
./dpf-argo.sh --verify
```

The renderer places tenant namespaces at wave `-30`, operator configuration at
`60`, and DPUClusters at `70`. DPF creates and reconciles the underlying
TenantControlPlanes, keepalived workloads, and credential Secrets. Do not commit
or separately manage those generated resources. Argo's health assessment alone
does not guarantee a DPUCluster is ready; `--verify` explicitly waits for its
phase to become `Ready`, with a 600-second timeout per tenant. Timeout exits
nonzero; inspect status and retry after fixing the reported problem.

`europe.example.yaml` and `asia.example.yaml` show the generated resource shape.
They contain placeholders and are outside Argo's source path. Edit `site.yaml`
and render; do not apply those reference files or hand-edit generated YAML.

## Settings contract

| Setting | Meaning |
| --- | --- |
| `tenants` | Optional mapping; omission creates no tenants. |
| `tenants.enabled` | Boolean; defaults to `false`. `true` requires `operator.enabled: true`. |
| `tenants.items` | Required nonempty list when enabled. Ignored when disabled, allowing placeholders. |
| `name` | Required unique lowercase DNS label, 1–56 characters. Both namespace and DPUCluster are named `tenant-<name>`. |
| `vip` | Required unique unicast IPv4 address string, without a prefix or port. IPv6 is not supported by this kit. |
| `interface` | Required Linux interface name, 1–15 letters, digits, underscores, dots or hyphens; begins with a letter, digit or underscore. `CHANGE-ME` is rejected. |
| `virtualRouterID` | Required unique integer 1–255. Must also be unused by other VRRP instances in the network. |
| `maxNodes` | Optional integer 1–1000; defaults to 1000, supplied examples use 1. Capacity of this DPUCluster, not control-plane replica count. |

The renderer rejects duplicate names, VIPs and VRRP IDs within the kit. It rejects
an IPv4 tenant VIP identical to `operator.apiServerHost`; it does not resolve DNS
to detect an address conflict. Both Zero Trust and host-trusted operator modes
can use these Kamaji tenant control planes. Neither mode provisions hardware at
this stage.

Each DPUCluster is labeled `customer.dpf.nvidia.com/tenant: europe` or `asia`.
Later DPUSet/DPUDeployment and service configuration must explicitly target the
intended cluster. Creating two control planes alone does not bind a particular
physical DPU to a tenant. Follow the selector contract of each DPF resource;
NVIDIA documents cluster selection in the DPUCluster reference linked above.

## Inspect the result

These commands use the current management-cluster context:

```bash
kubectl get dpuclusters -A
kubectl get tenantcontrolplanes,pods -n tenant-europe
kubectl get tenantcontrolplanes,pods -n tenant-asia
kubectl describe dpucluster tenant-europe -n tenant-europe
kubectl describe dpucluster tenant-asia -n tenant-asia
kubectl get events -n tenant-europe --sort-by=.lastTimestamp
kubectl get events -n tenant-asia --sort-by=.lastTimestamp
```

A ready control plane may have zero joined DPU nodes. This is expected until the
separate DPU provisioning stage. The wrapper logs its kubectl commands under
`.runtime/`; inspect Argo's Application resource tree for reconciliation errors.

Automatic pruning remains disabled. Removing a tenant from settings, renaming
it, or turning `tenants.enabled` off does not delete its existing control plane.
After disabling, `--verify` no longer checks that tenant. Tenant removal and
stateful-data cleanup require a separate procedure. Never treat a rename as a
migration.

These examples passed local rendering/schema checks only. A live tenant rollout,
VIP failover and DPU joins have not been validated for this GitOps package.
