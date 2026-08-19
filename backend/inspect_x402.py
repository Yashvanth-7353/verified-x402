import inspect

def dump_module(module_name):
    print(f"--- Module: {module_name} ---")
    try:
        mod = __import__(module_name, fromlist=['*'])
        for name in dir(mod):
            if not name.startswith('_'):
                obj = getattr(mod, name)
                if inspect.isclass(obj) or inspect.isfunction(obj):
                    try:
                        sig = inspect.signature(obj)
                        print(f"{name}{sig}")
                    except ValueError:
                        print(f"{name}(...)")
                    # print(f"  Doc: {inspect.getdoc(obj)[:100] if inspect.getdoc(obj) else 'None'}")
    except Exception as e:
        print(f"Error: {e}")

dump_module('x402.server')
dump_module('x402.facilitator')
dump_module('x402.http.middleware.fastapi')
dump_module('x402.mechanisms.avm.exact')
dump_module('x402.schemas')
