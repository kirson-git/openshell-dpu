#!/usr/bin/env python3
"""Customer DPF platform deployment through Argo CD (existing management cluster)."""
import argparse
import json
import pathlib
import subprocess
import sys
import yaml
import render

ROOT=pathlib.Path(__file__).resolve().parents[1]

def command(*args,show=True):
    output=render.run(list(args))
    if show and output:print(output,end='')
    return output

def kube_json(*args):
    return json.loads(command('kubectl',*args,*(() if '--raw' in args else ('-o','json')),show=False))

def current_context():
    command('kubectl','config','current-context')
    command('kubectl','version','--client')

def prepared(cfg):
    report=json.loads((ROOT/'render-report.json').read_text())
    if report['site']!=cfg:raise ValueError('site.yaml changed: run --render and commit/push the new rendered files first')
    if render.hashlib.sha256((ROOT/'rendered/platform.yaml').read_bytes()).hexdigest()!=report['platformSHA256']:
        raise ValueError('Rendered YAML changed: edit source values and rerun --render')
    if yaml.safe_load((ROOT/'application.yaml').read_text())!=render.application(cfg):
        raise ValueError('Application changed: edit site.yaml and rerun --render')

def argo_ready(cfg):
    ns=cfg['argoNamespace']
    command('kubectl','rollout','status','deployment','-n',ns,'-l','app.kubernetes.io/name=argocd-server','--timeout=300s')
    command('kubectl','rollout','status','statefulset','-n',ns,'-l','app.kubernetes.io/name=argocd-application-controller','--timeout=300s')
    configs=kube_json('get','configmap','-n',ns,'-l','app.kubernetes.io/name=argocd-cm')['items']
    if len(configs)!=1:raise ValueError('Expected one Argo CD configuration ConfigMap in argoNamespace')
    data=configs[0].get('data',{})
    if data.get('application.resourceTrackingMethod')!='annotation':
        raise ValueError('Existing Argo CD must use annotation resource tracking; see README before changing shared Argo settings')
    if ns!=render.NS:
        params=kube_json('get','configmap','-n',ns,'-l','app.kubernetes.io/name=argocd-cmd-params-cm')['items']
        allowed=params[0].get('data',{}).get('application.namespaces','') if len(params)==1 else ''
        if render.NS not in [x.strip() for x in allowed.split(',')]:
            raise ValueError('Existing Argo CD must watch Applications in dpf-operator-system; see README')

def check_application(cfg):
    text=command('kubectl','get','application','dpf-platform','-n',cfg['argoNamespace'],'--ignore-not-found','-o','json',show=False)
    if not text.strip():return
    old=json.loads(text)
    marker=old.get('metadata',{}).get('labels',{}).get('customer.dpf.nvidia.com/package')
    if marker!='dpf-platform-v26.4.0':
        raise ValueError('An unrelated Application named dpf-platform already exists; refusing to change it')

def check_collisions():
    objects=list(yaml.safe_load_all((ROOT/'rendered/platform.yaml').read_text()))
    existing_crds=kube_json('get','crd')['items']
    namespaces={o['metadata']['name'] for o in kube_json('get','namespace')['items']}
    wanted={(o['apiVersion'],o['kind'],o['metadata'].get('namespace',''),o['metadata']['name']) for o in objects if o['kind']!='Namespace'}
    custom={}
    for crd in existing_crds:
        for v in crd['spec']['versions']:
            if v.get('served'):
                custom[(crd['spec']['group']+'/'+v['name'],crd['spec']['names']['kind'])]=crd['spec']['names']['plural']
    desired_custom={(crd['spec']['group']+'/'+v['name'],crd['spec']['names']['kind'])
        for crd in objects if crd['kind']=='CustomResourceDefinition' for v in crd['spec']['versions']}
    groups=sorted({key[:3] for key in wanted})
    conflicts=[]
    for api,kind,namespace in groups:
        if namespace and namespace not in namespaces:continue
        if (api,kind) in desired_custom and (api,kind) not in custom:continue
        plural=custom.get((api,kind),{'StorageClass':'storageclasses','PriorityClass':'priorityclasses'}.get(kind,kind.lower()+'s'))
        prefix='/api/v1' if api=='v1' else '/apis/'+api
        path=prefix+('/namespaces/'+namespace if namespace else '')+'/'+plural
        existing=existing_crds if kind=='CustomResourceDefinition' else kube_json('get','--raw',path)['items']
        for obj in existing:
            meta=obj['metadata'];key=(api,kind,meta.get('namespace',''),meta['name'])
            tracking=meta.get('annotations',{}).get('argocd.argoproj.io/tracking-id','')
            if key in wanted and not tracking.startswith('dpf-platform:'):conflicts.append('/'.join(key))
    if conflicts:raise ValueError('Existing resources need a reviewed migration, not automatic adoption: '+', '.join(conflicts[:8]))

