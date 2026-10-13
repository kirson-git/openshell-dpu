import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import manage

class CollisionTests(unittest.TestCase):
    def test_any_existing_named_resource_without_tracking_is_rejected(self):
        for kind,plural,api,ns in [('StorageClass','storageclasses','storage.k8s.io/v1',''),
                                   ('ClusterRole','clusterroles','rbac.authorization.k8s.io/v1',''),
                                   ('Service','services','v1','dpf-operator-system')]:
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                root=pathlib.Path(tmp);(root/'rendered').mkdir()
                obj={'apiVersion':api,'kind':kind,'metadata':{'name':'existing'}}
                if ns:obj['metadata']['namespace']=ns
                (root/'rendered/platform.yaml').write_text(yaml.safe_dump(obj))
                def get(*args):
                    if args==('get','crd'):return {'items':[]}
                    if args==('get','namespace'):return {'items':[{'metadata':{'name':ns}}]}
                    if args[0]=='get' and args[1]=='--raw':return {'items':[obj]}
                    raise AssertionError(args)
                with patch.object(manage,'ROOT',root),patch.object(manage,'kube_json',side_effect=get):
                    with self.assertRaisesRegex(ValueError,'migration'):manage.check_collisions()
    def test_different_application_cannot_be_repointed(self):
        cfg={'argoNamespace':'argocd'}
        old={'metadata':{'name':'dpf-platform'},'spec':{'source':{'repoURL':'https://unrelated.invalid/repo'}}}
        with patch.object(manage,'command',return_value=__import__('json').dumps(old)):
            with self.assertRaisesRegex(ValueError,'Application'):manage.check_application(cfg)
    def test_stale_settings_require_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);(root/'render-report.json').write_text('{"site": {}}')
            with patch.object(manage,'ROOT',root):
                with self.assertRaisesRegex(ValueError,'changed'):manage.prepared({'different':True})

if __name__=='__main__':unittest.main()
