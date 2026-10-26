import os
import sys
import importlib
import importlib.machinery

# Ensure chatybot imports always resolve to the workspace's src/ directory
repo_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if repo_src not in sys.path:
    sys.path.insert(0, repo_src)

class SrcRedirectLoader:
    def __init__(self, real_name):
        self.real_name = real_name

    def create_module(self, spec):
        return importlib.import_module(self.real_name)

    def exec_module(self, module):
        pass


class SrcRedirectFinder:
    def find_spec(self, fullname, path, target=None):
        if fullname == "src":
            return importlib.machinery.ModuleSpec(fullname, None, is_package=True)
        if fullname.startswith("src.chatybot"):
            real_name = fullname[4:]  # strip 'src.'
            loader = SrcRedirectLoader(real_name)
            return importlib.machinery.ModuleSpec(fullname, loader)
        return None


# Register our finder at the beginning of sys.meta_path
sys.meta_path.insert(0, SrcRedirectFinder())
