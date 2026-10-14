# openshell-dpu

Customer deployment examples for DPU infrastructure.

## DPF with Argo CD

The [DPF deployment kit](DPF/README.md) installs DPF 26.4.0 and its prerequisites
on an existing Kubernetes management cluster using Argo CD.

```bash
git clone git@github.com:kirson-git/openshell-dpu.git
cd openshell-dpu/DPF
```

See the [architecture diagram and YAML-to-service map](DPF/README.md#how-dpf-uses-the-stack)
and [Europe/Asia example](DPF/README.md#example-zero-trust-with-europe-and-asia).
Start with the [Argo CD + DPF CLI installation commands](DPF/README.md#cli-installation-argo-cd--dpf)
or [DPF/QUICKSTART.txt](DPF/QUICKSTART.txt). Review `site.yaml`, render the
YAML, commit changes to your repository, bootstrap Argo CD, configure repository
access, and apply `application.yaml`.

- Argo CD source path: **`DPF/rendered`** on `main`.
- [Deployment settings](DPF/site.yaml) control storage and optional Zero Trust
  operator configuration.
- [Optional Europe/Asia tenants](DPF/tenants/README.md) add separate control planes
  using customer-reserved VIPs.
- [Application](DPF/application.yaml) points to the committed platform YAML.
- [Validation](DPF/VALIDATION.txt) records the local checks and live-test boundary.

The committed baseline installs the prerequisites and DPF Operator. Enable
site-specific operator configuration after setting the management API address.
Tenant control planes can then be enabled in the same settings file. Physical
DPU provisioning and HBN services are separate steps.

## NICo with DPF

See [NICo/README.md](NICo/README.md) for the differences from standalone DPF,
installation choices, v2.2.1 release considerations and which images/charts need
updating. The executable Argo kit remains under `DPF/`; the NICo section is an
integration and release-selection guide.

For the concrete installation differences, see
[what changes in the DPF installation](NICo/README.md#what-changes-in-the-installation).
The goal is one installer that bootstraps Argo CD, collects site settings and
deploys either standalone DPF or NICo with DPF. The combined installer is planned;
the DPF kit is the executable starting point.

The installer requirements also distinguish
[platform Argo CD from DPF service Argo CD and cover prerequisite management](NICo/README.md#two-argo-cd-roles-and-prerequisite-handling).
Their versions must be validated independently, including shared CRD compatibility
when separate instances run in the same Kubernetes cluster.