def verify(cfg):
    app=kube_json('get','application','dpf-platform','-n',cfg['argoNamespace'])
    status=app.get('status',{})
    sync=status.get('sync',{}).get('status');health=status.get('health',{}).get('status')
    print(f'Argo CD: sync={sync}, health={health}')
    for condition in status.get('conditions',[]):print(condition.get('type','')+': '+condition.get('message',''))
    if sync!='Synced' or health!='Healthy':raise ValueError('Argo CD is not Synced/Healthy; inspect --status and Argo resource errors')
    for namespace in ['cert-manager',render.NS]:
        command('kubectl','rollout','status','deployment','-n',namespace,'--timeout=300s')
    command('kubectl','rollout','status','statefulset/kamaji-etcd','-n',render.NS,'--timeout=300s')
    command('kubectl','get','datastore','default')
    command('kubectl','get','pvc','-n',render.NS)
    if cfg['operator']['enabled']:
        command('kubectl','wait','dpfoperatorconfig/dpfoperatorconfig','-n',render.NS,'--for=condition=Ready','--timeout=600s')
        config=kube_json('get','dpfoperatorconfig','dpfoperatorconfig','-n',render.NS)
        if config.get('status',{}).get('observedGeneration')!=config['metadata']['generation']:
            raise ValueError('DPFOperatorConfig readiness is from an older generation; retry verification after reconciliation')
        command('kubectl','get','dpfoperatorconfig','dpfoperatorconfig','-n',render.NS,'-o','yaml')
    for tenant in render.enabled_tenants(cfg):
        name='tenant-'+tenant['name']
        command('kubectl','wait','dpucluster/'+name,'-n',name,'--for=jsonpath={.status.phase}=Ready','--timeout=600s')
        command('kubectl','get','dpucluster',name,'-n',name,'-o','wide')
    print('Argo sync, platform workloads and enabled tenant control-plane checks passed. DPU provisioning and service readiness are separate checks.')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    for flag,help_text in [
      ('render','Generate manifests and Application from local bundled charts; no cluster access'),
      ('bootstrap-argo','Install fresh Argo CD 9.4.1, or verify an existing installation without upgrading it'),
      ('apply','Check prerequisites/ownership and apply the generated Argo Application to the current cluster'),
      ('status','Display Application, enabled tenants, pods and events without cluster writes'),
      ('verify','Require Argo Synced/Healthy, management rollouts and enabled tenant control planes')]:group.add_argument('--'+flag,action='store_true',help=help_text)
    parser.add_argument('--config',type=pathlib.Path,default=ROOT/'site.yaml',help='Site YAML path (default: site.yaml beside script)')
    args=parser.parse_args()
    try:
        cfg=render.load_config(args.config)
        if args.render:render.render(cfg,ROOT/'rendered');return 0
        current_context()
        if args.status:
            command('kubectl','get','application','dpf-platform','-n',cfg['argoNamespace'],'-o','wide')
            for ns in [cfg['argoNamespace'],render.NS,'cert-manager','local-path-provisioner']:
                command('kubectl','get','pods','-n',ns)
            for tenant in render.enabled_tenants(cfg):
                ns='tenant-'+tenant['name']
                command('kubectl','get','dpucluster',ns,'-n',ns,'-o','wide')
                command('kubectl','get','tenantcontrolplanes,pods','-n',ns)
            command('kubectl','get','events','-n',render.NS,'--sort-by=.lastTimestamp')
            return 0
        if args.verify:verify(cfg);return 0
        prepared(cfg)
        if args.bootstrap_argo:
            existing=kube_json('get','deployment','-n',cfg['argoNamespace'],'-l','app.kubernetes.io/name=argocd-server')['items']
            if existing:print('Argo CD already exists: verifying configuration, leaving its Helm release unchanged.')
            else:
                command('helm','install','argo-cd',str(ROOT/'charts/argo-cd-9.4.1.tgz'),
                    '--namespace',cfg['argoNamespace'],'--create-namespace','--values',str(ROOT/'argo-bootstrap-values.yaml'),
                    '--wait','--timeout','600s')
            argo_ready(cfg)
        elif args.apply:
            argo_ready(cfg)
            if not cfg['storage']['installLocalPath']:command('kubectl','get','storageclass',cfg['storage']['className'])
            check_application(cfg)
            check_collisions()
            command('kubectl','apply','-f',str(ROOT/'application.yaml'))
            print('Application submitted. Argo CD pulls the committed Git revision and reconciles the platform. Use --status, then --verify.')
        return 0
    except (ValueError,KeyError,TypeError,OSError,yaml.YAMLError,subprocess.CalledProcessError) as error:
        print('ERROR: '+str(error),file=sys.stderr)
        if isinstance(error,subprocess.CalledProcessError):print(error.stderr,file=sys.stderr)
        return 1
if __name__=='__main__':sys.exit(main())
