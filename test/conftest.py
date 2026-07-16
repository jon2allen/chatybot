import sys
import importlib
import importlib.machinery

class SrcRedirectFinder:
    def find_spec(self, fullname, path, target=None):
        if fullname == "src":
            # Return a dummy spec for 'src'
            return importlib.machinery.ModuleSpec(fullname, None, is_package=True)
        if fullname.startswith("src.chatybot"):
            real_name = fullname[4:] # strip 'src.'
            try:
                # Load/import the real module
                mod = importlib.import_module(real_name)
                # Register it under the fullname in sys.modules
                sys.modules[fullname] = mod
                # Return the spec of the real module
                return mod.__spec__
            except Exception as e:
                pass
        return None

# Register our finder at the beginning of sys.meta_path
sys.meta_path.insert(0, SrcRedirectFinder())
