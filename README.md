# openshell-dpu

Customer deployment examples for DPU infrastructure.

## DPF with Argo CD

The [DPF deployment kit](DPF/README.md) installs DPF 26.4.0 and its prerequisites
on an existing Kubernetes management cluster using Argo CD.

```bash
git clone git@github.com:kirson-git/openshell-dpu.git
cd openshell-dpu/DPF
```

Start with [DPF/QUICKSTART.txt](DPF/QUICKSTART.txt). Review `site.yaml`, render the
YAML, commit changes to your repository, bootstrap Argo CD, configure repository
access, and apply `application.yaml`.

- Argo CD source path: **`DPF/rendered`** on `main`.
- [Deployment settings](DPF/site.yaml) control storage and optional Zero Trust
  operator configuration.
- [Application](DPF/application.yaml) points to the committed platform YAML.
- [Validation](DPF/VALIDATION.txt) records the local checks and live-test boundary.

The committed baseline installs the prerequisites and DPF Operator. Enable
site-specific operator configuration after setting the management API address.
Physical DPU provisioning and HBN services are separate steps.
